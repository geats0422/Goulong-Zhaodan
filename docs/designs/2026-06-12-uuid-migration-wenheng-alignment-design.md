# 照胆数据库 UUID 迁移 — 对齐文衡基准

## 目标

将照胆（Goulong-zhaodan）的用户体系从 integer 主键 + username 登录，一次性迁移到 UUID 主键 + email/phone 双通道登录，完全对齐文衡（Goulong-wenheng）基准。同时为已有用户 `geats` 设置手机号 `17345823742` 和邮箱 `geats@qq.com`。

## 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 改造范围 | 完整 UUID 迁移 | 一步到位，避免后续二次迁移 |
| 现有数据 | 有业务数据需保留 | 需要写数据迁移逻辑 |
| 登录方式 | 完全移除 username | 对齐文衡，email/phone 双通道 |
| 迁移策略 | 单脚本原子迁移 | 项目在开发阶段，适合一次性变更 |

## 用户场景

1. **geats 用户迁移后**：可以用 `geats@qq.com` + 密码登录，或用 `17345823742` + 密码登录
2. **新用户注册**：必须提供 email 或 phone（至少一项）+ nickname + password
3. **所有现有业务数据**（体检记录、知识库设置、API Key、Agent 任务等）正确关联到新 UUID

## 数据模型变更

### users 表

**当前：**
```sql
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50)  NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ
);
```

**目标：**
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE,
    phone           VARCHAR(20)  UNIQUE,
    wechat_openid   VARCHAR(64)  UNIQUE,
    alipay_user_id  VARCHAR(64)  UNIQUE,
    nickname        VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    avatar_url      VARCHAR(500),
    is_active       BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_has_identity CHECK (
        email IS NOT NULL OR phone IS NOT NULL
    )
);
```

**关键变化：**
- `id`: SERIAL → UUID
- 删除 `username`
- 新增 `email`, `phone`, `wechat_openid`, `alipay_user_id`, `nickname`, `avatar_url`
- CHECK 约束确保至少一种登录方式

### user_profiles 表

**当前：**
```sql
CREATE TABLE user_profiles (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL FK → users.id UNIQUE,
    display_name      VARCHAR(100) NOT NULL,
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'personal',
    monthly_quota     INTEGER NOT NULL DEFAULT 500,
    quota_used        INTEGER NOT NULL DEFAULT 0,
    wechat_bound      BOOLEAN NOT NULL DEFAULT false,
    alipay_bound      BOOLEAN NOT NULL DEFAULT false,
    burn_after_read   BOOLEAN NOT NULL DEFAULT true,
    model_name        VARCHAR(120),
    phone             VARCHAR(32) UNIQUE,
    email             VARCHAR(255) UNIQUE,
    created_at        TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ
);
```

**目标：**
```sql
CREATE TABLE user_profiles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    legacy_id         INTEGER UNIQUE,
    subscription_plan VARCHAR(50) NOT NULL DEFAULT 'free',
    monthly_quota     INTEGER NOT NULL DEFAULT 50,
    quota_used        INTEGER NOT NULL DEFAULT 0,
    burn_after_read   BOOLEAN NOT NULL DEFAULT false,
    model_name        VARCHAR(120),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**删除字段：** `display_name` → users.nickname；`phone` → users.phone；`email` → users.email；`wechat_bound` → users.wechat_openid IS NOT NULL；`alipay_bound` → users.alipay_user_id IS NOT NULL

### 业务表 user_id FK 改 UUID

所有引用 `users.id` 的列从 `INTEGER` → `UUID`：

| 表 | 列 |
|----|-----|
| `user_profiles` | `user_id` |
| `api_keys` | `id`（主键也改 UUID）、`user_id` |
| `refresh_tokens` | `user_id` |
| `knowledge_document_settings` | `user_id` |
| `inspection_records` | `user_id` |
| `taboo_words` | `user_id` |
| `agent_jobs` | `user_id`、`api_key_id` |
| `knowledge_documents` | `owner_user_id` |

## 接口设计

### 认证 API 变更

**注册（改造后）：**
```
POST /auth/register
Body: { "email": "user@example.com", "nickname": "张三", "password": "..." }
   或 { "phone": "17345823742", "nickname": "张三", "password": "..." }
   或 { "email": "user@example.com", "phone": "17345823742", "nickname": "张三", "password": "..." }
Response: { "id": "<uuid>", "email": "...", "phone": "...", "nickname": "...", "access_token": "...", "refresh_token": "..." }
```

**登录（改造后）：**
```
POST /auth/login
Body: { "email": "geats@qq.com", "password": "..." }
   或 { "phone": "17345823742", "password": "..." }
Response: { "id": "<uuid>", "email": "...", "phone": "...", "nickname": "...", "access_token": "...", "refresh_token": "..." }
```

