# create-project 命令规范

## 目的
在根目录创建新项目时，确保命令系统完整可用。

## 前置检查
1. 目标项目存在 `.opencode/commands/manifest.json`。
2. `manifest.requiredCommands` 包含 `sync-config` 与 `create-project`。
3. `.opencode/opencode.json` 中 command 区域存在 `sync-config` 定义。

## 初始化要求
- 复制/生成 `.opencode/commands/` 目录结构。
- 保持 `create-project` 与 `sync-config` 的检查逻辑一致。

## 失败处理
- 任一检查失败时停止创建，并输出缺失项列表。
