---
name: execute-plans
description: 按照实施计划文档逐个执行任务。每个任务走完整流程：TDD 实现 → spec-compliance-review → code-quality-review。一个任务完成后自动继续下一个。
---

# 执行实施计划

加载实施计划文档，按顺序执行每个任务。

## 核心原则

1. **干净上下文** — 每个任务用独立的 subagent 实现（不继承主会话上下文）
2. **两阶段审查** — 实现后先做 spec compliance review，再做 code quality review
3. **连续执行** — 不要在任务之间暂停向用户报告进度，除非遇到阻塞
4. **强制 TDD** — 每个实现任务必须先写失败测试

## 工作流

```
/execute <任务编号>

1. 加载计划文档 → 定位目标任务
2. [无测试?] → 先配置测试框架
3. 派发 implementer subagent → TDD 实现
4. 派发 spec-compliance-reviewer subagent → 对照设计文档验证
5. 派发 code-quality-reviewer subagent → 代码质量审查
6. 标记任务完成
7. 自动继续下一个任务
```

## 执行过程

### 第 1 步：加载计划
- 读取 `Project/{项目名称}/docs/plans/YYYY-MM-DD-<topic>-plan.md`
- 定位目标任务
- 检查任务的依赖是否都已完成

### 第 2 步：准备测试框架
- 如果项目还没有测试框架，先配置（运行 `/tdd`）
- 确保现有测试基线通过

### 第 3 步：Implementer Subagent — TDD 实现
派发一个干净的 subagent（不继承主会话上下文）：

```
你是 implementer agent。你的任务是按照以下规范实现代码。

## 任务描述
[从计划中提取的任务描述]

## 涉及文件
[需要创建/修改的文件列表]

## 工作步骤
1. 先写测试 → 运行测试确认失败
2. 写最小实现 → 运行测试确认通过
3. 运行全部测试确认无回归
4. 提交代码（约定式提交格式）
5. 自我审查

## 约束
- 严格按照任务描述实现，不要添加额外功能
- 所有测试必须独立、快速
```

### 第 4 步：Spec-Compliance-Reviewer Subagent
```
你是 spec-compliance reviewer。

对照以下设计文档检查刚才的实现：
[设计文档路径]

检查要点：
1. 实现了所有设计中的需求吗？
2. 接口是否符合设计文档的定义？
3. 数据模型是否与设计一致？
4. 边界情况是否覆盖？

如果发现问题，报告具体差距（不要修复，让 implementer 修复）。
```

### 第 5 步：Code-Quality-Reviewer Subagent
使用 code-review skill 的标准流程：
- 代码质量、安全性、可维护性、性能审查
- 按 CRITICAL/HIGH/MEDIUM/LOW 分类问题
- implementer 修复后发现的问题后重新审查

### 第 6 步：标记完成
- 在计划文档中标记任务为 `[x]` 完成
- 如果有下一个任务，自动开始执行
- 如果所有任务完成 → 告诉用户运行 `/finish`

## 暂停条件

只有在以下情况暂停并通知用户：
- **BLOCKED**: 遇到无法自行解决的阻塞
- **AMBIGUITY**: 计划描述不够清晰，无法确定下一步
- **ALL_DONE**: 所有任务完成

不要在"应该继续吗？"这类问题上暂停 —— 继续执行就对了。

## 模型选择

| 任务类型 | 推荐模型 |
|---------|---------|
| 机械性实现（1-2 文件，规格清晰） | fast model |
| 多文件协调、模式匹配 | standard model |
| Debugging 复杂问题 | capable model |

## 下一步

没有阻塞的话，自动继续下一个任务。全部完成时告诉用户运行 `/finish`。
