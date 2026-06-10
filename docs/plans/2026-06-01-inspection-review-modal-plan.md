# 文件审核三步弹窗实施计划

## 总览
本计划基于已批准设计文档 `docs/designs/2026-06-01-文件审核三步弹窗设计.md`，按“后端解析会话能力 → 前端 API 封装 → 三步弹窗组件 → Dashboard/体检台接入 → 验证”的顺序推进。实现采用内存解析会话 MVP，保留旧 `POST /inspection/upload` 兼容入口，新 UI 使用 `/inspection/parse` 与 `/inspection/sessions/{session_id}/inspect` 完成“解析确认、知识库配置、执行审查、查看报告”。

## 前置准备
- [ ] 确认设计文档已批准：`docs/designs/2026-06-01-文件审核三步弹窗设计.md`
- [ ] 确认当前已有设置页知识库启停 API：`frontend/src/services/settingsApi.js` 与 `backend/routers/settings.py`
- [ ] 在 `backend/` 执行基线测试：`uv run pytest tests/test_inspection_api.py -v --tb=short`
- [ ] 在 `frontend/` 执行基线构建：`npm run build`
- [ ] 确认旧 `/inspection/upload` 仍需兼容，不在本轮移除

## 任务列表

### ✅ DONE 任务 1: 补充解析会话测试骨架 (~4 min)
- **描述**: 先为新 `/inspection/parse` 接口写失败测试，覆盖成功响应字段与合同/招投标识别的最小断言。
- **文件**:
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 新增 `test_parse_returns_session_and_file_metadata`
  - 新增 `test_parse_detects_contract_document_type`
  - 新增 `test_parse_detects_bidding_document_type`
- **验证**:
  - 执行 `uv run pytest tests/test_inspection_api.py -v --tb=short` 时新增测试因接口不存在而失败。
- **依赖**: 无

### ✅ DONE 任务 2: 定义解析会话响应模型 (~3 min)
- **描述**: 在体检路由中新增文件元信息与解析响应 Pydantic 模型，为 `/inspection/parse` 提供稳定契约。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 由任务 1 的解析接口测试覆盖。
- **验证**:
  - 存在 `InspectionParseFileResponse` 与 `InspectionParseResponse`，字段包含 `session_id`、`file.name`、`file.size`、`file.format`、`file.document_type`、`file.document_type_label`、`file.text_preview`。
- **依赖**: 任务 1

### ✅ DONE 任务 3: 抽取文件读取与基础校验函数 (~4 min)
- **描述**: 复用旧上传接口中的文件扩展名、大小、读取、文本长度校验逻辑，避免 `/parse` 与 `/upload` 复制实现。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 保持旧上传测试通过。
  - 解析接口后续错误测试复用该函数。
- **验证**:
  - `_read_inspection_upload_text(file)` 或等价函数能返回 `(filename, content_bytes, text)`。
  - 超 20MB、文本过短、不支持格式仍抛出原有语义的 HTTP 错误。
- **依赖**: 任务 2

### ✅ DONE 任务 4: 实现文件类型识别函数 (~4 min)
- **描述**: 按设计文档关键词规则识别 `contract` / `bidding`，同时返回中文标签与低置信度标记。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 任务 1 中合同/招投标识别测试转绿。
  - 可补充无法判断默认 `bidding` 的断言。
- **验证**:
  - 文件名或正文含“合同/协议/甲方/乙方/违约责任”时返回 `contract`、`合同`。
  - 含“招标/投标/采购/评标/中标”时返回 `bidding`、`招投标文件`。
  - 无命中时默认 `bidding` 且可附带 `confidence="low"`。
- **依赖**: 任务 3

### ✅ DONE 任务 5: 增加内存解析会话存储 (~4 min)
- **描述**: 新增 `_inspection_sessions` 内存字典、会话 TTL 常量和创建/读取/清理辅助函数，确保按用户隔离。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 由后续跨用户与过期访问测试覆盖。
- **验证**:
  - 会话结构包含 `id`、`user_id`、`filename`、`file_size`、`file_format`、`document_type`、`document_type_label`、`text`、`text_preview`、`created_at`。
  - 读取会话时要求 `session_id + user_id` 匹配。
- **依赖**: 任务 4

### ✅ DONE 任务 6: 实现 POST /inspection/parse (~5 min)
- **描述**: 新增解析接口，完成文件读取、类型识别、创建会话并返回文件摘要。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 任务 1 的解析成功与类型识别测试全部通过。
- **验证**:
  - `POST /inspection/parse` 返回 200，响应包含 `session_id` 与 `file` 元信息。
  - 文件大小使用实际字节数，格式为小写扩展名且不含点。
