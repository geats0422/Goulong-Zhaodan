# F4 设置 MVP 实施计划

## 总览

基于 `docs/designs/F4-设置-MVP-设计.md`，本计划将设置模块拆成后端持久化/API、体检链路接入、前端设置页改造三条线。后端先建立用户资料、违禁词、知识库文档启停三张表及 `/settings` 路由；前端保留现有视觉风格，将静态演示数据替换为登录用户的接口数据与可编辑操作。

关键决策：设置均按当前 JWT 用户隔离；知识库文档未显式设置时默认启用；微信/支付宝绑定仅保存模拟布尔状态；真实支付、审计、权限矩阵不进入本阶段。

## 前置准备

- [ ] 确认 `docs/designs/F4-设置-MVP-设计.md` 已获批准，且非目标范围不扩大。
- [ ] 确认后端依赖可安装，数据库配置指向开发/测试库。
- [ ] 确认前端依赖已安装，能运行 `npm run build` 与 `npm run test:routes`。
- [ ] 运行基线测试：`cd backend && pytest`、`cd frontend && npm run build && npm run test:routes`。

## 任务列表

### 任务 1: 创建设置数据模型 (~4 min)
- **描述**: 在现有 SQLAlchemy 模型中新增用户资料、违禁词、知识库文档启停模型，补充唯一约束与时间字段。
- **文件**:
  - 修改 `backend/models/knowledge.py`
  - 修改 `backend/models/__init__.py`
- **测试**: 暂不新增测试；后续 API 测试通过 `init_db()` 验证表可创建。
- **验证**: `python -m py_compile models/knowledge.py models/__init__.py` 通过；模型可从 `models` 包导入。
- **依赖**: 无

### 任务 2: 新增 Alembic 迁移 (~3 min)
- **描述**: 创建 `003` 迁移，新增 `user_profiles`、`taboo_words`、`knowledge_document_settings`，包含外键、唯一约束和索引。
- **文件**:
  - 创建 `backend/alembic/versions/003_add_settings_tables.py`
- **测试**: 暂不新增测试。
- **验证**: 迁移文件 `revision="003"`、`down_revision="002"`；`upgrade/downgrade` 对称。
- **依赖**: 任务 1

### 任务 3: 编写设置 API 测试脚手架 (~4 min)
- **描述**: 新建设置 API 测试文件，复用认证注册登录方式，准备清理设置表与知识库表的 fixture/helper。
- **文件**:
  - 创建 `backend/tests/test_settings_api.py`
- **测试**: 添加客户端 fixture、`register_and_auth` helper、测试数据清理逻辑。
- **验证**: `pytest backend/tests/test_settings_api.py` 能收集测试；初始断言可失败于未实现接口。
- **依赖**: 任务 1

### 任务 4: 测试设置 overview 默认数据 (~3 min)
- **描述**: 增加 `GET /settings/overview` 测试，验证新用户自动返回默认 profile、空 taboo_words、知识库结构且文档默认启用。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **测试**: 覆盖登录成功后带 Bearer Token 请求 overview。
- **验证**: 测试预期字段包含 `profile.username/display_name/subscription_plan/monthly_quota/quota_used/wechat_bound/alipay_bound/burn_after_read`。
- **依赖**: 任务 3

### 任务 5: 实现设置路由基础与 overview (~5 min)
- **描述**: 创建 `/settings` 路由、响应模型、`get_or_create_profile` helper，并组合 profile、知识库文档启停、违禁词列表。
- **文件**:
  - 创建 `backend/routers/settings.py`
  - 修改 `backend/main.py`
- **测试**: 使任务 4 的 overview 测试通过。
- **验证**: `GET /settings/overview` 未登录返回 401，登录后返回设计文档指定结构。
- **依赖**: 任务 1、任务 4

### 任务 6: 测试 profile 更新接口 (~3 min)
- **描述**: 增加 `PATCH /settings/profile` 测试，覆盖 display_name、微信/支付宝绑定、阅后即焚状态保存与再次读取。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **测试**: 包含正常更新和用户隔离断言。
- **验证**: 更新后 overview 中 profile 字段与请求一致，另一个用户不受影响。
- **依赖**: 任务 5

### 任务 7: 实现 profile 更新接口 (~4 min)
- **描述**: 增加请求模型与 `PATCH /settings/profile`，只允许更新设计指定字段，提交后返回最新 profile。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **测试**: 使任务 6 测试通过。
- **验证**: 非法字段不会被写入；当前用户只能更新自己的 profile。
- **依赖**: 任务 6

### 任务 8: 测试密码修改接口 (~4 min)
- **描述**: 增加 `POST /settings/password` 测试，覆盖旧密码正确、旧密码错误、新密码过短、修改后新密码可登录旧密码不可登录。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **测试**: 使用 `/auth/login` 验证密码变更结果。
- **验证**: 旧密码错误返回 400，新密码过短返回 422。
- **依赖**: 任务 5

