# 默认知识库与应用场景实施计划

## 总览
本计划基于已批准设计文档 `docs/designs/2026-06-01-默认知识库与应用场景设计.md`，采用最小侵入方式扩展知识库数据模型、上传接口、默认法规导入脚本和体检召回依赖。实施顺序按“模型/迁移 → 后端能力 → 脚本 → 审查接入 → 前端 → 验证”推进，确保每一步都有独立测试与验收标准。

## 前置准备
- [ ] 确认设计文档已批准：`docs/designs/2026-06-01-默认知识库与应用场景设计.md`
- [ ] 确认 `reference/招投标法律法规（新）-用于照胆` 在仓库中可访问
- [ ] 运行后端基线测试：在 `backend/` 执行 `python -m pytest tests/ -v --tb=short`
- [ ] 运行前端基线验证：在 `frontend/` 执行 `npm run build`
- [ ] 确认数据库迁移链当前最新 revision 为 `004`

## 任务列表

### 任务 1: 定义应用场景常量与校验函数 (~3 min)
- **描述**: 增加 `bidding` / `contract` 应用场景枚举常量和校验函数，统一后端入口校验。
- **文件**:
  - 修改 `backend/core/constants.py`
- **测试**:
  - 在后续 API/脚本测试中覆盖合法与非法场景。
- **验证**:
  - `validate_application_scenario("bidding")` 返回正常标签或标准值。
  - `validate_application_scenario("invalid")` 抛出 `ValueError`。
- **依赖**: 无

### 任务 2: 扩展 KnowledgeDocument ORM 字段 (~3 min)
- **描述**: 为知识库文档模型增加所有者、用户归属、应用场景、来源路径字段。
- **文件**:
  - 修改 `backend/models/knowledge.py`
- **测试**:
  - 模型导入测试由现有测试隐式覆盖。
- **验证**:
  - `KnowledgeDocument` 可访问 `owner_type`、`owner_user_id`、`application_scenario`、`source_path`。
  - `source_path` 支持空值且可作为唯一字段使用。
- **依赖**: 任务 1

### 任务 3: 更新模型导出清单 (~2 min)
- **描述**: 如新增类型或需要显式导出，补充模型导出；若仅新增字段则确认无需变更。
- **文件**:
  - 检查/修改 `backend/models/__init__.py`
- **测试**:
  - 运行 `python -m pytest tests/test_infrastructure.py -v --tb=short`。
- **验证**:
  - 应用启动和测试导入模型无异常。
- **依赖**: 任务 2

### 任务 4: 创建数据库迁移 005 (~4 min)
- **描述**: 新增迁移，为 `knowledge_documents` 添加 `owner_type`、`owner_user_id`、`application_scenario`、`source_path` 字段及索引/唯一约束。
- **文件**:
  - 创建 `backend/alembic/versions/005_add_knowledge_ownership_and_scenario.py`
- **测试**:
  - 迁移文件静态检查；若环境支持，执行 `alembic upgrade head`。
- **验证**:
  - `upgrade()` 包含新增字段、`owner_user_id` 外键、`source_path` 唯一约束或唯一索引。
  - `downgrade()` 能按相反顺序删除索引/约束/字段。
- **依赖**: 任务 2

### 任务 5: 让测试数据库初始化兼容新增字段 (~3 min)
- **描述**: 确保 `Base.metadata.create_all` 或测试初始化能创建新增列；必要时调整集成测试清理顺序。
- **文件**:
  - 检查/修改 `backend/tests/conftest.py`
  - 检查/修改 `backend/tests/test_settings_api.py`
- **测试**:
  - `python -m pytest tests/test_settings_api.py -v --tb=short`
- **验证**:
  - 设置页测试创建 `KnowledgeDocument` 时无需额外字段也能通过默认值创建。
- **依赖**: 任务 2

### 任务 6: 扩展知识库上传响应模型 (~3 min)
- **描述**: 上传响应增加 `application_scenario` 字段，概览文档项增加 `owner_type` 与 `application_scenario` 字段。
- **文件**:
  - 修改 `backend/routers/knowledge.py`
- **测试**:
  - 更新 `backend/tests/test_knowledge_api.py` 中响应断言。
