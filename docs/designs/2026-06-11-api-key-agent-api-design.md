# API Key 与 Agent API 设计文档

## 目标

为后续 MCP、Skill、CLI、第三方 Agent 助理提供安全、可控、异步的调用入口。

## 用户场景

- 用户在设置页创建 API Key，选择用途模板或高级自定义权限。
- 用户将 API Key 配置到 MCP、Skill、CLI、OpenClaw、Hermes Agent、马维斯、阿里悟空等 Agent 助理。
- 外部工具通过 `/api/v1/agent/*` 调用句龙照胆能力，执行文档解析、智能审查、知识库检索、报告查询。
- 长耗时任务通过 Arq + Redis 异步执行，调用方用 `job_id` 轮询状态和结果。

## 核心决策

- API Key 是用户级访问令牌，归属具体用户。
- API Key 支持权限模板 + 高级自定义 scopes。
- 设置页 API Key 列表支持隐藏/显示完整 Key，以及一键复制完整 Key。
- 显示完整 Key 前需要二次确认。
- 完整 Key 使用服务端密钥可逆加密保存，同时保存 hash 用于认证。
- 外部调用不直接复用 Web API，而是使用专用 `/api/v1/agent/*`。
- API Key 管理等业务操作走同步 async/await。
- Agent API 的大文件解析、AI 审查、知识库上传入库走 Arq + Redis + Worker。
- Worker 启动方式固定为：`cd backend && uv run arq app.workers.config.WorkerSettings`。

## 权限模型

### Scopes

| Scope | 能力 |
| --- | --- |
| `profile:read` | 查询当前 API Key 用户、权限、配额 |
| `inspection:run` | 创建解析/审查任务，重审历史记录 |
| `inspection:read` | 查询审查历史、报告详情、下载 PDF |
| `knowledge:read` | 查询知识库概览、文档、节点、检索法规片段 |
| `knowledge:write` | 上传用户知识库、启停知识库文档 |
| `settings:write` | 管理违禁词等非账号安全设置，首期仅高级自定义可选 |
| `records:delete` | 删除历史记录，高风险，首期建议隐藏或不开放 |

### 权限模板

| 模板 | Scopes | 适用对象 |
| --- | --- | --- |
| MCP 只读 | `profile:read`, `inspection:read`, `knowledge:read` | MCP 查询上下文、历史报告、法规知识 |
| CLI 审查 | `profile:read`, `inspection:run`, `inspection:read`, `knowledge:read` | CLI 上传文件并生成报告 |
| Agent 自动化 | `profile:read`, `inspection:run`, `inspection:read`, `knowledge:read`, `knowledge:write` | Agent 可上传知识库并执行审查 |
| 高级自定义 | 用户手动选择 scopes | 高级用户和内部集成 |

## 数据模型

### `api_keys`

| 字段 | 说明 |
| --- | --- |
| `id` | 自增 ID |
| `user_id` | 归属用户 |
| `name` | Key 名称 |
| `client_type` | `mcp | cli | skill | agent | other` |
| `scope_template` | `mcp_readonly | cli_inspection | agent_automation | custom` |
| `scopes` | JSON array |
| `key_prefix` | 脱敏展示和快速定位用前缀 |
| `key_hash` | 认证校验用 hash |
| `encrypted_key` | 可逆加密后的完整 Key |
| `status` | `active | revoked` |
| `expires_at` | 过期时间，可为空 |
| `last_used_at` | 最近认证成功时间 |
| `last_viewed_at` | 最近查看完整 Key 时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `revoked_at` | 撤销时间 |

### `agent_jobs`

| 字段 | 说明 |
| --- | --- |
| `id` | 自增 ID |
| `job_id` | `job_` 开头公开 ID |
| `user_id` | 归属用户 |
| `api_key_id` | 创建任务的 API Key |
| `job_type` | `inspect | parse | knowledge_upload` |
| `status` | `queued | running | succeeded | failed | cancelled` |
| `progress` | 0-100 |
| `message` | 当前阶段说明 |
| `input_payload` | 非敏感输入元信息 |
| `result_payload` | 结果，如 `record_id`、摘要 |
| `error_message` | 失败原因 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `finished_at` | 完成时间 |

## 接口设计

### Web API Key 管理接口

| 接口 | 能力 | 认证 |
| --- | --- | --- |
| `GET /settings/api-keys` | 列出当前用户 API Keys | JWT |
| `POST /settings/api-keys` | 创建 API Key | JWT |
| `GET /settings/api-keys/{id}/secret` | 二次确认后查看完整 Key | JWT |
| `PATCH /settings/api-keys/{id}` | 重命名、修改过期时间、调整 scopes | JWT |
| `DELETE /settings/api-keys/{id}` | 撤销 API Key | JWT |

### Agent API

