# 安全审查报告 #6 — 数据安全与隐私合规

**审查时间**: 2026-06-13
**审查范围**: `backend/app/models/knowledge.py`, `backend/app/services/file_storage.py`, `backend/app/core/database.py`, `backend/app/core/config.py`, `frontend/src/composables/useAuth.js`
**风险等级**: 🟡 **中等 (0 HIGH + 4 MEDIUM)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| 数据库连接安全 | 🟡 中危 | 连接字符串含明文密码，无 SSL 模式强制 |
| 静态加密 | ✅ 良好 | API Key 使用 Fernet 加密存储 |
| PII 存储 | 🟡 中危 | email/phone 明文存储，未脱敏 |
| 文件存储安全 | 🟡 中危 | 上传文件存于本地 `data/knowledge/`，无加密 |
| 数据保留策略 | 🟡 中危 | 体检记录永久保留，无自动清理 |
| 审计日志 | ✅ 基本满足 | `last_used_at`/`last_viewed_at`/`created_at` 跟踪 |
| 日志安全 | ✅ 良好 | 仅 `knowledge_ingestion.py` 一处 logger，无敏感数据 |
| 前端数据保护 | ✅ 良好 | sessionStorage 自动清除，无 localStorage 持久化 |
| 阅后即焚 | ✅ 良好 | burn API 正确清空内容 |

---

## 发现的问题

### 🟡 MEDIUM — 数据库连接无 SSL 强制

**位置**: `backend/app/core/config.py:22`

```python
database_url: str = "postgresql+asyncpg://postgres:your-password@localhost:5432/goulong"
```

**问题**:
- 默认连接字符串未指定 `sslmode=require`
- 生产环境中数据库连接可能通过明文 TCP 传输查询和结果
- 如果数据库与应用不在同一主机，中间人可嗅探所有查询（含用户 PII）

**修复建议**:
```python
# 生产环境 .env
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/goulong?sslmode=require
```

或在 `database.py` 中强制：
```python
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"ssl": "require"} if not settings.database_url.startswith("sqlite") else {},
)
```

---

### 🟡 MEDIUM — PII (email/phone) 明文存储未脱敏

**位置**: `backend/app/models/knowledge.py` (via goulong_auth.models.User)

**问题**:
- 用户 email 和 phone 在数据库中明文存储
- API 响应中 `GET /auth/me`、`GET /settings/overview` 直接返回完整 email 和 phone
- 在数据泄露场景下，PII 直接暴露

**修复建议**:
1. 数据库层：对 phone 字段使用 `pgcrypto` 加密：`encrypt(phone::bytea, current_setting('encryption.key')::bytea, 'aes')`
2. API 层：返回时脱敏 `email: "u***@example.com"`, `phone: "138****1234"`
3. 至少在列表/日志接口中脱敏显示

---

### 🟡 MEDIUM — 上传文件无静态加密

**位置**: `backend/app/services/file_storage.py:29-31`

```python
def save_upload_file(file_path: Path, content: bytes) -> Path:
    ensure_storage_dir(file_path.parent)
    file_path.write_bytes(content)
    return file_path
```

**问题**:
- 上传的工程文档（合同/招投标文件）直接以明文写入 `data/knowledge/` 目录
- 合同文件通常含商业秘密和个人信息
- 磁盘泄露（如备份外泄、磁盘报废未擦除）直接暴露敏感内容

**修复建议**:
1. 使用 `Fernet` (已有依赖) 加密文件内容后写入：
```python
def save_upload_file(file_path: Path, content: bytes) -> Path:
    ensure_storage_dir(file_path.parent)
    encrypted = _fernet_encrypt(content)
    file_path.write_bytes(encrypted)
    return file_path
```
2. 或依赖文件系统级加密（如 LUKS / 云盘加密）

---

### 🟡 MEDIUM — 体检记录无自动清理/保留策略

**位置**: `backend/app/models/knowledge.py:165-181` (InspectionRecord)

**问题**:
- `InspectionRecord` 表无限增长，所有体检记录（含 `parsed_content` 全文）永久保留
- `parsed_content` 可能含完整合同文本（商业秘密）
- 即使有 `burn_record_content` API（阅后即焚），需用户主动触发
- GDPR/个人信息保护法要求 "数据最小化" 和 "存储限制"

**修复建议**:
1. 添加定时任务清理超过 N 天的记录：
```python
# 每天凌晨清理 >90 天的记录
DELETE FROM inspection_records WHERE created_at < NOW() - INTERVAL '90 days'
```
2. 对 `burn_after_read=True` 的用户，审查完成后自动清空 `parsed_content`
3. 考虑只保留摘要 (`summary`) + 风险等级 (`overall_risk`)，不保留全文

---

## 通过的检查 ✅

- ✅ API Key 加密存储（Fernet AES-128-CBC + HMAC）
- ✅ API Key 哈希使用 SHA-256（验证时用 hmac.compare_digest，P0-1 已修复）
- ✅ 密码使用 bcrypt（通过 goulong_auth）
- ✅ `.env` 不提交到 git
- ✅ 生产环境启动检查 `assert_production_security()`
- ✅ 前端使用 `sessionStorage`（标签页关闭自动清除）
- ✅ 前端不使用 `localStorage` 持久化 token
- ✅ `credentials: 'include'` 仅对同源请求发送 Cookie
- ✅ refresh token 存于 HttpOnly Cookie（JS 不可读）
- ✅ refresh token 有 `jti` 可撤销
- ✅ 密码修改后自动撤销所有 refresh token
- ✅ API `list_api_keys` 返回时清除 `encrypted_key` 和 `key_hash`
- ✅ `model_api_key_preview` 仅返回末 4 位
- ✅ 日志不记录敏感数据（仅 `knowledge_ingestion.py` 一处 warning）
- ✅ `safe_path_segment` 防路径遍历
- ✅ 数据库连接池使用 SQLAlchemy async engine
- ✅ Agent API 的 `result_payload` 不包含 `parsed_content`
