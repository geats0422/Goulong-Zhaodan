# JWT 认证设计文档

## 目标

将 MVP 阶段的静态 API Key 认证替换为 JWT 双 Token 认证，支持多用户注册/登录，为后续 SaaS 多用户场景做准备。

## 用户场景

1. 新用户访问系统 → 跳转登录页 → 点击"注册" → 输入用户名+密码 → 注册成功 → 自动登录
2. 已注册用户 → 输入用户名+密码 → 登录 → 获取 JWT → 进入系统
3. 使用中 access_token 过期 → 前端自动用 refresh_token 静默刷新 → 无感知续期
4. refresh_token 过期 → 跳转登录页重新登录

## 技术方案

### 认证流程

```
注册: POST /auth/register → 创建用户 → 返回双 token
登录: POST /auth/login → 校验密码 → 返回双 token
刷新: POST /auth/refresh → 校验 refresh_token → 返回新 access_token
用户: GET /auth/me → 校验 access_token → 返回用户信息
```

### 双 Token 策略

| Token | 有效期 | 存储 | 用途 |
|-------|--------|------|------|
| access_token | 30 分钟 | 前端内存 (JS 变量) | API 请求鉴权 |
| refresh_token | 7 天 | httpOnly cookie | 静默刷新 access_token |

### 依赖库

- `PyJWT>=2.8.0` — JWT 编解码
- `passlib[bcrypt]>=1.7.4` — 密码哈希
- 移除 `settings.api_key` 配置

## 数据模型

### 新增 `users` 表

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Alembic 迁移

新增迁移文件 `002_add_users_table.py`，创建 `users` 表。

## 接口设计

### POST /auth/register

```json
// Request
{ "username": "admin", "password": "securepass123" }

// Response 201
{
  "id": 1,
  "username": "admin",
  "access_token": "eyJ...",
  "refresh_token": "eyJ..."  // 同时通过 httpOnly cookie 设置
}
```

校验规则：
- username: 3-50 字符，仅字母数字下划线
- password: 6-128 字符

### POST /auth/login

```json
// Request
{ "username": "admin", "password": "securepass123" }

// Response 200
{
  "id": 1,
  "username": "admin",
  "access_token": "eyJ...",
  "refresh_token": "eyJ..."  // 同时通过 httpOnly cookie 设置
}
```

### POST /auth/refresh

```json
// Request: refresh_token 从 httpOnly cookie 自动携带
// Response 200
{ "access_token": "eyJ..." }
```

### GET /auth/me

```json
// Request: Authorization: Bearer <access_token>
// Response 200
{ "id": 1, "username": "admin", "is_active": true }
```

## 后端实现

### 文件变更

| 文件 | 变更 |
|------|------|
| `core/auth.py` | 重写：JWT 签发/验证 + 密码哈希 + get_current_user 依赖 |
| `core/config.py` | 新增 `jwt_secret_key`, `jwt_algorithm`, `access_token_expire_minutes`, `refresh_token_expire_days` |
| `models/knowledge.py` | 新增 `User` 模型 |
| `routers/auth.py` | 新增：register/login/refresh/me 四个端点 |
| `main.py` | 挂载 `auth_router` |
| `alembic/versions/002_add_users_table.py` | 新增迁移 |
| `pyproject.toml` | 新增 `PyJWT`, `passlib[bcrypt]` 依赖 |
| `env.example` | 新增 `JWT_SECRET_KEY` |

### get_current_user 改动

现有 8 个端点的 `Depends(get_current_user)` 接口签名不变（返回 `dict`），内部改为解析 JWT access_token。所有路由和测试改动最小化。

### JWT Payload

```json
{
  "sub": "1",           // user_id (字符串)
  "type": "access",     // "access" | "refresh"
  "exp": 1234567890     // 过期时间
}
```

## 前端实现

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/pages/LoginPage.vue` | 登录/注册表单页面 |
| `src/composables/useAuth.js` | Token 管理 + 自动刷新 |

### 改动文件

| 文件 | 说明 |
|------|------|
| `src/router.js` | 添加 `/login` 路由 + 导航守卫 |
| `src/App.vue` | 无需改动 |

### useAuth.js 功能

```js
- login(username, password) → 调用 /auth/login，存 access_token
- register(username, password) → 调用 /auth/register
- refreshToken() → 调用 /auth/refresh（cookie 自动携带）
- logout() → 清除 token，跳转 /login
- getAuthHeaders() → 返回 { Authorization: 'Bearer <token>' }
- fetchWithAuth(url, options) → 封装 fetch，401 时自动刷新重试一次
```

### 路由守卫

```js
router.beforeEach((to) => {
  if (to.path !== '/login' && !isLoggedIn()) {
    return '/login'
  }
})
```

## 错误处理

| 场景 | HTTP 状态码 | 处理 |
|------|-------------|------|
| 用户名已存在 | 409 | 前端提示"用户名已被注册" |
| 用户名或密码错误 | 401 | 前端提示"用户名或密码错误" |
| access_token 过期 | 401 | 前端自动刷新 |
| refresh_token 过期 | 401 | 前端跳转登录页 |
| 无效 token | 401 | 前端跳转登录页 |
| 用户已停用 | 403 | 前端提示"账号已被停用" |

## 测试策略

### 后端测试（pytest）

1. `test_auth_api.py` — 注册/登录/刷新/me 四个端点的正常+异常流程
2. 现有 `test_knowledge_api.py` / `test_history_stats_api.py` 的 `get_current_user` override 改为返回 JWT 用户
3. 密码哈希正确性验证
4. Token 过期/无效/伪造场景

### 前端验证

- `npm run build` 通过
- `npm run test:routes` 通过

## 迁移策略

1. 新增 `users` 表（不影响现有表）
2. `get_current_user` 内部切换为 JWT，接口签名不变
3. 移除 `X-API-Key` header 检查
4. 前端从 `X-API-Key` 切换到 `Authorization: Bearer`