- **依赖**: 任务 5

### ✅ DONE 任务 7: 补充解析接口错误场景测试 (~4 min)
- **描述**: 覆盖不支持格式、文件过大、文本过短的错误返回，锁定 Step 1 错误处理契约。
- **文件**:
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 新增 `test_parse_rejects_unsupported_format`
  - 新增 `test_parse_rejects_short_text`
  - 新增或复用超大文件测试
- **验证**:
  - 不支持格式返回 400。
  - 文本过短返回 400。
  - 超 20MB 返回 413。
- **依赖**: 任务 6

### ✅ DONE 任务 8: 扩展体检报告响应文件类型字段 (~3 min)
- **描述**: 在 `InspectionReportResponse` 增加 `document_type` 与 `document_type_label` 可选/必填字段，并保持旧 `/upload` 响应兼容。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 旧 `/inspection/upload` 测试继续通过。
  - 新会话审查测试断言返回文件类型字段。
- **验证**:
  - 新响应包含 `document_type`、`document_type_label`。
  - 旧上传接口可使用传入 `application_scenario` 映射标签，不破坏现有断言。
- **依赖**: 任务 6

### ✅ DONE 任务 9: 编写会话审查接口测试 (~4 min)
- **描述**: 为 `POST /inspection/sessions/{session_id}/inspect` 写失败测试，断言不接收前端场景、从会话类型召回知识库并调用 Agent。
- **文件**:
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 新增 `test_session_inspect_uses_document_type_from_parse_session`
  - 新增 `test_session_inspect_rejects_other_users_session`
- **验证**:
  - 新测试在接口未实现时失败。
- **依赖**: 任务 8

### ✅ DONE 任务 10: 实现会话审查请求模型与接口 (~5 min)
- **描述**: 新增 `InspectionSessionInspectRequest` 和 `/inspection/sessions/{session_id}/inspect`，从会话读取文本与类型并执行现有审查流程。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - 任务 9 的会话审查主路径测试转绿。
- **验证**:
  - 请求体只需要 `project_id`，不读取 `application_scenario`。
  - `retrieve_regulation_base(..., application_scenario=session.document_type, limit=8)` 被调用。
  - `InspectionDeps.application_scenario` 使用会话类型。
- **依赖**: 任务 9

### ✅ DONE 任务 11: 抽取审查执行公共函数 (~5 min)
- **描述**: 将旧 `/upload` 与新会话审查中的违禁词加载、知识库召回、Agent 调用、记录生成逻辑抽成公共函数，减少分叉。
- **文件**:
  - 修改 `backend/routers/inspection.py`
- **测试**:
  - `uv run pytest tests/test_inspection_api.py -v --tb=short`
- **验证**:
  - 旧 `/inspection/upload` 与新 `/sessions/{id}/inspect` 均通过同一内部函数生成 `InspectionReportResponse`。
  - `_inspection_records` 仍记录 `user_id`、`document_name`、`project_id`、风险摘要、问题、引用、预览、配额。
- **依赖**: 任务 10

### ✅ DONE 任务 12: 补齐会话隔离与过期处理 (~4 min)
- **描述**: 实现会话过期清理与用户隔离错误处理，防止跨用户读取解析文本。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - 跨用户访问返回 404 或 403。
  - 过期/不存在 session 返回 404。
- **验证**:
  - `_get_session_for_user` 或等价函数按 `user_id` 校验。
  - 过期会话被删除或拒绝访问。
- **依赖**: 任务 11

### ✅ DONE 任务 13: 新增前端体检 API 服务 (~4 min)
- **描述**: 封装解析、会话审查和报告导出的前端调用，统一使用 `fetchWithAuth` 与错误解析。
- **文件**:
  - 创建 `frontend/src/services/inspectionApi.js`
- **测试**:
  - 构建验证覆盖导入语法。
- **验证**:
  - 导出 `parseInspectionFile(file)`、`inspectParsedSession(sessionId, payload)`、`downloadInspectionReport(report)` 或等价函数。
  - `parseInspectionFile` 使用 `FormData` 上传 `file`。
- **依赖**: 任务 6、任务 10

### ✅ DONE 任务 14: 创建 InspectionStepHeader 组件 (~3 min)
- **描述**: 实现三步状态条，支持未开始、当前、完成、错误四类状态，符合金色描边与低透明文本规则。
- **文件**:
  - 创建 `frontend/src/components/inspection/InspectionStepHeader.vue`
- **测试**:
  - 构建验证。
- **验证**:
  - 展示“解析文件 / 审查准备 / 审查报告”。
  - 当前步骤有金色描边，完成步骤有 check 或实心点，不使用 emoji。