- **验证**:
  - `/api/v1/knowledge/upload` 响应包含 `application_scenario`。
  - `/api/v1/knowledge/overview` 文档项包含 `owner_type`、`application_scenario`。
- **依赖**: 任务 1、任务 2

### 任务 7: 知识库上传 API 接收应用场景 (~4 min)
- **描述**: `POST /api/v1/knowledge/upload` 新增 `application_scenario` 表单字段，默认 `bidding`，非法值返回 400。
- **文件**:
  - 修改 `backend/routers/knowledge.py`
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**:
  - 新增 `test_upload_accepts_application_scenario`
  - 新增 `test_upload_rejects_invalid_application_scenario`
- **验证**:
  - 上传合同场景文档时创建的 `KnowledgeDocument.application_scenario == "contract"`。
  - 非法场景返回 400。
- **依赖**: 任务 6

### 任务 8: 知识库上传写入用户归属 (~4 min)
- **描述**: 用户上传新文档时写入 `owner_type="user"`、`owner_user_id=current_user_id`；复用旧文档时避免跨用户/跨场景误合并。
- **文件**:
  - 修改 `backend/routers/knowledge.py`
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**:
  - 新增同名不同场景或不同用户不复用同一文档的单元测试。
- **验证**:
  - 查询 existing_doc 时包含 `owner_type`、`owner_user_id`、`application_scenario` 条件。
  - 新建文档携带当前用户 ID。
- **依赖**: 任务 7

### 任务 9: 概览接口展示系统默认标识字段 (~3 min)
- **描述**: 概览返回默认知识库和用户知识库的文档元数据，供前端展示“系统默认”。
- **文件**:
  - 修改 `backend/routers/knowledge.py`
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**:
  - 更新 `TestGetOverview` 断言 `owner_type` 与 `application_scenario`。
- **验证**:
  - 系统文档返回 `owner_type="system"`。
  - 历史/用户文档默认返回 `owner_type="user"`。
- **依赖**: 任务 6

### 任务 10: 实现知识库召回服务骨架 (~4 min)
- **描述**: 创建服务模块，定义按场景召回默认知识库和用户启用知识库片段的函数签名与返回结构。
- **文件**:
  - 创建 `backend/services/knowledge_retrieval.py`
  - 创建/修改 `backend/tests/test_knowledge_retrieval.py`
- **测试**:
  - 编写返回空结果的基础测试。
- **验证**:
  - `retrieve_regulation_base(db, user_id, application_scenario, limit)` 可导入并返回包含 `snippets`/`sources` 的字典结构。
- **依赖**: 任务 1、任务 2

### 任务 11: 实现默认知识库召回查询 (~4 min)
- **描述**: 查询 `owner_type="system"` 且场景匹配的 completed 文档节点，按文档创建时间与节点 position 截取片段。
- **文件**:
  - 修改 `backend/services/knowledge_retrieval.py`
  - 修改 `backend/tests/test_knowledge_retrieval.py`
- **测试**:
  - 构造系统文档与节点，断言只返回匹配场景片段。
- **验证**:
  - `bidding` 查询不会返回 `contract` 系统文档片段。
- **依赖**: 任务 10

### 任务 12: 实现用户启用知识库召回查询 (~5 min)
- **描述**: 查询当前用户 `owner_type="user"`、场景匹配且未在设置中禁用的文档节点。
- **文件**:
  - 修改 `backend/services/knowledge_retrieval.py`
  - 修改 `backend/tests/test_knowledge_retrieval.py`
- **测试**:
  - 新增“用户禁用文档不返回”和“未配置 setting 默认启用”的测试。
- **验证**:
  - 禁用记录 `enabled=False` 的文档不会进入 `regulation_base`。
- **依赖**: 任务 11

### 任务 13: 扩展 InspectionDeps 场景字段 (~2 min)
- **描述**: 为审查依赖补充 `application_scenario` 字段，便于 Agent prompt 或日志使用。
- **文件**:
  - 修改 `backend/core/deps.py`
- **测试**:
  - 由体检路由测试覆盖。
- **验证**:
  - `InspectionDeps(application_scenario="contract")` 构造成功。
- **依赖**: 任务 1