| 接口 | 能力 | Scope |
| --- | --- | --- |
| `GET /api/v1/agent/me` | 查询当前 API Key 身份、权限、配额 | `profile:read` |
| `POST /api/v1/agent/jobs/inspect` | 创建异步审查任务 | `inspection:run` |
| `POST /api/v1/agent/jobs/parse` | 创建异步解析任务 | `inspection:run` |
| `GET /api/v1/agent/jobs/{job_id}` | 查询任务状态、进度、结果 | 任务所有者 |
| `GET /api/v1/agent/records` | 查询历史记录 | `inspection:read` |
| `GET /api/v1/agent/records/{id}` | 查询报告详情 | `inspection:read` |
| `GET /api/v1/agent/records/{id}/report.pdf` | 下载 PDF 报告 | `inspection:read` |
| `POST /api/v1/agent/knowledge/search` | 检索法规知识片段 | `knowledge:read` |
| `POST /api/v1/agent/knowledge/upload` | 创建知识库上传任务 | `knowledge:write` |

## API Key 展示与复制交互

- 列表默认显示脱敏 Key：`glzd_live_ab12••••wxyz`。
- 点击眼睛图标时弹出二次确认：“显示完整密钥存在泄露风险，确认显示？”。
- 用户确认后调用 `GET /settings/api-keys/{id}/secret`，当前行显示完整 Key。
- 再次点击眼睛图标时仅前端本地隐藏，不需要重新请求。
- 点击复制图标时，如果当前行已加载完整 Key，直接复制。
- 点击复制图标时，如果当前行尚未加载完整 Key，先弹出同样的二次确认，再获取完整 Key 并复制。
- 每次后端返回完整 Key 时更新 `last_viewed_at`。

## API Key 认证与授权

- 外部调用使用：`Authorization: Bearer glzd_live_xxx`。
- 认证流程：解析 Bearer token → 判断是否 API Key 前缀 → hash 校验 → 检查 revoked/expired → 更新 `last_used_at` → 返回用户上下文和 scopes。
- Web JWT 认证与 API Key 认证分离，避免 Web 页面误用 API Key 管理账号安全接口。
- Agent API 使用 `require_api_scope("scope")` 依赖检查权限。

## Arq + Redis Worker

### 启动方式

```powershell
cd backend
uv run arq app.workers.config.WorkerSettings
```

### 目录结构

| 文件 | 职责 |
| --- | --- |
| `backend/core/redis.py` | RedisSettings / create_pool 封装 |
| `backend/services/agent_job_service.py` | 创建 job、更新状态、查询 job、入队 |
| `backend/workers/config.py` | `WorkerSettings` |
| `backend/workers/tasks.py` | Arq 任务函数 |

### 任务

- `inspect_document_task(job_id)`
- `parse_document_task(job_id)`
- `knowledge_upload_task(job_id)`

### Worker 参数

- `job_timeout = 600`
- `max_tries = 3`
- `keep_result = 3600`

### 审查任务流程

```text
Agent / CLI / MCP
    ↓ Authorization: Bearer glzd_live_xxx
FastAPI /api/v1/agent/jobs/inspect
    ↓
1. 验证 API Key
2. 检查 scope: inspection:run
3. 保存上传文件
4. 创建 agent_jobs 记录(status=queued)
5. enqueue_job("inspect_document_task", job_id)
6. 立即返回 job_id
    ↓
Redis 队列
    ↓
ARQ Worker
    ↓
inspect_document_task(job_id)
    ↓
1. status=running, progress=10
2. 调用现有 convert_to_markdown
3. 文档类型识别
4. 知识库召回
5. run_inspection
6. 写入 InspectionRecord
7. status=succeeded, result_payload={record_id}
```

## 错误处理

- API Key 缺失或无效：`401 invalid_api_key`。
- API Key 已撤销：`401 api_key_revoked`。
- API Key 已过期：`401 api_key_expired`。
- Scope 不足：`403 insufficient_scope`。
- Job 不存在或不属于当前 Key 用户：`404 job_not_found`。
- Worker 执行失败：job 状态更新为 `failed`，写入 `error_message`。
- Redis 不可用：创建任务返回 `503 queue_unavailable`。

## 安全规则

- `encrypted_key` 必须使用服务端密钥加密，密钥来自 `API_KEY_ENCRYPTION_SECRET`。
- `key_hash` 用于认证，不使用明文比对。
- 完整 Key 默认不随列表返回。
- 显示完整 Key 与复制完整 Key 都需要二次确认。
- API Key 不可调用账号安全接口，例如修改密码、刷新 token、注册登录。
- 高风险 scope 如 `records:delete` 首期隐藏或不开放。

## 测试策略

- 后端单元测试：Key 生成、hash 校验、加解密、scope 模板、scope 检查。
- 后端 API 测试：创建/列表/查看 secret/撤销 API Key。
- Agent API 测试：无 Key、无 scope、有效 scope、job 创建、job 查询。
- Worker 测试：mock Arq enqueue，验证创建任务后状态为 queued；直接调用任务函数验证状态流转。
- 前端构建测试：设置页 API Key 标签、显示/隐藏、复制、撤销交互构建通过。
- 回归测试：JWT Web 流程不受 API Key 改动影响。
