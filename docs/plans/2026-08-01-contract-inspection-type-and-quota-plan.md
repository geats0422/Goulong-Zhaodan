# 合同初审类型与额度策略实施计划

## 总览

本计划基于已读取的最新设计文档 `docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md`，将现有 `bidding/contract` 场景收敛为合同初审，并把工程类别、合同类别、知识库优先级、分类推荐、额度环境策略和风险一致性拆成可独立验收的阶段。实施顺序遵循“数据模型与迁移 → 后端分类/检索/API → 前端 Step 2 与设置页 → 存量数据/法规导入 → 全量验证”的依赖关系。

## Grill 修订决策

以下决策优先于任务描述中的旧假设，执行任务时必须以此为准：

- 照胆只做合同初审，新业务不再提供招投标场景。
- Step 2 使用两个独立维度：工程类别（房建施工、市政道路、装饰装修、机电安装、钢结构、通用工程）和合同类别（劳务分包、专业工程分包、其他类）。AI 只提供推荐，用户最终确认。
- 知识库上传表单统一使用工程类别和合同类别，移除“新基建/传统基建/城市更新”旧分类；新上传固定为合同场景。
- 用户匹配的已启用知识库默认全选，可在 Step 2 多选；无匹配用户文档时回退系统默认通用工程合同规则包；系统文档不与用户文档混合。
- 系统和用户招投标知识库全部归档隐藏，不删除、不参与检索；普通用户可在设置页查看自己的归档资料并完整物理删除，系统归档资料仅管理员/迁移脚本可清理。
- `KnowledgeDocument.is_active` 统一控制系统/用户文档是否展示和检索。
- `application_scenario` 保留历史读取能力，新业务拒绝 `bidding` 并返回 `deprecated_application_scenario`。
- 首期官方合同规则包通过官方域名白名单、manifest、管理员导入和版本元数据维护，不把法规二进制提交 Git；所有工程类别共享通用规则包。
- 分类器独立于审查 Agent；分类超时不阻塞 Step 2，使用“通用工程 + 其他类”并允许人工确认；production 分类调用计入额度，local/development 只记录不拦截。
- 用户类别和系统类别使用稳定 key；已被引用的类别只能停用，历史记录保存名称快照。
- 额度不足统一跳转 `/settings?tab=billing`。
- 风险等级按问题最高严重等级服务端兜底提升，UI/API/PDF 使用最终风险等级。

实现阶段必须保留旧字段的读取能力，不修改既有 Alembic 文件；新迁移必须幂等处理存量记录。涉及用户输入、知识库权限、文件删除、额度、配置和历史数据时，执行任务前按项目约定进行 GitNexus impact analysis，并在完成前运行安全审查与完整验证。

## 前置准备

- [ ] 确认设计文档已批准：`docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md`
- [ ] 记录当前工作区已有改动，不覆盖 `backend/app/core/quota.py` 和其他未提交文件。
- [ ] 建立后端测试基线：`cd backend && uv run pytest tests/test_inspection_api.py tests/test_inspection_parse_async.py tests/test_knowledge_api.py tests/test_knowledge_retrieval.py tests/test_quota.py -q`
- [ ] 建立前端构建基线：`cd frontend && npm run build`
- [ ] 确认 Alembic 当前只有一个 head：`cd backend && uv run alembic heads`
- [ ] 确认本次新增的系统 slug、用户作用域 key、归档状态和默认规则包 manifest 字段，避免在实现阶段继续沿用临时场景分支。

## 任务列表

### 任务 1: 固化类别与风险契约测试 (~4 min)
- **描述**: 先补充类别枚举、未知类别降级、置信度、风险等级提升规则和旧记录兼容展示的失败测试，明确 `engineering`/`contract` 两个维度不能互换。
- **文件**:
  - 修改 `backend/tests/test_inspection_api.py`
  - 修改或新增 `backend/tests/test_inspection_classification.py`
  - 修改 `backend/tests/test_agent_worker_tasks.py` 或 `backend/unit_tests/test_document_worker_hardening.py`
