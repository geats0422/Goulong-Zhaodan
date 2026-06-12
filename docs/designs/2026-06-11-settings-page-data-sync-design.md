# 设置中枢数据同步与 UI 重构 — 设计文档

> 范围：`frontend/src/pages/SettingsPage.vue` + `backend/routers/settings.py` + `backend/core/config.py` + `frontend/src/pages/PricingPage.vue`
> 日期：2026-06-11
> 类型：前端 UI 重构 + 后端默认值调整 + 接口小幅扩展

## 目标

修复设置中枢 3 类与数据库/env 不同步的问题：

1. **账单与订阅管理**：默认订阅从 `personal` 改为 `free`（新用户体验套餐），订阅 tab 与 `/pricing` 共享 plans 数据。
2. **AI 模型与偏好**：把下拉选择改为 2 张大卡片（`deepseek-v4-pro` / `deepseek-v4-flash`），底部放数据脱敏，再下方加 API Key 列表+创建（用户自建 API Key，给 Agent/MCP/CLI 调用）。
3. **身份与绑定**：默认显示态只读，点击右上"编辑"进入可编辑态，支持修改 username 和 display_name；密码修改块保留在同区域。

## 关键决策（已与用户确认）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 订阅 tab 数据源 | 复用 PricingPage 共享配置 | 单一来源 |
| 模型卡片样式 | 大卡片平铺 | 与 MarketingHero / 套餐卡片视觉一致 |
| 用户名编辑后端 | 扩展 `updateProfile` 加 `username` 字段 | 不增新接口，复用一致性检查 |
| API Key 语义 | 用户自建 API Key（用于 Agent/MCP/CLI） | 与现有 `/settings/api-keys` 接口对齐 |
| 模型选择与 env 同步 | 前端从 `getSettingsOverview` 读 `model_name/model_base_url/model_api_key`，选中态由 `model_name` 决定 | 单次拉取，无新接口 |
| 模型选择持久化 | **是** — alembic 010 加 `user_profiles.model_name`，`updateProfile` 支持 | 用户确认 |
| 数据脱敏 toggle 位置 | **从"数据安全锁"移除**，移到 AI 模型 tab 卡片下方；`burn_after_read` 字段保留兼容 | 用户确认 |

## 数据模型

### 后端

#### `UserProfile` 字段扩展（alembic 010 迁移）

新增 1 列：

```python
# alembic 010: 010_add_user_profile_model_name.py
def upgrade():
    op.add_column(
        "user_profiles",
        sa.Column("model_name", sa.String(120), nullable=True),
    )
    # 历史用户默认值 = 当前 env MODEL_NAME
    bind = op.get_bind()
    from core.config import settings
    bind.execute(
        sa.text("UPDATE user_profiles SET model_name = :n WHERE model_name IS NULL"),
        {"n": settings.model_name},
    )
```

模型字段：

```python
class UserProfile(Base):
    # ... 既有字段 ...
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
```

`Settings` 已有逻辑层枚举映射：

```python
PLAN_CATALOG = {
    "free":       {"label": "免费体验",   "monthly_quota": 50,    "features": [...]},
    "personal":   {"label": "个人版",     "monthly_quota": 500,   "features": [...]},
    "team":       {"label": "团队版",     "monthly_quota": 3000,  "features": [...]},
    "enterprise": {"label": "企业定制",   "monthly_quota": None,  "features": [...]},
}
```

`_get_or_create_profile` 默认值变更：

```python
profile = UserProfile(
    user_id=db_user.id,
    display_name=db_user.username,
    subscription_plan="free",      # 旧值 "personal"
    monthly_quota=50,              # 旧值 500
    quota_used=0,
    ...
)
```

新增 settings overview 字段：

```python
class ProfileResponse(BaseModel):
    # ... 既有字段 ...
    subscription_label: str       # 中文标签（"免费体验"/"个人版"/...）
    subscription_period: str      # "/月" / "/年" / "按合同"
    subscription_price: str       # "¥0" / "¥39" / "议价"
    model_name: str               # 来自 UserProfile.model_name（fallback settings.model_name）
    model_base_url: str           # 来自 settings.model_base_url（脱敏展示用，完整值在 KEY section）
    model_api_key_preview: str    # "nvapi-****-****-xxxx"，仅显示后 4 位
    model_catalog: list[dict]     # 全部可选模型（[{model_name, label, tier, context}]）
```

`ProfileUpdateRequest` 扩展：

