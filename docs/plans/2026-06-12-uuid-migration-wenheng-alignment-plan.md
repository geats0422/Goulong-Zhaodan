# 照胆 UUID 迁移 — 实施计划

> 设计文档: `docs/designs/2026-06-12-uuid-migration-wenheng-alignment-design.md`

## 任务概览

| # | 任务名 | 预估时间 | 核心文件 | 依赖 |
|---|--------|---------|---------|------|
| 1 | Alembic 迁移脚本 | ~5 min | `alembic/versions/012_uuid_migration.py` | 无 |
| 2 | 模型层重写 | ~5 min | `models/knowledge.py`, `models/api_keys.py` | 无 |
| 3 | 认证层改造 | ~5 min | `core/auth.py`, `routers/auth.py` | 任务 2 |
| 4 | 路由层+服务层适配 | ~5 min | `routers/settings.py`, `inspection.py`, `knowledge.py`, `services/*.py` | 任务 2+3 |
| 5 | 迁移验证+认证测试 | ~5 min | `tests/test_012_uuid_migration.py`, `tests/test_auth_api.py` | 任务 1+2+3 |
| 6 | 全量测试适配 | ~5 min | 所有 `tests/test_*.py` (15+ 文件) | 任务 3+4+5 |
| 7 | 前端适配 | ~5 min | `useAuth.js`, `LoginPage.vue`, `RegisterPage.vue` | 任务 3 |
| 8 | 集成验证 | ~3 min | 纯验证 | 任务 6+7 |

---

## 任务 1: Alembic 迁移脚本

**文件:** `backend/alembic/versions/012_uuid_migration.py`

**操作:** 创建 Alembic 迁移脚本

**upgrade() 核心逻辑:**
1. 启用 `uuid-ossp` 扩展（`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`）
2. 创建临时映射表 `_uuid_mapping(old_id INTEGER, new_id UUID)`
3. 为所有旧 users 生成 UUID，写入 `_uuid_mapping`
4. 创建新 `users` 表（UUID 主键 + email/phone/wechat_openid/alipay_user_id/nickname/avatar_url）
5. 迁移 users 数据：
   - `nickname = COALESCE(up.display_name, u.username)`
   - geats 用户强制: `phone='17345823742'`, `email='geats@qq.com'`
   - 其他用户: `phone = up.phone`, `email = up.email`
   - 无 email 也无 phone 的用户: `email = u.username || '@placeholder.local'`（满足 CHECK 约束）
6. 删除旧 `user_profiles` 表
7. 创建新 `user_profiles` 表（UUID 主键 + legacy_id + 精简字段）
8. 逐一迁移业务表（api_keys, refresh_tokens, knowledge_document_settings, inspection_records, taboo_words, agent_jobs, knowledge_documents）：
   - 先删旧 FK 约束
   - 添加临时 UUID 列
   - 通过 `_uuid_mapping` JOIN 填充新 UUID
   - 删旧 integer 列，重命名 UUID 列为原列名
   - 重建 FK 约束
9. api_keys.id 也从 SERIAL → UUID（因为 agent_jobs.api_key_id 引用它）
10. 删除临时表 `_uuid_mapping`

**downgrade() 核心逻辑:** 反向操作（UUID → integer），仅用于开发回滚

**验证:**
- `$env:ALEMBIC_DATABASE_URL="postgresql+psycopg2://postgres:990715@localhost:5432/goulong"; alembic upgrade head`
- SQL 验证: `\d users` 确认 UUID 主键

---

## 任务 2: 模型层重写

**文件:**
- `backend/models/knowledge.py` — User、UserProfile
- `backend/models/api_keys.py` — ApiKey、AgentJob

**操作:**

### User 模型（对齐文衡基准）
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    alipay_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### UserProfile 模型（精简）
- `id` → UUID
- `user_id` → UUID FK
- 新增 `legacy_id: Mapped[int | None]`
- 删除 `display_name`, `phone`, `email`, `wechat_bound`, `alipay_bound`
- 保留 `subscription_plan`, `monthly_quota`, `quota_used`, `burn_after_read`, `model_name`

### ApiKey 模型
- `id` → UUID
- `user_id` → UUID FK

### AgentJob 模型
- `user_id` → UUID FK
- `api_key_id` → UUID FK

### 其他模型（inspection_records, taboo_words, knowledge_document_settings, knowledge_documents, refresh_tokens）
- 所有 `user_id` / `owner_user_id` 列从 `Integer` → `UUID(as_uuid=True)`

**验证:** `uv run python -c "from models.knowledge import User, UserProfile; print(User.__table__.c.id.type)"`

---

## 任务 3: 认证层改造

**文件:**
- `backend/core/auth.py` — user_id 类型注解
- `backend/routers/auth.py` — RegisterRequest/LoginRequest 重写

**操作:**

### core/auth.py
- `get_current_user()` 返回的 `user.id` 已经是 UUID，无需改逻辑
- 确认 JWT `sub` 字段为 `str(user.id)`（UUID 字符串）

### routers/auth.py

**RegisterRequest 重写:**
```python
class RegisterRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    nickname: str
    password: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone（至少一项）")
        return self
```

**LoginRequest 重写:**
```python
class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str

    @model_validator(mode="after")
    def check_identity(self):
        if not self.email and not self.phone:
            raise ValueError("必须提供 email 或 phone")
        return self
```

