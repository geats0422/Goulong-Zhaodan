# Goulong Zhaodan CLI

照胆命令行客户端，面向 `cli_review` API Key：只读查询 + AI 生成/体检。

## 权限

推荐使用 `cli_review` 模板创建 API Key，包含：

- `profile:read`
- `inspection:read`
- `knowledge:read`
- `inspection:run`

CLI 不提供知识库写入、删除记录、设置写入等高风险操作。

如需让 Openclaw、Hermes、阿里悟空、workbuddy 等 Agent 通过 CLI/MCP 协作，可使用 `agent_full_access` 模板。该模板包含只读、AI 生成/体检、知识库写入和设置写入权限，但仍不默认包含 `records:delete`。

也可以在设置页选择“高级自定义”，再按需勾选 scopes。CLI 只检查后端 API Key scopes，不依赖模板名。

## 环境变量

| 变量 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ZHAODAN_API_KEY` | 是 | 无 | 照胆 API Key，CLI 推荐 `cli_review`，Agent 协作可用 `agent_full_access` |
| `ZHAODAN_API_BASE_URL` | 否 | `http://localhost:8000` | 后端服务地址 |

## 安装与构建

```powershell
cd CLI
npm install
npm run build
```

## 命令

```powershell
zhaodan me
zhaodan records:list
zhaodan records:get --record-id 8
zhaodan knowledge:search --query "招投标 资格 条件" --limit 3
zhaodan inspect:text --document-name demo.txt --text "待审查正文至少十个字符"
zhaodan parse:file --file-path ./demo.docx
zhaodan inspect:record --record-id 8
zhaodan jobs:inspect --document-name demo.txt --text "待审查正文至少十个字符"
zhaodan jobs:parse --file-path ./demo.docx
zhaodan jobs:status --job-id <job_id>
```

开发期也可以使用：

```powershell
npm run dev -- me
npm run dev -- knowledge:search --query "招投标" --limit 3
```

## 输出

默认输出格式化 JSON。加 `--raw` 可输出原始 JSON 字符串。