### 任务 14: 体检上传接收应用场景并注入召回结果 (~5 min)
- **描述**: `POST /inspection/upload` 新增 `application_scenario` 表单字段，校验后调用知识库召回服务，并写入 `InspectionDeps.regulation_base`。
- **文件**:
  - 修改 `backend/routers/inspection.py`
  - 修改/创建 `backend/tests/test_inspection_api.py`
- **测试**:
  - 新增体检上传传入 `contract` 时调用召回服务的测试。
  - 新增非法场景返回 400 的测试。
- **验证**:
  - `run_inspection` 收到的 deps 包含 `application_scenario`、`regulation_base`、合并后的 `taboo_words`。
- **依赖**: 任务 10、任务 13

### 任务 15: 补充体检违禁词与知识库依赖测试 (~4 min)
- **描述**: 覆盖“用户保存违禁词 + 临时传入违禁词”合并，同时确认法规依据被传入 Agent。
- **文件**:
  - 修改/创建 `backend/tests/test_inspection_api.py`
- **测试**:
  - 保存违禁词、提交临时违禁词，断言去重后传入。
  - mock 召回服务，断言返回内容进入 deps。
- **验证**:
  - 测试能防止后续遗漏用户设置违禁词或法规依据。
- **依赖**: 任务 14

### 任务 16: 抽取默认知识库入库复用函数 (~5 min) ✅ DONE
- **描述**: 将上传接口中的转换、写 markdown、构建索引节点逻辑抽成可复用内部函数，供导入脚本调用，保持请求逻辑行为不变。
- **文件**:
  - 修改 `backend/routers/knowledge.py` 或创建 `backend/services/knowledge_ingestion.py`
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**:
  - 现有上传测试继续通过。
- **验证**:
  - 上传接口仍返回相同字段。
  - 脚本可复用同一转换和索引构建能力，无复制大段逻辑。
- **依赖**: 任务 8

### 任务 17: 创建默认知识库导入脚本分类函数 (~3 min) ✅ DONE
- **描述**: 创建脚本并实现文件名到应用场景的推断函数。
- **文件**:
  - 创建 `backend/scripts/import_default_knowledge.py`
  - 创建 `backend/tests/test_import_default_knowledge.py`
- **测试**:
  - 合同关键词归类为 `contract`。
  - 招标/投标/政府采购等关键词归类为 `bidding`。
  - 无法判断默认 `bidding`。
- **验证**:
  - 分类函数无需数据库即可单元测试。
- **依赖**: 任务 1

### 任务 18: 实现默认知识库扫描与幂等检查 (~4 min) ✅ DONE
- **描述**: 脚本扫描 reference 目录，使用 `source_path` 查询已导入文档，已存在则跳过。
- **文件**:
  - 修改 `backend/scripts/import_default_knowledge.py`
  - 修改 `backend/tests/test_import_default_knowledge.py`
- **测试**:
  - mock 数据库查询，断言重复 `source_path` 不创建文档。
- **验证**:
  - 重复执行脚本不会创建重复 `KnowledgeDocument`。
- **依赖**: 任务 17

### 任务 19: 实现默认知识库入库写入字段 (~5 min) ✅ DONE
- **描述**: 脚本创建 `owner_type="system"`、`owner_user_id=None`、`application_scenario`、`source_path` 的知识库文档，并创建版本和索引节点。
- **文件**:
  - 修改 `backend/scripts/import_default_knowledge.py`
  - 修改 `backend/tests/test_import_default_knowledge.py`
- **测试**:
  - 单文件成功导入时断言文档字段、版本状态、节点创建。
- **验证**:
  - 转换失败仅记录失败并继续处理其他文件。
- **依赖**: 任务 16、任务 18

### 任务 20: 导入脚本 CLI 与错误退出处理 (~3 min) ✅ DONE
- **描述**: 增加命令行入口、默认 reference 路径、目录不存在错误、导入汇总日志。
- **文件**:
  - 修改 `backend/scripts/import_default_knowledge.py`
- **测试**:
  - 单元测试目录不存在时返回非零或抛出清晰错误。
- **验证**:
  - `python scripts/import_default_knowledge.py --help` 可显示参数。
  - 目录不存在不影响服务启动，只影响脚本执行。
- **依赖**: 任务 19

