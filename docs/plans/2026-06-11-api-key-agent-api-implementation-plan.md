# API Key 与 Agent API 实施计划

## 总览

本计划基于最新设计文档 `docs/designs/2026-06-11-api-key-agent-api-design.md`，目标是新增用户级 API Key 管理、专用 `/api/v1/agent/*` 外部调用入口，以及 Arq + Redis 异步任务骨架。实现策略为：先落库和核心安全工具，再补 Web 管理 API 与前端交互，随后实现 Agent API 授权、Job 入队和 Worker 任务，最后用后端 API/Worker 测试与前端构建验证闭环。

关键约束：Web JWT 与 API Key 认证必须分离；完整 API Key 默认不在列表返回；显示/复制完整 Key 需要前端二次确认；后端每次返回完整 Key 必须更新 `last_viewed_at`；Agent 长耗时任务首期必须经 `agent_jobs` 记录和 Arq 队列入口。

## 前置准备

- [ ] 确认设计文档已批准：`docs/designs/2026-06-11-api-key-agent-api-design.md`
- [ ] 检查当前工作树，避免覆盖他人改动：`git status --short`
- [ ] 后端基线：`cd backend && uv run pytest`
- [ ] 前端基线：`cd frontend && npm run build`
- [ ] 影响分析：实现前按 AGENTS 要求，对将修改的核心符号运行 `gitnexus_impact`，至少覆盖 `get_current_user`、`get_settings_overview`、`app.include_router`、`SettingsPage` 等入口/共享符号
- [ ] 确认环境变量方案：新增 `API_KEY_ENCRYPTION_SECRET`、Redis 连接配置不应破坏现有本地测试

## 任务列表

### 任务 1: 添加 API Key 与 Agent Job 数据模型测试 (~4 min)
- **描述**: 先写失败测试，验证 `ApiKey` 与 `AgentJob` 模型字段、默认状态、JSON scopes/payload 能正常建表和读写。
- **文件**:
  - 创建 `backend/tests/test_api_key_models.py`
- **测试**: 使用测试库 session 创建用户、API Key、AgentJob，断言 `status=active/queued`、`scopes`、`job_id`、时间字段存在。
- **验证**: `cd backend && uv run pytest tests/test_api_key_models.py` 初始失败，失败点指向模型缺失。
- **依赖**: 无

### 任务 2: 实现后端模型与迁移 (~5 min)
- **描述**: 在统一模型文件中新增 `ApiKey`、`AgentJob` SQLAlchemy 模型，并新增 Alembic 迁移创建 `api_keys`、`agent_jobs` 表和必要索引/外键。
- **文件**:
  - 修改 `backend/models/knowledge.py`
  - 创建 `backend/alembic/versions/008_add_api_keys_and_agent_jobs.py`
- **测试**: 复用任务 1 测试。
- **验证**: `cd backend && uv run pytest tests/test_api_key_models.py` 通过。
- **依赖**: 任务 1

### 任务 3: 添加 API Key scope/模板常量测试 (~3 min)
- **描述**: 写测试覆盖 scope 枚举、模板映射、隐藏高风险 scope 的首期策略。
- **文件**:
  - 创建 `backend/tests/test_api_key_scopes.py`
- **测试**: 断言 `mcp_readonly`、`cli_inspection`、`agent_automation`、`custom` 模板返回设计文档中的 scopes；`records:delete` 不在默认可选列表。
- **验证**: `cd backend && uv run pytest tests/test_api_key_scopes.py` 初始失败。
- **依赖**: 无

### 任务 4: 实现 scope 模板常量与校验工具 (~4 min)
- **描述**: 新增 API Key scopes、client type、scope template 常量和模板解析函数，供服务层和路由复用。
- **文件**:
  - 创建 `backend/core/api_key_scopes.py`
- **测试**: 复用任务 3 测试。
- **验证**: `cd backend && uv run pytest tests/test_api_key_scopes.py` 通过。
- **依赖**: 任务 3

### 任务 5: 添加 API Key 加密/hash 工具测试 (~4 min)
- **描述**: 写单元测试覆盖 Key 生成格式、hash 验证、加密解密、错误密钥配置处理。
- **文件**:
  - 创建 `backend/tests/test_api_key_crypto.py`