### 任务 9: 实现密码修改接口 (~4 min)
- **描述**: 复用 `verify_password/hash_password`，实现当前用户密码修改，更新 `users.hashed_password`。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **测试**: 使任务 8 测试通过。
- **验证**: 成功修改返回明确成功状态或更新后的轻量结果；不会泄露 hash。
- **依赖**: 任务 8

### 任务 10: 测试知识库文档启停接口 (~4 min)
- **描述**: 增加知识库文档测试数据，覆盖 `PATCH /settings/knowledge/documents/{document_id}` 启用/停用、默认启用、文档不存在 404、用户隔离。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **测试**: 断言 overview 中对应 document 的 `enabled` 与当前用户设置一致。
- **验证**: 未写入设置的文档返回 `enabled=true`。
- **依赖**: 任务 5

### 任务 11: 实现知识库文档启停接口 (~5 min)
- **描述**: 实现文档存在性校验与 `knowledge_document_settings` upsert 逻辑，并让 overview 合并启停状态。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **测试**: 使任务 10 测试通过。
- **验证**: 不存在文档返回 404；重复切换不会创建重复记录。
- **依赖**: 任务 10

### 任务 12: 测试违禁词 CRUD (~5 min)
- **描述**: 增加违禁词新增、重复、编辑、删除、不存在 404、用户隔离测试。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py`
- **测试**: 覆盖 `POST/PATCH/DELETE /settings/taboo-words`。
- **验证**: 同用户重复 word 返回 409；删除成功返回 204。
- **依赖**: 任务 5

### 任务 13: 实现违禁词 CRUD (~5 min)
- **描述**: 实现违禁词请求模型、查重、按当前用户过滤、创建/编辑/删除逻辑。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **测试**: 使任务 12 测试通过。
- **验证**: 任何 word_id 操作都不能影响其他用户数据。
- **依赖**: 任务 12

### 任务 14: 测试体检合并用户违禁词 (~4 min)
- **描述**: 为 `POST /inspection/upload` 增加测试，验证已保存违禁词与上传临时 `taboo_words` 合并去重后传入 `InspectionDeps`。
- **文件**:
  - 修改 `backend/tests/test_settings_api.py` 或创建 `backend/tests/test_inspection_settings_integration.py`
- **测试**: mock `run_inspection` 捕获 deps.taboo_words。
- **验证**: 合并顺序稳定、无重复；保留临时参数兼容性。
- **依赖**: 任务 13

### 任务 15: 接入体检链路的用户违禁词 (~4 min)
- **描述**: 给 `upload_and_inspect` 注入数据库 session，查询当前用户 taboo_words，与表单临时词合并去重。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**: 使任务 14 测试通过；回归既有 inspection/history 测试。
- **验证**: 未保存违禁词时行为与原接口一致。
- **依赖**: 任务 14

### 任务 16: 前端创建设置 API 封装 (~4 min)
- **描述**: 新增轻量 API helper，读取本地 access token 或沿用现有认证存储方式，封装 overview、profile、password、knowledge toggle、taboo CRUD。
- **文件**:
  - 创建 `frontend/src/services/settingsApi.js`
  - 如已有认证存储约定，必要时修改相关文件
- **测试**: 暂无单元测试；通过构建与页面手动验证覆盖。
- **验证**: API helper 方法路径与后端一致，错误响应能抛出可展示信息。
- **依赖**: 任务 5、任务 7、任务 9、任务 11、任务 13

### 任务 17: 设置页加载 overview 并展示状态 (~5 min)
- **描述**: 将 `SettingsPage.vue` 静态数据替换为接口数据，增加 loading/error 状态，展示账号、订阅、额度、绑定、知识库、违禁词。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 运行 `npm run build`；手动用登录用户打开设置页。
- **验证**: 首屏只需一次 overview 请求即可渲染三个 tab 的基础数据。
- **依赖**: 任务 16

### 任务 18: 实现系统设置表单交互 (~5 min)
- **描述**: 增加 display_name 编辑、微信/支付宝模拟绑定切换、阅后即焚开关、密码修改表单与保存反馈。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 运行 `npm run build`；手动验证保存后刷新仍保留状态，新密码可登录。
- **验证**: 保存按钮禁用/加载状态合理，失败时显示错误消息。
- **依赖**: 任务 17

### 任务 19: 实现知识库文档开关交互 (~4 min)
- **描述**: 根据 overview 的分类/子类/文档结构渲染文档级开关，切换时调用接口并本地更新状态。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 运行 `npm run build`；手动验证有/无文档两种状态。
- **验证**: 开关失败时回滚 UI 或重新拉取 overview。
- **依赖**: 任务 17

### 任务 20: 实现违禁词新增编辑删除交互 (~5 min)
- **描述**: 将违禁词 tab 改为可新增、编辑 replacement/note、删除的列表/表单，处理 409/404 错误提示。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 运行 `npm run build`；手动验证新增、重复、编辑、删除。
- **验证**: 删除后列表即时更新；重复词提示清晰。
- **依赖**: 任务 17

### 任务 21: 补齐前端样式与可访问性细节 (~3 min)
- **描述**: 在不破坏现有视觉风格的前提下，为新增表单、按钮、开关、错误提示、空状态补齐 scoped CSS 与 aria label。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 运行 `npm run build`。
- **验证**: 900px 以下布局仍可用；所有交互控件有可读文本或 aria-label。
- **依赖**: 任务 18、任务 19、任务 20

### 任务 22: 更新/确认前端路由验证 (~3 min)
- **描述**: 若设置页新增依赖影响路由加载，更新路由验证脚本预期；否则运行并记录结果。
- **文件**:
  - 可能修改 `frontend/scripts/verify-routes.mjs`
- **测试**: `cd frontend && npm run test:routes`。
- **验证**: 设置页路由仍可被验证脚本加载。
- **依赖**: 任务 21

### 任务 23: 后端格式与全量回归 (~4 min)
- **描述**: 运行后端 lint/测试，修复导入顺序、类型、异步测试隔离问题。
- **文件**:
  - 可能修改 `backend/routers/settings.py`
  - 可能修改 `backend/routers/inspection.py`
  - 可能修改 `backend/tests/test_settings_api.py`
- **测试**: `cd backend && ruff check . && pytest`。
- **验证**: 后端 lint 与测试全部通过。
- **依赖**: 任务 15

### 任务 24: 前端构建与最终手动验收 (~4 min)
- **描述**: 运行前端构建/路由测试，并按设计文档手动验证三个 tab 主流程。
- **文件**:
  - 不固定；只修复发现的小问题
- **测试**: `cd frontend && npm run build && npm run test:routes`。
- **验证**: 设置页加载、保存、开关、新增、编辑、删除全部可用；无控制台关键错误。
- **依赖**: 任务 22、任务 23

## 并行机会

- 任务 2 可在任务 1 完成后与任务 3 并行。
- 任务 6/8/10/12 可在任务 5 完成后并行编写测试。
- 任务 7/9/11/13 可在对应测试完成后由不同开发者并行实现，但需避免同时编辑 `backend/routers/settings.py` 产生冲突。
- 任务 16 可在后端接口路径和响应模型稳定后，与任务 14/15 并行。
- 任务 18/19/20 可在任务 17 完成后并行开发同一页面的不同 tab，合并时重点处理样式冲突。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 设置表与现有 `init_db()`/Alembic 双轨创建不一致 | 中 | 中 | 模型与迁移字段保持完全一致，测试用 `init_db()`，部署用 Alembic |
| 多个任务同时修改 `SettingsPage.vue` 冲突 | 中 | 中 | 先完成 overview 数据结构，再按 tab 分段修改并及时合并 |
| 体检测试 mock 与现有全局 fake 模块冲突 | 中 | 中 | 单独测试文件中显式 monkeypatch `routers.inspection.run_inspection` |
| 用户隔离遗漏导致跨用户读写 | 低 | 高 | 所有查询条件包含 `user_id`，测试覆盖双用户隔离 |
| 违禁词重复校验受空格/大小写影响 | 中 | 低 | 保存前 trim；MVP 先按精确 word 唯一，必要时后续增加规范化规则 |
| 前端认证 token 存储方式不明确 | 中 | 中 | 先搜索现有登录页存储逻辑，API helper 复用现有约定，不引入新认证机制 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 后端单元/API 测试 | `backend/tests/test_settings_api.py` | overview/profile/password/knowledge/taboo_words 正常和异常流程 |
| 后端集成测试 | `inspection/upload` + 用户保存违禁词 | 用户违禁词与临时表单词合并去重，兼容原参数 |
| 用户隔离测试 | 双用户 profile、knowledge setting、taboo words | 防止跨用户读写 |
| 前端构建验证 | `npm run build` | Vue 语法、类型推断、打包无错误 |
| 前端路由验证 | `npm run test:routes` | 设置页路由可加载 |
| 手动验收 | 设置页三个 tab | 加载、保存、开关、新增、编辑、删除主流程 |

## 最终验收命令

```bash
cd backend && ruff check . && pytest
cd frontend && npm run build && npm run test:routes
```

## 交付说明

完成后应确认：

- `/settings/overview` 可一次返回设置页所需 profile、knowledge、taboo_words。
- `/settings/profile`、`/settings/password`、`/settings/knowledge/documents/{document_id}`、`/settings/taboo-words` CRUD 均要求 JWT。
- `POST /inspection/upload` 自动合并当前用户保存的违禁词与本次临时违禁词。
- `frontend/src/pages/SettingsPage.vue` 不再依赖静态演示数据，且保留原有暗色金色视觉风格。
