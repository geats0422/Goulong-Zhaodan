# 照胆自适应 MinerU 文档处理链路实施计划

## 总览

以统一解析服务和持久化后台任务为核心，先建立可测试的文件路由与质量检测，再接入 MinerU、PageIndex、体检/知识库 API 和前端进度。所有行为变更遵循 TDD，现有同步接口与新后台链路在同一发布中完成前后端切换。

## 前置准备

- [x] 设计已获用户批准
- [x] 已确认不支持直接图片上传
- [x] 已确认后台任务与进度方案
- [x] 已确认 PPTX/XLSX 失败时提示转 PDF
- [x] 已分析体检、知识库、Agent Job、ARQ Worker 和前端调用链
- [x] 已执行 API 影响分析：体检文件影响 46 条执行流，知识库上传影响较低

## 任务列表

### 任务 1: 固定文件路由和质量判定契约
- **描述**: 先写纯函数测试，覆盖 TXT/MD、Word、文本 PDF、扫描/混合 PDF、PPTX/XLSX 的解析路由。
- **文件**:
  - 新增 `backend/unit_tests/test_document_quality.py`
  - 新增 `backend/unit_tests/test_document_router.py`
- **测试**: 文本长度、可打印比例、乱码、占位符和 PDF 有效文本页比例。
- **验证**: 新测试因实现缺失而失败。
- **依赖**: 无

### 任务 2: 实现质量检测与解析路由
- **描述**: 实现集中配置的 Markdown 质量检测和 PDF 文本层分类，输出明确的解析决策。
- **文件**:
  - 新增 `backend/app/services/document_quality.py`
  - 新增 `backend/app/services/document_router.py`
  - 修改 `backend/app/core/config.py`
- **测试**: 任务 1 转绿。
- **验证**: 扫描/混合 PDF 不会被少量乱码误判为本地解析成功。
- **依赖**: 任务 1

### 任务 3: 固定 MinerU 客户端契约
- **描述**: 复制文衡已验证流程的行为测试，覆盖上传申请、PUT、轮询、ZIP Markdown 提取、超时和错误脱敏。
- **文件**:
  - 新增 `backend/tests/test_mineru_client.py`
- **测试**: 全部 HTTP 使用 Mock，不调用真实 MinerU。
- **验证**: 新测试先失败。
- **依赖**: 无

### 任务 4: 实现照胆 MinerU 客户端
- **描述**: 在照胆内独立封装 MinerU API v4，并将配置加入生产校验。
- **文件**:
  - 新增 `backend/app/lib/mineru/__init__.py`
  - 新增 `backend/app/lib/mineru/client.py`
  - 修改 `backend/app/core/config.py`
  - 修改 `backend/.env.example`、`backend/env.example`
- **测试**: 任务 3 转绿；配置静态检查和示例回读通过。
- **验证**: 日志、异常和响应均不包含 Token 或预签名 URL。
- **依赖**: 任务 3

### 任务 5: 建立统一解析服务
- **描述**: 编排直接读取、MarkItDown、质量检测、MinerU 兜底和 Markdown 规范化。
- **文件**:
  - 新增 `backend/app/services/document_parser.py`
  - 修改 `backend/app/services/markdown_converter.py`
  - 新增 `backend/tests/test_document_parser.py`
- **测试**: Word 兜底、PDF 分流、PPTX/XLSX 提示、MD/TXT 直读。
- **验证**: 解析结果包含引擎、哈希、质量指标和 Markdown。
- **依赖**: 任务 2、任务 4

### 任务 6: 设计任务表和迁移
- **描述**: 先写模型/迁移测试，再新增持久化文档处理任务和索引。
- **文件**:
  - 新增 `backend/app/models/document_job.py`
  - 修改 `backend/app/models/__init__.py`
  - 新增 `backend/alembic/versions/019_document_processing_jobs.py`
  - 新增 `backend/tests/test_document_job_model.py`
  - 新增 `backend/tests/test_document_job_migration.py`
