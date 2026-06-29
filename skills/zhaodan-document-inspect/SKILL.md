---
name: zhaodan-document-inspect
description: Use this skill whenever an AI Agent needs to run Goulong Zhaodan / 照胆 document inspection, compliance review, bidding document review, contract review, AI risk analysis, file parsing, record_id reinspection, or async inspection jobs. Trigger for phrases like 体检文档, 审查合同, 检查招标文件, parse then inspect, run compliance report, or create inspection job.
---

# 照胆文档体检

Use this skill to submit text or files to 照胆 and return a structured inspection report.

## Required scope

- `inspection:run`

For stronger Agent collaboration, use a key with `agent_full_access` or custom scopes that include `inspection:run`. The key does not need a special template name.

## Choose the right flow

| Situation | Recommended flow |
| --- | --- |
| Short text already extracted | Inspect text directly |
| Local file needs parsing | Parse file, then inspect by `record_id` |
| Long-running or batch work | Create async job, then poll status |
| Record already parsed | Inspect by `record_id` |

## MCP tools

Inspect text:

```json
{
  "tool": "zhaodan_inspect_text",
  "arguments": {
    "document_name": "招标文件.txt",
    "text": "待审查正文，至少 10 个字符",
    "application_scenario": "bidding",
    "taboo_words": "",
    "project_id": "default"
  }
}
```

Parse file:

```json
{
  "tool": "zhaodan_parse_file",
  "arguments": {
    "file_path": "D:/path/to/file.docx",
    "project_id": "default"
  }
}
```

Inspect parsed record:

```json
{
  "tool": "zhaodan_inspect_record",
  "arguments": {
    "record_id": 8,
    "application_scenario": "contract",
    "taboo_words": "",
    "project_id": "default"
  }
}
```

Async inspect:

```json
{
  "tool": "zhaodan_create_inspect_job",
  "arguments": {
    "document_name": "合同.txt",
    "text": "待审查正文，至少 10 个字符",
    "application_scenario": "contract",
    "taboo_words": "",
    "project_id": "default"
  }
}
```

## CLI commands

```bash
zhaodan inspect:text --document-name "招标文件.txt" --text "待审查正文，至少 10 个字符" --application-scenario bidding
zhaodan parse:file --file-path "D:/path/to/file.docx"
zhaodan inspect:record --record-id 8 --application-scenario contract
zhaodan jobs:inspect --document-name "合同.txt" --text "待审查正文，至少 10 个字符" --application-scenario contract
```

## Direct HTTP endpoints

- `POST /api/v1/agent/inspect`
- `POST /api/v1/agent/parse`
- `POST /api/v1/agent/jobs/inspect`
- `POST /api/v1/agent/jobs/parse`

Use `Authorization: Bearer <ZHAODAN_API_KEY>` for all requests.

## Output format

Summarize results in this structure:

```markdown
**体检摘要**
- 文档: `<document_name>`
- 风险等级: `<overall_risk>`
- 问题数量: `<count>`
- 摘要: `<summary>`

**重点问题**
1. `<issue title>` — `<severity>`
   - 位置/证据: `<quote or location>`
   - 建议: `<recommendation>`

**引用依据**
- `<regulation/source>`
```

## Safety notes

- Do not submit files unless the user intends them to be inspected.
- Do not leak full API keys in logs or summaries.
- If an operation returns `403`, map it to missing `inspection:run`.
- If text is too short, ask for the full document or use parse-file flow.