- **测试**: 覆盖未知 key、低置信度、模型超时、非法 `overall_risk`、问题最高等级高于模型标签。
- **验证**: 新测试在现有实现下至少针对新增契约失败，失败原因对应缺失能力而非测试夹具错误。
- **依赖**: 无

### 任务 2: 新增类别、分类字段和知识库绑定迁移 (~5 min)
- **描述**: 新增类别预设表/模型、知识库文档工程类别和合同类别绑定字段、体检分类结果与快照字段，保留 `application_scenario`；为用户作用域唯一性和启用状态建立约束/索引。
- **文件**:
  - 修改 `backend/app/models/knowledge.py`
  - 新增 `backend/alembic/versions/025_contract_inspection_types.py`
  - 如模型拆分，新增 `backend/app/models/inspection_types.py`
- **测试**: 新增 `backend/tests/test_contract_inspection_type_migration.py`，验证升级、字段类型、约束、索引和重复名称隔离。
- **验证**: `cd backend && uv run alembic upgrade head && uv run alembic heads` 成功且只有一个 head；不修改旧迁移文件。
- **依赖**: 任务 1

### 任务 3: 添加幂等预设初始化和存量回填 (~5 min)
- **描述**: 初始化六个工程类别、三个合同类别和通用规则包标识；合同旧记录回填为“通用工程/其他类”并标记 `legacy`，招投标旧记录标记 `archived_legacy`，写入名称快照且不重分类。
- **文件**:
  - 修改 `backend/alembic/versions/025_contract_inspection_types.py`
  - 新增 `backend/scripts/backfill_contract_inspection_types.py`（如迁移外需可重复执行）
  - 新增或修改 `backend/tests/test_contract_inspection_type_backfill.py`
- **测试**: 迁移重复执行/脚本重复执行不产生重复预设；旧历史记录可读取，已有文件、索引和报告不删除。
- **验证**: 在包含 bidding、contract、缺失分类的夹具库上执行两次，结果一致且快照稳定。
- **依赖**: 任务 2

### 任务 4: 实现类别查询与私有类别 CRUD API (~5 min)
- **描述**: 实现工程类别和合同类别的 GET/POST/PATCH/DELETE 接口；系统类别不可被普通用户改名/删除，已引用类别只能停用，用户类别严格按 `owner_user_id` 隔离。
- **文件**:
  - 新增或修改 `backend/app/api/v1/inspection.py`
  - 新增 `backend/app/schemas/inspection_types.py`（如项目已有 schema 目录则放入对应目录）
  - 新增或修改 `backend/app/api/v1/__init__.py`
  - 新增 `backend/tests/test_inspection_types_api.py`
- **测试**: 两个用户互不可见；非法维度、重复名称、删除已引用类别、停用类别和越权 PATCH/DELETE 均返回稳定错误。
- **验证**: OpenAPI 中出现 8 个类别路由，响应只返回当前用户可见的系统/私有启用及必要历史类别。
- **依赖**: 任务 2、任务 3

