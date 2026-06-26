# MCP 体检：基于 record_id 与异步 Worker 的迭代设计（方案2）

> 状态：**核心实现完成**（2026-06-26 更新）。本文档承接方案1（同步纯文本体检），记录"复用 record_id"与"接通 arq 异步 worker"两条演进路径的设计与当前实现契约。

## 实现进展（2026-06-26）

### ✅ 已完成：record_id 两步体检（方案2-A）

- 新增 `POST /api/v1/agent/parse`：API Key 客户端上传文件，复用 Web 侧解析/魔数校验/类型识别逻辑，创建 `pending` 的 `InspectionRecord`，返回 `record_id`。
- 扩展 `POST /api/v1/agent/inspect`：兼容原 `{document_name, text}` 同步体检，同时支持 `{record_id}` 复用已落库 `parsed_content`，并更新同一条记录。
- `execute_inspection` 已下沉到 `app/services/inspection_runner.py`，Web inspection router、Agent router、worker runner 共同复用。

**`POST /api/v1/agent/parse` 返回契约**：

| 字段 | 说明 |
| --- | --- |
| `record_id` | 后续体检使用的记录 ID |
| `document_name` | 上传文件名 |
| `document_type` | 自动识别的类型，可能为 `bidding` / `contract` / `unknown` |
| `document_type_label` | 类型中文标签 |
| `text_preview` | 解析正文前 500 字符 |

### ✅ 已完成：arq worker runner 接通（方案2-B 核心）

- `enqueue_job` 实现（arq 投递到 Redis），见 `app/services/agent_job_service.py`
- `_run_inspect` runner 实现（取 `input_payload` → 调 `execute_inspection` → 返回结果摘要），见 `app/workers/tasks.py`
- `_run_parse` runner 实现（取 `input_payload.text` 或 `content_base64` → 解析/类型识别 → 创建 pending record → 返回 `record_id`）
- `_run_knowledge_upload` runner 实现（取 `content_base64` → 构造 `UploadFile` → 复用现有知识库入库 handler）
- 修复 `create_job`：传 `job.job_id`（str）而非 `job.id`（int）；投递失败时标记 `failed` 而非卡在 `queued`
- worker 启动命令：`cd backend && uv run arq app.workers.config.WorkerSettings`
- 单元测试覆盖：`_run_inspect` / `_run_parse` / `_run_knowledge_upload` 真实逻辑 + `_execute_task` 状态机 + enqueue 失败标记
- web 侧 enqueue smoke 验证通过（连真实 Redis 投递成功）

**input_payload 契约（inspect job）**：

| 字段 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | 是 | — | 文档正文（< 10 字符时 runner 标记 failed） |
| `document_name` | 否 | "未命名文档" | 文档名 |
| `application_scenario` | 否 | "bidding" | `bidding` / `contract` |
| `taboo_words` | 否 | "" | 逗号分隔的临时违禁词 |
| `project_id` | 否 | "default" | 项目标识 |

**调用示例**：`POST /api/v1/agent/jobs/inspect`（需 `inspection:run` scope，如 `mcp_inspect`/`agent_automation` 模板），body `{"input_payload": {"document_name": "x.pdf", "text": "..."}}` → 返回 `job_id` → 轮询 `GET /api/v1/agent/jobs/{job_id}` 看 `status: queued → running → succeeded`，`result_payload` 含 `{record_id, overall_risk, document_name}`。

**input_payload 契约（parse job）**：

| 字段 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | 条件必需 | — | 已解析正文；与 `content_base64` 二选一 |
| `content_base64` | 条件必需 | — | 原始文件 base64；与 `text` 二选一 |
| `document_name` / `filename` | 否 | "未命名文档.txt" | 文档名；`content_base64` 路径会按扩展名解析 |
| `project_id` | 否 | "default" | 项目标识 |

**input_payload 契约（knowledge_upload job）**：

| 字段 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `content_base64` | 是 | — | 原始知识库文件 base64；文件类型沿用知识库上传限制 |
| `document_name` / `filename` | 否 | "knowledge.pdf" | 文件名 |
| `category` | 否 | "general" | 工程分类 key |
| `subcategory_id` / `subcategory_name` | 是 | — | 与知识库上传一致，二选一 |
| `application_scenario` | 否 | "bidding" | 应用场景 |

### ⏳ 仍待实现/后续优化

- 将 knowledge upload 路由中的入库 orchestration 下沉到 service，避免 worker 直接复用 router handler。
- 为 job payload 提供 OpenAPI/文档化示例与 SDK 封装。
- 技术债：`get_api_key_user`（返回 UUID）与 `get_current_user`（返回 str）返回类型统一

