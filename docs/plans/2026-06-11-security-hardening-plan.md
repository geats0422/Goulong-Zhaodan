# 安全加固 实施计划

## 总览

分 8 个任务实现 7 项安全修复（3 项 HIGH + 4 项 MEDIUM），按优先级从高到低排列。前 4 个任务聚焦上线阻断问题，后 4 个任务处理 B 端数据安全。整体策略是：先阻断安全漏洞（密钥检查、Cookie、注册防刷、CORS），再加固数据链路（脱敏、加密、阅后即焚）。

## 前置准备

- [x] 设计文档已批准：`docs/designs/2026-06-11-security-hardening-design.md`
- [ ] 确认开发环境就绪：`uv sync`、`npm install`
- [ ] 运行现有测试确认基线通过：`cd backend && uv run pytest`

---

## 任务列表

### 任务 1: 生产环境强制密钥配置检查 (~3 min)

- **描述**: 在 `Settings` 中新增 `environment` 配置项，创建启动检查函数，生产环境拒绝默认密钥启动
- **文件**:
  - 修改 `backend/core/config.py` — 新增 `environment` 和 `data_encryption_key` 配置项，新增 `assert_production_security()` 函数
  - 修改 `backend/main.py` — lifespan 中调用安全检查
  - 修改 `backend/env.example` — 新增 `ENVIRONMENT` 和 `DATA_ENCRYPTION_KEY` 环境变量示例
- **实现细节**:
  1. `config.py` 的 `Settings` 类新增：
     ```python
     environment: str = "development"  # development / production
     data_encryption_key: str = ""     # 文档原文 AES 加密密钥
     ```
  2. `config.py` 新增顶层函数 `assert_production_security()`:
     ```python
     def assert_production_security() -> None:
         if settings.environment != "production":
             return
         defaults = {
             "jwt_secret_key": "goulong-jwt-dev-secret-change-in-production",
             "api_key_encryption_secret": "dev-encryption-secret-change-in-production",
         }
         for attr, default in defaults.items():
             if getattr(settings, attr) == default:
                 raise RuntimeError(f"生产环境不允许使用默认 {attr}")
         if not settings.model_api_key:
             raise RuntimeError("生产环境必须配置 MODEL_API_KEY")
     ```
  3. `main.py` lifespan 中 `await init_db()` 后调用 `assert_production_security()`
- **测试**:
  - 新建/追加 `backend/tests/test_security_config.py`
  - 测试用例 1: `environment="development"` 时检查跳过
  - 测试用例 2: `environment="production"` + 默认密钥时抛出 `RuntimeError`
  - 测试用例 3: `environment="production"` + 已修改密钥时不抛异常
- **验证**: `uv run pytest tests/test_security_config.py -v` 通过
- **依赖**: 无

---

### 任务 2: Cookie 添加 Secure 属性 (~2 min)

- **描述**: 为 Refresh Token Cookie 添加 `secure=True`，生产环境强制 HTTPS-only
- **文件**:
  - 修改 `backend/routers/auth.py` — `_set_refresh_cookie` 函数添加 `secure` 参数
- **实现细节**:
  1. 修改 `_set_refresh_cookie` 函数：
     ```python
     def _set_refresh_cookie(response: Response, token: str) -> None:
         response.set_cookie(
             _REFRESH_COOKIE_NAME,
             token,
             httponly=True,
             secure=settings.environment == "production",
             max_age=_REFRESH_COOKIE_MAX_AGE,
             samesite="lax",
         )
     ```
  2. 确保已 import `settings`（当前已有 `from core.config import settings`）
- **测试**:
  - 追加 `backend/tests/test_auth_api.py`
  - 测试用例：注册成功后检查 `set-cookie` header 中是否有 `Secure` 属性（开发环境无，需要 mock `settings.environment`）
- **验证**: `uv run pytest tests/test_auth_api.py -v` 全部通过（包括已有用例）
- **依赖**: 任务 1（需要 `settings.environment`）

---

### 任务 3: 注册接口防滥用 (~4 min)