- **依赖**: 无

### ✅ DONE 任务 15: 创建文件摘要与文档预览组件 (~5 min)
- **描述**: 实现 Step 1 文件信息卡与 Step 2/3 左侧文本预览纸张视图。
- **文件**:
  - 创建 `frontend/src/components/inspection/InspectionFileSummary.vue`
  - 创建 `frontend/src/components/inspection/DocumentPreviewPane.vue`
- **测试**:
  - 构建验证。
- **验证**:
  - 文件摘要展示名称、大小、格式、类型、预览/字符数、解析状态。
  - 文档预览支持显示 `text_preview`，无内容时展示占位说明。
- **依赖**: 任务 14

### ✅ DONE 任务 16: 创建 KnowledgeTogglePanel 组件 (~5 min)
- **描述**: 实现审查准备右侧面板，加载设置概览并展示系统默认知识库、用户知识库启停、违禁词挂载说明和开始审查按钮。
- **文件**:
  - 创建 `frontend/src/components/inspection/KnowledgeTogglePanel.vue`
  - 复用 `frontend/src/services/settingsApi.js`
- **测试**:
  - 构建验证。
- **验证**:
  - 文件类型只读展示。
  - 系统默认知识库显示为只读启用。
  - 用户知识库可调用 `updateKnowledgeDocument` 即时启停，失败时回滚开关。
- **依赖**: 任务 13

### ✅ DONE 任务 17: 创建 InspectionReportPane 组件 (~5 min)
- **描述**: 抽取/复用体检台诊断书视觉结构，用于 Step 3 展示报告摘要、风险 chip、问题列表、引用标尺和结束分隔线。
- **文件**:
  - 创建 `frontend/src/components/inspection/InspectionReportPane.vue`
  - 参考 `frontend/src/pages/InspectionDeskPage.vue`
- **测试**:
  - 构建验证。
- **验证**:
  - 支持真实 `issues`、`summary`、`overall_risk`、`regulation_refs` 数据。
  - 空问题时显示“未发现明显风险”类状态。
  - 包含“导出体检报告”“返回审查准备”“关闭弹窗”操作位。
- **依赖**: 任务 15

### ✅ DONE 任务 18: 创建 InspectionReviewModal 主组件 (~5 min)
- **描述**: 组装三步弹窗，管理 `parsing`、`prepare`、`report` 状态和解析会话/知识库/报告数据。
- **文件**:
  - 创建 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 引用 `frontend/src/services/inspectionApi.js`
- **测试**:
  - 构建验证。
- **验证**:
  - 接收 `file` 与 `open`/显示状态属性或通过 `v-if` 控制。
  - 打开后自动调用解析接口，解析成功停留 Step 1 等待确认。
  - Step 2 点击“开始审查”后调用会话审查接口并进入 Step 3。
  - 解析失败、知识库失败、审查失败均显示错误和重试入口。
- **依赖**: 任务 14、任务 15、任务 16、任务 17

### ✅ DONE 任务 19: Dashboard 接入三步弹窗 (~4 min)
- **描述**: 修改文件选择流程，不再跳转 `/inspection-desk`，而是打开 `InspectionReviewModal` 并传入选中的 `File`。
- **文件**:
  - 修改 `frontend/src/pages/DashboardPage.vue`
- **测试**:
  - 构建验证。
  - 手动验证选择文件后弹窗出现。
- **验证**:
  - `handleFileSelected` 保存 `selectedInspectionFile` 并打开弹窗。
  - 关闭弹窗后清空 file input，允许再次选择同一文件。
  - 不再执行 `window.location.href = '/inspection-desk'`。
- **依赖**: 任务 18

### ✅ DONE 任务 20: 调整体检台审查场景为只读 (~3 min)
- **描述**: 移除 `InspectionDeskPage.vue` 顶部审查场景下拉，改为只读文本展示默认文件类型。
- **文件**:
  - 修改 `frontend/src/pages/InspectionDeskPage.vue`
- **测试**:
  - 构建验证。
- **验证**:
  - 页面不再出现 `<select>` 场景选择控件。
  - 顶部展示“审查场景：招投标文件”或后续可由报告详情参数驱动的只读字段。
  - “导出体检报告”和“物理销毁案卷”保留。
- **依赖**: 无

### ✅ DONE 任务 21: 补充导出报告最小实现 (~4 min)
- **描述**: 为 Step 3 导出按钮实现 MVP 下载（HTML/JSON 文本均可），避免按钮无行为。
- **文件**:
  - 修改 `frontend/src/services/inspectionApi.js`
  - 修改 `frontend/src/components/inspection/InspectionReportPane.vue`
  - 可能修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