```python
class ProfileUpdateRequest(BaseModel):
    username: str | None = None   # 新增：唯一性校验，3-50 字符
    display_name: str | None = None
    wechat_bound: bool | None = None
    alipay_bound: bool | None = None
    burn_after_read: bool | None = None
    subscription_plan: str | None = None   # 新增：可选值 free/personal/team/enterprise
    model_name: str | None = None          # 新增：仅允许 MODEL_CATALOG 中的 model_name

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not 3 <= len(value) <= 50 or not re.match(r"^[A-Za-z0-9_.-]+$", value):
            raise ValueError("用户名须 3-50 字符，仅含字母/数字/_.-")
        return value

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {m["model_name"] for m in MODEL_CATALOG}
        if value not in allowed:
            raise ValueError("model_name 必须在 MODEL_CATALOG 中")
        return value
```

新增 `MODEL_CATALOG`（与前端硬编码的 2 张卡片严格一致）：

```python
MODEL_CATALOG = [
    {"model_name": "deepseek-ai/deepseek-v4-pro",   "label": "DeepSeek V4 Pro",   "tier": "高准确度 · 慢",    "context": "128K"},
    {"model_name": "deepseek-ai/deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tier": "快速响应",         "context": "64K"},
]
```

`update_profile` 路由：
- `username`：查询唯一性冲突 → 409；更新 `User.username` 与 `UserProfile.display_name`（如未显式修改 display_name）。
- `subscription_plan`：校验在 `PLAN_CATALOG` 内；更新 `UserProfile.subscription_plan` 和 `monthly_quota`。
- `model_name`：写入 `UserProfile.model_name`，前端 `modelForm.model_name` 同步。

#### `/settings/overview` 注入 env 信息

`_profile_response` 注入 model_* 字段：

```python
def _profile_response(db_user: User, profile: UserProfile) -> ProfileResponse:
    key = settings.model_api_key
    preview = f"****-****-{key[-4:]}" if len(key) >= 4 else "****"
    plan = PLAN_CATALOG.get(profile.subscription_plan, PLAN_CATALOG["free"])
    effective_model = profile.model_name or settings.model_name
    return ProfileResponse(
        username=db_user.username,
        display_name=profile.display_name,
        subscription_plan=profile.subscription_plan,
        subscription_label=plan["label"],
        subscription_period=plan["period"],
        subscription_price=plan["price"],
        monthly_quota=profile.monthly_quota or plan["monthly_quota"],
        quota_used=profile.quota_used,
        wechat_bound=profile.wechat_bound,
        alipay_bound=profile.alipay_bound,
        burn_after_read=profile.burn_after_read,
        model_name=effective_model,
        model_base_url=settings.model_base_url,
        model_api_key_preview=preview,
        model_catalog=MODEL_CATALOG,
    )
```

#### 数据迁移

对历史 `subscription_plan='personal'` 且 `quota_used=0` 的账号，回滚到 `free`：

```sql
UPDATE user_profiles
SET subscription_plan='free', monthly_quota=50
WHERE subscription_plan='personal' AND quota_used=0;
```

放到 alembic migration 009，或一次性脚本（`backend/scripts/migrate_default_to_free.py`）。

## 接口设计

### 后端改动

| 端点 | 改动 |
|------|------|
| `GET /settings/overview` | 响应新增 `subscription_label/period/price/model_name/model_base_url/model_api_key_preview` |
| `PATCH /settings/profile` | 请求支持 `username` / `subscription_plan`；唯一性冲突返回 409 |
| `_get_or_create_profile` | 默认值改为 `free` |

### 前端改动

#### `frontend/src/data/plans.js`（新增，plans 配置共享源）

```js
export const PLAN_CATALOG = {
  free:       { key: 'free',       label: '免费体验', price: '¥0',    period: '永久',  quota: 50,    category: 'personal',   features: ['基础智能审查', '单文件上传', 'Markdown 报告'] },
  personal:   { key: 'personal',   label: '个人版',   price: '¥39',   period: '/月',   quota: 500,   category: 'personal',   features: ['多文件材料包', '私域红线标准', '本地脱敏', '阅后即焚'] },
  team:       { key: 'team',       label: '团队版',   price: '¥299',  period: '/月',   quota: 3000,  category: 'team',       features: ['团队协作', '审计留痕', '自定义红线', '优先支持'] },
  enterprise: { key: 'enterprise', label: '企业定制', price: '议价', period: '按合同', quota: '不限', category: 'enterprise', features: ['私有化部署', 'SSO 单点登录', 'SLA 保障', '专属客户成功'] },
}

export const PLAN_CATEGORY_TABS = [
  { key: 'personal',   label: '个人' },
  { key: 'team',       label: '团队' },
  { key: 'enterprise', label: '企业' },
]
```