- **描述**: 创建 IP 级别注册速率限制器 + 统一注册错误消息防止用户枚举
- **文件**:
  - 新建 `backend/core/rate_limit.py` — 通用滑动窗口速率限制器
  - 修改 `backend/routers/auth.py` — 注册接口添加限流 + 统一错误消息
- **实现细节**:
  1. 新建 `core/rate_limit.py`：
     ```python
     class IPRateLimiter:
         """基于内存的滑动窗口 IP 速率限制器"""
         def __init__(self, max_requests: int, window_seconds: int): ...
         def is_limited(self, ip: str) -> bool: ...
         def record(self, ip: str) -> None: ...

     register_limiter = IPRateLimiter(max_requests=5, window_seconds=3600)
     ```
  2. 修改 `auth.py` 的 `register` 端点：
     - 从 `Request` 获取客户端 IP
     - 检查 `register_limiter.is_limited(ip)` → 返回 429
     - 注册前调用 `register_limiter.record(ip)`
     - **统一错误消息**：用户名已存在、其他错误统一返回 `{"detail": "注册失败"}`，不暴露原因
     - 成功响应不变（201 + token）
- **测试**:
  - 新建 `backend/tests/test_register_rate_limit.py`
  - 测试用例 1: 同一 IP 连续注册 5 次成功
  - 测试用例 2: 第 6 次注册返回 429
  - 测试用例 3: 不同 IP 互不影响
  - 测试用例 4: 注册失败（用户名重复）返回统一消息"注册失败"
- **验证**: `uv run pytest tests/test_register_rate_limit.py -v` 通过
- **依赖**: 无

---

### 任务 4: CORS 收紧 (~2 min)

- **描述**: 将 CORS 的 `allow_methods` 和 `allow_headers` 从通配符改为实际使用的值
- **文件**:
  - 修改 `backend/main.py` — CORS 中间件配置
- **实现细节**:
  1. 修改 `app.add_middleware(CORSMiddleware, ...)`:
     ```python
     allow_methods=["GET", "POST", "PATCH", "DELETE"],
     allow_headers=["Authorization", "Content-Type"],
     ```
  2. 保持 `allow_origins` 和 `allow_credentials` 不变
- **测试**:
  - 追加 `backend/tests/test_infrastructure.py` 或新建 CORS 测试
  - 测试用例 1: OPTIONS 预检请求返回正确的 `Access-Control-Allow-Methods`
  - 测试用例 2: 非允许的 Method (PUT) 被拒绝
- **验证**: `uv run pytest tests/test_infrastructure.py -v` 通过
- **依赖**: 无

---

### 任务 5: AI 数据脱敏层 (~5 min)

- **描述**: 创建脱敏引擎，在 prompt 格式化层对文档文本进行敏感信息替换后再发送给 LLM
- **文件**:
  - 新建 `backend/core/data_masking.py` — 脱敏引擎
  - 修改 `backend/app/prompts/inspection_prompts.py` — format 函数中调用脱敏
- **实现细节**:
  1. 新建 `core/data_masking.py`：
     ```python
     import re
     from dataclasses import dataclass, field

     @dataclass
     class MaskingResult:
         text: str
         mask_map: dict[str, str] = field(default_factory=dict)
         masked_count: int = 0

     MASKING_RULES: list[tuple[str, str]] = [
         (r"\d+[\.,]\d{1,2}\s*(万|元|亿元|万元)", "[金额]"),
         (r"1[3-9]\d{9}", "[手机号***]"),
         (r"\d{17}[\dXx]", "[身份证***]"),
         (r"\d{16,19}", "[银行卡***]"),
         (r"[\w.-]+@[\w.-]+\.\w+", "[邮箱***]"),
     ]

     def mask_sensitive_data(text: str) -> MaskingResult: ...
     ```
  2. 修改 `inspection_prompts.py` 的 `format_regulation_prompt` 和 `format_inspection_prompt`：
     - 对 `document_text` 参数调用 `mask_sensitive_data(text).text`
     - 在 system prompt 中追加声明："你正在处理的是经过脱敏的文档，[金额]等占位符代表实际数据"
  3. 脱敏映射表不持久化，仅在当次请求内存中存在
  4. 脱敏失败时返回原文（确保不阻塞业务）