### ✅ 已完成（独立 commit `d89e769`）：scope 体系优化

新增 `mcp_inspect` 模板（能体检 + 查询），前端新建 key 默认选它；修复 `cli_review`/`advanced_custom` 创建 key 报 500 的命名不一致 bug。

---

## 目标

- 提供"先解析落库、再凭 record_id 体检"的两步能力，减少大文本重复传输，并保留可追溯的解析记录。
- 接通现有但空壳化的 arq worker，让 `/api/v1/agent/jobs/*` 真正异步执行体检/解析，支撑批量与大文件场景。
- 与方案1（`POST /api/v1/agent/inspect` 同步纯文本）互补：小文件/即时调用走同步，大文件/批量走异步。

## 背景

方案1（已实现，2026-06-26）新增 `POST /api/v1/agent/inspect`，MCP/Agent 客户端直接传入文档正文 `text`，同步返回完整审查报告。该方案契合 MCP 同步工具语义，但不适合：

- 文档正文极大、需多次复检（重复传输成本高）
- 批量体检、长耗时任务（同步 HTTP 易超时）
- 需要保留解析中间产物、按记录回溯的场景

以上场景正是方案2 要覆盖的。

## 当前缺口（精确位置）

| 缺口 | 位置 | 现状 |
| --- | --- | --- |
| enqueue 空壳 | `app/services/agent_job_service.py:12` `enqueue_job` 为 `pass` | 任务只入库 `queued`，不投递 arq |
| runner 空壳 | `app/workers/tasks.py` `_run_inspect`/`_run_parse`/`_run_knowledge_upload` | 已接通真实逻辑 |
| worker 无启动入口 | `app/workers/config.py` 定义了 `WorkerSettings`（arq 约定） | 无文档化启动命令、无进程守护 |
| agent parse 不落库 | `app/api/v1/agent.py` `/parse` 与 `/jobs/parse` | 同步 `/parse` 已落库；异步 `_run_parse` 已落库 |
| scope 模板名不一致 | `settings.py:50` 用 `cli_review`，`api_key_scopes.py:23` 用 `cli_inspection` | 前后端需统一 |
| auth 返回类型不一致 | `get_api_key_user` 返回原生 `uuid.UUID`，`get_current_user` 返回 `str` | 已通过 `_current_user_id` 加 `str()` 兜底，根因待统一 |

## 设计

### 方案2-A：基于 record_id 的两步体检（同步）

两步走，文本只在第一步传输：

```
① POST /api/v1/agent/parse        （multipart 文件上传）
   ← { record_id, document_name, document_type, document_type_label, text_preview }
② POST /api/v1/agent/inspect      （body: { record_id, application_scenario?, taboo_words? }）
   ← InspectionReportResponse
```

**实现要点：**

1. 新增 `POST /api/v1/agent/parse`（scope: `inspection:run`）：
   - 接收 `UploadFile`，复用 `inspection._read_inspection_upload_text` 做魔数校验 + 解析 + 清洗。
   - 复用 `inspection._detect_document_type` 识别文档类型。
   - 复用 `inspection._create_pending_inspection_record` 落库（`overall_risk="pending"`，`parsed_content=encrypt_text(text)`）。
   - 返回 `record_id` 与基础元信息。
2. 扩展 `POST /api/v1/agent/inspect` 的请求模型，支持二选一：
   - `{ document_name, text, ... }`（方案1，已实现）
   - `{ record_id, application_scenario?, taboo_words? }`（方案2-A，新增）
   - 当传 `record_id` 时：校验归属 → `decrypt_text(record.parsed_content)` 取正文 → 复用 `execute_inspection(record_id=...)`（该函数已支持 `record_id` 更新既有记录）。
3. 应用场景回退规则：`body.application_scenario or record.document_type`；若为 `unknown` 则回退 `bidding`（与前端 `inspect_session` 一致）。

**注意：** `execute_inspection` 当前位于 `app/api/v1/inspection.py`（router 模块）。建议在本次迭代中将其下沉到 `app/services/inspection_runner.py`，由 inspection 与 agent 两个 router 共同引用，避免 router 间横向依赖。下沉时一并带走 `_load_user_taboo_words`、`_merge_unique_words`、`_sanitize_inspection_result_refs`、`_allowed_regulation_refs` 等纯逻辑助手；`_current_user_id` 留在 router 层。

