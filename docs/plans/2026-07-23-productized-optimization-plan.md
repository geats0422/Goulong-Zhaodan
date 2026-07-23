# 句龙照胆产品化优化实施计划

## 总览

本计划基于 `docs/designs/2026-07-23-productized-optimization-design.md`，按“大版本统一验收、实施可分阶段”的节奏推进。先恢复 `/inspection/parse` 默认本地存储，再引入 `InspectionRecord.status` 和新统计契约，最后完成全局主题、核心页面 token 迁移和设计规范检查。

所有实现任务遵循 TDD 和最小变更原则。涉及 `config.py`、存储、上传、数据库和用户输入的任务，在执行阶段必须运行 GitNexus impact analysis，并在完成前触发 security-review 与配置三步验证。

## 前置准备

- [x] 设计文档已批准：`docs/designs/2026-07-23-productized-optimization-design.md`
- [x] `grill-me` 压力测试已完成
- [x] 已确认采用新统计契约，不保留旧字段兼容
- [x] 已确认保留 `dark | light | system` 明暗双主题
- [x] 运行基线检查：`cd backend && uv run pytest tests/test_history_stats_api.py -q`
- [x] 运行前端基线构建：`cd frontend && npm run build`
- [x] 若修改符号，按 `AGENTS.md` 运行 GitNexus impact analysis

## 任务列表

### 任务 1: 固定存储模式测试契约 (~4 min)

- **描述**: 先写存储模式单元测试，覆盖默认本地、OSS 配置残留但后端为 local、显式 OSS、OSS 异常转换。
- **文件**:
  - 新增 `backend/tests/test_file_storage_backend.py`
- **测试**: mock `settings` 和 OSS bucket，避免真实网络调用。
- **验证**: 新测试在当前实现下失败，能复现“bucket/endpoint 非空即误启 OSS”。
- **安全**: 是（文件上传、存储、密钥配置）
- **依赖**: 无

### 任务 2: 增加 STORAGE_BACKEND 配置 (~3 min)

- **描述**: 在配置层新增 `storage_backend` 字段，默认 `local`，限制合法值为 `local|oss`。
- **文件**:
  - 修改 `backend/app/core/config.py`
  - 修改 `backend/env.example`
  - 如存在，修改 `backend/.env.example`
- **测试**: 扩展 `backend/tests/test_security_config.py` 或任务 1 测试。
- **验证**: `cd backend && uv run python -c "from app.core.config import settings; print(settings.storage_backend)"` 输出 `local`。
- **安全**: 是（配置、密钥）
- **依赖**: 任务 1

### 任务 3: 改造 file_storage 显式后端判断 (~4 min)

- **描述**: 修改 `is_oss_enabled()`，只有 `storage_backend == "oss"` 且 OSS 配置完整才启用 OSS；`save_file/read_file/delete_file/file_exists` 保持相对路径契约。
- **文件**:
  - 修改 `backend/app/services/file_storage.py`
- **测试**: 任务 1 转绿。
- **验证**: OSS bucket/endpoint 存在但 `STORAGE_BACKEND=local` 时，`save_file()` 写入本地。
- **安全**: 是（文件上传、路径）
- **依赖**: 任务 2

### 任务 4: 增加 OSS 生产配置校验 (~3 min)

- **描述**: 在生产安全检查中校验显式 OSS 模式需要完整 bucket、endpoint 和 access key；local 模式不要求 OSS。
- **文件**:
  - 修改 `backend/app/core/config.py`
  - 修改 `backend/tests/test_security_config.py`
- **测试**: production + `STORAGE_BACKEND=oss` + OSS 缺失应失败；production + local 应通过 OSS 检查。
- **验证**: 配置静态检查和 readback 均通过。
- **安全**: 是（生产配置、密钥）
- **依赖**: 任务 2

### 任务 5: 统一存储错误映射到上传 API (~4 min)