**register() 路由重写:**
- 查重: `db.execute(select(User).where(User.email == body.email))` 或 phone
- 创建 User（nickname, hashed_password, email/phone）
- 创建 UserProfile（默认 free 计划）

**login() 路由重写:**
- 按 email 或 phone 查找用户
- verify_password
- 生成 JWT（sub 为 UUID 字符串）

**验证:** `uv run pytest tests/test_auth_api.py -v`（需要任务 5 的测试先写好）

---

## 任务 4: 路由层+服务层适配

**文件:**
- `backend/routers/settings.py` — ProfileResponse/ProfileUpdateRequest
- `backend/routers/inspection.py` — user_id 类型
- `backend/routers/knowledge.py` — owner_user_id 类型
- `backend/services/api_key_service.py` — user_id 类型
- `backend/services/agent_job_service.py` — user_id/api_key_id 类型
- `backend/services/knowledge_retrieval.py` — user_id 类型

**操作:**

### settings.py
- `ProfileResponse`: 移除 `username`/`wechat_bound`/`alipay_bound`，新增 `nickname`/`email`/`phone`/`avatar_url`/`has_wechat`/`has_alipay`
  - `email` 和 `phone` 从 `User` 表直接读取（不再从 UserProfile）
  - `has_wechat = user.wechat_openid is not None`
  - `has_alipay = user.alipay_user_id is not None`
- `ProfileUpdateRequest`: 移除 `username`，新增 `nickname`/`avatar_url`
- 修改密码: `hash_password(body.new_password)` → `user.hashed_password = ...`

### inspection.py / knowledge.py
- `user_id: int` → `user_id: uuid.UUID`

### services/*.py
- 所有 `user_id: int` 参数改为 `user_id: uuid.UUID`

**验证:** `uv run ruff check backend/` + `uv run python -c "from routers.settings import ..."`

---

## 任务 5: 迁移验证+认证测试

**文件:**
- `backend/tests/test_012_uuid_migration.py` — 新增
- `backend/tests/test_auth_api.py` — 重写

**操作:**

### test_012_uuid_migration.py
- 测试迁移后 users 表结构（UUID 主键、email/phone 列存在）
- 测试 geats 用户数据（phone='17345823742', email='geats@qq.com'）
- 测试 FK 完整性（所有业务表 user_id 指向有效 UUID）
- 测试 legacy_id 映射

### test_auth_api.py
- email + password 注册
- phone + password 注册
- email + password 登录
- phone + password 登录
- 缺少 email 和 phone 注册 → 422
- 重复 email 注册 → 409
- username 登录 → 401（已移除）

**验证:** `$env:DATABASE_URL="postgresql+asyncpg://postgres:990715@localhost:5432/goulong_test"; uv run pytest tests/test_012_uuid_migration.py tests/test_auth_api.py -v`

---

## 任务 6: 全量测试适配

**文件:** 所有 `backend/tests/test_*.py` (15+ 文件)

**操作:**
- 所有 `user_id` 类型从 `int` → `uuid.uuid4()`
- 所有 `User(username=...)` → `User(nickname=..., email=...)`
- 所有 `UserProfile(display_name=...)` → 移除
- 所有 `hashed_password="fakehash"` 保持不变
- api_keys 测试: `id` 改为 UUID, `key_hash` 不变
- agent_jobs 测试: `api_key_id` 改为 UUID

**验证:** `$env:DATABASE_URL="...goulong_test"; uv run pytest tests/ -v`

---

## 任务 7: 前端适配

**文件:**
- `frontend/src/composables/useAuth.js`
- `frontend/src/pages/LoginPage.vue`
- `frontend/src/pages/RegisterPage.vue`
- `frontend/src/data/plans.js`（如引用 username）

**操作:**

### useAuth.js
- `login(username, password)` → `login(identity, password)`
- 自动判断 identity 是 email 还是 phone 格式
- 注册: `register({ email?, phone?, nickname, password })`

### LoginPage.vue
- 移除 username 输入框
- 保留 email 输入框和 phone 输入框（tab 切换）
- 调用 `login({ email: value, password })` 或 `login({ phone: value, password })`

### RegisterPage.vue
- 移除 username 输入框
- 新增 nickname 输入框
- email 和 phone 至少填一个
- 密码规则校验保持不变

**验证:** `cd frontend && npm run build`

---

## 任务 8: 集成验证

**操作:**
1. 确认 alembic_version = 012
2. 后端: `uv run pytest tests/ -v` 全量通过
3. 前端: `npm run build` 构建成功
4. 启动后端 `uv run uvicorn main:app --host 0.0.0.0 --port 8000`
5. 手动验证: 用 `geats@qq.com` + 密码登录
6. 手动验证: 用 `17345823742` + 密码登录
7. 检查 SettingsPage 显示 nickname/email/phone

**验证:** 全部通过后，准备 `/finish` 收尾

---

## 高风险项

| 风险 | 影响 | 缓解 |
|------|------|------|
| 迁移中途失败 | 数据库不一致 | Alembic 事务回滚 + 迁移前手动备份 |
| 遗漏 int→UUID 转换点 | 运行时类型错误 | `grep -rn "user_id.*int" backend/` 全局搜索确认 |
| 前端旧 token 失效 | 用户需重新登录 | 迁移后提示重新登录 |
