---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# TypeScript/JavaScript Hooks

> 此文件扩展自 [common/hooks.md](../common/hooks.md)，包含 TypeScript/JavaScript 特定内容。

## PostToolUse Hooks

在 `~/.claude/settings.json` 中配置：

- **Prettier**：编辑后自动格式化 JS/TS 文件
- **TypeScript check**：编辑 `.ts`/`.tsx` 文件后运行 `tsc`
- **console.log warning**：警告编辑文件中的 `console.log`

## Stop Hooks

- **console.log audit**：在会话结束前检查所有修改文件中的 `console.log`