- **描述**: 为存储异常引入稳定错误类型或复用现有业务错误，`/inspection/parse` 将其转换为可读 HTTP 错误。
- **文件**:
  - 修改 `backend/app/services/file_storage.py`
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/tests/test_inspection_parse_async.py`
- **测试**: mock `save_file()` 抛存储错误，API 返回稳定错误文案且不暴露 OSS 细节。
- **验证**: 用户提供的 OSS 502 类异常不会原样进入响应。
- **安全**: 是（文件上传、错误脱敏）
- **依赖**: 任务 3

### 任务 6: 创建 InspectionRecord.status 迁移测试 (~4 min)

- **描述**: 先写迁移测试，确认新增状态字段、约束、默认值和历史数据映射。
- **文件**:
  - 新增 `backend/tests/test_inspection_record_status_migration.py`
- **测试**: 覆盖 pending、completed、failed 三类历史记录映射。
- **验证**: 当前迁移不存在时测试失败。
- **安全**: 否
- **依赖**: 无

### 任务 7: 新增 InspectionRecord.status 模型和迁移 (~5 min)

- **描述**: 增加模型字段、Alembic 迁移、check constraint 和必要索引。
- **文件**:
  - 修改 `backend/app/models/knowledge.py`
  - 新增 `backend/alembic/versions/024_add_inspection_record_status.py`
- **测试**: 任务 6 转绿。
- **验证**: `cd backend && uv run alembic heads` 只有一个 head。
- **安全**: 否
- **依赖**: 任务 6

### 任务 8: 更新 pending 记录创建状态 (~3 min)

- **描述**: 让 `/inspection/parse` 和相关 pending 创建函数写入 `status="processing"`。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/tests/test_inspection_parse_async.py`
- **测试**: 创建异步体检记录后状态为 processing。
- **验证**: 记录初始状态不再依赖 `overall_risk="pending"` 推断。
- **安全**: 是（用户输入、文件上传链路）
- **依赖**: 任务 7

### 任务 9: 更新同步体检完成/失败状态 (~4 min)

- **描述**: 同步体检成功时标记 `completed`；如果已创建记录后失败，标记 `failed` 并保持错误可诊断。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**: 成功、LLM 失败、文件内容不足等路径。
- **验证**: 历史列表和统计可直接读取 record status。
- **安全**: 是（用户输入、AI 输出）
- **依赖**: 任务 8

### 任务 10: 更新 worker 体检完成/失败状态 (~5 min)

- **描述**: 异步 worker 完成体检后写入 `completed`，解析或审查失败时写入 `failed`。
- **文件**:
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/tests/test_document_worker.py`
- **测试**: worker succeeded、failed、retry 后成功路径。
- **验证**: `DocumentProcessingJob.status` 和 `InspectionRecord.status` 保持一致但职责分离。
- **安全**: 是（文件解析、用户数据）
- **依赖**: 任务 8

### 任务 11: 固定新统计契约测试 (~4 min)

- **描述**: 重写或新增统计 API 测试，覆盖新字段和 hit_rate 口径。
- **文件**:
  - 修改 `backend/tests/test_history_stats_api.py`
- **测试**: uploaded/completed/hit/failed/pending/quota、project_id 过滤、range 校验。
- **验证**: 当前 `_inspection_records` 实现无法通过新契约测试。
- **安全**: 否
- **依赖**: 任务 7

### 任务 12: 实现数据库聚合统计接口 (~5 min)

- **描述**: `/inspection/stats/history` 改为依赖 DB 查询 `InspectionRecord`，按日期聚合新契约字段。
- **文件**:
  - 修改 `backend/app/api/v1/inspection.py`
- **测试**: 任务 11 转绿。
- **验证**: API 不再引用 `_inspection_records` 作为统计数据源。
- **安全**: 是（用户数据隔离、API）
- **依赖**: 任务 11

### 任务 13: 清理或隔离进程内统计缓存 (~3 min)

- **描述**: 移除统计链路对 `_inspection_records` 和 `append_history_record()` 的依赖；如仍需兼容内部用途，明确标注非统计数据源。
- **文件**:
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/app/api/v1/inspection.py`
- **测试**: 统计测试仍全部通过。
- **验证**: `rg "_inspection_records|append_history_record" backend/app` 不出现在统计 endpoint 依赖路径中。
- **安全**: 否
- **依赖**: 任务 12

### 任务 14: 定义前端主题 token 基线 (~5 min)

