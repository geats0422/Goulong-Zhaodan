---
name: zhaodan-api-access
description: Use this skill whenever an AI Agent needs to connect to Goulong Zhaodan / 照胆, verify an API Key, choose between MCP, CLI, or direct HTTP API access, inspect available scopes, or troubleshoot authentication for Openclaw, Hermes, 阿里悟空, workbuddy, Claude, or other agents. This is the first skill to use before calling any照胆 product capability.
---

# 照胆 API Access

Use this skill to establish a safe, predictable connection to 照胆 before invoking product capabilities.

## What this enables

- Verify `ZHAODAN_API_KEY` and scopes.
- Decide whether to call MCP tools, CLI commands, or direct HTTP APIs.
- Explain missing permissions without exposing secrets.
- Prepare the Agent for follow-up skills such as knowledge search, document inspection, or record lookup.

## Required environment

- `ZHAODAN_API_KEY`: required.
- `ZHAODAN_API_BASE_URL`: optional, defaults to `http://localhost:8000`.

Never print the full API Key. When summarizing, show only a non-sensitive prefix pattern such as `glzd_live_****`.

## Access strategy

Prefer these routes in order:

1. MCP if the host Agent supports MCP.
2. CLI if the Agent can run shell commands.
3. Direct HTTP if neither MCP nor CLI is available.

## MCP path

Call:

```json
{
  "tool": "zhaodan_me",
  "arguments": {}
}
```

Expected response fields:

- `user_id`
- `api_key_id`
- `scopes`

## CLI path

Use:

```bash
zhaodan me
```

Development fallback from the repository:

```bash
cd CLI
npm run start -- me
```

## Direct HTTP path

```http
GET /api/v1/agent/me
Authorization: Bearer <ZHAODAN_API_KEY>
```

## Permission guide

| Capability | Required scope |
| --- | --- |
| Identity check | any valid key |
| Knowledge search | `knowledge:read` |
| List/read inspection records | `inspection:read` |
| Inspect text, parse file, create jobs | `inspection:run` |
| Knowledge writing | `knowledge:write` |
| Settings writing | `settings:write` |

The product intentionally does not expose destructive deletion to Agent skills. Do not ask for or assume `records:delete`.

## Output format

When reporting connection status, use:

```markdown
**照胆连接状态**
- API Base URL: `<url>`
- 认证: 通过/失败
- 可用权限: `<scopes>`
- 推荐下一步: `<tool or skill>`
```

## Failure handling

- `401` or missing key: ask the user to create or provide a valid API Key.
- `403`: explain which scope is missing and which preset/custom scopes can provide it.
- Network failure: check `ZHAODAN_API_BASE_URL` and whether the backend is running.
- Never retry mutating operations blindly.
