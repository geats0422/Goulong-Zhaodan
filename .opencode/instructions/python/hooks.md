---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> 此文件扩展自 [common/hooks.md](../common/hooks.md)，包含 Python 特定内容。

## PostToolUse Hooks

在 `~/.claude/settings.json` 中配置：

- **black/ruff**：编辑后自动格式化 `.py` 文件
- **mypy/pyright**：编辑 `.py` 文件后运行类型检查

## 警告

- 警告编辑文件中的 `print()` 语句（请改用 `logging` 模块）
