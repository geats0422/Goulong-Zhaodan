# 合同场景启用实施计划

## 总览
基于最新设计文档 `docs/designs/2026-06-11-v0.2.0-contract-scenario-design.md`，本计划将合同类文件审查链路补齐为「解析识别 → Step2 场景提示与知识库切换 → 合同专属 prompt → 按场景召回与报告引用约束 → 默认知识库补齐」。当前代码已存在部分实现（如 `document_type` 识别、会话审查按场景召回、Step2 展示文档类型），实施时应优先对齐设计差异并用测试锁定行为。

关键决策：后端保留既有 snake_case 响应字段以兼容现有前端，同时如需满足设计示例可增加前端适配或 API alias；未识别类型应按设计返回 `unknown`，但审查执行仍兜底到 `bidding`，避免破坏现有审查路径。

## 前置准备
- [x] 确认设计文档已批准：`docs/designs/2026-06-11-v0.2.0-contract-scenario-design.md`
- [x] 查看当前工作树，避免覆盖他人改动：`git status --short`
- [x] 后端基线：在 `backend/` 运行 `uv run pytest tests/test_inspection_api.py tests/test_inspection_prompts.py tests/test_import_default_knowledge.py`
- [x] 前端基线：在 `frontend/` 运行 `npm run build`
- [x] 确认本轮不新增数据库迁移（`InspectionRecord.document_type` 已存在）

## 任务列表

### 任务 1: 对齐文档类型枚举与兜底策略 (~4 min) ✅
- **描述**: 将解析识别结果支持 `unknown`，未命中关键词时返回 `unknown` 与「未知类型」标签；审查执行前再将 `unknown` 兜底为 `bidding`。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 修改 `backend/tests/test_inspection_api.py` 中 `test_detect_document_type_defaults_to_low_confidence_bidding` 为期望 `unknown`
  - 新增/调整会话审查测试，验证 `unknown` 会话执行时召回 `bidding` 知识库
- **验证**:
  - `uv run pytest tests/test_inspection_api.py -k "detect_document_type or session_inspect"`
- **依赖**: 无

### 任务 2: 补全文档类型关键词覆盖 (~3 min) ✅
- **描述**: 按设计补齐合同关键词：`签订`、`协议`、`付款`、`履约`、`违约金`、`不可抗力`；保留/复核招投标关键词覆盖。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 在 `backend/tests/test_inspection_api.py` 新增合同关键词参数化测试，覆盖付款、履约、不可抗力等合同文本
- **验证**:
  - `uv run pytest tests/test_inspection_api.py -k "detect_document_type"`
- **依赖**: 任务 1

### 任务 3: 增加 `/inspection/parse` 响应兼容字段 (~4 min) ✅
- **描述**: 根据接口设计补充 `documentType` 字段（建议在 `file` 内增加 camelCase alias，必要时顶层也可增加只读 alias），同时保留现有 `file.document_type`，避免前端破坏性改动。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改 `frontend/src/services/inspectionApi.js`（如选择在前端做 normalize）
- **测试**:
  - 在 `backend/tests/test_inspection_api.py` 断言 parse 响应同时包含兼容字段与既有字段
- **验证**:
  - `uv run pytest tests/test_inspection_api.py -k "parse_returns_session or parse_detects"`
- **依赖**: 任务 1

### 任务 4: 编写合同专属 Prompt 模板测试 (~3 min) ✅
- **描述**: 先写失败测试，要求合同 prompt 常量/格式化函数包含合同审查核心维度：权利义务对等、违约责任、金额、履约期限、不可抗力、争议解决、绝对化用语。
- **文件**:
  - 修改 `backend/tests/test_inspection_prompts.py`
- **测试**:
  - 新增 `test_contract_prompt_templates_include_core_review_dimensions`
  - 新增场景调度格式化测试（contract 使用合同模板，bidding 使用默认模板）
- **验证**:
  - `uv run pytest tests/test_inspection_prompts.py`，预期先红后绿
- **依赖**: 无

### 任务 5: 实现合同专属 Prompt 与调度接口 (~5 min) ✅
- **描述**: 在提示词模块新增合同模板和按场景选择的格式化入口；`bidding` 保持现有提示词，`contract` 使用合同审查表达。
- **文件**:
  - 修改 `backend/app/prompts/inspection_prompts.py`
