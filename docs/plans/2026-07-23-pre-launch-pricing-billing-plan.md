# 句龙照胆上线前定价与账单优化实施计划

## 总览

本计划基于 `docs/designs/2026-07-23-pre-launch-pricing-billing-design.md`，目标是上线前完成商业化闭环：更新定价表、建立额度账单拦截（402）、实现免费 20 万/月兜底、简化知识库设置分区、统一 AI 模型选择。

实施按四大模块推进：① 定价更新（前后端数据源同步）→ ② 免费额度 + 拦截依赖（新建 `quota.py`，端点接入，移除内联检查，月度重置）→ ③ 前端额度展示与 402 引导 → ④ 知识库分区 + 模型显示精简。

**关键现状修正**（设计文档未明确、实施必须处理）：
- `CurrentUserContext` 仅含 `user_id`/`is_active`，**不含 `membership`** → `require_quota` 依赖必须接收 `db` 并自行查询 Membership。
- 现有内联额度检查（`inspection_runner.py` L158-176）用 **403**，仅覆盖同步 `execute_inspection`，未覆盖 `/parse`、`/upload` 入口 → 需统一改为依赖级 402。
- 注册默认 `token_quota=50`（非 0）→ 需改为 0 走 effective 兜底 20 万。
- 本模块**无数据库迁移**（`token_quota`/`token_used` 字段已存在，仅默认值语义变化）。

所有实现遵循 TDD 与最小变更。涉及额度、支付、用户输入的任务，执行阶段须运行 GitNexus impact analysis，并在完成前触发 security-review。

## 前置准备

- [x] 设计文档已批准：`docs/designs/2026-07-23-pre-launch-pricing-billing-design.md`
- [x] 确认免费额度兜底语义：`token_quota=0` 时有效额度 = 20 万
- [x] 确认 402 作为额度不足的稳定状态码（替代现有 403）
- [ ] 运行后端基线：`cd backend && uv run pytest tests/test_inspection_api.py tests/test_payment_state_machine.py tests/test_settings_api.py tests/test_knowledge_api.py -q`
- [ ] 运行前端基线构建：`cd frontend && npm run build`
- [ ] 若修改符号，按 `AGENTS.md` 运行 GitNexus impact analysis

## 任务列表

### 任务 1: 编写定价契约测试 (~3 min)

- **描述**: 先写测试锁定新定价表，覆盖 7 个商品的 amount_cents 与 token_quota。
- **文件**:
  - 新增 `backend/tests/test_payment_catalog.py`
- **测试**: 断言 `light=900/100万`、`standard=2900/500万`、`large=8900/2000万`、`pro_monthly=6900/300万`、`pro_quarterly=17900/900万`、`pro_yearly=59900/3600万`，`test_0_1` 保持不变。
- **验证**: 新测试在当前旧价格下失败（红）。
- **安全**: 否
- **依赖**: 无

### 任务 2: 更新后端定价表 (~3 min)

- **描述**: 按 2.1 新定价表更新 `PRODUCTS` 字典的 `amount_cents` 与 `token_quota`。
- **文件**:
  - 修改 `backend/app/services/payment_catalog.py`
- **测试**: 任务 1 转绿。
- **验证**: `cd backend && uv run pytest tests/test_payment_catalog.py -q` 通过。
- **安全**: 是（支付金额）
- **依赖**: 任务 1

### 任务 3: 更新前端定价数据源与展示 (~4 min)

- **描述**: 同步 `plans.js` 的 `POWER_PACKS`/`SUB_PLANS` 与 `PricingPage.vue` 的 `addons`/`subscriptions` 价格/额度；特征文案中 Token 额度同步更新（如月度 200万→300万）。
- **文件**:
  - 修改 `frontend/src/data/plans.js`
  - 修改 `frontend/src/pages/PricingPage.vue`
- **测试**: 人工核对 PricingPage 渲染价格与后端 `PRODUCTS` 一致。
- **验证**: `cd frontend && npm run build` 通过；浏览器核对四档加购包 + 三档订阅价格。
- **安全**: 否
- **依赖**: 任务 2（价格口径以后端为准）

### 任务 4: 编写额度兜底单元测试 (~3 min)