- **测试**: 断言生成值以 `glzd_live_` 开头；同一明文 hash 可验证；密文不等于明文；解密后等于原 Key；缺少 `API_KEY_ENCRYPTION_SECRET` 时抛出明确错误。
- **验证**: `cd backend && uv run pytest tests/test_api_key_crypto.py` 初始失败。
- **依赖**: 无

### 任务 6: 实现 API Key 加密/hash 工具 (~5 min)
- **描述**: 新增安全工具，使用服务端密钥可逆加密完整 Key，并保存认证 hash。避免日志输出明文 Key。
- **文件**:
  - 创建 `backend/core/api_key_crypto.py`
  - 修改 `backend/core/config.py`
- **测试**: 复用任务 5 测试。
- **验证**: `cd backend && uv run pytest tests/test_api_key_crypto.py` 通过。
- **依赖**: 任务 5

### 任务 7: 添加 API Key 服务层测试 (~5 min)
- **描述**: 写服务层测试覆盖创建、列表脱敏、查看 secret 更新 `last_viewed_at`、更新 scopes/过期时间、撤销。
- **文件**:
  - 创建 `backend/tests/test_api_key_service.py`
- **测试**: 使用测试 DB 调用服务方法；断言列表不返回完整 Key；撤销后 `status=revoked` 且 `revoked_at` 非空。
- **验证**: `cd backend && uv run pytest tests/test_api_key_service.py` 初始失败。
- **依赖**: 任务 2、4、6

### 任务 8: 实现 API Key 服务层 (~5 min)
- **描述**: 封装 API Key 业务操作，包括生成完整 Key、保存 hash/encrypted_key、脱敏展示、scope 模板处理、用户归属校验。
- **文件**:
  - 创建 `backend/services/api_key_service.py`
- **测试**: 复用任务 7 测试。
- **验证**: `cd backend && uv run pytest tests/test_api_key_service.py` 通过。
- **依赖**: 任务 7

### 任务 9: 添加 Web API Key 管理接口测试 (~5 min)
- **描述**: 写 API 测试覆盖 JWT 下创建/列表/查看 secret/更新/撤销 API Key。
- **文件**:
  - 创建 `backend/tests/test_api_key_settings_api.py`
- **测试**: 使用现有认证测试夹具或登录流程拿 JWT；断言 `POST /settings/api-keys` 仅创建响应返回完整 Key，`GET /settings/api-keys` 不返回完整 Key，`GET /settings/api-keys/{id}/secret` 更新查看时间。
- **验证**: `cd backend && uv run pytest tests/test_api_key_settings_api.py` 初始失败。
- **依赖**: 任务 8

### 任务 10: 实现 Web API Key 管理路由 (~5 min)
- **描述**: 在设置路由新增 API Key 管理端点和 Pydantic 请求/响应模型，复用 JWT `get_current_user`。
- **文件**:
  - 修改 `backend/routers/settings.py`
- **测试**: 复用任务 9 测试，并回归现有设置测试。
- **验证**: `cd backend && uv run pytest tests/test_api_key_settings_api.py tests/test_settings_api.py` 通过。
- **依赖**: 任务 9

### 任务 11: 添加 API Key 认证依赖测试 (~4 min)
- **描述**: 写测试覆盖 Bearer API Key 认证：缺失、无效、撤销、过期、有效更新 `last_used_at`。
- **文件**:
  - 创建 `backend/tests/test_agent_auth_deps.py`
- **测试**: 直接调用依赖工具或通过临时测试路由验证 HTTP 状态和错误码：`invalid_api_key`、`api_key_revoked`、`api_key_expired`。
- **验证**: `cd backend && uv run pytest tests/test_agent_auth_deps.py` 初始失败。
- **依赖**: 任务 8

### 任务 12: 实现 API Key 认证与 scope 依赖 (~5 min)
- **描述**: 新增 Agent API 专用依赖，解析 `Authorization: Bearer glzd_live_xxx`，校验 hash/status/expires/scopes，并提供 `require_api_scope(scope)`。
- **文件**:
  - 创建 `backend/core/agent_auth.py`
- **测试**: 复用任务 11 测试。
- **验证**: `cd backend && uv run pytest tests/test_agent_auth_deps.py` 通过。
- **依赖**: 任务 11

### 任务 13: 添加 Redis/Arq 配置测试 (~3 min)
- **描述**: 写测试确认 Redis 配置可从 settings 读取，WorkerSettings 注册任务名和参数符合设计。
- **文件**:
  - 创建 `backend/tests/test_agent_worker_config.py`