`PricingPage.vue` 改为消费 `PLAN_CATALOG`：当前硬编码的 4 张卡片（`#pricing` 个人区是月度/年度/季度子方案）属于"个人 category"内的子方案，**保留**；团队/企业区改为从 catalog 读对应 category 的方案卡。

设置页账单 tab：从 `profile.subscription_plan` 定位当前方案，并按 `PLAN_CATEGORY_TABS` 切换显示不同 category 的方案卡。**只读展示** + 切方案按钮 → 调用 `updateProfile({ subscription_plan })`。

#### `SettingsPage.vue` 改动

**账单 tab**：
- 当前方案徽章：`profile.subscription_label` + `profile.subscription_price` + `profile.subscription_period`。
- tab 行：3 个 category tab（个人/团队/企业），默认按 `PLAN_CATEGORY_TABS[0]`。
- 方案卡 grid：显示当前 category 的所有方案（个人 category 含 free + personal；团队含 team；企业含 enterprise）。
- 切方案：POST `updateProfile({ subscription_plan })`，成功后刷新本地 `profile`。

**AI 模型 tab**：
- 顶部 2 张大卡片（grid 2 列）：
  - `deepseek-ai/deepseek-v4-pro`：描述"高准确度 · 慢"
  - `deepseek-ai/deepseek-v4-flash`：描述"快速响应"
  - 选中态：`model_name` 与卡片 model_name 匹配时金色边框 + ✓ 标识。
  - 点击调用后端 `/settings/model-preference` 持久化？**不**——用户没要求持久化，点击只是更新本地 + 显示提示"已选择"（不写库）。若要持久化，扩展 `UserProfile.model_name` 字段。**简化版：仅本地显示态切换**。
- 卡片下方：副信息条"当前服务端：{{ model_base_url }} · API Key: {{ model_api_key_preview }}"（只读）。
- 数据脱敏 checkbox：放在副信息条下方，绑定 `profileForm.burn_after_read`（复用"阅后即焚"语义——用户语义上"数据脱敏"对应后端"burn_after_read"）。
- **API Key 列表 section**：
  - 标题"开发者 API Key"（副标题"用于 Agent / MCP / CLI 调用"）。
  - 列表渲染 `apiKeys` 数组（行：name + prefix + status + 创建时间 + 操作按钮"查看 secret / 撤销"）。
  - 顶部"创建 API Key"按钮 → 展开表单：name、client_type (select)、scope_template (select)、可选 scopes、提交后展示一次性 full_key 提示复制。

**身份与绑定 tab**：
- 默认显示态：
  - 卡片右上"编辑"按钮。
  - 用户名 + 显示名称都只读 input。
  - 第三方绑定 chips（保留）。
- 点击"编辑"：
  - 用户名变可编辑 input。
  - 显示名称变可编辑 input。
  - "保存"+"取消"按钮组。
  - 保存：PATCH `/settings/profile` 传 `{username, display_name, wechat_bound, alipay_bound, burn_after_read}`。成功后切换回只读态，刷新 localStorage user。
- "修改密码"卡片：保留在身份与绑定**下方**（紧邻），而非"数据安全锁"上方。当前结构已是这样（行 224-231），不动位置。
- "数据安全锁"卡片：保持原位置（行 233-248），但其中"阅后即焚模式"开关语义改为"数据脱敏"，label 改为"启用数据脱敏（身份证 / 手机号 / 银行卡 / 金额）"——这与用户描述"数据脱敏在模型选择下方"**冲突**。

⚠️ **澄清点**：用户说"数据脱敏在模型选择下方"——指 AI 模型 tab 内的"模型卡片下方"，还是"身份与绑定 tab 内"？从上下文看，应是 **AI 模型 tab 内**（即模型卡片下方），与"数据安全锁"分离。我将：
- 移除 `burn_after_read` toggle from "数据安全锁"卡片。
- 在 AI 模型 tab 卡片下方新增 `enable_data_masking` 复选框。
- `burn_after_read` 字段在 Pydantic 模型中保留（不删），后端 `update_profile` 仍支持。
- UserProfile 表字段保持不变（数据库 schema 无改动）。

