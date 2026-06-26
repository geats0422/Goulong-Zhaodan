# 安全审查报告 #1 — 密钥管理与认证授权

**审查时间**: 2026-06-13
**审查者**: opencode (security-review skill)
**审查范围**: backend/app/core/{config,auth,api_key_crypto,data_encryption}.py, backend/app/core/agent_auth.py, backend/app/services/api_key_service.py
**风险等级**: 🟡 **中等 (有 1 个高危 + 2 个中危)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| 密钥管理 | ⚠️ 中危 | 开发默认值已声明但未在生产强制 |
| 密码哈希 | ✅ 良好 | bcrypt via goulong_auth |
| JWT 签名 | ✅ 良好 | HS256 统一管理 |
| 认证流程 | ✅ 良好 | Bearer + 用户表 |
| 授权（越权） | 🟡 中危 | 部分端点仅依赖 user_id 字符串 |
| API Key 哈希比较 | 🔴 **高危** | 使用 `==` 而非 `hmac.compare_digest`（时序侧信道） |
| Token 撤销 | ✅ 良好 | jti 持久化 + revoked 标记 |
| Cookie 属性 | ⚠️ 待查 | 见第 3 次审查 |

---

## 发现的问题

### 🔴 HIGH — API Key 哈希比较存在时序侧信道

**位置**: `backend/app/core/api_key_crypto.py:23-24`

```python
def verify_api_key_hash(plain_key: str, hashed: str) -> bool:
    return hashlib.sha256(plain_key.encode()).hexdigest() == hashed
```

**问题**: 使用 `==` 比较哈希值时，Python 字符串比较会在发现第一个不同字符时立即返回。这造成可测量的时间差异，攻击者通过精心测量响应时间可逐字节推断哈希值。

**调用路径**: `services/api_key_service.py:125` 在 `lookup_api_key_by_token` 中使用此函数。

**修复建议**:
```python
import hmac

def verify_api_key_hash(plain_key: str, hashed: str) -> bool:
    computed = hashlib.sha256(plain_key.encode()).hexdigest()
    return hmac.compare_digest(computed, hashed)
```

---

### 🟡 MEDIUM — 生产环境安全断言只检查 2 项

**位置**: `backend/app/core/config.py:65-76`

```python
def assert_production_security() -> None:
    if settings.environment != "production":
        return
    defaults = {
        "jwt_secret_key": "goulong-jwt-dev-secret-change-in-production",
        "api_key_encryption_secret": "dev-encryption-secret-change-in-production",
    }
    ...
```

**问题**: 仅检查 jwt_secret_key 和 api_key_encryption_secret 是否还是默认值。未检查：
- `data_encryption_key`（加密体检文档）
- `database_url`（不应包含默认 `your-password`）
- `cors_origins`（不应含 `*`）
- `model_api_key`（虽已检查但允许空串）

**修复建议**: 扩展断言函数，添加：
```python
if "your-password" in settings.database_url:
    raise RuntimeError("DATABASE_URL 使用了默认占位符密码")
if "*" in settings.cors_origins.split(","):
    raise RuntimeError("CORS 配置包含通配符")
if not settings.data_encryption_key:
    raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY")
```

---

### 🟡 MEDIUM — Authorization 解析使用 `request.headers` 而非 FastAPI Security

**位置**: `backend/app/core/auth.py:74-85`, `backend/app/core/agent_auth.py:15-30`

```python
async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]
    ...
```

**问题**: 手写 Bearer token 解析绕过了 FastAPI 的 `OAuth2PasswordBearer` 标准流程，导致：
1. 缺少 `WWW-Authenticate: Bearer realm="..."` 自动头
2. 无法在 OpenAPI 文档中正确显示认证要求
3. 不利于后续扩展（多 scope、API Key 等）

**修复建议**: 使用 FastAPI 内置 `OAuth2PasswordBearer`，参考 goulong-auth 的 `auth/dependencies.py` 实现。

---

### ✅ 通过的检查

- ✅ 密码哈希使用 bcrypt（goulong_auth.auth.password）
- ✅ JWT 包含 user_id/product/exp/iat 字段
- ✅ Refresh token 通过 jti 持久化，可主动撤销
- ✅ `assert_production_security` 在 lifespan 启动时调用
- ✅ `.env` 在 .gitignore 中（验证：`backend/.env` 已忽略）
- ✅ 开发密钥默认值显式命名为 `*-dev-*-change-in-production`
- ✅ `requirements.txt` 中包含 `cryptography` 库
- ✅ API Key 加密使用 Fernet（AES-128-CBC + HMAC）
- ✅ `data_encryption_key` 在生产环境缺失时抛错

---

## 下次审查重点

- 注入防护（SQL 字符串拼接、XSS、命令注入）
- 文件上传验证（MIME、扩展名、大小）
- 错误处理（堆栈泄露、内部细节暴露）
- CORS 配置审查
