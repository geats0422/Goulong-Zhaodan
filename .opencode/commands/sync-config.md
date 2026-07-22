# /sync-config 命令规范

## 目的
将项目 `.opencode/` 配置单向同步到根目录 `D:\work\Huanyu Code\.opencode`。

## 前置检查
1. 当前目录存在 `.opencode/`。
2. 当前目录存在 `.opencode/commands/manifest.json`。
3. `manifest.requiredCommands` 包含 `sync-config` 和 `create-project`。

## 同步范围
- `opencode.json`（合并 command 段，保留根目录 `create-project`）
- `AGENTS.md`, `ETHOS.md`, `.gitignore`
- `agents/`, `instructions/`, `plugins/`, `prompts/`, `rules/`, `skills/`, `commands/`
- `state/` 不同步

## 结果输出
- 输出同步文件清单
- 提示运行 `git diff`
- 若缺失 commands manifest 或关键条目，终止并提示先修复
