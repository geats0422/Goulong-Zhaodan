# F4 设置 MVP 设计文档

## 目标

实现个人版 SaaS 的设置模块，覆盖系统设置、知识库设置、违禁词设置。所有配置按登录用户保存，不引入审计、权限、角色体系。

## 用户场景

1. 用户进入设置页，查看账号信息、订阅套餐、额度、微信/支付宝绑定状态。
2. 用户编辑账号资料、修改密码、模拟绑定或解绑微信/支付宝。
3. 用户在知识库设置中按文档启用或停用知识库内容。
4. 用户维护违禁词列表，新增、编辑、删除词条。
5. 用户后续执行体检时，系统自动使用该用户启用的知识库和违禁词配置。

## 技术方案

### 范围

- 个人版 MVP：所有设置归属于当前登录用户。
- 不做审计日志。
- 不做权限矩阵。
- 不做真实支付绑定，微信/支付宝绑定先用模拟状态保存，后续可替换为官方支付/账号绑定回调。

### 后端模块

新增 `routers/settings.py`，统一挂载到 `/settings`。

新增持久化表：

- `user_profiles`：用户资料、订阅、额度、支付绑定模拟状态。
- `taboo_words`：用户违禁词。
- `knowledge_document_settings`：用户对知识库文档的启停状态。

现有 `get_current_user` 继续作为认证依赖，所有设置接口都要求 JWT 登录。

### 前端模块

改造 `frontend/src/pages/SettingsPage.vue`：

- 从静态演示数据改为调用后端接口。
- 保留现有视觉风格。
- 系统设置展示可编辑表单。
- 知识库设置展示文档级开关。
- 违禁词设置支持新增、编辑、删除。

## 数据模型

### user_profiles

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| user_id | int | 用户 ID，唯一 |
| display_name | varchar(100) | 显示名称 |
| subscription_plan | varchar(50) | 订阅套餐，MVP 默认 personal |
| monthly_quota | int | 月度额度 |
| quota_used | int | 已用额度 |
| wechat_bound | bool | 微信绑定状态，模拟 |
| alipay_bound | bool | 支付宝绑定状态，模拟 |
| burn_after_read | bool | 阅后即焚模式 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### taboo_words

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| user_id | int | 用户 ID |
| word | varchar(100) | 违禁词 |
| replacement | varchar(100) nullable | 建议替换词 |
| note | text nullable | 备注 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

约束：同一用户下 `word` 唯一。

### knowledge_document_settings

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| user_id | int | 用户 ID |
| document_id | int | 知识库文档 ID |
| enabled | bool | 是否启用 |
| updated_at | datetime | 更新时间 |

约束：同一用户下 `document_id` 唯一。

未写入设置的文档默认 `enabled=true`。

## 接口设计

### GET /settings/overview

返回设置页首屏所需数据，减少前端瀑布请求。

```json
{
  "profile": {
    "username": "demo",
    "display_name": "demo",
    "subscription_plan": "personal",
    "monthly_quota": 500,
    "quota_used": 142,
    "wechat_bound": false,
    "alipay_bound": true,
    "burn_after_read": true
  },
  "knowledge": [
    {
      "category_key": "traditional",
      "category_label": "传统基建",
      "subcategories": [
        {
          "id": 1,
          "name": "房建",
          "documents": [
            { "id": 1, "title": "施工规范.pdf", "enabled": true }
          ]
        }
      ]
    }
  ],
  "taboo_words": [
    { "id": 1, "word": "绝对化极限违约金条款", "replacement": "", "note": "" }
  ]
}
```

### PATCH /settings/profile

更新系统设置资料与模拟绑定状态。

```json
{
  "display_name": "张三",
  "wechat_bound": true,
  "alipay_bound": false,
  "burn_after_read": true
}
```

### POST /settings/password

修改当前用户密码。

```json
{
  "old_password": "oldpass123",
  "new_password": "newpass123"
}
```

### PATCH /settings/knowledge/documents/{document_id}

启用或停用某个知识库文档。

```json
{ "enabled": false }
```

### POST /settings/taboo-words

新增违禁词。

```json
{ "word": "内部绝密代号X7", "replacement": "", "note": "" }
```

### PATCH /settings/taboo-words/{word_id}

编辑违禁词。

```json
{ "word": "内部代号", "replacement": "项目编号", "note": "" }
```

### DELETE /settings/taboo-words/{word_id}

删除违禁词。

返回 `204 No Content`。

## 行为接入

### 违禁词接入体检

`POST /inspection/upload` 当前支持表单字段 `taboo_words`。F4 后改为：

1. 查询当前用户保存的违禁词。
2. 合并本次上传临时传入的 `taboo_words`。
3. 去重后传入 `InspectionDeps.taboo_words`。

保留上传临时违禁词参数，避免破坏已有调用。

### 知识库启停接入

检索/召回链路尚未完成，因此本阶段先做到数据层与 API 层：

1. `settings/overview` 返回每个文档的启停状态。
2. 后续检索实现时，只查询当前用户 `enabled=true` 的文档。
3. 若没有设置记录，文档默认启用。

## 错误处理

| 场景 | 状态码 | 说明 |
|------|--------|------|
| 未登录 | 401 | JWT 无效或缺失 |
| 旧密码错误 | 400 | 修改密码失败 |
| 新密码太短 | 422 | Pydantic 参数校验 |
| 违禁词重复 | 409 | 同一用户下重复 word |
| 文档不存在 | 404 | 启停不存在的文档 |
| 违禁词不存在 | 404 | 编辑/删除不存在的词条 |

## 测试策略

### 后端测试

- `test_settings_api.py`
- 覆盖 `overview/profile/password/knowledge/taboo_words` 正常和异常流程。
- 验证设置按用户隔离。
- 验证 `inspection/upload` 自动合并用户违禁词。

### 前端验证

- `npm run build`
- `npm run test:routes`
- 手动验证设置页三个 tab 的加载、保存、开关、新增、编辑、删除。

## 非目标

- 不实现真实微信/支付宝绑定。
- 不实现真实支付订阅变更。
- 不实现审计日志。
- 不实现权限/角色矩阵。
- 不实现配置版本回滚。