- **测试**:
  - 跑通任务 4 中新增测试
- **验证**:
  - `uv run pytest tests/test_inspection_prompts.py`
- **依赖**: 任务 4

### 任务 6: Agent 审查流程接入场景 Prompt 调度 (~4 min) ✅
- **描述**: `run_inspection` 根据 `deps.application_scenario` 选择 regulation/inspection/summary prompt；当合同模板缺失或场景非法时兜底 bidding/default。
- **文件**:
  - 修改 `backend/agents/inspector.py`
  - 如需导出新函数，修改 `backend/app/prompts/inspection_prompts.py`
- **测试**:
  - 在 `backend/tests/test_inspection_api.py` 或新增 `backend/tests/test_inspector_prompt_dispatch.py` 中 mock agent，验证 contract 场景传入的 prompt 含合同审查维度
- **验证**:
  - `uv run pytest tests/test_inspection_prompts.py tests/test_inspection_api.py -k "prompt or contract or session_inspect"`
- **依赖**: 任务 5

### 任务 7: 锁定合同报告只引用合同知识库 (~5 min) ✅
- **描述**: 完善集成测试，确保合同会话审查时 `retrieve_regulation_base(application_scenario="contract")`，并且 `_sanitize_inspection_result_refs` 会过滤非合同来源引用。
- **文件**:
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 新增合同审查返回混合引用时，仅保留 `regulation_base.sources` 中合同来源的断言
- **验证**:
  - `uv run pytest tests/test_inspection_api.py -k "contract and regulation"`
- **依赖**: 任务 6

### 任务 8: Step2 自动识别提示与场景状态封装 (~4 min) ✅
- **描述**: 在父组件基于 parse 结果维护 `selectedScenarios` 与用户是否手动覆盖的标记；合同自动选择 contract、取消 bidding；unknown 保持 bidding 默认。
- **文件**:
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
- **测试**:
  - 若项目暂无前端测试框架，先补充可手工验证清单；如引入测试需先单独评估依赖，不在本任务新增依赖
- **验证**:
  - `npm run build`
  - 手工上传合同文本，Step2 进入后默认场景为合同
- **依赖**: 任务 1、任务 3

### 任务 9: KnowledgeTogglePanel 支持 selectedScenarios 双向更新 (~5 min) ✅
- **描述**: 新增 prop `selectedScenarios`，新增 emit `update:selectedScenarios`；展示「已自动识别为合同类，已启用相关知识库」提示；用户切换后触发父组件覆盖状态。
- **文件**:
  - 修改 `frontend/src/components/inspection/KnowledgeTogglePanel.vue`
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
- **测试**:
  - 检查合同/招投标/unknown 三种状态 UI 文案与按钮可用性
- **验证**:
  - `npm run build`
  - 手工验证：合同显示合同 chip 与自动启用提示；招投标显示招投标；unknown 保持招投标默认且不误报合同
- **依赖**: 任务 8

### 任务 10: 审查请求携带用户最终选择场景 (~4 min) ✅
- **描述**: 当用户在 Step2 手动切换场景时，`inspectParsedSession` 请求体携带最终 `application_scenario`；后端优先使用显式场景但必须校验合法，未传则使用会话识别结果。
- **文件**:
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 修改 `frontend/src/services/inspectionApi.js`（如需 normalize payload）
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 在 `backend/tests/test_inspection_api.py` 新增 session inspect 传入 `application_scenario` 覆盖 session 类型的测试
- **验证**:
  - `uv run pytest tests/test_inspection_api.py -k "session_inspect"`
  - `npm run build`
- **依赖**: 任务 9

### 任务 11: 修复默认知识库 source_path 比对并补齐导入测试 (~4 min) ✅
- **描述**: 确认 `import_default_knowledge.py` 使用稳定、规范化的 `source_path` 比对，避免相对/绝对路径不一致导致重复或漏导；补测试覆盖等价路径。
- **文件**:
  - 修改 `backend/scripts/import_default_knowledge.py`
  - 修改 `backend/tests/test_import_default_knowledge.py`
- **测试**:
  - 新增 source_path 规范化/重复跳过测试
