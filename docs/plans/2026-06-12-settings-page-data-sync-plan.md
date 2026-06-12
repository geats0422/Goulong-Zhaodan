# 设置中枢数据同步与 UI 重构 — 实施计划

## 总览

本计划覆盖设置中枢的 3 大改造：①后端默认订阅 `personal → free` + 新增 `UserProfile.model_name` 字段 + `ProfileResponse` 扩展；②前端 SettingsPage 三大 tab（账单/模型/身份）全面重构；③前端新增共享 `plans.js` 数据源与浅色主题适配。按后端→迁移→前端共享→前端页面→样式→测试 的顺序执行，后端任务 1-4 可部分并行。

## 前置准备

- [x] 设计文档已批准：`docs/designs/2026-06-11-settings-page-data-sync-design.md`
- [x] 开发环境就绪：后端 `uv run`，前端 `npm run dev`
- [ ] 运行现有测试确认基线通过：`cd backend && uv run pytest tests/test_settings_api.py -v`

## 任务列表

---

### 任务 1: 后端 — UserProfile 模型加 model_name 字段 (~3 min)

- **描述**: 在 `UserProfile` SQLAlchemy 模型中新增 `model_name` 列（`String(120), nullable=True`），为后续 alembic 迁移和接口扩展做准备。
- **文件**:
  - 修改 `backend/models/knowledge.py` → `UserProfile` 类
- **具体操作**:
  1. 在 `UserProfile` 类中，`burn_after_read` 字段后新增一行：
     ```python
     model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
     ```
- **测试**: 无新增（模型变更本身无需单独测试，由迁移+接口测试覆盖）
- **验证**: `uv run python -c "from models.knowledge import UserProfile; print(UserProfile.model_name)"` 不报错
- **依赖**: 无

---

### 任务 2: 后端 — settings 路由扩展常量 + ProfileResponse + ProfileUpdateRequest (~5 min)

- **描述**: 在 `routers/settings.py` 中新增 `PLAN_CATALOG` 和 `MODEL_CATALOG` 常量，扩展 `ProfileResponse` 和 `ProfileUpdateRequest` Pydantic 模型，更新 `_get_or_create_profile` 默认值为 `free`。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **具体操作**:
  1. 文件顶部新增 `import re`
  2. 在 `router` 定义之后，新增常量：
     ```python
     PLAN_CATALOG = {
         "free":       {"label": "免费体验",   "period": "永久",  "price": "¥0",    "monthly_quota": 50,    "features": ["基础智能审查", "单文件上传", "Markdown 报告"]},
         "personal":   {"label": "个人版",     "period": "/月",   "price": "¥39",   "monthly_quota": 500,   "features": ["多文件材料包", "私域红线标准", "本地脱敏", "阅后即焚"]},
         "team":       {"label": "团队版",     "period": "/月",   "price": "¥299",  "monthly_quota": 3000,  "features": ["团队协作", "审计留痕", "自定义红线", "优先支持"]},
         "enterprise": {"label": "企业定制",   "period": "按合同", "price": "议价",  "monthly_quota": None,  "features": ["私有化部署", "SSO 单点登录", "SLA 保障", "专属客户成功"]},
     }

     MODEL_CATALOG = [
         {"model_name": "deepseek-ai/deepseek-v4-pro",   "label": "DeepSeek V4 Pro",   "tier": "高准确度 · 慢", "context": "128K"},
         {"model_name": "deepseek-ai/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tier": "快速响应",      "context": "64K"},
     ]
     ```
  3. 扩展 `ProfileResponse`，新增字段：
     ```python
     subscription_label: str
     subscription_period: str
     subscription_price: str
     model_name: str
     model_base_url: str
     model_api_key_preview: str
     model_catalog: list[dict]
     ```
  4. 扩展 `ProfileUpdateRequest`，新增字段 + validators：
     ```python
     username: str | None = None
     subscription_plan: str | None = None
     model_name: str | None = None
     ```
     新增 `validate_username` 和 `validate_model_name` field_validator。
  5. 修改 `_get_or_create_profile`：`subscription_plan="free"`, `monthly_quota=50`
  6. 修改 `_profile_response` 函数，注入 `subscription_label/period/price/model_name/model_base_url/model_api_key_preview/model_catalog`（需引入 `from core.config import settings`）
