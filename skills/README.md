# 照胆 Agent Skills

本目录提供给 Openclaw、Hermes、阿里悟空、workbuddy 等 AI Agent 安装或引用的 skills，用于通过照胆 API/MCP/CLI 完成合规知识检索、文档解析体检、记录查询和异步任务轮询。

## Skills

| Skill | 用途 | 推荐权限 |
| --- | --- | --- |
| `zhaodan-api-access` | 连接、认证、权限检查和入口选择 | 任意有效 API Key |
| `zhaodan-knowledge-search` | 检索法规/知识库上下文 | `knowledge:read` |
| `zhaodan-document-inspect` | 文档正文体检、文件解析、record_id 复检、异步体检 | `inspection:run`，通常配合 `knowledge:read` |
| `zhaodan-records-jobs` | 查询历史记录、记录详情、异步任务状态 | `inspection:read`，job 查询需有效 API Key |

## 使用方式

优先级建议：

1. Agent 支持 MCP 时，使用 `MCP/` 提供的 `goulong-zhaodan` MCP Server。
2. Agent 可运行命令行但没有 MCP 时，使用 `CLI/` 提供的 `zhaodan` CLI。
3. Agent 只能发 HTTP 请求时，直接调用 `/api/v1/agent/*` API。

环境变量：

- `ZHAODAN_API_KEY`：必需。
- `ZHAODAN_API_BASE_URL`：可选，默认 `http://localhost:8000`。

权限模板建议：

- 只读 Agent：`mcp_readonly`。
- CLI 体检：`cli_review`。
- Agent 协作：`agent_full_access`。
- 精细控制：设置页选择“高级自定义”，按需勾选 scopes。

安全边界：这些 skills 不提供删除记录能力；默认不要请求或假设 `records:delete`。