- **描述**: 建立 dark/light token 和字体变量，导入 Syne、Hanken Grotesk、JetBrains Mono。
- **文件**:
  - 修改 `frontend/src/style.css`
  - 如需要新增 `frontend/src/styles/tokens.css`
- **测试**: 前端构建。
- **验证**: 全局存在 `--font-display/body/mono` 与主题色 token。
- **安全**: 否
- **依赖**: 无

### 任务 15: 统一主题 API 和持久化行为 (~4 min)

- **描述**: 修复 `useTheme.toggleTheme()` 未持久化的问题，确保所有入口使用同一主题 API，system 模式监听系统变化。
- **文件**:
  - 修改 `frontend/src/theme.js`
  - 修改 `frontend/src/composables/useTheme.js`
  - 新增 `frontend/src/composables/__tests__/useTheme.test.mjs` 或轻量 Node 测试
- **测试**: localStorage、`html[data-theme]`、system 模式、路由后保持。
- **验证**: 任意入口切换主题后刷新或跳转仍一致。
- **安全**: 否
- **依赖**: 任务 14

### 任务 16: 移除登录/注册局部主题源 (~4 min)

- **描述**: 登录页和注册页不再用局部 `:data-theme` 作为主题源，样式统一读取 `html[data-theme]`。
- **文件**:
  - 修改 `frontend/src/pages/LoginPage.vue`
  - 修改 `frontend/src/pages/RegisterPage.vue`
- **测试**: 主题切换测试或构建覆盖。
- **验证**: 登录页切换主题后进入其他页面保持一致，其他页面切换后回登录页也一致。
- **安全**: 是（认证页面 UI，不改认证逻辑）
- **依赖**: 任务 15

### 任务 17: 改造统计页新契约和错误态 (~5 min)

- **描述**: 前端统计页消费新字段，区分加载中、真实空数据、接口失败，失败不再把 summary 置 0。
- **文件**:
  - 修改 `frontend/src/pages/StatisticsPage.vue`
- **测试**: 新增或补充统计页逻辑测试；至少构建验证。
- **验证**: 0 数据、失败、正常数据三种状态显示不同。
- **安全**: 否
- **依赖**: 任务 12、任务 14

### 任务 18: 统一 app shell footer 贴底 (~3 min)

- **描述**: 统一内页 main 容器 `flex: 1`，修复统计页空数据时 footer 漂浮。
- **文件**:
  - 修改 `frontend/src/style.css`
  - 修改 `frontend/src/pages/StatisticsPage.vue`
  - 如必要修改 `frontend/src/components/app/DashboardFooter.vue`
- **测试**: 构建和截图验证。
- **验证**: 空数据统计页 footer 位于视口底部。
- **安全**: 否
- **依赖**: 任务 14

### 任务 19: 迁移顶栏和 footer 到 token (~4 min)

- **描述**: `AppTopNav` 与 `DashboardFooter` 使用全局字体和色彩 token，移除旧硬编码主题值。
- **文件**:
  - 修改 `frontend/src/components/app/AppTopNav.vue`
  - 修改 `frontend/src/components/app/DashboardFooter.vue`
- **测试**: 前端构建。
- **验证**: dark/light 下导航和 footer 均与 token 一致。
- **安全**: 否
- **依赖**: 任务 14

### 任务 20: 迁移核心工作台页面 token (~5 min)

- **描述**: 迁移知识库、历史页、体检台、设置页的旧字体和色彩硬编码。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
  - 修改 `frontend/src/pages/HistoryPage.vue`
  - 修改 `frontend/src/pages/InspectionDeskPage.vue`
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 前端构建。
- **验证**: 核心工作台页面在 dark/light 下无明显旧浅色硬编码漏出。
- **安全**: 是（设置页包含账号/密钥 UI，仅样式变更）
- **依赖**: 任务 14、任务 15

### 任务 21: 迁移体检弹窗和报告组件 token (~5 min)

- **描述**: 迁移体检弹窗、报告面板、预览面板、文件摘要和知识库选择面板的样式 token。
- **文件**:
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 修改 `frontend/src/components/inspection/InspectionReportPane.vue`
  - 修改 `frontend/src/components/inspection/DocumentPreviewPane.vue`
  - 修改 `frontend/src/components/inspection/InspectionFileSummary.vue`
  - 修改 `frontend/src/components/inspection/KnowledgeTogglePanel.vue`