- **测试**: 无新增（任务 3 路由逻辑测试覆盖）
- **验证**: `uv run python -c "from routers.settings import PLAN_CATALOG, MODEL_CATALOG; print(len(PLAN_CATALOG), len(MODEL_CATALOG))"` 输出 `4 2`
- **依赖**: 任务 1

---

### 任务 3: 后端 — update_profile 路由扩展 username/subscription_plan/model_name 处理 (~4 min)

- **描述**: 扩展 `update_profile` 路由，支持 `username` 唯一性校验（409 冲突）、`subscription_plan` 更新（同步 `monthly_quota`）、`model_name` 持久化到 `UserProfile`。
- **文件**:
  - 修改 `backend/routers/settings.py` → `update_profile` 函数
- **具体操作**:
  1. 在 `update_profile` 函数体中，遍历字段之前新增：
     - `username` 处理：若 `body.username` 非空，查唯一性 → 冲突抛 `HTTPException(409)` → 更新 `db_user.username` 和 `profile.display_name`（如 display_name 未显式修改）
     - `subscription_plan` 处理：若 `body.subscription_plan` 非空，查 `PLAN_CATALOG` → 更新 `profile.subscription_plan` 和 `profile.monthly_quota`
     - `model_name` 处理：若 `body.model_name` 非空，写入 `profile.model_name`
  2. 保留原有遍历 `display_name/wechat_bound/alipay_bound/burn_after_read` 逻辑不变
  3. `username` 更新后，需同步 `db_user.username`（需 `await db.flush()` 保证唯一约束检查生效）
- **测试**: 任务 9 后端测试覆盖
- **验证**: `uv run python -c "from routers.settings import update_profile; print('ok')"` 无语法错误
- **依赖**: 任务 2

---

### 任务 4: 后端 — api_key_service.last_viewed_at 已有，无需修改 (~0 min)

- **描述**: 确认 `services/api_key_service.py` 中 `get_api_key_secret` 已在行 77 更新 `last_viewed_at = datetime.datetime.utcnow()`，无需额外修改。
- **文件**: 无修改
- **验证**: 代码审查确认 `api_key_service.py:77` 已有 `api_key.last_viewed_at = datetime.datetime.utcnow()`
- **依赖**: 无

---

### 任务 5: Alembic 迁移 — 009 legacy personal → free (~3 min)

- **描述**: 创建 alembic 009 迁移，将历史 `subscription_plan='personal' AND quota_used=0` 的 profile 回退到 `free/50`。
- **文件**:
  - 创建 `backend/alembic/versions/009_legacy_personal_to_free.py`
- **具体操作**:
  ```python
  revision = "009"
  down_revision = "008"

  def upgrade():
      op.execute(
          "UPDATE user_profiles SET subscription_plan='free', monthly_quota=50 "
          "WHERE subscription_plan='personal' AND quota_used=0"
      )

  def downgrade():
      pass  # 不可逆
  ```
- **测试**: 手动验证（构造 personal+quota_used=0 数据后执行迁移，确认变为 free/50）
- **验证**: `uv run alembic upgrade head` 不报错
- **依赖**: 无（可与任务 1-3 并行）

---

### 任务 6: Alembic 迁移 — 010 新增 model_name 列 (~3 min)

- **描述**: 创建 alembic 010 迁移，给 `user_profiles` 表新增 `model_name` 列，默认值取 `settings.model_name`。
- **文件**:
  - 创建 `backend/alembic/versions/010_add_user_profile_model_name.py`
- **具体操作**:
  ```python
  revision = "010"
  down_revision = "009"

  def upgrade():
      op.add_column("user_profiles", sa.Column("model_name", sa.String(120), nullable=True))
      bind = op.get_bind()
      from core.config import settings
      bind.execute(
          sa.text("UPDATE user_profiles SET model_name = :n WHERE model_name IS NULL"),
          {"n": settings.model_name},
      )

  def downgrade():
      op.drop_column("user_profiles", "model_name")
  ```