**用户名 input 行为**：
- 唯一性冲突 409 → 提示"用户名已被占用"。
- 用户名变更后，刷新本地 `useAuth().currentUser`（`sessionStorage` 同步）。

## UI/UX 状态机

### 身份与绑定卡片

```
[只读态]                   [编辑态]
用户名  [geats      ]      用户名  [geats____]
显示名  [geats      ]      显示名  [geats____]
[第三方绑定 chips]          [第三方绑定 chips]

[编辑]                      [保存] [取消]
```

切换：本地 ref `editingIdentity: boolean`。
保存成功后 `editingIdentity = false` 并 reload `loadSettings()`。

### 模型卡片

```
┌─────────────────────────────┐ ┌─────────────────────────────┐
│ ✓ deepseek-ai/deepseek-v4-pro│ │   deepseek-ai/deepseek-v4-flash│
│ 高准确度 · 慢                │ │   快速响应                   │
│ 上下文: 128K                 │ │   上下文: 64K                │
└─────────────────────────────┘ └─────────────────────────────┘
当前服务端：https://integrate.api.nvidia.com/v1
API Key：nvapi-****-****-xxxx
[✓] 启用数据脱敏（身份证 / 手机号 / 银行卡 / 金额）
```

✓ 仅当前 `model_name` 匹配的卡片显示。点击另一张 → 立即调用 `PATCH /settings/profile` 传 `{model_name}` 持久化，成功后视觉切换 + 顶部 toast"已切换至 XXX"。

### API Key 列表行（显示/隐藏/复制 状态机）

```
                       未加载完整 Key              已加载完整 Key
显示（默认）  glzd_live_ab12••••wxyz       glzd_live_ab12XXXXXXXXwxyz
              [👁 眼睛]  [📋 复制]           [👁 眼睛（已睁开）]  [📋 复制]
```

**交互流程**（由用户确认）：

1. 列表默认显示脱敏 Key：`glzd_live_ab12••••wxyz`（使用后端响应中的 `key_prefix` 拼接 `last4`）。
2. 点击眼睛图标 → 弹出二次确认对话框：「显示完整密钥存在泄露风险，确认显示？」。
3. 用户确认 → 调用 `GET /settings/api-keys/{id}/secret`，当前行显示完整 Key。
4. 再次点击眼睛图标 → **仅前端本地隐藏**（清除 local 缓存），不需要重新请求。
5. 点击复制图标：
   - 如果当前行**已加载完整 Key**（`secretCache[id]` 存在）→ 直接 `navigator.clipboard.writeText(secretCache[id])`，toast "已复制"。
   - 如果**尚未加载完整 Key** → 弹出同样的二次确认 → 用户确认后调用 `GET /settings/api-keys/{id}/secret` → 自动复制 + 显示完整 Key。
6. 每次后端返回完整 Key 时**后端自动更新 `last_viewed_at`**（在 `get_api_key_secret` 服务函数里 `update last_viewed_at = now()`）；前端无需关心。

**前端状态**（`SettingsPage.vue` 中）：

```js
const secretCache = ref({})        // { [keyId]: fullKey }
const confirmingKeyId = ref(null)  // 当前弹确认的 key
const confirmAction = ref(null)    // 'reveal' | 'copy'

async function handleEyeClick(keyId) {
  if (secretCache.value[keyId]) {
    // 已加载 → 本地隐藏
    delete secretCache.value[keyId]
    return
  }
  // 未加载 → 弹确认 → 加载
  confirmAction.value = 'reveal'
  confirmingKeyId.value = keyId
}

async function handleCopyClick(keyId) {
  if (secretCache.value[keyId]) {
    await copyToClipboard(secretCache.value[keyId])
    return
  }
  confirmAction.value = 'copy'
  confirmingKeyId.value = keyId
}

async function confirmReveal() {
  const id = confirmingKeyId.value
  const action = confirmAction.value
  confirmingKeyId.value = null
  confirmAction.value = null
  const fullKey = await getApiKeySecret(id)
  secretCache.value[id] = fullKey
  if (action === 'copy') {
    await copyToClipboard(fullKey)
  }
}
```

**样式**：眼睛图标用 Material Symbols `visibility` / `visibility_off`；复制用 `content_copy`。操作按钮使用 `apikey-icon-btn`（已有样式，行 1068）。

