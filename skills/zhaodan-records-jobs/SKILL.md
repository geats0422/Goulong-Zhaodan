---
name: zhaodan-records-jobs
description: Use this skill whenever an AI Agent needs to list Goulong Zhaodan / 照胆 inspection records, read a historical report by record_id, summarize previous compliance results, poll async parse/inspect jobs, or troubleshoot job status. Trigger for phrases like 查历史体检, 获取 record_id 报告, list records, job status, 轮询任务, or 查看上次审查结果.
---

# 照胆记录与任务查询

Use this skill to read historical inspection records and poll async jobs.

## Required scopes

- List records: `inspection:read`
- Get record detail: `inspection:read`
- Get job status: any valid API Key for that user

## MCP tools

List records:

```json
{
  "tool": "zhaodan_list_records",
  "arguments": {}
}
```

Get record:

```json
{
  "tool": "zhaodan_get_record",
  "arguments": { "record_id": 8 }
}
```

Poll job:

```json
{
  "tool": "zhaodan_get_job_status",
  "arguments": { "job_id": "job-id" }
}
```

## CLI commands

```bash
zhaodan records:list
zhaodan records:get --record-id 8
zhaodan jobs:status --job-id <job_id>
```

## Direct HTTP endpoints

- `GET /api/v1/agent/records`
- `GET /api/v1/agent/records/{record_id}`
- `GET /api/v1/agent/jobs/{job_id}`

Use `Authorization: Bearer <ZHAODAN_API_KEY>`.

## Output format for records

```markdown
**历史体检记录**
- 总数: `<count>`

| ID | 文档 | 类型 | 风险 | 创建时间 |
| --- | --- | --- | --- | --- |
| `<id>` | `<document_name>` | `<document_type_label>` | `<overall_risk>` | `<created_at>` |
```

## Output format for detail

```markdown
**记录详情**
- ID: `<record_id>`
- 文档: `<document_name>`
- 风险等级: `<overall_risk>`
- 摘要: `<summary>`
- 问题数量: `<count>`

**主要问题**
1. `<issue>`
```

## Output format for jobs

```markdown
**任务状态**
- Job ID: `<job_id>`
- 类型: `<job_type>`
- 状态: `<status>`
- 进度: `<progress>`
- 消息: `<message>`
- 结果: `<result_payload summary>`
- 错误: `<error_message if any>`
```

## Safety notes

- This skill is read-only from the user's perspective.
- Do not invent records that are not returned by the API.
- If `record_not_found` or `job_not_found` appears, report it plainly and ask for a valid ID.
- Do not request delete permissions; deletion is outside this skill's scope.