- **测试**: `uv run alembic upgrade head` 后检查数据库 `user_profiles` 表结构
- **验证**: `uv run alembic upgrade head` 成功，`model_name` 列存在
- **依赖**: 任务 5（迁移链顺序）

---

### 任务 7: 前端 — 新建 plans.js 共享数据源 (~2 min)

- **描述**: 创建 `frontend/src/data/plans.js`，导出 `PLAN_CATALOG`、`PLAN_CATEGORY_TABS`、`MODEL_CATALOG`，供 SettingsPage 和 PricingPage 共同消费。
- **文件**:
  - 创建 `frontend/src/data/plans.js`
- **具体操作**:
  ```js
  export const PLAN_CATALOG = {
    free:       { key: 'free',       label: '免费体验', price: '¥0',    period: '永久',  quota: 50,    category: 'personal',   features: [...] },
    personal:   { key: 'personal',   label: '个人版',   price: '¥39',   period: '/月',   quota: 500,   category: 'personal',   features: [...] },
    team:       { key: 'team',       label: '团队版',   price: '¥299',  period: '/月',   quota: 3000,  category: 'team',       features: [...] },
    enterprise: { key: 'enterprise', label: '企业定制', price: '议价', period: '按合同', quota: '不限', category: 'enterprise', features: [...] },
  }

  export const PLAN_CATEGORY_TABS = [
    { key: 'personal',   label: '个人' },
    { key: 'team',       label: '团队' },
    { key: 'enterprise', label: '企业' },
  ]

  export const MODEL_CATALOG = [
    { model_name: 'deepseek-ai/deepseek-v4-pro',   label: 'DeepSeek V4 Pro',   tier: '高准确度 · 慢', context: '128K' },
    { model_name: 'deepseek-ai/deepseek-v4-flash', label: 'DeepSeek V4 Flash', tier: '快速响应',      context: '64K' },
  ]
  ```
- **测试**: 无（纯数据，由页面测试覆盖）
- **验证**: `import { PLAN_CATALOG } from './data/plans.js'` 无报错
- **依赖**: 无（可与任务 1-6 并行）

---

### 任务 8: 前端 — PricingPage 改为消费 PLAN_CATALOG (~3 min)

- **描述**: 修改 `PricingPage.vue` 团队/企业区，从硬编码改为消费 `PLAN_CATALOG` 中的 team/enterprise 数据。个人区保持当前 3 张子方案卡（月度/年度/季度）不变。
- **文件**:
  - 修改 `frontend/src/pages/PricingPage.vue`
- **具体操作**:
  1. 导入 `PLAN_CATALOG` from `../data/plans.js`
  2. 团队 tab 区域：从 `PLAN_CATALOG.team` 读取 label/features 生成内容卡片
  3. 企业 tab 区域：从 `PLAN_CATALOG.enterprise` 读取 label/features
  4. 个人区保留当前硬编码的 3 张月/年/季卡片不变（它们是 personal category 内的子方案，不属于 PLAN_CATALOG 直接映射）
- **测试**: 手动验证 `/pricing` 页面团队/企业区显示正确
- **验证**: `npm run dev` 后访问 `/pricing`，团队 tab 显示"团队版 ¥299/月"及 features
- **依赖**: 任务 7

---

### 任务 9: 后端测试 — 扩展 test_settings_api.py (~5 min)

- **描述**: 新增 9 个后端测试，覆盖默认订阅 free、username 唯一性冲突、model_name 持久化、overview 返回 model_* 字段、subscription_plan 切换、legacy 迁移。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **具体操作**（新增测试函数）:
  1. `test_default_subscription_is_free` — 注册新用户，overview 返回 `subscription_plan='free'`，`monthly_quota=50`
  2. `test_overview_includes_model_env` — overview 响应含 `model_name/model_base_url/model_api_key_preview/model_catalog/subscription_label/subscription_period/subscription_price`
  3. `test_update_profile_username` — 改名成功，overview 确认新 username
  4. `test_update_profile_username_unique_conflict` — 改为已存在用户名，期望 409
  5. `test_update_profile_invalid_username` — 含特殊字符（如空格/中文），期望 422
  6. `test_update_profile_subscription_plan` — 切到 `team`，期望 `subscription_plan='team'`，`monthly_quota=3000`
  7. `test_update_profile_model_name` — 切到 `deepseek-ai/deepseek-v4-pro`，期望持久化 + 二次查 overview 仍是该值
  8. `test_update_profile_model_name_invalid` — 传 `gpt-4o`，期望 422
  9. `test_get_api_key_secret_updates_last_viewed_at` — 创建 key → 调 secret 端点 → 期望 `last_viewed_at` 不为 None