- **测试**: 断言 `job_timeout=600`、`max_tries=3`、`keep_result=3600`，函数列表包含三个任务名。
- **验证**: `cd backend && uv run pytest tests/test_agent_worker_config.py` 初始失败。
- **依赖**: 无

### 任务 14: 实现 Redis 封装与 Worker 配置骨架 (~5 min)
- **描述**: 新增 Redis settings/create_pool 封装、WorkerSettings、任务函数占位入口，确保 Arq 启动路径固定。
- **文件**:
  - 创建 `backend/core/redis.py`
  - 创建 `backend/workers/__init__.py`
  - 创建 `backend/workers/config.py`
  - 创建 `backend/workers/tasks.py`
  - 修改 `backend/core/config.py`
  - 如依赖未声明，修改 `backend/pyproject.toml`
- **测试**: 复用任务 13 测试。
- **验证**: `cd backend && uv run pytest tests/test_agent_worker_config.py` 通过；命令 `cd backend && uv run python -c "from workers.config import WorkerSettings; print(WorkerSettings.job_timeout)"` 输出 600。
- **依赖**: 任务 13

### 任务 15: 添加 Agent Job 服务层测试 (~5 min)
- **描述**: 写服务测试覆盖创建 job、入队失败回滚/503 映射、查询所有权、状态更新、完成/失败状态流转。
- **文件**:
  - 创建 `backend/tests/test_agent_job_service.py`
- **测试**: mock Arq pool 的 `enqueue_job`；断言创建 inspect/parse/knowledge_upload job 后数据库状态为 `queued`，非所属用户查询返回 None 或抛业务错误。
- **验证**: `cd backend && uv run pytest tests/test_agent_job_service.py` 初始失败。
- **依赖**: 任务 2、14

### 任务 16: 实现 Agent Job 服务层 (~5 min)
- **描述**: 封装创建 job、查询 job、更新进度、完成、失败、入队逻辑；输入 payload 仅保存非敏感元信息。
- **文件**:
  - 创建 `backend/services/agent_job_service.py`
- **测试**: 复用任务 15 测试。
- **验证**: `cd backend && uv run pytest tests/test_agent_job_service.py` 通过。
- **依赖**: 任务 15

### 任务 17: 添加 Agent API 路由测试 (~5 min)
- **描述**: 写 API 测试覆盖 `/api/v1/agent/me`、创建 inspect/parse job、查询 job、无 scope 403、非所属 job 404。
- **文件**:
  - 创建 `backend/tests/test_agent_api.py`
- **测试**: 使用任务 8 服务创建不同 scope 的 API Key；mock 入队；断言错误 detail 使用设计文档错误码。
- **验证**: `cd backend && uv run pytest tests/test_agent_api.py` 初始失败。
- **依赖**: 任务 12、16

### 任务 18: 实现 Agent API 基础路由并注册 (~5 min)
- **描述**: 新增 `/api/v1/agent` 路由，先实现 me、inspect/parse job 创建、job 查询，返回标准 job 状态结构。
- **文件**:
  - 创建 `backend/routers/agent.py`
  - 修改 `backend/main.py`
- **测试**: 复用任务 17 测试。
- **验证**: `cd backend && uv run pytest tests/test_agent_api.py` 通过。
- **依赖**: 任务 17

### 任务 19: 添加 Agent records/knowledge 只读接口测试 (~5 min)
- **描述**: 写测试覆盖历史记录查询、报告详情、知识库检索接口的 API Key scope 授权与用户隔离。
- **文件**:
  - 扩展 `backend/tests/test_agent_api.py`
- **测试**: `inspection:read` 可访问 records；无 scope 返回 403；`knowledge:read` 可检索法规片段；非本用户记录不可访问。
- **验证**: `cd backend && uv run pytest tests/test_agent_api.py` 对新增用例初始失败。
- **依赖**: 任务 18

### 任务 20: 实现 Agent records 与 knowledge search 接口 (~5 min)
- **描述**: 在 Agent 路由中桥接现有 InspectionRecord 查询与知识库检索服务，保持专用认证，不复用 Web JWT。
- **文件**:
  - 修改 `backend/routers/agent.py`