- **测试**: 状态、阶段、所有权、内容哈希、重试和资源关联约束。
- **验证**: Alembic 只有一个 head，upgrade/downgrade 测试通过。
- **依赖**: 无

### 任务 7: 实现任务服务和阶段续跑
- **描述**: 创建、查询、更新、失败、重试和按阶段恢复；同用户相同哈希可复用成功 Markdown。
- **文件**:
  - 新增 `backend/app/services/document_job_service.py`
  - 新增 `backend/tests/test_document_job_service.py`
- **测试**: 所有权隔离、幂等、重试次数、Markdown 续跑、不重复 MinerU。
- **验证**: 失败任务重试时从最后有效产物继续。
- **依赖**: 任务 5、任务 6

### 任务 8: 新增登录用户任务 API
- **描述**: 提供状态查询和失败任务重试接口，统一响应字段。
- **文件**:
  - 新增 `backend/app/api/v1/document_jobs.py`
  - 修改 `backend/app/api/router.py`
  - 新增 `backend/tests/test_document_job_api.py`
- **测试**: 认证、跨用户 404/403、状态响应、重试限制和错误脱敏。
- **验证**: API shape 与前端轮询契约一致。
- **依赖**: 任务 7

### 任务 9: 实现 ARQ 文档处理 Worker
- **描述**: Worker 执行解析、Markdown 持久化、PageIndex、体检审查和状态更新。
- **文件**:
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/app/workers/config.py`
  - 新增 `backend/tests/test_document_worker.py`
- **测试**: 各阶段进度、异常转失败、重跑幂等、知识库和体检分支。
- **验证**: Worker 重启后任务可恢复，完成/失败状态稳定。
- **依赖**: 任务 7

### 任务 10: 切换体检上传 API
- **描述**: 将 `/inspection/parse` 改为保存原文件、创建任务并返回 202；体检审查消费已索引的 Markdown 结构。
- **文件**:
  - 修改 `backend/app/api/v1/inspection.py`
  - 修改 `backend/app/services/inspection_runner.py`
  - 修改 `backend/tests/test_inspection_api.py`
- **测试**: 文件校验、202 契约、任务关联、完成后体检、旧同步解析不再被调用。
- **验证**: PDF/Word 不能绕过统一解析服务直达 DeepSeek。
- **依赖**: 任务 8、任务 9

### 任务 11: 切换知识库上传 API
- **描述**: 将 `/knowledge/upload` 改为 202 后台任务，保持 `DocumentVersion` 状态兼容。
- **文件**:
  - 修改 `backend/app/api/v1/knowledge.py`
  - 修改 `backend/app/services/knowledge_ingestion.py`
  - 修改 `backend/tests/test_knowledge_api.py` 或现有知识库测试
- **测试**: pending、converting、indexing、completed、failed 状态同步。
- **验证**: 上传请求不等待 MinerU；PageIndex 节点正确关联版本。
- **依赖**: 任务 8、任务 9

### 任务 12: 统一 Agent API 解析路径
- **描述**: Agent 同步和异步解析复用统一解析服务，保持现有 Agent Job 响应兼容。
- **文件**:
  - 修改 `backend/app/api/v1/agent.py`
  - 修改 `backend/app/workers/tasks.py`
  - 修改 `backend/tests/test_agent_api.py`
- **测试**: 现有同步/异步契约、扫描 PDF 分流和错误映射。
- **验证**: Agent、Web 体检和知识库不再维护三套解析逻辑。
- **依赖**: 任务 5、任务 9

### 任务 13: 实现前端任务 API 与轮询器
- **描述**: 封装上传、状态轮询、重试和清理逻辑。
- **文件**:
  - 新增 `frontend/src/services/documentJobApi.js`
  - 修改 `frontend/src/services/inspectionApi.js`
  - 新增轮询器测试
- **测试**: 完成/失败停止、组件卸载清理、网络错误退避。
- **验证**: 不产生重复定时器或页面卸载后的请求。
- **依赖**: 任务 8、任务 10

### 任务 14: 更新体检进度与失败弹窗
- **描述**: 在体检弹窗中展示解析、索引、审查阶段，失败时可重试原任务。
- **文件**:
  - 修改 `frontend/src/components/inspection/InspectionReviewModal.vue`
  - 修改 `frontend/src/components/inspection/InspectionFileSummary.vue`
  - 新增/修改组件测试
- **测试**: 阶段显示、MinerU 标识、失败弹窗、重试、完成后进入报告。
- **验证**: 页面刷新或重新打开能恢复任务状态。
- **依赖**: 任务 13

### 任务 15: 更新知识库上传与状态
- **描述**: 上传后关闭阻塞状态，显示后台进度和失败重试入口。
- **文件**:
  - 修改 `frontend/src/pages/KnowledgeBasePage.vue`
  - 新增/修改页面测试
- **测试**: 202 响应、列表刷新、失败提示、转 PDF 提示。
- **验证**: 知识库上传不会等待 MinerU 完成。
- **依赖**: 任务 11、任务 13

### 任务 16: 部署 Zhaodan Worker 与 MinerU 配置
- **描述**: 增加 Worker 服务、共享卷和 MinerU 环境变量。
- **文件**:
  - 修改 `Goulong-Wenheng/deploy/docker-compose.yml`
  - 修改 `Goulong-Wenheng/deploy/.env.production.example`
  - 如有需要修改 `Goulong-Wenheng/deploy/Dockerfile.zhaodan`
- **测试**: `docker compose config --quiet`、示例值安全回读。
- **验证**: 后端与 Worker 使用相同 Redis、数据库、存储和 MinerU 配置。
- **依赖**: 任务 9

### 任务 17: 综合验证和安全审查
- **描述**: 运行完整测试、构建、迁移、变更影响、安全和代码质量审查。
- **验证**:
  - 后端专项及完整测试
  - 前端路由检查和生产构建
  - Ruff、编译、Alembic 单 head
  - API shape 和所有权检查
  - 不存在 Token/预签名 URL 泄露
- **依赖**: 任务 10-16

### 任务 18: ECS 生产验证
- **描述**: 部署后执行三步验证和真实链路闭环。
- **验证**:
  - 静态：Compose config、迁移成功
  - 回读：后端/Worker 实际加载 MinerU 配置且不输出 Token
  - 真实调用：小型扫描 PDF → MinerU → Markdown → PageIndex → DeepSeek
  - 容器状态：后端 healthy、Worker 持续运行、nginx 正常
- **依赖**: 任务 17

## 并行机会

- 任务 1-2、任务 3-4、任务 6 可并行进行。
- 任务 14 和任务 15 可在任务 13 后并行。
- 任务 16 可与前端任务并行，但最终验证必须等待全部完成。

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 上传 API 响应由同步结果变为 202 | 高 | 高 | 前后端同版本发布，增加契约测试和旧 Agent API 回归 |
| MinerU 长轮询导致 Worker 堵塞 | 中 | 高 | 独立 Worker、并发限制、超时、任务状态持久化 |
| 扫描 PDF 误判为文本型 | 中 | 高 | 文本层检测和 Markdown 二次质量门禁 |
| 重试重复消耗 MinerU | 中 | 中 | 内容哈希、Markdown 持久化、阶段续跑 |
| 原文件/正文泄露 | 低 | 高 | 用户隔离存储、状态接口授权、日志脱敏 |
| Worker 与后端配置不一致 | 中 | 高 | Compose 同源环境变量、回读检查、启动校验 |
| 本地测试缺少 PostgreSQL/完整依赖 | 中 | 中 | Docker 测试环境和 ECS 迁移 dry-run |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
| --- | --- | --- |
| 纯单元 | 路由、质量、哈希、错误映射 | 所有分支 |
| 服务 | MarkItDown/MinerU/PageIndex 编排 | 关键路径 100% |
| API | 上传、状态、重试、用户隔离 | 所有新契约 |
| Worker | 阶段、幂等、恢复 | 成功与失败路径 |
| 前端 | 轮询、进度、弹窗、清理 | 用户主流程 |
| 生产 E2E | 扫描 PDF 完整链路 | 真实外部服务闭环 |
