# JWT 认证实施计划

## 总览

将 MVP 阶段的静态 API Key 认证替换为 JWT 双 Token 认证。策略：后端先行（模型 → 认证核心 → 路由 → 测试），前端跟进（composable → 登录页 → 路由守卫 → API 调用迁移）。关键约束：`get_current_user` 的接口签名（返回 `dict`）保持不变，所有路由文件零改动。共 12 个任务，预估总工时 ~45 分钟。

## 任务列表

### 任务 1: 添加 JWT/密码哈希依赖 (~2 min)
- **文件**: `backend/pyproject.toml`
- **变更**: dependencies 新增 `PyJWT>=2.8.0`, `passlib[bcrypt]>=1.7.4`
- **验证**: `pip install -e ".[dev]"` 成功

### 任务 2: 添加 JWT 配置项到 Settings (~2 min)
- **文件**: `backend/core/config.py`, `backend/env.example`
- **变更**: 新增 `jwt_secret_key`, `jwt_algorithm`, `access_token_expire_minutes`, `refresh_token_expire_days`
- **验证**: `from core.config import settings; settings.jwt_secret_key` 无报错

### 任务 3: 新增 User 模型 (~3 min)
- **文件**: `backend/models/knowledge.py`
- **变更**: 新增 `User` 表 (id, username, hashed_password, is_active, created_at, updated_at)
- **验证**: `from models.knowledge import User` 无报错

### 任务 4: 创建 Alembic 迁移 — users 表 (~2 min)
- **文件**: `backend/alembic/versions/002_add_users_table.py`
- **验证**: `alembic upgrade head` 成功

### 任务 5: 重写 core/auth.py — JWT 签发/验证 (~5 min)
- **文件**: 重写 `backend/core/auth.py`
- **变更**: JWT 双 Token 签发/验证 + 密码哈希，`get_current_user(request) -> dict` 签名不变
- **验证**: 签发/解码 token 正常，无效 token 抛 401

### 任务 6: 创建 auth 路由 — register/login/refresh/me (~5 min)
- **文件**: 创建 `backend/routers/auth.py`
- **变更**: 4 个端点，register 返回 201，refresh_token 通过 httpOnly cookie
- **验证**: 各端点正常/异常场景通过

### 任务 7: 挂载 auth 路由到应用 (~1 min)
- **文件**: `backend/main.py`
- **变更**: `app.include_router(auth_router)`

### 任务 8: 创建 auth API 测试 (~5 min)
- **文件**: `backend/tests/test_auth_api.py`
- **测试**: 12 个用例覆盖注册/登录/刷新/me 正常+异常

### 任务 9: 更新现有测试的认证方式 (~3 min)
- **文件**: `conftest.py`, `test_knowledge_api.py`, `test_history_stats_api.py`
- **变更**: override 改为 JWT 用户格式

### 任务 10: 创建 useAuth composable (~4 min)
- **文件**: `frontend/src/composables/useAuth.js`
- **功能**: login, register, refreshToken, logout, getAuthHeaders, fetchWithAuth, isLoggedIn

### 任务 11: 创建登录/注册页面 (~3 min)
- **文件**: `frontend/src/pages/LoginPage.vue`

### 任务 12: 路由守卫 + API 调用迁移 (~5 min)
- **文件**: `router.js`, `KnowledgeBasePage.vue`, `StatisticsPage.vue`
- **变更**: 添加 /login 路由 + beforeEach 守卫 + fetch→fetchWithAuth

## 依赖关系

```
任务1+2+3 并行 → 任务5(依赖1+2) → 任务6(依赖3+5) → 任务7 → 任务8+9
任务10(可并行) → 任务11 → 任务12
```

## 执行状态

- [ ] 任务 1: 添加 JWT/密码哈希依赖
- [ ] 任务 2: 添加 JWT 配置项到 Settings
- [ ] 任务 3: 新增 User 模型
- [ ] 任务 4: 创建 Alembic 迁移
- [ ] 任务 5: 重写 core/auth.py
- [ ] 任务 6: 创建 auth 路由
- [ ] 任务 7: 挂载 auth 路由
- [ ] 任务 8: 创建 auth API 测试
- [ ] 任务 9: 更新现有测试认证方式
- [ ] 任务 10: 创建 useAuth composable
- [ ] 任务 11: 创建登录/注册页面
- [ ] 任务 12: 路由守卫 + API 调用迁移