**JWT payload：**
```json
{ "sub": "<uuid-string>", "type": "access", "exp": 1718000000 }
```

### Settings API 变更

- `ProfileResponse` 移除 `username`、`wechat_bound`、`alipay_bound`
- 新增 `email`、`phone`、`nickname`、`avatar_url`、`has_wechat`、`has_alipay`
- `ProfileUpdateRequest` 移除 `username`，新增 `nickname`

## 受影响的文件

### 模型层（重写）
- `backend/models/knowledge.py` — User、UserProfile、所有 user_id FK
- `backend/models/api_keys.py` — ApiKey、AgentJob 的 id 和 user_id

### 认证层
- `backend/core/auth.py` — user_id 类型 int → uuid.UUID
- `backend/routers/auth.py` — RegisterRequest/LoginRequest 重写

### 路由层
- `backend/routers/settings.py` — ProfileResponse/ProfileUpdateRequest 适配
- `backend/routers/inspection.py` — user_id 类型
- `backend/routers/knowledge.py` — user_id 类型

### 服务层
- `backend/services/api_key_service.py`
- `backend/services/agent_job_service.py`
- `backend/services/knowledge_retrieval.py`

### 迁移
- `backend/alembic/versions/012_uuid_migration.py` — 新增

### 前端
- `frontend/src/composables/useAuth.js`
- `frontend/src/pages/LoginPage.vue`
- `frontend/src/pages/RegisterPage.vue`

### 测试
- `backend/tests/test_auth_api.py`
- `backend/tests/test_settings_api.py`
- `backend/tests/test_inspection_api.py`
- `backend/tests/test_api_key_models.py`
- `backend/tests/test_api_key_service.py`
- `backend/tests/test_agent_job_service.py`
- `backend/tests/test_agent_auth_deps.py`
- `backend/tests/test_knowledge_retrieval.py`
- 新增 `backend/tests/test_012_uuid_migration.py`

## 迁移脚本核心逻辑

```
Alembic 012_uuid_migration.py upgrade():

1. 创建临时表 _uuid_mapping(old_id INTEGER, new_id UUID)
2. 为所有旧 users 生成 UUID，写入 _uuid_mapping
3. 创建新 users 表（UUID 主键）
4. 迁移 users 数据：
   - nickname = COALESCE(up.display_name, u.username)
   - phone = COALESCE(特殊映射, up.phone)
   - email = COALESCE(特殊映射, up.email)
   - geats 用户强制: phone='17345823742', email='geats@qq.com'
5. 创建新 user_profiles 表，迁移数据，记录 legacy_id
6. 逐一迁移业务表（通过 _uuid_mapping JOIN 找新 UUID）
7. 删旧表、重命名新表
8. 删除临时表 _uuid_mapping
```

## 错误处理

| 失败模式 | 应对策略 |
|----------|---------|
| 迁移中途失败 | Alembic 事务回滚，数据库回到迁移前状态 |
| geats 用户不存在 | 迁移脚本正常完成（无匹配则跳过特殊处理） |
| phone/email 唯一约束冲突 | 迁移前检查重复数据，合并或标记 |
| 前端旧 token 失效 | 迁移后要求用户重新登录 |

## 测试策略

### 1. 迁移验证测试
- 旧用户数据完整迁移到新表
- geats 用户 phone='17345823742' email='geats@qq.com'
- 所有 FK 关系完整
- legacy_id 映射正确

### 2. 认证流程测试
- email + password 注册
- email + password 登录
- phone + password 登录
- username 登录返回 401
- JWT sub 为 UUID 格式

### 3. 全量回归测试
- `uv run pytest` — 所有现有测试适配后通过

## 验证清单

- [ ] `users.id` 为 UUID 类型
- [ ] `users.email` 和 `users.phone` 至少一项非空
- [ ] `users.wechat_openid` 和 `users.alipay_user_id` 列存在
- [ ] 所有业务表 `user_id` 为 UUID
- [ ] 所有 FK 指向新 `users.id`
- [ ] JWT sub 为 UUID 字符串
- [ ] 登录支持 email + password 和 phone + password
- [ ] username 登录已移除
- [ ] geats 用户 phone='17345823742' email='geats@qq.com'
- [ ] `user_profiles.legacy_id` 记录旧 integer id
- [ ] 全部测试通过

## 注意事项

1. **不改动核心业务逻辑** — 本次仅改造用户体系数据结构
2. **照胆特有字段保留** — `subscription_plan`、`monthly_quota`、`quota_used`、`burn_after_read`、`model_name`
3. **`api_keys.id` 也改 UUID** — 因为 `agent_jobs.api_key_id` 引用它
4. **api_keys.key_prefix** — 照胆保持自己的前缀
5. **手机验证码登录** — 本次预留接口，实际短信发送后续实现
