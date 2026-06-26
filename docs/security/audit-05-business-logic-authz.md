# 安全审查报告 #5 — 业务逻辑与授权安全

**审查时间**: 2026-06-13
**审查范围**: `backend/app/api/v1/*.py`, `backend/app/core/auth.py`, `backend/app/core/agent_auth.py`, `backend/app/core/rate_limit.py`, `backend/app/services/api_key_service.py`
**风险等级**: 🟠 **中高 (2 HIGH + 3 MEDIUM)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| 用户数据隔离 | ✅ 良好 | 所有查询带 `user_id == current_user` 条件 |
| API Key 授权 | ✅ 良好 | scope 机制 + user_id 隔离 |
| 速率限制 | 🟡 中危 | 仅注册有限制，登录/体检/API Key 操作无限制 |
| 配额执行 | 🔴 **高危** | subscription_plan 可由用户自行修改（无支付验证） |
| 权限提升 | 🔴 **高危** | `update_profile` 允许修改 `subscription_plan` 无后端校验 |
| IDOR 防护 | ✅ 良好 | knowledge/inspection/settings 均检查 user_id |
| 竞态条件 | 🟡 中危 | 多处无 SELECT FOR UPDATE / 乐观锁 |
| 密码修改 | ✅ 良好 | 需验证旧密码 + 自动撤销所有 refresh token |
| 阅后即焚 | ✅ 良好 | burn API 正确清空 `parsed_content` |

---

## 发现的问题

### 🔴 HIGH — 用户可自行修改 subscription_plan 绕过付费

**位置**: `backend/app/api/v1/settings.py:395-398`

```python
if body.subscription_plan is not None and body.subscription_plan != membership.plan:
    plan_cfg = PLAN_CATALOG[body.subscription_plan]
    membership.plan = body.subscription_plan
    membership.token_quota = plan_cfg["monthly_quota"] or 0
```

**问题**:
- `PATCH /settings/profile` 允许用户直接修改 `subscription_plan`（如 `free` → `enterprise`）
- 后端无支付验证、无权限校验、无 webhook 回调
- 配额直接更新为 `PLAN_CATALOG` 中的最大值
- 攻击者可一键从免费版升级到企业版

**修复建议**:
```python
# 从 ProfileUpdateRequest 中移除 subscription_plan
# 改为通过支付回调/webhook 更新
class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None
    # subscription_plan: str | None = None  ← 删除
    model_name: str | None = None
    burn_after_read: bool | None = None
    email: str | None = None
    phone: str | None = None
```

或添加后端权限检查：
```python
if body.subscription_plan is not None:
    raise HTTPException(status_code=403, detail="订阅计划变更需通过支付渠道")
```

---

### 🔴 HIGH — settings API 允许设置任意 avatar_url（SSRF 向量）

**位置**: `backend/app/api/v1/settings.py:392-393`

```python
if body.avatar_url is not None:
    db_user.avatar_url = body.avatar_url
```

**问题**:
- `avatar_url` 仅做 Pydantic `str` 类型校验，无 URL 格式/协议/白名单检查
- 攻击者可设置 `avatar_url = "http://169.254.169.254/latest/meta-data/"` (AWS 元数据)
- 或 `avatar_url = "http://localhost:6379/"` (Redis)
- 如果前端或其他服务请求这个 URL，会造成 SSRF

**修复建议**:
```python
@field_validator("avatar_url")
@classmethod
def validate_avatar_url(cls, value: str | None) -> str | None:
    if value is None:
        return value
    from urllib.parse import urlparse
    parsed = urlparse(value)
    if parsed.scheme not in ("https",):
        raise ValueError("头像链接仅支持 HTTPS")
    if parsed.hostname in ("localhost", "127.0.0.1", "169.254.169.254"):
        raise ValueError("不允许的内网地址")
    return value
```

---

### 🟡 MEDIUM — 速率限制覆盖不全

**位置**: `backend/app/core/rate_limit.py` 全文件

**问题**:
- **注册**: 有 IP 速率限制（5次/小时）✅
- **登录**: 有指数退避（5/10/15/15+ 次后递增等待）✅
- **体检上传**: **无限制** — 用户可无限上传大文件消耗 AI 配额
- **API Key 创建**: **无限制** — 用户可无限创建 API Key
- **知识库上传**: **无限制** — 用户可无限上传 50MB 文件填满磁盘
- **密码修改**: **无限制** — 可暴力尝试旧密码

**修复建议**: 为关键端点添加速率限制：
```python
inspection_limiter = IPRateLimiter(max_requests=20, window_seconds=3600)
apikey_limiter = IPRateLimiter(max_requests=10, window_seconds=3600)
upload_limiter = IPRateLimiter(max_requests=30, window_seconds=3600)
```

---

### 🟡 MEDIUM — 竞态条件：API Key 查找无行锁

**位置**: `backend/app/services/api_key_service.py:116-127`

```python
async def lookup_api_key_by_token(db: AsyncSession, full_key: str) -> ApiKey | None:
    prefix = get_key_prefix(full_key)
    stmt = select(ApiKey).where(ApiKey.key_prefix == prefix)
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())
    for candidate in candidates:
        if verify_api_key_hash(full_key, candidate.key_hash):
            return candidate
    return None
```

**问题**: 在高并发下，`select` → `verify` → `update last_used_at` 不是原子操作。虽然对 API Key 验证场景影响较小，但如果未来引入 usage 计费，可能导致重复计费或跳过计费。

**修复建议**: 对计费相关操作使用 `SELECT ... FOR UPDATE`。

---

### 🟡 MEDIUM — inspection 内存会话无用户级并发保护

**位置**: `backend/app/api/v1/inspection.py:96-127`

**问题**: `_inspection_sessions` 是进程内 `dict`，在高并发下：
- `_trim_inspection_sessions` 在 trim 时 `sorted()` 不是线程安全的
- Python asyncio 是单线程的所以无数据竞争，但如果未来切换到多 worker（uvicorn workers>1），内存会话不共享

**修复建议**: 长期应迁移到 Redis（代码注释已标注）。

---

## 通过的检查 ✅

- ✅ 所有 `InspectionRecord` 查询带 `user_id` 条件（IDOR 安全）
- ✅ 所有 `TabooWord` 查询带 `user_id` 条件
- ✅ `KnowledgeDocument` 可见性检查 `_is_document_visible()` + `_visible_document_filter()`
- ✅ API Key 操作全部带 `user_id` 校验
- ✅ Agent API 通过 `require_api_scope()` 做 scope 校验
- ✅ Agent `get_job` 按 `user_id` 隔离
- ✅ `burn_record_content` 正确清空 `parsed_content`
- ✅ 密码修改需验证旧密码 + 自动撤销 refresh token
- ✅ 邮箱/手机号更新时检查唯一性（排除自身）
- ✅ 注册防重复检查（email + phone 分别查重）
- ✅ `model_name` 限制在 `MODEL_CATALOG` 白名单中
- ✅ 登录失败返回通用错误（"邮箱/手机号或密码错误"，不泄露具体哪个错误）
