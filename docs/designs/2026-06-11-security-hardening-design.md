# 安全加固设计文档

## 目标

修复上线阻断安全问题和实现 B 端数据安全机制，确保句龙照胆作为 B 端产品可以安全上线。

## 用户场景

- 管理员部署系统时，必须配置安全密钥，否则系统拒绝启动
- 用户上传企业私有文档进行体检，系统对敏感信息进行脱敏后再发送给 LLM
- 用户查看体检报告后，可手动选择删除文档原文（阅后即焚）
- 所有 API 调用有速率限制，防止滥用

## 修复清单

### HIGH — 上线阻断（3 项）

#### 1. 生产环境强制密钥配置检查

**问题**: JWT 密钥、API Key 加密密钥有硬编码默认值，部署时可能忘记更换。

**方案**: 在 FastAPI lifespan 启动时检查关键配置项是否已被修改。如果密钥仍为默认值且非开发环境，拒绝启动。

**实现**:
- 在 `core/config.py` 添加 `ENVIRONMENT` 配置项（`development` / `production`，默认 `development`）
- 在 `main.py` lifespan 中调用 `assert_production_security()` 检查函数
- 检查项: `jwt_secret_key`、`api_key_encryption_secret`、`model_api_key` 是否为默认值
- 开发环境跳过检查

**文件**: `backend/core/config.py`, `backend/main.py`

#### 2. Cookie 添加 Secure 属性

**问题**: Refresh Token Cookie 没有 `secure=True`。

**方案**: 添加 `secure=True`，并根据 `ENVIRONMENT` 动态决定。

**实现**:
- `_set_refresh_cookie` 中添加 `secure=settings.environment == "production"`
- 开发环境保持 `secure=False` 以便 HTTP 调试

**文件**: `backend/routers/auth.py`, `backend/core/config.py`

#### 3. 注册接口防滥用

**问题**: `/auth/register` 完全开放，无速率限制。

**方案**: 添加 IP 级别注册速率限制 + 统一错误消息防枚举。

**实现**:
- 创建 `core/rate_limit.py`：基于内存的滑动窗口速率限制器
- 注册接口限制：同一 IP 每小时最多 5 次注册
- 统一错误消息：注册失败统一返回"注册失败"，不区分"用户名已存在"和"其他错误"
- 登录接口已有 `LoginThrottle`，保持不变

**文件**: `backend/core/rate_limit.py`（新建）, `backend/routers/auth.py`

### MEDIUM — B 端安全（4 项）

#### 4. AI 数据脱敏层

**问题**: 用户企业文档全文直接发送给外部 LLM API，无脱敏。

**方案**: 在发送给 LLM 前对文档文本进行敏感信息脱敏，使用正则+规则引擎替换为占位符。

**脱敏规则**:
| 类型 | 正则模式 | 替换为 |
|------|----------|--------|
| 金额 | `\d+[\.,]\d{1,2}\s*(万|元|亿元|万元)` | `[金额]` |
| 手机号 | `1[3-9]\d{9}` | `[手机号***]` |
| 身份证 | `\d{17}[\dXx]` | `[身份证***]` |
| 银行卡 | `\d{16,19}` | `[银行卡***]` |
| 邮箱 | `[\w.-]+@[\w.-]+\.\w+` | `[邮箱***]` |
| 日期 | `\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?` | 保留（不脱敏） |

**实现**:
- 创建 `core/data_masking.py`：脱敏引擎，接收原文返回脱敏后文本 + 映射表
- 映射表用于 LLM 返回结果中还原 `[金额]` → 原始值（可选）
- 在 `inspection_prompts.py` 的 `format_*` 函数中调用脱敏
- 在 Agent system prompt 中声明"你正在处理的是经过脱敏的文档，[金额]等占位符代表实际数据"

**文件**: `backend/core/data_masking.py`（新建）, `backend/app/prompts/inspection_prompts.py`

**约束**:
- 脱敏在 prompt 格式化层进行，不修改数据库中的原文
- LLM 返回结果中的占位符不还原（报告中的 `[金额]` 保持不变，这是安全的）
- 脱敏映射表不持久化，仅在当次请求内存中存在

#### 5. 文档原文加密存储

**问题**: `parsed_content` 明文存储完整文档原文。

**方案**: 对 `parsed_content` 字段进行 AES-GCM 加密存储，读取时解密。

**实现**:
- 在 `core/config.py` 添加 `DATA_ENCRYPTION_KEY` 配置项
- 创建 `core/data_encryption.py`：加密/解密工具（使用 cryptography 库已有的 AES）
- 修改写入 `parsed_content` 的位置进行加密
- 修改读取 `parsed_content` 的位置进行解密
- 使用 `text_preview`（前 200 字符明文）替代大部分场景的原文展示需求

**文件**: `backend/core/data_encryption.py`（新建）, `backend/routers/inspection.py`

#### 6. 阅后即焚（用户手动）

**问题**: `burn_after_read` 字段已存在于 UserProfile 但从未使用。

**方案**: 前端设置页已有开关，后端需要实现清理逻辑和手动触发接口。

**实现**:
- 新增 `POST /inspection/records/{id}/burn` 接口：删除 `parsed_content` 内容，保留报告摘要
- 前端历史记录详情页增加"焚烧原文"按钮（仅当 `parsed_content` 非空时显示）
- 定期清理任务（可选）：检查 `burn_after_read=True` 的用户，清理超过 7 天的 `parsed_content`

**文件**: `backend/routers/inspection.py`, `frontend/src/pages/HistoryPage.vue`（或相关详情组件）

#### 7. CORS 收紧

**问题**: `allow_methods=["*"]` 和 `allow_headers=["*"]` 过于宽松。

**方案**: 限制为实际使用的 HTTP 方法和头部。

**实现**:
```python
allow_methods=["GET", "POST", "PATCH", "DELETE"],
allow_headers=["Authorization", "Content-Type"],
```

**文件**: `backend/main.py`

## 技术方案

### 依赖变更
无需新增 Python 包（`cryptography` 已在 v0.3.0 添加）。

### 配置项新增
| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `environment` | `ENVIRONMENT` | `development` | 环境标识 |
| `data_encryption_key` | `DATA_ENCRYPTION_KEY` | `""` | 文档原文加密密钥 |

### 数据流变更

**修复前**:
```
用户上传 → Markdown 全文 → Prompt → LLM API
                        ↓
                  DB (parsed_content 明文)
```

**修复后**:
```
用户上传 → Markdown 全文 → 加密存储 → DB (parsed_content 密文)
                              ↓
                         解密 → 脱敏 → Prompt → LLM API
                                             ↓
                                         报告结果

用户手动焚烧 → 清除 parsed_content（保留报告摘要）
```

## 错误处理

- `DATA_ENCRYPTION_KEY` 缺失时：生产环境拒绝启动，开发环境使用固定密钥
- 脱敏失败时：跳过脱敏，使用原文（确保不阻塞业务）
- 焚烧已焚烧记录：返回 404 或幂等成功

## 测试策略

| 层级 | 内容 |
|------|------|
| 单元测试 | 脱敏引擎（各类型正则匹配）、加密/解密、速率限制 |
| 集成测试 | 注册速率限制、密钥检查启动拦截、Cookie Secure 属性 |
| 安全测试 | 脱敏后文本不含原始敏感信息、加密后密文不可逆（无密钥时） |
| 回归测试 | 体检全流程仍正常工作 |