- **描述**: 先写测试覆盖 `effective_token_quota`/`remaining_tokens`：membership=None→20万、token_quota=0→20万、token_quota=5000→5000、超额→remaining=0。
- **文件**:
  - 新增 `backend/tests/test_quota.py`
- **测试**: 用 dataclass mock membership，不依赖 DB。
- **验证**: 测试在 `quota.py` 不存在时导入失败（红）。
- **安全**: 否
- **依赖**: 无

### 任务 5: 新建 quota.py 额度核心模块 (~3 min)

- **描述**: 创建 `FREE_MONTHLY_TOKEN_QUOTA=200_000`、`effective_token_quota(membership)`、`remaining_tokens(membership)`。暂不含 `require_quota` 依赖（下一任务）。
- **文件**:
  - 新建 `backend/app/core/quota.py`
- **测试**: 任务 4 转绿。
- **验证**: `cd backend && uv run pytest tests/test_quota.py -q` 通过。
- **安全**: 否
- **依赖**: 任务 4

### 任务 6: 接入免费额度兜底到注册与设置默认值 (~4 min)

- **描述**: 将注册（`auth.py` L216）与 `_get_or_create_membership`（`settings.py` L284）默认 `token_quota` 从 50 改为 0；`_profile_response` 的 `monthly_quota` 改用 `effective_token_quota(membership)`。
- **文件**:
  - 修改 `backend/app/api/v1/auth.py`
  - 修改 `backend/app/api/v1/settings.py`
- **测试**: 扩展 `tests/test_settings_api.py`：新注册用户 overview 返回 `monthly_quota=200000`、`quota_used=0`。
- **验证**: 注册后 GET `/settings/overview` 显示有效额度 200000。
- **安全**: 是（用户额度、会员状态）
- **依赖**: 任务 5

### 任务 7: 编写 require_quota 依赖测试 (~4 min)

- **描述**: 写测试覆盖 `require_quota` 依赖：额度充足→返回带 membership 的上下文；`remaining_tokens<=0`→抛 402 且 `detail.code=="insufficient_quota"`；membership 不存在→按免费兜底校验。
- **文件**:
  - 扩展 `backend/tests/test_quota.py`
- **测试**: 用 `AsyncMock` 模拟 `db.execute` 返回 membership 行。
- **验证**: 测试在 `require_quota` 未实现时失败（红）。
- **安全**: 否
- **依赖**: 任务 5

### 任务 8: 实现 require_quota 拦截依赖 (~4 min)

- **描述**: 在 `quota.py` 实现 `async def require_quota(db, user)`：查 `Membership(product="zhaodan", status="active")`，用 `remaining_tokens` 校验，不足抛 `HTTPException(402, detail={"code":"insufficient_quota","message":"算力额度不足，请购买额度包后继续使用"})`。返回 membership 供后续复用。
- **文件**:
  - 修改 `backend/app/core/quota.py`
- **测试**: 任务 7 转绿。
- **验证**: `cd backend && uv run pytest tests/test_quota.py -q` 通过。
- **安全**: 是（额度拦截、认证）
- **依赖**: 任务 7

### 任务 9: 五端点接入 require_quota 依赖 (~5 min)

- **描述**: 为 5 个写入/体检端点追加 `Depends(require_quota)`：`POST /inspection/upload`、`POST /inspection/parse`、`POST /inspection/sessions/{id}/inspect`、`POST /api/v1/agent/jobs/inspect`、`POST /api/v1/knowledge/upload`。注意 agent 端点已有 `require_api_scope`，require_quota 与之并存。
- **文件**:
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/app/api/v1/agent.py`
  - 修改 `backend/app/api/v1/knowledge.py`
- **测试**: 扩展 `tests/test_inspection_api.py`：构造 `token_used>=quota` 用户 → 调 `/inspection/upload` 返 402。
- **验证**: 额度耗尽用户调用任一端点返 402 + `insufficient_quota`。
- **安全**: 是（额度拦截）
- **依赖**: 任务 8

### 任务 10: 移除 inspection_runner 内联额度检查 (~3 min)

- **描述**: 删除 `execute_inspection` 内 L158-176 的内联 membership 查询与 403 拦截（改由端点依赖统一处理）；保留 L229-230 的扣减逻辑（扣减需基于依赖返回的 membership 或重新查询）。注意异步 worker 路径（`tasks.py`）不经端点依赖，需在 worker 调 `execute_inspection` 前补一次 `remaining_tokens` 校验。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/app/workers/tasks.py`（异步体检前补校验）
- **测试**: 确认现有 `test_inspection_api.py` 通过；额度耗尽不再产生 403。
- **验证**: `cd backend && uv run pytest tests/test_inspection_api.py tests/test_document_worker.py -q` 通过。
- **安全**: 是（额度扣减一致性）
- **依赖**: 任务 9