- **测试**: 复用任务 19 测试，并回归 `tests/test_inspection_api.py`、`tests/test_knowledge_api.py`。
- **验证**: `cd backend && uv run pytest tests/test_agent_api.py tests/test_inspection_api.py tests/test_knowledge_api.py` 通过。
- **依赖**: 任务 19

### 任务 21: 添加 Worker 任务状态流转测试 (~5 min)
- **描述**: 写测试直接调用 `inspect_document_task`、`parse_document_task`、`knowledge_upload_task`，mock 实际转换/审查/入库逻辑，验证 job 状态流转。
- **文件**:
  - 创建 `backend/tests/test_agent_worker_tasks.py`
- **测试**: 成功时 `queued -> running -> succeeded` 且 progress 到 100；异常时 `failed` 且写入 `error_message`。
- **验证**: `cd backend && uv run pytest tests/test_agent_worker_tasks.py` 初始失败。
- **依赖**: 任务 16

### 任务 22: 实现 Worker 任务最小闭环 (~5 min)
- **描述**: 实现三个 Arq 任务函数的状态流转；审查任务集成现有 markdown 转换、知识召回和 `run_inspection` 的最小可测路径；解析/知识上传任务先完成设计范围内骨架。
- **文件**:
  - 修改 `backend/workers/tasks.py`
  - 视需要修改 `backend/services/agent_job_service.py`
- **测试**: 复用任务 21 测试。
- **验证**: `cd backend && uv run pytest tests/test_agent_worker_tasks.py` 通过。
- **依赖**: 任务 21

### 任务 23: 添加前端 API Key service 函数 (~3 min)
- **描述**: 增加设置页调用的 API Key 管理 service 方法，保持与现有 `fetchWithAuth`/`parseResponse` 风格一致。
- **文件**:
  - 修改 `frontend/src/services/settingsApi.js`
- **测试**: 若项目已有前端单测则补 service 测试；否则通过构建和页面手测验证。
- **验证**: `cd frontend && npm run build` 不因导出缺失失败。
- **依赖**: 任务 10

### 任务 24: 添加设置页 API Key 标签与状态 (~4 min)
- **描述**: 在设置页新增 `[API Key]` 标签及状态变量，挂载时/切换时加载 key 列表。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 前端构建；手动确认标签出现、列表 loading/error 状态不影响其他三个设置标签。
- **验证**: `cd frontend && npm run build` 通过。
- **依赖**: 任务 23

### 任务 25: 实现 API Key 创建表单与列表展示 (~5 min)
- **描述**: 在设置页实现 Key 名称、client type、模板/自定义 scopes、过期时间表单；列表展示脱敏 key、状态、scopes、last_used_at。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 前端构建；手动创建后完整 Key 只在创建结果区出现，列表仍脱敏。
- **验证**: `cd frontend && npm run build` 通过；浏览器创建 key 后能看到 `glzd_live_` 完整值提示。
- **依赖**: 任务 24

### 任务 26: 实现显示/复制/撤销交互 (~5 min)
- **描述**: 实现眼睛图标二次确认后调用 secret 接口、再次点击本地隐藏、复制前二次确认、撤销按钮调用 DELETE。
- **文件**:
  - 修改 `frontend/src/pages/SettingsPage.vue`
- **测试**: 前端构建；手测确认未加载完整 Key 时复制会先确认并请求 secret，撤销后状态变为 revoked。
- **验证**: `cd frontend && npm run build` 通过。
- **依赖**: 任务 25

### 任务 27: 后端错误码与安全回归收口 (~4 min)
- **描述**: 统一 Agent API 错误 detail，确认 API Key 不能访问账号安全接口，完整 Key 不进入列表/日志/异常。
- **文件**:
  - 修改 `backend/core/agent_auth.py`
  - 修改 `backend/routers/agent.py`
  - 修改 `backend/routers/settings.py`
  - 扩展相关后端测试
- **测试**: 新增/扩展无效 key、撤销、过期、scope 不足、列表不含 `encrypted_key/full_key` 用例。
- **验证**: `cd backend && uv run pytest tests/test_api_key_settings_api.py tests/test_agent_auth_deps.py tests/test_agent_api.py` 通过。
- **依赖**: 任务 10、18、20

### 任务 28: 文档与运行说明更新 (~3 min)
- **描述**: 更新后端/项目文档，记录新增环境变量、Worker 启动命令、Agent API 认证示例。
- **文件**:
  - 修改 `README.md` 或 `backend/README.md`（按项目现有文档位置选择）
  - 如有必要，修改 `.env.example`