- **验证**: `uv run pytest tests/test_settings_api.py -v` 全部通过
- **依赖**: 任务 3（路由逻辑完成）

---

### 任务 10: 前端 — SettingsPage 账单 tab 重构 (~5 min)

- **描述**: 重构账单 tab，使用 `PLAN_CATALOG` + `PLAN_CATEGORY_TABS` 渲染 category tab 行和方案卡 grid，支持切换订阅方案。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **具体操作**:
  1. 导入 `PLAN_CATALOG`, `PLAN_CATEGORY_TABS` from `../data/plans.js`
  2. 删除本地 `plans` 硬编码数组（行 43-48）
  3. 新增 `billingCategoryTab` ref（默认 `'personal'`）
  4. 新增 `billingPlans` computed：根据 `billingCategoryTab` 筛选 `PLAN_CATALOG` 中 `category` 匹配的方案
  5. 模板重构：
     - 账单徽章：使用 `profile.subscription_label/subscription_price/subscription_period`
     - 3 个 category tab 按钮（个人/团队/企业）
     - 方案 grid：`v-for` 渲染当前 category 的方案卡
     - 切方案按钮：调用 `updateProfile({ subscription_plan })`，成功后刷新本地 `profile`
  6. 修改 `loadSettings()` 中 `profileForm` 初始化，适配新的 `ProfileResponse` 字段
- **测试**: 手动验证账单 tab 3 个 category 切换正常，切订阅后徽章更新
- **验证**: `npm run dev` 后登录 → 设置 → 账单 tab → 切换 category → 点击"切换到此方案"
- **依赖**: 任务 7, 任务 9（后端接口就绪）

---

### 任务 11: 前端 — SettingsPage AI 模型 tab 重构（大卡片 + 数据脱敏 + API Key） (~5 min)

- **描述**: 重构 AI 模型 tab：顶部 2 张大卡片（从 `model_catalog` 渲染）、副信息条、数据脱敏 checkbox、API Key 列表+创建+显示/隐藏/复制状态机。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **具体操作**:
  1. 导入 `MODEL_CATALOG` from `../data/plans.js`，导入 `listApiKeys, createApiKey, getApiKeySecret, revokeApiKey` from `settingsApi.js`
  2. 新增 ref：
     - `apiKeys = ref([])`
     - `secretCache = ref({})` — `{ [keyId]: fullKey }`
     - `confirmingKeyId = ref(null)`
     - `confirmAction = ref(null)` — `'reveal' | 'copy'`
     - `showApiKeyForm = ref(false)`
     - `apiKeyForm = ref({ name: '', client_type: 'agent', scope_template: 'read_only', scopes: null })`
     - `newlyCreatedKey = ref(null)` — 创建后一次性 full_key 展示
  3. 新增 `loadApiKeys()` 函数（挂载时或切到模型 tab 时调用）
  4. 新增 `handleEyeClick(keyId)` / `handleCopyClick(keyId)` / `confirmReveal()` 函数（按设计文档状态机）
  5. 新增 `handleCreateApiKey()` / `handleRevokeApiKey(keyId)` 函数
  6. 新增 `selectModel(modelName)` — 调用 `updateProfile({ model_name: modelName })`，成功后 toast + 刷新 profile
  7. 删除旧的 `modelForm` ref 和 `saveModelPreferences` 函数
  8. 模板重构：
     - `.model-card-grid` 2 列布局渲染 MODEL_CATALOG
     - 选中态：`profile.model_name === card.model_name` 时金色边框 + ✓
     - 副信息条：显示 `profile.model_base_url` + `profile.model_api_key_preview`
     - 数据脱敏 checkbox：绑定 `profileForm.burn_after_read`
     - "开发者 API Key" section：列表 + 创建表单 + 确认弹窗 + 一次性 key 展示
  9. `loadSettings()` 中同步 `modelForm.model_name` 为 `profile.model_name`