- **测试**: 前端构建；如已有组件测试则补充状态覆盖。
- **验证**: 体检主流程组件在 dark/light 下文字可读、状态清晰。
- **安全**: 是（文件体检主流程 UI，仅样式和状态）
- **依赖**: 任务 14、任务 15

### 任务 22: 营销和静态页面接入 token (~4 min)

- **描述**: 营销页、帮助页、隐私页和条款页只做 token 接入，不全面重排版式。
- **文件**:
  - 修改 `frontend/src/components/marketing/MarketingNavbar.vue`
  - 修改 `frontend/src/components/marketing/MarketingShell.vue`
  - 修改相关营销和静态页面样式
- **测试**: 前端构建。
- **验证**: 主题切换入口和全局主题一致。
- **安全**: 否
- **依赖**: 任务 15

### 任务 23: 更新 DESIGN.md 明暗主题规范 (~4 min)

- **描述**: 补充 Light Theme Extension 和 Theme Behavior，明确浅色主题、全局主题源和 token 使用规则。
- **文件**:
  - 修改 `DESIGN.md`
- **测试**: 文档自检。
- **验证**: 文档包含 light theme token 方向和全局主题一致性规则。
- **安全**: 否
- **依赖**: 任务 14、任务 15

### 任务 24: 增加 design:check 脚本和 baseline (~5 min)

- **描述**: 新增脚本扫描未知 hex 色值和未知 font-family，使用 baseline 防止新增违规。
- **文件**:
  - 新增 `frontend/scripts/check-design-tokens.mjs`
  - 新增 `frontend/scripts/design-token-baseline.json`
  - 修改 `frontend/package.json`
- **测试**: `cd frontend && npm run design:check`。
- **验证**: 核心迁移文件违规数下降，新增违规会失败。
- **安全**: 否
- **依赖**: 任务 20、任务 21、任务 22

### 任务 25: 后端专项验证和安全审查 (~5 min)

- **描述**: 运行后端专项测试、lint、配置三步验证和 security-review。
- **文件**: 无或仅修复发现的小问题。
- **验证**:
  - `cd backend && uv run pytest tests/test_file_storage_backend.py tests/test_history_stats_api.py tests/test_inspection_parse_async.py -q`
  - `cd backend && uv run ruff check`
  - `cd backend && uv run mypy app`
  - 配置 static/readback/live call 按 `AGENTS.md` 执行
- **安全**: 是（必须 security-review）
- **依赖**: 任务 1-13

### 任务 26: 前端专项验证和截图验收 (~5 min)

- **描述**: 运行前端构建、主题检查、设计检查，并用浏览器截图验证核心页面 dark/light。
- **文件**: 无或仅修复发现的小问题。
- **验证**:
  - `cd frontend && npm run build`
  - `cd frontend && npm run test:routes`
  - `cd frontend && npm run design:check`
  - 本地启动后检查统计页、设置页、历史页、体检台 dark/light 截图
- **安全**: 否
- **依赖**: 任务 14-24

### 任务 27: 最终集成验证和变更影响检查 (~5 min)

- **描述**: 汇总后端、前端、迁移、设计检查结果，运行 GitNexus detect changes，确认变更影响符合计划。
- **文件**: 无或仅修复发现的小问题。
- **验证**:
  - `cd backend && uv run alembic heads`
  - `cd backend && uv run pytest -q`
  - `cd frontend && npm run build`
  - `cd frontend && npm run design:check`
  - `npx gitnexus detect-changes`
- **安全**: 是（最终安全和影响复核）
- **依赖**: 任务 25、任务 26

## 执行状态