**创建后的一次性显示**：新建 API Key 时，后端响应包含 `full_key`。前端展示在 `apikey-new-key` 区块（已有样式，行 966），并提示"请立即复制，关闭后无法再次查看完整 Key"。

**接口要求**：`GET /settings/api-keys/{key_id}/secret` 路由已在 `routers/settings.py:487` 存在；后端需在 `services/api_key_service.get_api_key_secret` 内更新 `last_viewed_at = datetime.utcnow()`。

## 错误处理

| 场景 | 处理 |
|------|------|
| 用户名冲突 (409) | toast 红色"用户名已被占用" |
| 切订阅失败 (400/500) | toast 红色，恢复原 plan，禁用按钮短暂时间防双击 |
| 订阅 plan 不在 catalog | 后端 422（Pydantic validator） |
| API Key 创建失败 (400) | 表单顶部 toast，保留已输入数据 |
| API Key 撤销失败 (404) | toast "Key 不存在或已撤销"，刷新列表 |

## 测试策略

- 后端：扩展 `test_settings_api.py`：
  - `test_default_subscription_is_free` — 新建用户查 overview，期望 `subscription_plan='free'`。
  - `test_update_profile_username_unique_conflict` — 改名为已存在用户名，期望 409。
  - `test_update_profile_invalid_username` — 含特殊字符，期望 422。
  - `test_overview_includes_model_env` — 期望响应含 `model_name/model_base_url/model_api_key_preview/model_catalog`。
  - `test_update_profile_subscription_plan` — 切换到 team，期望 `subscription_plan='team'`，`monthly_quota=3000`。
  - `test_update_profile_model_name` — 切换到 deepseek-v4-pro，期望持久化 + 二次查 overview 仍是该值。
  - `test_update_profile_model_name_invalid` — 传 `gpt-4o`，期望 422（Pydantic validator）。
  - `test_migration_legacy_personal_to_free` — 脚本测试：构造 quota_used=0 的 personal profile，运行迁移脚本，期望变为 free/50。
  - `test_get_api_key_secret_updates_last_viewed_at` — 创建 key → 调用 secret 端点 → 期望 `last_viewed_at` 被更新。

- 前端：扩展 `test_settings.spec.js`（如不存在则新建）：
  - 账单 tab 默认显示 free 套餐。
  - 切订阅成功/失败提示。
  - AI 模型 tab 2 张卡片渲染，选中态由 `model_name` 决定。
  - 点击模型卡片 → 调 updateProfile，loading 状态。
  - 身份与绑定默认只读，"编辑"进入可编辑态，保存后回到只读。
  - 用户名冲突 409 提示。
  - **API Key 显示/隐藏流程**：
    - 列表默认脱敏。
    - 点击眼睛 → 弹确认 → 确认后调 secret 端点 + 显示完整。
    - 再次点击眼睛 → 本地隐藏，无网络请求。
    - 点击复制（已加载）→ 复制，无网络请求。
    - 点击复制（未加载）→ 弹确认 → 调 secret + 自动复制。
  - 创建 API Key → 展示一次性 full_key 区块。
  - AI 模型 tab 显示 2 张卡片。
  - 点击"编辑"进入编辑态，"保存"后回到只读态。
  - 模型卡片点击切换选中态。

## 风险与权衡

- **数据迁移**：历史 personal 用户的 `quota_used=0` 会被自动回退到 free。如用户已使用部分额度（quota_used>0），保留其 personal。提供手动脚本可强制转换。
- **用户名变更**：影响登录。修改后旧用户名无法登录，前端在保存确认对话框中提示。
- **模型 env API Key 仅展示**：用户要求显示模型 base_url/apikey 在设置页，这是 env 注入，不可由用户修改。副信息条文案："API Key 由服务端环境变量配置，不可在此修改；切换下方模型卡片仅影响用户偏好，env 不变。"
- **模型偏好与 env 解耦**：`UserProfile.model_name` 是用户偏好，`settings.model_name`（env）是服务端默认值。如用户选了 deepseek-v4-pro，但后端实际仍按 env 调模型——这是已知行为，留待后续 inspection 路由读取 `user_profile.model_name` 时再接入。
- **API Key 完整值仅一次返回**：创建时后端响应含 `full_key`；查看时后端响应含 `full_key` 并更新 `last_viewed_at`。前端 secret 缓存在内存，不写入 localStorage（防止泄露）。

## 不在范围内