- **测试**: 手动验证模型卡片渲染、选中态切换、API Key 显示/隐藏/复制流程
- **验证**: AI 模型 tab 显示 2 张卡片，点击切换后持久化，API Key 列表加载正常
- **依赖**: 任务 10（同一文件，顺序编辑）

---

### 任务 12: 前端 — SettingsPage 身份与绑定 tab 重构（只读/编辑态切换） (~4 min)

- **描述**: 重构身份与绑定 tab 为默认只读态 + 点击"编辑"进入可编辑态，支持修改 `username` 和 `display_name`，移除"数据安全锁"中的 `burn_after_read` toggle。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **具体操作**:
  1. 新增 ref：`editingIdentity = ref(false)`
  2. 新增 `identityForm = ref({ username: '', display_name: '' })` — 进入编辑态时从 profile 复制
  3. 新增 `startEditingIdentity()` / `cancelEditingIdentity()` / `saveIdentity()` 函数
  4. `saveIdentity()` — 调用 `updateProfile({ username, display_name, wechat_bound, alipay_bound, burn_after_read })`，成功后：
     - `editingIdentity = false`
     - 调用 `loadSettings()` 刷新
     - 更新 `useAuth().currentUser` 的 username（同步 `sessionStorage`）
     - 409 错误 → toast "用户名已被占用"
  5. 模板重构：
     - 只读态：用户名/显示名称 `readonly input`，右上角"编辑"按钮
     - 编辑态：可编辑 input，底部"保存"+"取消"按钮组
  6. 修改"数据安全锁"卡片：
     - 移除 `burn_after_read` toggle
     - 保留卡片结构，仅展示说明文字（"激活后，所有会话结束立即清除内存残留痕迹..."）
  7. `loadSettings()` 中初始化 `identityForm`
- **测试**: 手动验证只读/编辑态切换、用户名修改成功/冲突处理
- **验证**: 身份 tab 默认只读，点"编辑"进入可编辑，保存后回到只读，刷新 localStorage
- **依赖**: 任务 11（同一文件，顺序编辑）

---

### 任务 13: 前端 — SettingsPage settingsApi 补充 revokeApiKey 导入 (~1 min)

- **描述**: 确保 `SettingsPage.vue` 中已导入所有需要的 API 函数。检查 `settingsApi.js` 中 `revokeApiKey` 已存在（行 88-92 确认存在），无需新增后端接口。
- **文件**: 无修改（`settingsApi.js` 已有全部所需函数）
- **验证**: 确认 `settingsApi.js` 导出 `listApiKeys/createApiKey/getApiKeySecret/revokeApiKey`
- **依赖**: 无

---

### 任务 14: 前端样式 — 新增模型卡片 + 账单 category tab + API Key 确认弹窗样式 (~4 min)

- **描述**: 在 `SettingsPage.vue` 的 `<style scoped>` 中新增模型卡片 grid、category tab、API Key 确认弹窗的 CSS。在 `style.css` 浅色主题块中补充适配。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue` → `<style scoped>`
  - 修改 `frontend/src/style.css` → 浅色主题 `[data-theme="light"]` 块
- **具体操作**:
  1. `SettingsPage.vue` style 新增：
     - `.model-card-grid`：`display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;`
     - `.model-card`：`border: 1px solid #353534; padding: 20px; cursor: pointer; transition: ...`
     - `.model-card.selected`：`border-color: #d4af37; background: linear-gradient(...); box-shadow: ...`（金色边框 + 发光）
     - `.model-card .model-check`：右上角 ✓ 图标（金色）
     - `.plan-category-tabs`：flex 布局，小号 tab 按钮
     - `.confirm-dialog-overlay` + `.confirm-dialog`：模态弹窗样式
     - `.model-info-bar`：副信息条样式
  2. `style.css` 浅色主题新增：
     - `[data-theme="light"] .model-card` / `.model-card.selected` 反色适配
     - `[data-theme="light"] .plan-category-tabs button` 适配
     - `[data-theme="light"] .confirm-dialog` 适配