- **测试**:
  - 构建验证。
  - 手动点击导出按钮检查浏览器下载。
- **验证**:
  - 导出文件名包含报告 ID 或文档名。
  - 导出失败时在报告页显示非阻塞错误提示。
- **依赖**: 任务 17、任务 18

### ✅ DONE 任务 22: 深浅主题可读性修正 (~5 min)
- **描述**: 检查新增弹窗与子组件在深浅主题下的文字、边框、chip、按钮对比度，避免低透明浅色文字。
- **文件**:
  - 修改 `frontend/src/components/inspection/*.vue`
  - 必要时修改 `frontend/src/pages/DashboardPage.vue`
- **测试**:
  - `npm run build`
  - 手动切换深浅主题检查关键文字。
- **验证**:
  - 深色主题正文接近 `#e5e2e1`，次级文字不低于设计要求。
  - 浅色主题正文使用深色，状态 chip 文字可读。
- **依赖**: 任务 18、任务 19、任务 20

### ✅ DONE 任务 23: 后端最终验证与 lint (~4 min)
- **描述**: 运行设计文档指定后端测试与 lint，修复仅限本功能相关问题。
- **文件**:
  - 可能修改 `backend/routers/inspection.py`
  - 可能修改 `backend/tests/test_inspection_api.py`
- **测试**:
  - `uv run pytest tests/test_inspection_api.py -v --tb=short`
  - `uv run ruff check routers/inspection.py tests/test_inspection_api.py`
- **验证**:
  - 两条命令均通过。
- **依赖**: 任务 12

### ✅ DONE 任务 24: 前端最终构建与路由契约验证 (~4 min)
- **描述**: 运行前端构建和路由测试，确认新增组件导入、Dashboard 接入、InspectionDesk 调整无语法/路由破坏。
- **文件**:
  - 可能修改 `frontend/src/components/inspection/*.vue`
  - 可能修改 `frontend/src/pages/DashboardPage.vue`
  - 可能修改 `frontend/src/pages/InspectionDeskPage.vue`
- **测试**:
  - `npm run build`
  - `npm run test:routes`
- **验证**:
  - 两条命令均通过。
- **依赖**: 任务 22

## 并行机会
- 任务 14、15、17 可在任务 13 完成前并行做静态 UI 组件。
- 任务 20 可与后端任务 1-12 并行执行，因为只影响体检台静态展示。
- 任务 21 可在任务 17 完成后与任务 19 并行。
- 任务 23 与任务 24 可在对应前后端实现完成后并行验证。

## 风险 & 缓解
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 内存会话在多进程/重启后丢失 | 中 | 中 | 明确 MVP 限制，过期/丢失时提示重新上传；后续再持久化 PostgreSQL |
| PDF/DOCX 当前仅按字节解码导致预览不完整 | 中 | 中 | 本轮非目标为真实翻页渲染，先保持文本预览；错误提示“无法提取有效文本” |
| 新接口与旧 `/inspection/upload` 逻辑分叉 | 中 | 高 | 任务 11 抽取公共审查函数，旧接口保留兼容测试 |
| 用户知识库启停接口失败导致状态不一致 | 中 | 中 | 前端即时保存失败回滚开关并显示错误 |
| 弹窗组件过大影响维护 | 中 | 中 | 子组件按 StepHeader/FileSummary/Preview/Knowledge/Report 拆分，主组件只管状态编排 |

## 测试策略
| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 后端单元/接口测试 | `/inspection/parse`、文件类型识别、错误文件、会话审查、跨用户隔离 | 解析会话与审查安全边界 |
| 后端兼容测试 | 旧 `/inspection/upload` 原有场景与违禁词/知识库注入 | 防止旧调用失效 |
| 前端构建测试 | 新增 Vue 组件、服务封装、Dashboard/InspectionDesk 导入 | 语法、依赖和路由基本正确 |
| 手动交互验证 | Dashboard 选文件 → Step 1 → Step 2 知识库启停 → Step 3 报告导出 | 主流程体验闭环 |
| 主题可读性检查 | 深色/浅色下步骤条、文件信息、按钮、状态 chip | 符合 `DESIGN.md` 可读性要求 |

## 最终验收命令
- 后端：在 `backend/` 执行 `uv run pytest tests/test_inspection_api.py -v --tb=short`
- 后端 lint：在 `backend/` 执行 `uv run ruff check routers/inspection.py tests/test_inspection_api.py`
- 前端构建：在 `frontend/` 执行 `npm run build`
- 前端路由契约：在 `frontend/` 执行 `npm run test:routes`
