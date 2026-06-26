# 安全审查报告 #3 — 数据传输、CORS、错误处理、信息泄露

**审查时间**: 2026-06-13
**审查者**: opencode (security-review skill)
**审查范围**: backend/main.py, backend/app/api/v1/auth.py, backend/app/core/config.py, frontend/src/composables/useAuth.js
**风险等级**: 🟠 **中等偏高 (有 1 个高危 + 3 个中危)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| CORS 配置 | 🟡 中危 | 默认白名单 OK，但需在生产环境明确限制 |
| Cookie 属性 | 🟡 中危 | refresh token Cookie 配置基本正确 |
| HTTPS 强制 | 🔴 **高危** | 未强制 HTTPS / 无 HSTS |
| 安全响应头 | 🔴 **缺失** | 无 CSP/X-Frame-Options/X-Content-Type-Options |
| CORS 凭证 | ✅ 良好 | `allow_credentials=True` + 白名单 |
| 错误消息泄露 | 🟡 中危 | 部分堆栈信息回传客户端 |
| 日志记录 | ✅ 良好 | 无敏感信息打印 |
| 错误日志记录 | 🟡 中危 | 部分异常未记录到日志 |
| 客户端 token 存储 | 🟡 中危 | sessionStorage (XSS 仍可窃取) |
| API Key 完整密钥返回 | ✅ 良好 | 严格控制（见 audit-01） |
| 异常处理广度 | 🟡 中危 | `except Exception` 范围过广 |

---

## 发现的问题

### 🔴 HIGH — 无 HTTPS 强制 / 无 HSTS / 无安全响应头

**位置**: `backend/main.py` (FastAPI 应用入口)

```python
app = FastAPI(
    title="句龙照胆 — 体检台 API",
    version="0.1.0",
    ...
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**问题**:
1. **无 HTTPS 强制** — 没有 `HSTS` 中间件，中间人攻击者可降级 HTTP
2. **无安全响应头** — 缺少：
   - `X-Content-Type-Options: nosniff`（防 MIME 嗅探）
   - `X-Frame-Options: DENY`（防点击劫持）
   - `Content-Security-Policy: default-src 'self'`（防 XSS）
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: geolocation=(), microphone=()`（最小权限）
3. **CORS 方法列表**包含 PATCH/DELETE 是合理的（CRUD 应用），但缺少限制 `max_age`（preflight 缓存）

**修复建议** — 添加 `SecurityHeadersMiddleware`:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

并对 HTTPS-only 服务在启动时检测并要求。

---

### 🟡 MEDIUM — Cookie `secure` 仅生产环境启用

**位置**: `backend/app/api/v1/auth.py:67-75`

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

**问题**: 在 staging/预发布环境（如 `environment="staging"`）`secure=False`，可能导致 refresh token 在测试时通过 HTTP 泄露。

**修复建议**:
```python
secure=settings.environment != "development",
```

或更严格：
```python
secure=True,  # 总是 True，通过 HTTPS-only 部署
```

---

### 🟡 MEDIUM — 错误消息泄露内部细节

**位置**: `backend/app/api/v1/inspection.py:206-207, 591-595`

```python
except Exception as exc:
    raise HTTPException(status_code=400, detail=f"无法读取文件: {exc}") from exc
...
except Exception as exc:
    raise HTTPException(
        status_code=502,
        detail=f"智能审查引擎不可用: {exc}",
    ) from exc
```

**问题**:
- `detail=f"...: {exc}"` 将原始异常信息回传客户端
- 攻击者可通过构造输入触发不同异常来探测系统（如 "openai API key invalid" 提示泄露 API key 错误）
- 应记录到日志（`logger.exception`），对客户端只返回通用消息

**修复建议**:
```python
import logging
logger = logging.getLogger(__name__)

except Exception as exc:
    logger.exception("文件读取失败: filename=%s", filename)
    raise HTTPException(status_code=400, detail="文件无法解析") from exc
```

---

### 🟡 MEDIUM — Access token 存于 `sessionStorage`（XSS 可窃取）

**位置**: `frontend/src/composables/useAuth.js:6, 73, 98, 109`

```javascript
sessionStorage.setItem(ACCESS_TOKEN_KEY, _accessToken)
sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser.value))
```

**问题**:
- `sessionStorage` 任何同源脚本（包括恶意注入的 `<script>`）都可读取
- 推荐做法：
  1. **首选**：access token 存于 HttpOnly Cookie（与 refresh token 同样）
  2. **次选**：access token 存于内存（Vue 变量），刷新后重新登录或通过 refresh token 续期

**修复建议** (内存优先 + Cookie 续期):
```javascript
// 不持久化 access token
let _accessToken = null

// 路由拦截器自动用 refresh token 续期
```

但这会增加交互复杂度。可接受折衷：保持 sessionStorage 但 **加 CSP 严格策略 + 子完整性校验**。

---

### 🟡 MEDIUM — `except Exception` 捕获过广

**位置**: `backend/app/api/v1/inspection.py:206, 591`, `services/data_encryption.py:32, 39`

**问题**: `except Exception` 会吞掉所有异常（包括 KeyboardInterrupt、SystemExit、AsyncpgInternalError 等系统级异常），掩盖真实问题。

**修复建议**:
```python
except (ValueError, RuntimeError, OSError) as exc:  # 明确列出
    ...
```

或保留 `Exception` 但加 `logger.exception(...)` 记录完整堆栈。

---

### ✅ 通过的检查

- ✅ CORS 默认白名单为 `localhost:5174,localhost:5173`（非 `*`）
- ✅ `allow_credentials=True` 与白名单配合而非通配符
- ✅ Cookie `httponly=True`（防 JS 读取）
- ✅ Cookie `samesite="lax"`（防 CSRF）
- ✅ 无 `print(secret/password/token)` 调用
- ✅ `assert_production_security` 启动时检查默认值
- ✅ 无 `dangerouslySetInnerHTML` 或 `v-html`
- ✅ refresh token 通过 jti 持久化，可主动撤销
- ✅ 错误响应使用 HTTP 标准状态码（400/401/403/413/429/500/502）
- ✅ 错误时 `from exc` 保留异常链
- ✅ 客户端不直接渲染错误对象到 UI（仅显示 message）
