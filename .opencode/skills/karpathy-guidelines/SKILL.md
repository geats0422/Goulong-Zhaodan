---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.
license: MIT
---

# Karpathy Guidelines

行为准则，用于减少 LLM 编码常见错误：错误假设、过度复杂化、无关改动、缺少验证目标。

**权衡**: 这些准则偏向谨慎而不是速度。对明显的一行小改可以使用判断力，但不能把“简单”当作跳过验证的借口。

## 1. Think Before Coding

**不要假设。不要隐藏困惑。呈现权衡。**

实现前：
- 明确陈述假设；不确定就询问。
- 如果存在多种解释，呈现这些解释，不要静默选择。
- 如果存在更简单方案，指出并解释取舍。
- 如果不清楚，停止并说明哪里不清楚。

## 2. Simplicity First

**能解决问题的最小代码。不要投机式设计。**

- 不添加请求之外的功能。
- 不为单次使用代码创建抽象。
- 不添加未请求的“灵活性”或“可配置性”。
- 不为不可能场景编写大量错误处理。
- 如果 200 行可以是 50 行，先重写为 50 行。

检查问题：资深工程师会不会说这过度复杂？如果会，简化。

## 3. Surgical Changes

**只动必须动的地方。只清理自己造成的混乱。**

编辑现有代码时：
- 不“顺手优化”相邻代码、注释或格式。
- 不重构没坏的东西。
- 匹配现有风格，即使你会用不同方式写。
- 发现无关死代码时报告，不删除。

当你的修改造成孤儿代码时：
- 删除本次修改导致未使用的 import、变量、函数。
- 不删除修改前就存在的死代码，除非用户要求。

测试：每一行改动都必须能追溯到用户请求。

## 4. Goal-Driven Execution

**定义成功标准。循环直到验证通过。**

把任务转化为可验证目标：
- “添加验证” → “为非法输入写测试，然后让它通过”。
- “修 bug” → “写一个复现 bug 的测试，然后让它通过”。
- “重构 X” → “重构前后测试都通过，行为不变”。

多步骤任务应使用简短计划：

```text
1. [步骤] → 验证: [检查]
2. [步骤] → 验证: [检查]
3. [步骤] → 验证: [检查]
```

强成功标准让 Agent 能独立循环。弱标准（如“让它能用”）需要先澄清。

## How To Know It Is Working

- Diff 中无关变更减少。
- 首次实现更简单，返工更少。
- 澄清问题发生在实现前，而不是出错后。
- PR 更小、更干净、更容易 review。
