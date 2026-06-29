---
name: zhaodan-knowledge-search
description: Use this skill whenever a user or AI Agent needs to search Goulong Zhaodan / 照胆 regulations, compliance references, bidding law, contract rules, knowledge snippets, or source documents before drafting, reviewing, or answering construction/legal compliance questions. Trigger for phrases like 查法规, 搜知识库, 招投标依据, 合同条款依据, retrieve regulation context, or find compliance sources.
---

# 照胆知识检索

Use this skill to retrieve law, regulation, and knowledge-base snippets from 照胆 before generating compliance answers.

## Required scope

- `knowledge:read`

If the current API Key does not include `knowledge:read`, explain the missing scope and ask the user to create a key with `mcp_readonly`, `cli_review`, `agent_full_access`, or custom scopes including `knowledge:read`.

## Inputs to collect

- `query`: the legal/compliance concept or user question.
- `application_scenario`: `bidding` or `contract`; default to `bidding` when unclear.
- `limit`: default `10`, max `100`.

## MCP path

Call:

```json
{
  "tool": "zhaodan_search_knowledge",
  "arguments": {
    "query": "招投标 资格条件",
    "application_scenario": "bidding",
    "limit": 10
  }
}
```

## CLI path

```bash
zhaodan knowledge:search --query "招投标 资格条件" --application-scenario bidding --limit 10
```

Development fallback:

```bash
cd CLI
npm run start -- knowledge:search --query "招投标 资格条件" --application-scenario bidding --limit 10
```

## Direct HTTP path

```http
POST /api/v1/agent/knowledge/search
Authorization: Bearer <ZHAODAN_API_KEY>
Content-Type: application/json

{
  "query": "招投标 资格条件",
  "application_scenario": "bidding",
  "limit": 10
}
```

## How to use results

- Prefer cited snippets over general model knowledge.
- Include `sources` and `document_id` when explaining answers.
- If snippets are weak or unrelated, say so and broaden/refine the query.
- Do not invent article numbers or legal text not present in retrieved snippets.

## Output format

```markdown
**检索结论**
- 查询: `<query>`
- 场景: `<bidding|contract>`
- 命中片段: `<count>`

**关键依据**
1. `<title>` / `<path_label>`: `<short quote>`

**建议下一步**
- `<inspect document / refine query / answer question>`
```