- 第三方登录（微信/支付宝）真实 OAuth 流程（仅保留 chips 切换，不做真实绑定）。
- 新增 billing / payment 接口。
- 团队/企业的邀请码/成员管理。

## 实施任务

1. **后端**：
   1.1 `models/knowledge.py` `UserProfile` 加 `model_name` 字段（`String(120), nullable=True`）。
   1.2 `routers/settings.py`：
       - 新增 `PLAN_CATALOG` 与 `MODEL_CATALOG` 常量。
       - 扩展 `ProfileResponse`（`subscription_label/period/price/model_name/model_base_url/model_api_key_preview/model_catalog`）。
       - 扩展 `ProfileUpdateRequest`（`username/subscription_plan/model_name` + validators）。
       - `_get_or_create_profile` 默认值改为 `free`。
       - `update_profile` 路由处理 `username` 唯一性 + `model_name` 持久化。
       - `_profile_response` 注入 `effective_model = profile.model_name or settings.model_name` 与 `model_catalog`。
   1.3 `services/api_key_service.py` `get_api_key_secret` 内部更新 `last_viewed_at = now()`。
2. **alembic 迁移**：
   2.1 `009_legacy_personal_to_free.py`：将 `subscription_plan='personal' AND quota_used=0` 的 profile 回退到 `free`/`monthly_quota=50`。
   2.2 `010_add_user_profile_model_name.py`：加 `model_name` 列，默认值取 `settings.model_name`。
3. **前端共享数据**：
   3.1 新建 `frontend/src/data/plans.js`（导出 `PLAN_CATALOG`、`PLAN_CATEGORY_TABS`、`MODEL_CATALOG`）。
   3.2 `PricingPage.vue` 改为消费 `PLAN_CATALOG`（团队/企业区）。
4. **`SettingsPage.vue` 全面重构**：
   4.1 账单 tab：3 category tab + 方案 grid，绑定 `updateProfile({subscription_plan})`。
   4.2 AI 模型 tab：2 张大卡片（消费 `model_catalog`）+ 副信息条 + 数据脱敏 + API Key 列表/创建/显示隐藏/复制。
   4.3 身份与绑定 tab：默认只读 + 编辑态切换，支持修改 `username` + `display_name`，移除原"数据安全锁"中的脱敏 toggle。
   4.4 API Key 行：实现"显示/隐藏/复制"状态机（眼睛 + 复制按钮 + 二次确认弹窗）。
5. **样式**：
   5.1 新增 `.model-card-grid`、`.model-card`、`.model-card.selected`、`.plan-category-tabs`、`.api-key-row`、`.confirm-dialog`。
   5.2 浅色主题适配（在 `style.css` 末尾 `[data-theme="light"]` 块补充）。
6. **测试**：
   6.1 后端 `test_settings_api.py` 新增 7 个测试 + `test_api_key_service.py` 加 `last_viewed_at` 测试。
   6.2 前端 `test_settings.spec.js`（如无则新建）覆盖：账单切换、模型切换、身份编辑、API Key 显示/隐藏/复制全流程。
7. **端到端验证**：启动前后端，登录 `geats`，逐个 tab 走查，截图。

## 验收标准

- 新注册用户 `subscription_plan='free'`, `monthly_quota=50`。
- 历史 personal 且 quota_used=0 的用户被回退到 free/50（alembic 009）。
- `UserProfile.model_name` 列存在（alembic 010）；新用户默认取 `settings.model_name`。
- 账单 tab 默认显示 free 套餐徽章；3 个 category tab 可切换；切订阅生效。
- AI 模型 tab 显示 2 张卡片（来自 `model_catalog`），选中态由 `model_name` 决定；点击切换调 `updateProfile` 持久化；副信息条展示当前 baseurl + apikey 后 4 位；数据脱敏 checkbox 绑定 `burn_after_read`。
- API Key 列表：默认脱敏；眼睛图标二次确认后调 secret 端点加载完整；再次点击本地隐藏；复制按钮在已加载时直接复制，未加载时二次确认后自动加载并复制；`last_viewed_at` 每次调 secret 后端自动更新。
- 创建 API Key → 展示一次性 `full_key` 区块 + 复制按钮 + 关闭提示。
- 身份与绑定默认只读，"编辑"按钮可切换为可编辑；用户名变更成功后保存为只读；冲突 409 提示。
- "数据安全锁"卡片保留（无 toggle），仅展示说明。
- 所有现有测试通过；新增测试覆盖关键路径。