- **测试**: 文档无需单测。
- **验证**: 文档包含 `API_KEY_ENCRYPTION_SECRET` 和 `cd backend && uv run arq workers.config.WorkerSettings`。
- **依赖**: 任务 14、18

### 任务 29: 全量验证与影响检查 (~5 min)
- **描述**: 运行后端/前端验证命令，并使用 GitNexus 检查改动影响范围。
- **文件**: 无业务文件修改
- **测试**:
  - `cd backend && uv run pytest`
  - `cd frontend && npm run build`
  - 如存在 lint/typecheck 脚本，运行 `cd frontend && npm run lint`、后端对应 lint/type check
- **验证**: 所有命令通过；`gitnexus_detect_changes(scope="all", repo="Goulong-Zhaodan")` 显示影响范围符合预期。
- **依赖**: 全部实现任务

## 并行机会

- 任务 1/3/5/13 可并行编写：分别覆盖模型、scope、crypto、worker 配置。
- 任务 2 与任务 4/6 可在任务 1/3/5 完成后并行实现，互相依赖较弱。
- 任务 9/11/15 可在任务 8、12、14 基础具备后并行补测试。
- 任务 23 可在后端 Web API 路由契约稳定后与任务 17/19 并行。
- 任务 24-26 前端实现可与任务 21-22 Worker 状态流转并行。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 完整 API Key 泄露到列表响应、日志或测试快照 | 中 | 高 | 后端响应模型显式区分 `full_key` 仅创建/secret 返回；测试断言列表无明文/密文 |
| `API_KEY_ENCRYPTION_SECRET` 配置不兼容本地/CI | 中 | 中 | 测试中 monkeypatch 固定密钥；文档和 `.env.example` 明确配置；缺失时报明确错误 |
| API Key 认证误复用 Web JWT 能力 | 中 | 高 | `core/agent_auth.py` 独立依赖；Agent 路由只使用 `require_api_scope`；测试覆盖 API Key 不能访问账号安全接口 |
| Arq/Redis 依赖导致测试不稳定 | 中 | 中 | 服务层 mock `enqueue_job`；Worker 任务直接调用；仅配置层验证启动参数 |
| 异步审查任务集成现有体检链路时输入文件保存边界不清 | 中 | 中 | 首期 `input_payload` 只存非敏感元信息，上传文件走既有 file storage；Worker 测试 mock 转换/审查 |
| 前端复制 API 受浏览器权限限制 | 低 | 中 | 使用 `navigator.clipboard` 并提供失败提示；手测 HTTPS/本地场景 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 后端单元测试 | scope 模板、Key 生成、hash 校验、加解密、服务层脱敏/撤销 | API Key 安全基础逻辑 100% 覆盖关键分支 |
| 后端 API 测试 | `/settings/api-keys*`、`/api/v1/agent/*` 授权与错误码 | 创建/列表/secret/撤销、scope 不足、job 创建/查询 |
| Worker 测试 | mock Arq 入队、直接调用任务函数 | queued/running/succeeded/failed 状态流转 |
| 前端构建/手测 | 设置页 API Key 标签、创建、显示/隐藏、复制、撤销 | 交互符合二次确认与默认脱敏要求 |
| 回归测试 | 现有 auth/settings/inspection/knowledge 测试 | JWT Web 流程和原有体检/知识库能力不受影响 |

## 最终验收清单

- [ ] `POST /settings/api-keys` 能创建 Key，并只在创建响应返回完整 Key
- [ ] `GET /settings/api-keys` 仅返回脱敏 Key 和元数据
- [ ] `GET /settings/api-keys/{id}/secret` 需 JWT 且更新 `last_viewed_at`
- [ ] 撤销/过期/无效 API Key 返回设计文档错误码
- [ ] `require_api_scope` 能正确拦截 scope 不足
- [ ] `/api/v1/agent/jobs/inspect` 创建 `agent_jobs` 记录并入队，立即返回 `job_id`
- [ ] Worker 任务能将 job 更新到 succeeded/failed
- [ ] 设置页支持显示/隐藏完整 Key、复制完整 Key、撤销 Key，且显示/复制前有二次确认
- [ ] `cd backend && uv run pytest` 通过
- [ ] `cd frontend && npm run build` 通过