- **测试**:
  - 新建 `backend/tests/test_data_masking.py`
  - 测试用例 1: 金额 "100.00万元" → "[金额]"
  - 测试用例 2: 手机号 "13812345678" → "[手机号***]"
  - 测试用例 3: 身份证 "110101199001011234" → "[身份证***]"
  - 测试用例 4: 邮箱 "test@example.com" → "[邮箱***]"
  - 测试用例 5: 混合文本正确脱敏
  - 测试用例 6: 无敏感信息的文本不变化
  - 测试用例 7: 日期 `\d{4}年\d{1,2}月\d{1,2}日` 不被脱敏
- **验证**: `uv run pytest tests/test_data_masking.py -v` 通过
- **依赖**: 无

---

### 任务 6: 文档原文加密存储 (~5 min)

- **描述**: 对 `parsed_content` 字段使用 AES-GCM 加密存储，读取时解密
- **文件**:
  - 新建 `backend/core/data_encryption.py` — 文档加密/解密工具
  - 修改 `backend/routers/inspection.py` — 写入加密、读取解密
- **实现细节**:
  1. 新建 `core/data_encryption.py`：
     ```python
     from cryptography.fernet import Fernet
     import base64, hashlib
     from core.config import settings

     def _get_fernet() -> Fernet:
         key = settings.data_encryption_key
         if not key:
             if settings.environment == "production":
                 raise ValueError("DATA_ENCRYPTION_KEY 未配置")
             # 开发环境使用固定密钥
             key = "dev-data-encryption-key"
         derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
         return Fernet(derived)

     def encrypt_text(plain: str) -> str:
         return _get_fernet().encrypt(plain.encode()).decode()

     def decrypt_text(encrypted: str) -> str:
         return _get_fernet().decrypt(encrypted.encode()).decode()
     ```
  2. 修改 `routers/inspection.py`：
     - `_create_pending_inspection_record`: `parsed_content=encrypt_text(text)` (第 415 行)
     - `_execute_inspection` 中写入时: `record.parsed_content = encrypt_text(text)` (第 613 行)
     - `_execute_inspection` 中读取时（重审记录）: `text = decrypt_text(record.parsed_content)` (第 855 行)
     - `get_record` 返回时: `decrypt_text(record.parsed_content)` (第 810 行)
     - 所有解密操作使用 try/except 包裹，解密失败则返回原文（向后兼容已有明文数据）
- **测试**:
  - 新建 `backend/tests/test_data_encryption.py`
  - 测试用例 1: `encrypt_text` + `decrypt_text` 往返正确
  - 测试用例 2: 密文与明文不同
  - 测试用例 3: 不同明文产生不同密文
  - 测试用例 4: 开发环境空密钥时使用固定密钥不报错
- **验证**: `uv run pytest tests/test_data_encryption.py -v` 通过
- **依赖**: 任务 1（需要 `settings.data_encryption_key` 和 `settings.environment`）

---

### 任务 7: 阅后即焚接口 + 前端按钮 (~4 min)

- **描述**: 后端新增焚烧原文接口，前端详情页增加"焚烧原文"按钮
- **文件**:
  - 修改 `backend/routers/inspection.py` — 新增 `POST /inspection/records/{id}/burn` 端点
  - 修改 `frontend/src/services/inspectionApi.js` — 新增 `burnInspectionRecord` API
  - 修改 `frontend/src/pages/HistoryPage.vue` — 详情弹窗中增加焚烧按钮