### 方案2-B：接通 arq 异步 Worker

让 `/api/v1/agent/jobs/*` 真正异步执行：

**实现要点：**

1. 实现 `enqueue_job`（`agent_job_service.py`）：
   ```python
   from arq import create_pool
   from app.core.redis import get_redis_settings

   async def enqueue_job(task_name: str, job_id: str) -> None:
       pool = await create_pool(get_redis_settings())
       await pool.enqueue_job(task_name, job_id=job_id)
   ```
2. 实现 runner（`workers/tasks.py`）：
   - `_run_inspect`：从 `AgentJob` 取 `user_id` + `input_payload` → 构造 `InspectionDeps`（含 `async_session` 取得的 db）→ 调 `run_inspection` → 清洗引用 → 更新 `InspectionRecord` → 返回 `result_payload`。
   - `_run_parse`：复用 `_read_inspection_upload_text` + `_create_pending_inspection_record`，`result_payload` 返回 `record_id`。
   - runner 内通过 `async_session()` 自管 db 生命周期，不依赖请求级 session。
3. worker 启动命令固定为（写入 `backend/README` 或 `AGENTS.md`）：
   ```
   cd backend && uv run arq app.workers.config.WorkerSettings
   ```
4. `input_payload` 契约需明确（见下）。

### `input_payload` 契约草案

异步 job 的 `input_payload`（JSON）：

| job_type | 字段 | 说明 |
| --- | --- | --- |
| `inspect` | `document_name`, `text`, `application_scenario`, `taboo_words`, `project_id` | 与方案1 同步端点一致；text 由客户端预解析 |
| `inspect` | `record_id`（可选替代 text） | 复用已落库正文 |
| `parse` | `text` 或 `content_base64`, `document_name`, `project_id` | 创建 pending `InspectionRecord`，返回 `record_id` |
| `knowledge_upload` | `content_base64`, `document_name`, `category`, `subcategory_id`/`subcategory_name`, `application_scenario` | 复用知识库上传入库链路 |

## 影响面与风险

- **文件存储**：当前异步 job 通过 JSON `content_base64` 传递文件内容，避免 `UploadFile` 跨进程问题；大文件/批量场景后续仍建议升级为对象存储或临时文件引用，避免 Redis/job payload 膨胀。
- **worker 与 web 进程解耦**：worker 需独立进程常驻，部署文档与进程守护（systemd/supervisor/Docker）需补齐。
- **Redis 可用性**：arq 强依赖 Redis，需纳入健康检查与故障兜底（job 投递失败时 `create_job` 应标记 `failed` 而非卡在 `queued`）。
- **权限**：parse/inspect-by-record 均需 `inspection:run`；只读 MCP key（`mcp_readonly`）仍只能查不能跑。
- **测试**：异步链需 mock arq `enqueue_job` 与 `run_inspection`；worker runner 可单独单测（已有 `test_agent_worker_tasks.py`）。

## 验收标准

- 方案2-A：
  - `POST /api/v1/agent/parse` 上传文件返回 `record_id`，且 `inspection_records` 表存在 `pending` 记录。✅
  - `POST /api/v1/agent/inspect` 传 `record_id` 能返回报告，且更新同一记录而非新建。✅
  - 跨用户 `record_id` 返回 404。
- 方案2-B：
  - `POST /api/v1/agent/jobs/inspect` 投递后，worker 进程能在 `job_timeout` 内将 job 从 `queued` → `running` → `succeeded`，`result_payload` 含审查结果。✅（runner + enqueue 已覆盖，需部署后长跑验证）
  - `enqueue_job` 失败时 job 标记 `failed`，不留孤儿 `queued`。✅
  - `cd backend && uv run arq app.workers.config.WorkerSettings` 可稳定启动并消费任务。✅（import/smoke 已验证）

## 技术债清单（建议本次或下迭代一并清理）

1. 统一 auth 依赖返回类型：`get_api_key_user` 与 `get_current_user` 的 `user_id` 统一为 `str` 或统一为 `uuid.UUID`，消除 `_current_user_id` 的 `str()` 兜底。
2. 统一 scope 模板名：`cli_review` ↔ `cli_inspection` 二选一，前后端 + 测试同步。
3. 将 knowledge upload orchestration 下沉到 service，解除 worker 对 router handler 的复用。
4. 清理 `app/tools/common.py` 对 `compliance_tool` 的错误 import（`base.py` 仅定义 `inspection_tool`）。
5. 清理 `test_agent_api.py` 预先存在的未使用 import（ruff F401）。
