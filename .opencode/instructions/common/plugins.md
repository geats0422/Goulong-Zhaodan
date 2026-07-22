# Plugins 系统

## 插件概述

插件允许你通过挂钩各种事件和自定义行为来扩展 OpenCode。你可以创建插件来添加新功能、集成外部服务，或修改 OpenCode 的默认行为。

## 插件目录

- **项目级插件**：`.opencode/plugins/`
- **全局插件**：`~/.config/opencode/plugins/`

这些目录中的文件会在启动时自动加载。

## 基本结构

```typescript
import type { Plugin } from "@opencode-ai/plugin"

export const MyPlugin: Plugin = async ({ project, client, $, directory, worktree }) => {
  return {
    // Hook implementations go here
  }}
}
```

插件函数接收以下参数：
- **project**：当前项目信息
- **directory**：当前工作目录
- **worktree**：git 工作树路径
- **client**：用于与 AI 交互的 OpenCode SDK 客户端
- **$**：Bun 的 Shell API，用于执行命令

## 可用事件

### 命令事件
- `command.executed`：命令执行后

### 文件事件
- `file.edited`：文件编辑后
- `file.watcher.updated`：文件监视器更新

### LSP 事件
- `lsp.client.diagnostics`：LSP 客户端诊断
- `lsp.updated`：LSP 更新

### 消息事件
- `message.part.removed`：消息部分移除
- `message.part.updated`：消息部分更新
- `message.removed`：消息移除
- `message.updated`：消息更新

### 权限事件
- `permission.asked`：权限询问
- `permission.replied`：权限回复

### 服务器事件
- `server.connected`：服务器连接

### 会话事件
- `session.created`：会话创建
- `session.compacted`：会话压缩
- `session.deleted`：会话删除
- `session.diff`：会话差异
- `session.error`：会话错误
- `session.idle`：会话空闲
- `session.status`：会话状态
- `session.updated`：会话更新

### 待办事项事件
- `todo.updated`：待办更新

### Shell 事件
- `shell.env`：Shell 环境变量

### 工具事件
- `tool.execute.after`：工具执行后
- `tool.execute.before`：工具执行前

### TUI 事件
- `tui.prompt.append`：TUI 提示追加
- `tui.command.execute`：TUI 命令执行
- `tui.toast.show`：TUI 通知显示

## 插件示例

### .env 保护
阻止 OpenCode 读取 .env 文件：
```typescript
export const EnvProtection = async ({ project, client, $, directory, worktree }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath.includes(".env")) {
        throw new Error("Do not read .env files")
      }
    },
  }}
```

### 注入环境变量
将环境变量注入所有 Shell 执行：
```typescript
export const InjectEnvPlugin = async () => {
  return {
    "shell.env": async (input, output) => {
      output.env.MY_API_KEY = "secret"
      output.env.PROJECT_ROOT = input.cwd
    },
  }}
```

## 依赖项

本地插件可以使用外部 npm 包。在配置目录中添加 `package.json`：
```json
{
  "dependencies": {
    "shescape": "^2.1.0"
  }}
```
OpenCode 会在启动时运行 `bun install` 来安装这些依赖项。

## TodoWrite 最佳实践

使用 TodoWrite 工具来：
- 跟踪多步骤任务的进度
- 验证对指令的理解
- 实现实时引导
- 显示粒度化的实施步骤

待办列表揭示：
- 顺序错误的步骤
- 缺失的项目
- 额外不必要的项目
- 错误的粒度
- 误解的需求