### 任务 21: 前端上传表单增加应用场景状态 (~3 min) ✅ DONE
- **描述**: 在知识库页面上传表单状态中增加 `application_scenario`，打开弹窗时默认 `bidding`。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
- **测试**:
  - 可通过后续组件/构建验证。
- **验证**:
  - 重新打开弹窗时应用场景回到“招投标”。
- **依赖**: 任务 7

### 任务 22: 前端上传弹窗增加应用场景单选 (~4 min) ✅ DONE
- **描述**: 在上传弹窗中增加“招投标 / 合同”单选项，并提交到 FormData。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
- **测试**:
  - 若项目已有前端测试框架，新增组件交互测试；否则以 `npm run build` 验证。
- **验证**:
  - 网络请求 FormData 包含 `application_scenario`。
  - 选择“合同”时提交值为 `contract`。
- **依赖**: 任务 21

### 任务 23: 前端概览展示系统默认标签并隐藏系统文档操作 (~4 min) ✅ DONE
- **描述**: 映射概览新增字段，系统默认文档显示“系统默认”标签，隐藏或禁用重命名/删除按钮。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
- **测试**:
  - 构建验证；如有测试框架，增加系统文档不显示删除按钮测试。
- **验证**:
  - `owner_type="system"` 文档显示系统标识。
  - 用户文档保留重命名/删除入口。
- **依赖**: 任务 9

### 任务 24: 修复上传弹窗浅色/深色主题样式 (~4 min) ✅ DONE
- **描述**: 将弹窗、输入框、select、按钮的固定黑白颜色替换为主题变量或语义色，保证浅色主题可读。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
  - 必要时检查 `frontend/src/theme.js`
- **测试**:
  - `npm run build`
  - 手动切换浅色/深色主题检查弹窗可读性。
- **验证**:
  - 浅色主题下输入框文字、背景、边框有足够对比度。
  - 深色主题下视觉风格不回退。
- **依赖**: 任务 22

### 任务 25: 修复知识库页面 HTML 当 JSON 解析问题 (~3 min) ✅ DONE
- **描述**: 获取概览和上传失败时先检查 `content-type`，非 JSON 或 401/404 时给出友好错误，避免直接 JSON parse HTML。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
- **测试**:
  - 如无前端测试框架，以手动 mock 失败响应或构建验证。
- **验证**:
  - 后端返回 HTML 错误页时页面显示可读错误，不抛出 JSON 解析异常。
- **依赖**: 任务 21

### 任务 26: 体检页面预留应用场景上传参数 (~4 min) ✅ DONE
- **描述**: 如果体检页当前未接真实上传，先在后续上传调用位置预留应用场景状态与表单控件；若已有上传入口则提交 `application_scenario`。
- **文件**:
  - 修改 `frontend/src/pages/InspectionDeskPage.vue`
- **测试**:
  - `npm run build`
- **验证**:
  - 用户可选择招投标/合同审查场景。
  - 后续接入真实上传 API 时能直接复用该状态。
- **依赖**: 任务 14

### 任务 27: 更新后端测试辅助对象字段 (~3 min) ✅ DONE
- **描述**: 调整 `test_knowledge_api.py` 中 `_make_document` 的 `spec` 和默认字段，避免新增字段导致测试对象缺属性。
- **文件**:
  - 修改 `backend/tests/test_knowledge_api.py`
- **测试**:
  - `python -m pytest tests/test_knowledge_api.py -v --tb=short`
- **验证**:
  - 知识库 API 测试全部通过。
- **依赖**: 任务 2、任务 9

### 任务 28: 后端目标测试与迁移验证 (~5 min) ✅ DONE
- **描述**: 运行与本功能相关的后端测试，修复测试夹具或断言遗漏。
- **文件**:
  - 可能修改 `backend/tests/*.py`
- **测试**:
  - `python -m pytest tests/test_knowledge_api.py tests/test_settings_api.py tests/test_inspection_api.py tests/test_knowledge_retrieval.py tests/test_import_default_knowledge.py -v --tb=short`
- **验证**:
  - 目标测试全部通过。
- **依赖**: 任务 1-20、任务 27

### 任务 29: 前端构建验证 (~3 min) ✅ DONE
- **描述**: 运行前端构建，确认模板和样式变更无语法错误。
- **文件**:
  - 不修改文件，除非构建暴露问题。