- **验证**: 浅色/深色主题切换后，模型卡片、账单 tab、确认弹窗显示正常
- **依赖**: 任务 11（模板结构完成后才能加样式）

---

### 任务 15: 后端测试 — 更新 test_settings_overview_defaults 适配 free 默认值 (~2 min)

- **描述**: 修改现有 `test_settings_overview_defaults` 测试（行 110-111），将期望值从 `personal/500` 改为 `free/50`。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py` → `test_settings_overview_defaults`
- **具体操作**:
  1. 行 110：`assert data["profile"]["subscription_plan"] == "free"`（原 `"personal"`）
  2. 行 111：`assert data["profile"]["monthly_quota"] == 50`（原 `500`）
- **验证**: `uv run pytest tests/test_settings_api.py::test_settings_overview_defaults -v` 通过
- **依赖**: 任务 2（`_get_or_create_profile` 默认值已改为 `free`）

---

### 任务 16: 端到端验证 (~5 min)

- **描述**: 启动前后端，登录 `geats` 账号，逐个 tab 走查所有功能点。
- **验证清单**:
  - [ ] 新注册用户 `subscription_plan='free'`，`monthly_quota=50`
  - [ ] 账单 tab：free 徽章显示"免费体验 ¥0 永久"；3 个 category tab 可切换；切到 personal 方案后徽章更新
  - [ ] AI 模型 tab：2 张大卡片渲染；选中态金色边框；点击切换后 toast + 持久化（刷新后仍为选中值）
  - [ ] 副信息条显示 base_url + api_key 后 4 位
  - [ ] 数据脱敏 checkbox 绑定正确
  - [ ] API Key 列表加载；眼睛图标二次确认 → 显示完整 key；再次点击本地隐藏；复制按钮已加载时直接复制，未加载时二次确认
  - [ ] 创建 API Key → 一次性 full_key 展示 + 复制按钮
  - [ ] 身份 tab 默认只读，"编辑"进入可编辑；修改 username 成功保存；冲突用户名 → 409 提示
  - [ ] "数据安全锁"卡片仅显示说明，无 toggle
  - [ ] 浅色/深色主题切换正常
  - [ ] `/pricing` 页面团队/企业区数据来自 PLAN_CATALOG
  - [ ] 所有后端测试通过：`uv run pytest tests/test_settings_api.py -v`
- **依赖**: 任务 1-15 全部完成

## 并行机会

- **任务 1-3（后端路由）** 与 **任务 5-6（alembic 迁移）** 与 **任务 7-8（前端共享数据）** 可并行
- **任务 4** 无需修改，仅确认（0 min）
- **任务 9（后端测试）** 必须等任务 3 完成
- **任务 10-12（前端页面重构）** 必须顺序执行（同一文件，每步递增）
- **任务 14（样式）** 等任务 11 完成后可做
- **任务 15（修改现有测试）** 等任务 2 完成

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据迁移 009 误改已使用额度的 personal 用户 | 低 | 高 | WHERE 条件严格限定 `quota_used=0`；提供手动回滚脚本 |
| 用户名修改后旧 token 的 username 不同步 | 中 | 中 | 修改后刷新 `sessionStorage` + `currentUser` ref；token payload 中不含 username 无风险 |
| model_name 切换但后端实际推理仍用 env 值 | 确定 | 低 | 设计文档已确认为已知行为，用户偏好先持久化，后续 inspection 路由接入 |
| 前端 SettingsPage.vue 单文件过大（~1400行→~1800行） | 中 | 低 | 当前 MVP 阶段可接受；后续可拆分 tab 为子组件 |
| 浅色主题样式遗漏 | 中 | 低 | 任务 16 端到端走查时双主题验证 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 后端单元/集成测试 | `test_settings_api.py` 新增 9 个 + 修改 1 个 | 默认值 free、username 唯一性、model_name 持久化、subscription_plan 切换、overview 字段完整、api_key last_viewed_at |
| 前端手动验证 | 逐 tab 走查（任务 16） | 账单切换、模型卡片、身份编辑、API Key 显示/隐藏/复制全流程 |
| 端到端 | 启动前后端完整走查 | 双主题、数据持久化、跨 tab 状态一致性 |