- [x] 任务 1：固定存储模式测试契约
- [x] 任务 2：增加 STORAGE_BACKEND 配置
- [x] 任务 3：改造 file_storage 显式后端判断
- [x] 任务 4：增加 OSS 生产配置校验
- [x] 任务 5：统一存储错误映射到上传 API
- [x] 任务 6：创建 InspectionRecord.status 迁移测试
- [x] 任务 7：新增 InspectionRecord.status 模型和迁移
- [x] 任务 8：更新 pending 记录创建状态
- [x] 任务 9：更新同步体检完成/失败状态
- [x] 任务 10：更新 worker 体检完成/失败状态
- [x] 任务 11：固定新统计契约测试
- [x] 任务 12：实现数据库聚合统计接口
- [x] 任务 13：清理或隔离进程内统计缓存
- [x] 任务 14：定义前端主题 token 基线
- [x] 任务 15：统一主题 API 和持久化行为
- [x] 任务 16：移除登录/注册局部主题源
- [x] 任务 17：改造统计页新契约和错误态
- [x] 任务 18：统一 app shell footer 贴底
- [x] 任务 19：迁移顶栏和 footer 到 token
- [x] 任务 20：迁移核心工作台页面 token
- [x] 任务 21：迁移体检弹窗和报告组件 token
- [x] 任务 22：营销和静态页面接入 token
- [x] 任务 23：更新 DESIGN.md 明暗主题规范
- [x] 任务 24：增加 design:check 脚本和 baseline
- [x] 任务 25：后端专项验证和安全审查
- [x] 任务 26：前端专项验证和截图验收
- [x] 任务 27：最终集成验证和变更影响检查

## 并行机会

- 任务 1-5 存储止血可以先行，完成后即可局部验证 `/inspection/parse`。
- 任务 6-13 统计链路依赖数据库迁移，可与任务 14-16 主题基础并行。
- 任务 20 和任务 21 可在 token 与主题 API 稳定后并行。
- 任务 23 可与前端迁移并行，但最终内容要反映实际 token 命名。
- 任务 25 和任务 26 可并行，任务 27 必须等待两者完成。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| `STORAGE_BACKEND` 默认 local 与某些已有 OSS 数据环境冲突 | 低 | 中 | 设计已明确不做历史迁移，需要 OSS 数据的环境显式配置 `STORAGE_BACKEND=oss` |
| 统计契约破坏旧前端 | 中 | 中 | 当前无真实用户，前后端同版本切换；测试锁定新契约 |
| `InspectionRecord.status` 迁移误判历史数据 | 低 | 中 | 迁移测试覆盖典型历史状态，当前无真实用户降低风险 |
| 统计 join 或聚合性能不足 | 低 | 中 | 增加 `(user_id, created_at)`、`(user_id, project_id, created_at)` 等索引，后续按查询计划裁剪 |
| 主题 token 迁移引发大面积视觉回归 | 中 | 中 | 先建 token，再迁移核心页面，最后截图验收 dark/light |
| design:check 初次过严阻塞非核心页面 | 中 | 低 | 使用 baseline 策略，先防新增违规，再分批收敛 |
| 配置或错误日志泄露 OSS 信息 | 低 | 高 | 存储错误统一转换，security-review 检查日志和响应脱敏 |
| 本地 PostgreSQL 不可用导致后端测试失败 | 中 | 中 | 明确记录环境阻塞；优先运行不依赖 DB 的单元测试，DB 测试需本地测试库就绪 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
| --- | --- | --- |
| 后端单元 | 存储模式、路径防护、OSS 错误转换 | 存储后端选择和错误脱敏 |
| 后端迁移 | `InspectionRecord.status` 字段、约束、历史映射 | 数据模型稳定 |
| 后端 API | `/inspection/parse`、`/inspection/stats/history` | 上传可用性、真实统计和用户隔离 |
| Worker | 异步体检完成/失败状态同步 | 记录状态准确 |
| 前端逻辑 | 主题持久化、system 模式、统计错误态 | 全局主题和统计状态 |
| 前端构建 | `npm run build`、`npm run test:routes` | 路由和生产构建 |
| 设计检查 | `npm run design:check` | 防止新增未知颜色和字体 |
| 视觉验收 | 核心页面 dark/light 截图 | 文字可读、footer 贴底、主题一致 |

## 执行顺序建议

先执行任务 1-5 恢复文档体检可用性，再执行任务 6-13 完成数据库统计真实化。随后执行任务 14-24 做主题和设计规范落地，最后执行任务 25-27 做安全、构建、截图和影响范围收口。

下一步建议运行 `$execute-plans 1`，从“固定存储模式测试契约”开始。