- **实现细节**:
  1. 后端新增端点：
     ```python
     @router.post("/records/{record_id}/burn")
     async def burn_record_content(
         record_id: int,
         db=Depends(get_db_session),
         user=Depends(get_current_user),
     ):
         user_id = _current_user_id(user)
         record = await db.scalar(...)
         if record is None:
             raise HTTPException(status_code=404)
         record.parsed_content = ""
         await db.commit()
         return {"id": record.id, "burned": True}
     ```
  2. 幂等设计：已焚烧的记录再次调用返回 200 + `{"burned": True}`
  3. 前端 `inspectionApi.js` 新增：
     ```javascript
     export async function burnInspectionRecord(recordId) {
       return parseResponse(await fetchWithAuth(`/inspection/records/${recordId}/burn`, { method: 'POST' }))
     }
     ```
  4. 前端 `HistoryPage.vue` 详情弹窗中：
     - 仅当 `selectedRecord.parsed_content` 非空时显示"焚烧原文"按钮
     - 点击前弹窗确认："焚烧后原文不可恢复，确认焚烧？"
     - 焚烧后 `selectedRecord.parsed_content = ""`，按钮消失
- **测试**:
  - 后端：追加 `backend/tests/test_inspection_api.py`
    - 测试用例 1: 焚烧成功后 `parsed_content` 为空
    - 测试用例 2: 重复焚烧返回 200（幂等）
    - 测试用例 3: 不存在的记录返回 404
  - 前端：构建通过即可
- **验证**: `uv run pytest tests/test_inspection_api.py -v` + `cd frontend && npm run build` 通过
- **依赖**: 任务 6（焚烧前需确认加密存储已就绪）

---

### 任务 8: 回归测试 + 更新 env.example (~3 min)

- **描述**: 运行全量测试确认无回归，更新 env.example 文档
- **文件**:
  - 修改 `backend/env.example` — 确保新增环境变量已记录
- **实现细节**:
  1. 确认 `env.example` 包含：
     ```
     ENVIRONMENT=development
     DATA_ENCRYPTION_KEY=
     ```
  2. 运行完整后端测试套件：`uv run pytest`
  3. 确认前端构建通过：`cd frontend && npm run build`
  4. 手动验证体检全流程（上传 → 解析 → 审查 → 查看报告 → 焚烧）
- **测试**: 全量测试套件通过
- **验证**: `uv run pytest` 全绿 + `npm run build` 成功
- **依赖**: 任务 1–7 全部完成

---

## 并行机会

- **任务 3（注册防刷）** 与 **任务 4（CORS）** 与 **任务 5（脱敏）** 可以并行执行（互不依赖）
- **任务 2（Cookie Secure）** 依赖任务 1 的 `environment` 配置，需等待任务 1 完成
- **任务 6（加密存储）** 依赖任务 1，需等待任务 1 完成
- **任务 7（阅后即焚）** 依赖任务 6，需等待任务 6 完成

## 执行顺序建议

```
任务 1 (密钥检查)
├── 任务 2 (Cookie Secure)  ─┐
├── 任务 6 (加密存储) ────────┤
│                            ├── 任务 8 (回归测试)
├── 任务 3 (注册防刷) ───────┤
├── 任务 4 (CORS) ──────────┤
└── 任务 5 (脱敏) ───────────┘
    任务 6 → 任务 7 (阅后即焚)
```

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 加密存储导致已有明文记录读取失败 | 中 | 高 | 解密函数 try/except 包裹，失败返回原文（向后兼容） |
| 脱敏正则误匹配（如金额匹配到页码） | 中 | 低 | 日期模式明确排除；脱敏失败不阻塞业务 |
| 速率限制器内存泄漏（IP 不断累积） | 低 | 中 | `IPRateLimiter` 内置定期清理过期记录 |
| `ENVIRONMENT` 配置遗漏导致生产启动失败 | 低 | 高 | 设计如此——这正是安全检查的目的；开发环境默认跳过 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 单元测试 | 脱敏引擎（6 种类型正则）、加密/解密往返、速率限制器、密钥检查函数 | 核心安全逻辑 100% |
| API 测试 | 注册速率限制（429）、统一错误消息、焚烧端点（幂等）、Cookie Secure 属性 | 关键安全路径 |
| 回归测试 | 全量 pytest（包括 60+ 已有测试） | 无功能回归 |
| 手工验证 | 上传文档 → 查看报告 → 焚烧原文 全流程 | 端到端安全 |
