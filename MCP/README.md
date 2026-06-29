# Goulong Zhaodan MCP Server

本目录提供一个本地 stdio MCP Server，用于让 AI 客户端通过照胆后端的 Agent API 完成法规知识检索、文档体检、记录查询和异步任务轮询。

## 适合 AI 调用的端点

优先封装 `backend/app/api/v1/agent.py` 下的 API Key 端点，因为它们具备明确的 scope 控制，适合 MCP/Agent 客户端使用：

| MCP 工具 | 后端端点 | 用途 | 需要 scope |
| --- | --- | --- | --- |
| `zhaodan_me` | `GET /api/v1/agent/me` | 检查 API Key 与 scopes | 任意有效 key |
| `zhaodan_search_knowledge` | `POST /api/v1/agent/knowledge/search` | 检索法规/知识库片段 | `knowledge:read` |
| `zhaodan_list_records` | `GET /api/v1/agent/records` | 查询体检记录列表 | `inspection:read` |
| `zhaodan_get_record` | `GET /api/v1/agent/records/{record_id}` | 查询体检记录详情 | `inspection:read` |
| `zhaodan_inspect_text` | `POST /api/v1/agent/inspect` | 直接审查正文 | `inspection:run` |
| `zhaodan_parse_file` | `POST /api/v1/agent/parse` | 上传本地文件解析，返回 `record_id` | `inspection:run` |
| `zhaodan_inspect_record` | `POST /api/v1/agent/inspect` | 基于 `record_id` 复用已解析正文体检 | `inspection:run` |
| `zhaodan_create_inspect_job` | `POST /api/v1/agent/jobs/inspect` | 创建异步体检任务 | `inspection:run` |
| `zhaodan_create_parse_job` | `POST /api/v1/agent/jobs/parse` | 创建异步解析任务 | `inspection:run` |
| `zhaodan_get_job_status` | `GET /api/v1/agent/jobs/{job_id}` | 轮询异步任务状态 | 有效 API Key |

暂不封装 JWT 用户设置端点（例如 `/settings/*`）和 Web UI 专用端点，因为这些端点依赖用户会话语义，不如 Agent API 适合 MCP。知识库上传目前没有 API Key 同步端点，也暂不暴露。

## 环境变量

| 变量 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ZHAODAN_API_KEY` | 是 | 无 | 照胆 API Key；只读工具可用 `mcp_readonly`，更多权限请用 `agent_full_access` |
| `ZHAODAN_API_BASE_URL` | 否 | `http://localhost:8000` | 后端服务地址 |

## 安装与构建

```bash
cd MCP
npm install
npm run build
```

## 本地运行

```bash
cd MCP
ZHAODAN_API_BASE_URL=http://localhost:8000 ZHAODAN_API_KEY=glk_xxx npm start
```

Windows PowerShell：

```powershell
cd MCP
$env:ZHAODAN_API_BASE_URL="http://localhost:8000"
$env:ZHAODAN_API_KEY="glk_xxx"
npm start
```

## MCP 客户端配置示例

```json
{
  "mcpServers": {
    "goulong-zhaodan": {
      "command": "node",
      "args": ["D:/work/Huanyu Code/Project/Goulong-Zhaodan/MCP/dist/index.js"],
      "env": {
        "ZHAODAN_API_BASE_URL": "http://localhost:8000",
        "ZHAODAN_API_KEY": "glk_xxx"
      }
    }
  }
}
```

## 推荐调用流程

1. `zhaodan_me`：确认 API Key 可用与 scopes。
2. `zhaodan_search_knowledge`：先查法规上下文。
3. 小文本：直接用 `zhaodan_inspect_text`。
4. 文件：先 `zhaodan_parse_file`，再用返回的 `record_id` 调 `zhaodan_inspect_record`。
5. 长耗时任务：用 `zhaodan_create_inspect_job` 或 `zhaodan_create_parse_job`，再用 `zhaodan_get_job_status` 轮询。

## 权限模板

- `mcp_readonly`：`profile:read`、`inspection:read`、`knowledge:read`，仅支持身份、记录、知识库查询。
- `agent_full_access`：在 AI 生成/体检基础上增加 `knowledge:write` 与 `settings:write`，面向 Openclaw、Hermes、阿里悟空、workbuddy 等 Agent 协作。

也可以在设置页选择“高级自定义”，再按需勾选 scopes。MCP 工具只检查后端 API Key scopes，不依赖模板名。

## 验证

```bash
npm run build
```

可选：使用 MCP Inspector 测试工具发现与调用。

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

## 评估

`evaluation.xml` 包含 10 个只读、独立的问答对，用于验证 LLM 能否有效使用本 MCP Server。

这些问题围绕工具契约与参数约束设计（枚举值、长度限制、404 错误 detail、返回结构字段名），答案由工具实现逻辑决定，不依赖运行时动态数据，因此稳定可复现。

使用 MCP 评估脚本运行：

```bash
pip install anthropic mcp
export ANTHROPIC_API_KEY=your_key
export ZHAODAN_API_KEY=glk_xxx
export ZHAODAN_API_BASE_URL=http://localhost:8000

python ../.opencode/skills/mcp-builder/scripts/evaluation.py \
  -t stdio \
  -c node \
  -a dist/index.js \
  -e ZHAODAN_API_KEY=$ZHAODAN_API_KEY \
  -e ZHAODAN_API_BASE_URL=$ZHAODAN_API_BASE_URL \
  evaluation.xml
```