### 任务 5: 抽取合同分类器和规则初筛 (~5 min)
- **描述**: 将现有文档类型识别替换为独立分类器：输入文件名、解析正文和关键词初筛，输出工程类别、合同类别、置信度、证据与来源；未知模型 key、超时和异常统一降级为通用工程/其他类，不阻塞 Step 2。
- **文件**:
  - 新增 `backend/app/services/contract_classifier.py`
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/app/services/inspection_runner.py`
  - 如使用独立提示词，修改 `backend/app/prompts/*` 或对应 prompt 文件
  - 新增 `backend/tests/test_contract_classifier.py`
- **测试**: 文件名/章节/正文规则命中、模型结构化输出、未知 key、低置信度、超时和模型异常降级。
- **验证**: 合同正文不会再返回 bidding；分类调用失败仍可进入 Step 2，并返回默认推荐值及需要确认的提示。
- **依赖**: 任务 3

### 任务 6: 改造解析任务返回分类推荐和记录快照 (~4 min)
- **描述**: 解析完成响应和 `InspectionRecord` 写入 detected/final 字段、置信度、来源、类别快照；新体检固定为合同场景，不再接受或默认生成 bidding。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/app/services/document_job_service.py`（如任务载荷需要传递分类结果）
  - 修改 `backend/tests/test_inspection_parse_async.py`
- **测试**: 解析成功、分类超时、非法前端分类值、历史记录兼容和 worker 重试后的字段持久化。
- **验证**: 新解析响应包含两类推荐、置信度、证据/来源；服务端不信任模型或前端提交的未知 key。
- **依赖**: 任务 4、任务 5

### 任务 7: 实现用户知识库优先与通用规则回退 (~5 min)
- **描述**: 将知识库检索改为按工程类别+合同类别匹配，优先当前用户已启用文档；存在用户文档时不混入系统文档，无匹配时只返回系统默认通用合同规则包；停用、归档和招投标文档排除。
- **文件**:
  - 修改 `backend/app/services/knowledge_retrieval.py`
  - 修改 `backend/app/api/v1/knowledge.py`
  - 修改 `backend/app/api/v1/settings.py`
  - 修改 `backend/tests/test_knowledge_retrieval.py`
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**: 精确绑定、通用绑定、用户已启用/停用、用户无文档回退、其他用户文档不可见、归档文档不可检索。
- **验证**: 返回 sources 同时携带规则包/类别信息和用户默认回退提示；查询计划不读取未启用用户文档。
- **依赖**: 任务 2、任务 3、任务 6

### 任务 8: 重构 Step 2 后端提交与历史报告响应 (~4 min)
- **描述**: 新增/修改 Step 2 提交契约，接受 `engineering_type_key`、`contract_type_key`、`knowledge_document_ids`；服务端验证类别归属、启用状态和用户权限，保存最终类别及知识来源快照。
- **文件**:
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/app/schemas/inspection.py`（如存在）或新增 schema 文件
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**: 合法提交、未知 key、跨用户私有类别、停用文档、系统归档文档、空用户知识库回退和报告历史读取。
- **验证**: 新体检接口拒绝 `application_scenario=bidding` 并返回 `deprecated_application_scenario`；旧报告仍可查看且不要求重新分类。
- **依赖**: 任务 4、任务 6、任务 7

### 任务 9: 收敛知识库上传和归档资料接口 (~5 min)
- **描述**: 上传表单固定合同场景，写入工程/合同绑定；旧 bidding 上传返回弃用错误；增加归档招投标资料只读列表和用户完整删除流程，删除原文件、Markdown、索引节点、版本和记录并写审计日志。
- **文件**:
  - 修改 `backend/app/api/v1/knowledge.py`
  - 修改 `backend/app/services/knowledge_ingestion.py`
  - 修改 `backend/app/services/file_storage.py`
  - 新增 `backend/app/services/knowledge_archive.py`（如需隔离删除编排）
  - 新增 `backend/tests/test_archived_knowledge_api.py`
- **测试**: 上传固定 contract、归档资料只读、用户只能删除自己的资料、删除失败回滚/幂等、系统资料不可由普通用户清理。
- **验证**: `GET /inspection/archived-knowledge` 和 `DELETE /inspection/archived-knowledge/{id}` 行为符合契约，任何普通检索均不返回归档文档。
- **依赖**: 任务 7、任务 8

### 任务 10: 导入官方默认合同规则包 (~4 min)
- **描述**: 将官方法规来源维护为 manifest，加入官方域名白名单、发布日期/施行日期/版本/hash 元数据和管理员幂等导入；新版本停用旧版本但不删除。
- **文件**:
  - 修改 `backend/scripts/import_default_knowledge.py`
  - 新增 `backend/scripts/default_contract_rules_manifest.json`
  - 新增 `backend/tests/test_import_default_knowledge.py`
  - 如需说明，新增 `docs/knowledge/default-contract-rules.md`
- **测试**: manifest 校验、官方域名白名单、重复导入、版本切换、旧版本停用、历史快照不变；测试不得依赖实时公网。
- **验证**: 使用本地 fixture 执行 `cd backend && uv run python scripts/import_default_knowledge.py --dry-run`，只生成 contract 通用规则包，不把法规二进制提交 Git。
- **依赖**: 任务 3、任务 7

### 任务 11: 统一风险等级最终化和快照保存 (~4 min)
- **描述**: 在服务端校验 `overall_risk` 枚举，按 issues 最高严重等级提升而不降低，所有 API、历史、PDF 使用最终值；保存规则包和知识来源快照。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/app/services/report_pdf.py`
  - 修改 `backend/tests/test_report_pdf.py`
  - 新增或修改 `backend/tests/test_risk_consistency.py`
- **测试**: 标签冲突、缺失/未知标签、问题等级提升、历史快照和 PDF 标签一致。
- **验证**: UI/API/PDF 不再直接消费未经服务端归一化的风险标签；法规版本切换不改变旧报告来源快照。
- **依赖**: 任务 6、任务 8、任务 10

### 任务 12: 固化 ENVIRONMENT 额度策略和配置校验 (~4 min)
- **描述**: 将环境值限制为 local/development/production；development 按 local 处理并记录迁移提示，未知值启动失败；local/development 只记使用量，production 才检查和消耗额度。
- **文件**:
  - 修改 `backend/app/core/config.py`
  - 修改 `backend/app/core/quota.py`
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/tests/test_quota.py`
  - 修改 `backend/tests/test_security_config.py`
  - 修改 `backend/env.example`
- **测试**: 三种环境额度行为、未知环境启动失败、development 警告、生产不足额度 402、调用量记录不被本地阻断。
- **验证**: `cd backend && uv run python -c "from app.core.config import settings; print(settings.environment)"` 成功；配置读取、额度判断和错误码均符合设计。
- **依赖**: 任务 6

### 任务 13: 统一额度不足错误契约 (~3 min)
- **描述**: 保留稳定 `insufficient_quota` 错误码，统一文案和前端可识别结构；所有解析/审查入口返回同一 402 业务错误，不暴露内部实现细节。
- **文件**:
  - 修改 `backend/app/core/quota.py`
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/tests/test_quota.py`
  - 修改 `backend/tests/test_inspection_parse_async.py`
- **测试**: parse、start inspection、worker 入口的额度不足响应均含错误码和账单跳转所需信息。
- **验证**: 不再出现跳转 `/pricing` 的后端错误分支或不稳定错误文案。
- **依赖**: 任务 12

### 任务 14: 重做 Step 2 合同初审准备面板 (~5 min)
- **描述**: 移除招投标/合同切换，标题改为“合同初审准备”；分别显示工程类别、合同类别、AI 推荐、置信度、低置信度提醒、用户知识库多选和系统默认回退状态。
- **文件**:
  - 修改 `frontend/src/components/inspection/KnowledgeTogglePanel.vue`
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 修改 `frontend/src/components/inspection/InspectionStepHeader.vue`
  - 修改 `frontend/src/services/inspectionApi.js`
  - 新增或修改前端组件测试文件
- **测试**: 工程/合同类别可独立修改；未知/低置信度显示提醒但可继续；用户文档与默认文档互斥展示；提交 payload 正确。
- **验证**: Step 2 DOM 中不再出现 bidding/招投标场景切换；点击开始审查提交设计中的三字段 JSON。
- **依赖**: 任务 6、任务 7、任务 8

### 任务 15: 更新知识库管理页和设置页归档区域 (~5 min)
- **描述**: 上传表单仅保留合同场景并使用工程/合同类别；隐藏停用招投标资料；设置页增加“已归档招投标资料”只读区域和用户删除操作。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
  - 修改 `frontend/src/pages/SettingsPage.vue`
  - 修改 `frontend/src/services/settingsApi.js`
  - 新增或修改前端页面测试
- **测试**: 上传 payload 不含 bidding；归档资料不可重新启用；删除确认、成功刷新和失败恢复正确。
- **验证**: 默认概览、知识库管理和 Step 2 均不展示停用招投标文档，用户仅能删除本人归档资料。
- **依赖**: 任务 9

### 任务 16: 统一额度弹窗与账单 Tab 跳转 (~4 min)
- **描述**: 将额度不足提示统一为“当前账户额度不足”，按钮跳转 `/settings?tab=billing`；SettingsPage 读取 query 参数后自动打开账单与订阅管理 Tab。
- **文件**:
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 修改 `frontend/src/components/PaymentModal.vue` 或共享错误提示组件
  - 修改 `frontend/src/pages/SettingsPage.vue`
  - 修改前端路由/入口配置文件（如 `frontend/src/App.vue`）
  - 新增前端额度跳转测试
- **测试**: 402 错误码触发统一弹窗，点击按钮 URL 正确且设置页直接显示 billing；关闭按钮不改变路由。
- **验证**: 全局搜索不再将额度不足入口指向 `/pricing`。
- **依赖**: 任务 13

### 任务 17: 更新历史详情与报告前端展示 (~4 min)
- **描述**: 历史列表、详情弹窗、报告面板和 PDF 下载前端消费最终风险、最终工程/合同类别、置信度、规则包和知识来源快照；无新字段的旧记录显示历史兼容文本。
- **文件**:
  - 修改 `frontend/src/pages/HistoryPage.vue`
  - 修改 `frontend/src/components/inspection/InspectionDetailModal.vue`
  - 修改 `frontend/src/components/inspection/InspectionReportPane.vue`
  - 修改 `frontend/src/pages/DashboardPage.vue`
  - 新增或修改相关前端测试
- **测试**: 新旧记录、低置信度、历史 bidding 归档提示和风险等级展示一致。
- **验证**: 刷新页面后展示内容来自服务端快照，不因当前规则包变化而漂移。
- **依赖**: 任务 11

### 任务 18: 清理文档与开发者入口中的招投标新业务描述 (~3 min)
- **描述**: 将 HelpPage、DeveloperDocs、README/API 示例改为合同初审接口和类别字段；仅保留历史兼容字段的弃用说明。
- **文件**:
  - 修改 `frontend/src/pages/HelpPage.vue`
  - 修改 `frontend/src/pages/DeveloperDocsPage.vue`
  - 修改 `README.md` 或对应 API 文档
  - 如存在，修改 `docs/api/*`
- **测试**: 文本检查确保新业务入口、示例 payload 和 curl 不再使用 bidding；历史兼容说明仍存在。
- **验证**: `rg "招投标|application_scenario.*bidding|/pricing" frontend/src/pages frontend/src/components README.md docs` 结果仅剩明确的历史兼容/归档说明。
- **依赖**: 任务 14、任务 15、任务 16

### 任务 19: 补齐跨后端前端集成测试 (~5 min)
- **描述**: 用现有测试夹具覆盖上传→解析分类→Step 2 确认→知识库检索→额度检查→报告/历史查看的主流程，并覆盖归档删除和旧报告查看。
- **文件**:
  - 新增或修改 `backend/tests/test_contract_inspection_flow.py`
  - 新增或修改 `frontend` 现有测试目录中的 `contract-inspection` 测试
  - 如项目已有 E2E 配置，修改对应 Playwright 测试文件
- **测试**: 主流程、低置信度继续、无用户知识库回退、production 额度不足、local 不拦截、旧 bidding 报告查看。
- **验证**: 后端 targeted tests、前端测试/构建全部通过；失败响应不泄露模型或存储内部错误。
- **依赖**: 任务 8、任务 10、任务 12、任务 14、任务 16、任务 17

### 任务 20: 执行迁移、静态检查和最终回归 (~5 min)
- **描述**: 在干净测试数据库执行迁移和回填，在本地 fixture 导入默认规则包，运行前后端 lint/typecheck/测试，并检查工作区差异只包含计划范围。
- **文件**:
  - 视验证结果修正 `backend/alembic/versions/025_contract_inspection_types.py`
  - 视验证结果修正后端/前端测试与文档
- **测试**: `cd backend && uv run pytest -q`；前端 lint/typecheck/build 和 targeted tests。
- **验证**: `uv run alembic upgrade head`、`uv run alembic heads`、后端 lint/typecheck、前端 lint/typecheck/build 均通过；检查 `git diff` 不包含旧迁移重写、法规二进制或密钥。
- **依赖**: 任务 19

## 并行机会

- 任务 1 可与任务 12 的额度契约测试并行；两者都只新增测试。
- 任务 4 与任务 5 在任务 2 完成后可并行。
- 任务 9 与任务 10 在任务 7 完成后可并行，但任务 10 的 manifest 字段需遵循任务 7 的检索契约。
- 任务 14 与任务 15 在对应后端接口稳定后可并行。
- 任务 17 与任务 18 在任务 11 完成后可并行。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 旧 bidding 数据被误删除或误重分类 | 中 | 高 | 只新增迁移；标记归档并保留文件、索引、历史报告；回填脚本幂等并先在副本验证 |
| 用户知识库与系统默认文档混合，导致审查依据漂移 | 中 | 高 | 检索层明确“用户有启用文档则完全优先，否则系统回退”，并保存 sources 快照 |
| 前端伪造类别或停用文档 ID | 高 | 高 | 后端按用户、启用状态、类别维度重新查询并拒绝非法 payload |
| 分类模型超时阻塞主流程 | 中 | 中 | 分类器设置超时与规则初筛降级，Step 2 始终允许人工确认 |
| local/development 配置被误当 production 或未知值静默放行 | 中 | 高 | Pydantic 配置枚举校验；development 显式警告；未知值启动失败 |
| 额度错误仍跳定价页 | 中 | 中 | 统一 `insufficient_quota` 错误码，前端只实现 `/settings?tab=billing` 入口并添加回归测试 |
| 风险报告历史结果因规则包更新而改变 | 低 | 高 | 保存类别、规则包、来源和名称快照；版本切换只停用旧包，不更新历史快照 |
| 删除归档资料留下孤儿文件或索引 | 中 | 高 | 删除编排覆盖原文件、Markdown、索引节点、版本和记录；事务/补偿与审计日志测试 |
| 当前工作区已有未提交 quota 改动被覆盖 | 中 | 高 | 实施前单独查看 `git diff -- backend/app/core/quota.py`，只在必要行合并，不执行全文件覆盖 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 单元测试 | 分类规则、模型输出解析、风险归一化、额度环境判断、类别 key 校验 | 未知/超时/冲突/边界行为 |
| 服务测试 | 类别 CRUD、知识库优先级、回退检索、归档删除、默认规则 manifest | 权限隔离、启用状态、版本快照、幂等性 |
| API 集成测试 | 解析、Step 2 提交、历史报告、额度不足和弃用 bidding 请求 | 主流程契约、错误码、旧记录兼容 |
| 前端组件测试 | Step 2、知识库多选、低置信度提示、额度弹窗、Settings billing query | 交互和路由验收 |
| E2E/回归 | 上传合同→确认类别→开始审查→查看报告；额度不足→账单页；归档删除 | 用户可见完整链路 |
| 静态/安全检查 | 后端 lint/typecheck、前端 lint/typecheck/build、敏感错误脱敏、迁移 head、Git diff 检查 | 交付质量和数据安全 |