- **验证**:
  - `uv run pytest tests/test_import_default_knowledge.py`
- **依赖**: 无

### 任务 12: 执行默认知识库补齐脚本并记录结果 (~5 min) ✅
- **描述**: 重新运行默认知识库导入脚本，确认缺失的 3 个 bidding 法规被补齐，contract 类仍为 2 个；将执行结果记录到计划或后续变更说明。
- **文件**:
  - 运行 `backend/scripts/import_default_knowledge.py`
  - 不直接修改业务代码；如产生数据库/存储变更，按项目约定确认是否纳入提交
- **测试**:
  - 无新增代码测试；以脚本输出和数据库统计为准
- **验证**:
  - `uv run python scripts/import_default_knowledge.py`
  - 用现有接口或 SQL 确认 bidding / contract 数量符合验收标准（注意设计中「补全后 24 个 bidding + 2 个 contract」与验收「bidding=25」存在不一致，需实施时记录实际口径）
- **依赖**: 任务 11

### 任务 13: 完整回归与验收走查 (~5 min) ✅
- **描述**: 运行后端相关测试与前端构建，完成合同/招投标两条主流程手工验收。
- **文件**:
  - 不修改文件
- **测试**:
  - 后端：`uv run pytest tests/test_inspection_api.py tests/test_inspection_prompts.py tests/test_import_default_knowledge.py`
  - 前端：`npm run build`
- **验证**:
  - 上传《施工合同》：Step2 显示合同类并启用合同知识库，报告引用均来自合同知识库
  - 上传招投标文件：Step2 默认招投标知识库，报告引用招投标来源
  - unknown 文档：不崩溃，默认 bidding 兜底
- **依赖**: 任务 1-12

## 并行机会
- 任务 1-3（后端解析/API 字段）与任务 4-6（Prompt 与 Agent 调度）可分支并行，任务 6 需等待任务 5。
- 任务 11 可与任务 1-10 并行，任务 12 需等待任务 11。
- 任务 8-9 可在任务 3 的响应字段策略确定后与后端 Prompt 工作并行。
- 任务 7 依赖任务 6，但可与前端任务 8-10 并行。

## 风险 & 缓解
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 设计要求 `unknown` 与现有默认 bidding 行为冲突 | 中 | 中 | 解析返回 unknown，审查执行层兜底 bidding，兼顾语义与稳定性 |
| API 字段 camelCase/snake_case 不一致导致前端破坏 | 中 | 中 | 保留既有字段，新增兼容 alias 或前端 normalize，不做破坏性替换 |
| 用户手动切换场景与自动识别互相覆盖 | 中 | 中 | 父组件维护 `userOverriddenScenario`，仅在未覆盖时自动切换 |
| 合同 Prompt 引用未启用法规 | 中 | 高 | 保持 `_sanitize_inspection_result_refs` 过滤，并增加混合引用测试 |
| 默认知识库数量口径不一致 | 中 | 低 | 实施时记录实际统计，向产品确认 24 还是 25 个 bidding 为准 |
| 导入脚本重复导入或跳过错误 | 中 | 中 | source_path 规范化测试 + 执行前备份/确认数据库环境 |

## 测试策略
| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 单元测试 | `_detect_document_type`、Prompt 模板、source_path 规范化 | 类型识别、合同审查维度、导入去重 |
| API/集成测试 | `/inspection/parse`、`/inspection/sessions/{id}/inspect` | parse 响应、场景召回、引用过滤、手动覆盖场景 |
| 前端构建 | `npm run build` | Vue 组件 props/emits 与模板无构建错误 |
| 手工验收 | 合同、招投标、unknown 三类上传流程 | Step2 自动勾选、提示文案、报告引用来源 |

## 最终验收清单
- [ ] 上传《施工合同》后 Step2 显示「已识别为合同类」，默认启用合同知识库
- [ ] 合同报告 `regulation_refs` 全部来自合同类知识库或允许的违禁词引用
- [ ] 上传招投标文件后仍默认启用招投标知识库
- [ ] unknown 文档不阻塞流程，审查时稳定兜底 bidding
- [ ] 默认知识库补齐结果已记录，并解释 bidding 数量口径
- [ ] 后端相关测试通过，前端构建通过