- **测试**:
  - 在 `frontend/` 执行 `npm run build`
- **验证**:
  - 构建成功，无 Vue 模板编译错误。
- **依赖**: 任务 21-26

### 任务 30: 全量回归与导入脚本 dry-run (~5 min) ✅ DONE
- **描述**: 执行设计文档要求的最终验证命令，并以测试目录或 dry-run 模式验证默认知识库导入脚本。
- **文件**:
  - 不修改文件，除非验证暴露问题。
- **测试**:
  - 后端：`python -m pytest tests/ -v --tb=short`
  - 前端：`npm run test:routes`（若脚本存在）
  - 前端构建：`npm run build`
  - 脚本：`python scripts/import_default_knowledge.py --help`，必要时增加 `--dry-run` 后执行
- **验证**:
  - 全部验证命令通过，或记录不可运行原因与替代验证证据。
- **依赖**: 任务 28、任务 29

## 并行机会
- 任务 1-4 完成后，任务 6-9（知识库 API）与任务 10-12（召回服务）可并行。
- 任务 17-20（导入脚本）可在任务 16 抽取入库函数后与任务 14-15（体检接入）并行。
- 任务 21-25（知识库前端）可在任务 7/9 后与后端召回和脚本任务并行。
- 任务 26 可在任务 14 完成接口字段后独立进行。
- 任务 28 与任务 29 分别针对后端/前端，可并行执行；任务 30 需在二者完成后执行。

## 风险 & 缓解
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 历史知识库文档缺少 `owner_user_id` 导致用户隔离不完整 | 中 | 中 | 按设计保持兼容，历史文档默认 user/NULL；本次只保证新上传写入用户归属，后续单独做数据修复 |
| `source_path` 在不同数据库上 nullable unique 行为差异 | 中 | 中 | 使用唯一索引并只对系统导入写入非空路径；测试覆盖重复导入跳过 |
| 上传入库逻辑抽取影响现有上传接口 | 中 | 高 | 先补上传接口回归测试，再做小步抽取，保持响应字段不变 |
| 默认法规文件转换失败阻塞导入 | 中 | 中 | 单文件失败记录错误并继续，最终输出失败清单 |
| 召回策略初版过于粗糙导致上下文过长或不相关 | 中 | 中 | 限制 `limit`，按场景过滤，后续再升级 BM25/向量检索 |
| 前端当前体检页是静态页面，真实上传入口不明确 | 高 | 低 | 只预留场景状态/控件，不强行重构体检流程；真实上传联调另起任务 |
| 浅色主题变量覆盖不完整 | 中 | 中 | 明确手动检查弹窗、input、select、按钮四类元素 |

## 测试策略
| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 后端单元测试 | 应用场景校验、文件名分类、召回服务查询过滤 | 场景分类、系统/用户知识库过滤、禁用文档排除 |
| 后端 API 测试 | 知识库上传/概览、体检上传 | `application_scenario` 入参/响应、非法场景 400、违禁词与法规依据注入 |
| 数据库迁移验证 | Alembic 005 upgrade/downgrade | 新列、外键、唯一索引可创建与回滚 |
| 脚本测试 | 默认知识库导入脚本 | reference 扫描、幂等跳过、单文件失败继续 |
| 前端构建/交互 | 知识库上传弹窗、系统默认标签、错误处理 | 表单提交场景字段、浅色/深色可读、非 JSON 错误不崩溃 |
| 全量回归 | 后端 pytest、前端 routes/build | 确认结构性变更未破坏既有功能 |

## 最终验收标准
- `knowledge_documents` 支持系统/用户归属、应用场景和默认导入来源路径。
- 用户上传知识库可选择招投标/合同场景，后端保存并在响应/概览中返回。
- 默认法规导入脚本可幂等导入 reference 目录文档，重复运行不重复创建。
- 体检上传按应用场景聚合默认知识库、用户启用知识库和用户违禁词进入 Agent 依赖。
- 知识库页面展示系统默认标识，系统默认文档不暴露用户重命名/删除操作。
- 上传弹窗在浅色/深色主题下均可读，API 错误不会触发 HTML 当 JSON 解析崩溃。