### 任务 11: 新增免费额度月度重置 cron (~4 min)

- **描述**: 新增 `reset_monthly_free_quota_task`：将 `plan='free'` 的 membership `token_used` 归零（订阅用户按订阅周期已由 subscription_service 处理，不在此重置）。在 `workers/config.py` 注册每月 1 号 00:05 执行。
- **文件**:
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/app/workers/config.py`
- **测试**: 新增 `tests/test_monthly_quota_reset.py`：构造 free + used>0 的 membership，执行 task 后 used=0；pro 用户 used 不变。
- **验证**: `cd backend && uv run pytest tests/test_monthly_quota_reset.py -q` 通过。
- **安全**: 是（额度结算）
- **依赖**: 任务 5

### 任务 12: 设置页账单区域加额度预警 (~3 min)

- **描述**: 在 `SettingsPage.vue` 账单区（L821-829）进度条逻辑上加：剩余 < 10% 时进度条/文案转黄色预警 + 提示"额度即将耗尽，建议补充"。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 人工核对：quota_used/monthly_quota ≥ 0.9 时黄色态。
- **验证**: `cd frontend && npm run build` 通过；浏览器核对预警态。
- **安全**: 否
- **依赖**: 任务 6（后端返回正确 monthly_quota）

### 任务 13: 体检流程 402 引导购买弹窗 (~5 min)

- **描述**: 在 `inspectionApi.js` 的 `parseResponse` 中识别 402 + `code=="insufficient_quota"`，抛带 `quotaExhausted` 标志的错误；在 `InspectionReviewModal.vue` 的解析失败（`startParse` catch）/体检失败处识别该标志，显示"额度不足"引导卡片含"前往补充额度"按钮（跳转 `/pricing`）。
- **文件**:
  - 修改 `frontend/src/services/inspectionApi.js`
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
- **测试**: 人工核对：额度耗尽时上传文件 → 弹窗显示购买引导而非通用错误。
- **验证**: `cd frontend && npm run build` 通过；浏览器模拟 402 响应核对引导卡片。
- **安全**: 否
- **依赖**: 任务 9（后端真实返 402）

### 任务 14: 编写知识库 overview 分组契约测试 (~3 min)

- **描述**: 先写测试锁定 `GET /settings/overview` 的 `knowledge` 改为 `system`/`user` 两组结构（含 documents 列表 + enabled + 业务标签）。
- **文件**:
  - 扩展 `backend/tests/test_settings_api.py`
- **测试**: 构造 system + user 各一份文档，断言响应分组与 enabled 字段。
- **验证**: 测试在当前按 ENGINEERING_CATEGORIES 分组结构下失败（红）。
- **安全**: 否
- **依赖**: 无

### 任务 15: 后端 settings overview 改为 system/user 分组 (~4 min)

- **描述**: 将 `_build_knowledge`（settings.py L329-362）从按 `ENGINEERING_CATEGORIES` 分组改为按 `owner_type`（system/user）两组；保留 `KnowledgeDocumentSetting.enabled` 读取；文档项附 `application_scenario` 业务标签。
- **文件**:
  - 修改 `backend/app/api/v1/settings.py`
  - 同步 `SettingsKnowledgeCategory` Pydantic 模型（改为 owner_type 分组字段）
- **测试**: 任务 14 转绿；回归 `test_knowledge_retrieval.py`（retrieve_regulation_base 仍按 enabled 过滤）。
- **验证**: `cd backend && uv run pytest tests/test_settings_api.py tests/test_knowledge_retrieval.py -q` 通过。
- **安全**: 否
- **依赖**: 任务 14

### 任务 16: 前端设置页知识库上下分区改造 (~5 min)

- **描述**: 将 `SettingsPage.vue` 知识库 tab（L1087-1107）从按 category 循环改为上下两区：上部"系统默认知识库"（owner_type=system）、下部"我的知识库"（owner_type=user，附上传入口）；保留每文档启用/停用开关。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 人工核对分区渲染 + 开关切换生效。
- **验证**: `cd frontend && npm run build` 通过；浏览器核对两区与开关。
- **安全**: 否
- **依赖**: 任务 15

### 任务 17: 设置页删除模型服务端 URL 与 API Key 显示 (~2 min)

- **描述**: 删除 `SettingsPage.vue` L945-948 的 `model-info-bar`（服务端 URL + API Key 预览）；保留模型选择卡片与脱敏开关。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 人工核对模型 tab 不再泄露 base_url / api_key。
- **验证**: `cd frontend && npm run build` 通过。
- **安全**: 是（移除敏感信息展示）
- **依赖**: 无

### 任务 18: 最终验证与回归 (~5 min)

- **描述**: 运行完整后端测试套件 + 前端 lint/构建；核对额度闭环端到端：注册→20万→耗尽→402→购买→恢复。
- **文件**: 无（仅验证）
- **测试**: 全量回归。
- **验证**:
  - `cd backend && uv run pytest -q` 全绿
  - `cd backend && uv run ruff check .` 无错
  - `cd frontend && npm run lint && npm run build` 通过
  - 手动：新注册用户有效额度 200000；耗尽后体检返 402 + 引导；购买加购包后额度恢复
- **安全**: 是（支付闭环、额度结算）
- **依赖**: 任务 1-17 全部完成

## 并行机会

- **任务 1 与 任务 4、任务 14**：分属定价/额度/知识库三个独立模块的测试，可并行起步。
- **任务 3（前端定价）与 任务 6（后端默认值）**：无依赖，可并行（前者依赖任务 2 口径，后者依赖任务 5）。
- **任务 11（月度重置）与 任务 12（前端预警）**：无依赖，可并行。
- **任务 16（前端知识库分区）与 任务 17（删除模型显示）**：同文件 SettingsPage.vue，**不可并行**（需串行避免冲突）。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| require_quota 依赖引入 DB 查询，拖慢热路径 | 中 | 中 | membership 查询走 user_id 索引；`get_current_user` 已有一次 DB 查询，额度查询量级相当 |
| 异步 worker 路径不经端点依赖，额度拦截遗漏 | 中 | 高 | 任务 10 显式在 worker 体检前补 `remaining_tokens` 校验 |
| 月度重置误重置订阅用户额度 | 低 | 高 | cron 仅重置 `plan='free'`；测试覆盖 pro 不变 |
| 前端 plans.js 与 PricingPage 价格漂移 | 中 | 中 | 任务 3 以后端 `PRODUCTS` 为单一口径，人工核对一致 |
| 知识库分组结构变更破坏 retrieve_regulation_base | 低 | 中 | 任务 15 回归 `test_knowledge_retrieval.py`；分组仅改展示层，检索仍按 enabled |
| 删除内联额度检查后并发超额扣减 | 低 | 中 | 扣减在事务内；本轮不引入悲观锁，作为后续独立事项 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 单元测试 | `payment_catalog` 价格表、`quota` 兜底与拦截逻辑、月度重置 task | 核心额度逻辑 100% |
| 集成测试 | 5 端点 402 拦截、`/settings/overview` 分组、注册默认额度 | 关键路径 |
| 回归测试 | `test_inspection_api`、`test_knowledge_retrieval`、`test_payment_state_machine` | 不破坏现有行为 |
| 前端 | 402 引导弹窗、额度预警态、知识库分区渲染、模型显示精简 | 主交互流程 |
| 端到端 | 注册→20万→耗尽→402→购买→恢复 | 商业化闭环 |

## 下一步

计划文档已保存至 `docs/plans/2026-07-23-pre-launch-pricing-billing-plan.md`。建议运行 `/execute 1` 开始执行任务 1（定价契约测试）。
