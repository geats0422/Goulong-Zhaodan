---
name: optimization-spec
description: 将洞察报告（/insights 或 /quality 输出）转化为可执行的优化规格文档。遵循 spec 方法论：分析问题 → 制定方案 → 预估影响 → 拆解任务。所有优化必须有明确的"优化前/优化后"对比指标。
---

# Optimization Spec — 把洞察变成规格

从分析报告到可执行计划，每一步都有 spec。

## 核心原则

1. **每个优化都要有 spec** — 不凭直觉改，先写清楚"改什么、为什么、预期效果"
2. **可量化对比** — 每个优化目标要有 before/after 指标
3. **渐进式交付** — 一次只优化一个维度，逐个验证
4. **遵循项目已有的 spec 流程** — 优化也是功能，走 brainstorming → plan → execute → finish

## 触发条件

- 运行 `/insights` 或 `/quality` 后，用户说"优化"、"按报告改进"、"fix this"
- 用户运行 `/optimize` 命令
- 用户说"根据 insights 报告制定优化计划"

## 工作流

```
/insights 或 /quality 产出报告
    ↓
/optimize → optimization-spec
    ├─ 阶段 1: 读取报告 → 提取可优化项
    ├─ 阶段 2: 按影响/成本排序 → 优先级矩阵
    ├─ 阶段 3: 为 Top 3 项编写优化 spec
    ├─ 阶段 4: 生成 optimization-design.md
    ├─ 阶段 5: 用户批准
    └─ 阶段 6: 终端状态 → 建议运行 /plan
        ↓
    /plan → writing-plans (拆解为实施任务)
        ↓
    /execute → 逐任务执行 (含 TDD + 两阶段 review)
        ↓
    /finish → 验证优化效果 (重新运行 /quality 对比)
```

## 优化规格格式

保存到 `Project/{项目名称}/docs/optimizations/YYYY-MM-DD-<scope>-optimization.md`：

```markdown
# 优化规格文档

**日期**: YYYY-MM-DD
**基于报告**: Project/{项目名称}/docs/insights/YYYY-MM-DD-insights.md
**当前评分**: XX/100 (如适用)

---

## 优先级矩阵

| 优先级 | 优化项 | 影响 | 成本 | 影响/成本 | 选择 |
|--------|--------|------|------|----------|------|
| P0 | 启用 TypeScript strict mode | 高 | 低 | ⭐⭐⭐ | ✅ |
| P1 | 添加 missing import 自动检测 | 中 | 低 | ⭐⭐ | ✅ |
| P2 | 创建 frontend-patterns skill | 中 | 中 | ⭐ | 本次 |
| P3 | 重构 App.tsx (12次修改) | 高 | 高 | ⭐ | 下次 |

---

## 优化项 1: 启用 TypeScript strict mode [P0]

### 问题描述
过去 30 天有 5 次 "fix: type error" 提交，涉及运行时类型错误。
根因: tsconfig.json 中 `strict: false`。

### 优化方案
1. 修改 `tsconfig.json`: `strict: false` → `strict: true`
2. 运行 `tsc --noEmit` 收集所有类型错误
3. 逐文件修复类型错误（不改变运行时行为）
4. 全部修复后运行测试确认无回归

### 预期效果
| 指标 | Before | After | 改善 |
|------|--------|-------|------|
| TypeScript 错误 | ~30 | 0 | -100% |
| 类型相关 bug | ~5/月 | ~1/月 | -80% |
| 质量评分(类型安全) | 4/10 | 9/10 | +125% |

### 风险
- 已有代码大量 `any` 使用 → 先用 `@ts-ignore` 标记，逐步修复
- 第三方库类型不完整 → 创建 `*.d.ts` 声明文件

### 验证
优化完成后，运行 `/quality` 对比前后评分。

---

## 优化项 2: 添加 missing import 自动检测 [P1]

### 问题描述
过去 30 天有 3 次 "fix: add missing import" 提交。

### 优化方案
1. 配置 ESLint `import/no-unresolved` 规则
2. 配置 organize-imports-on-save (如果 IDE 支持)
3. 在 `rules/common.md` 添加: "每次编辑文件后检查 import"

### 预期效果
| 指标 | Before | After | 改善 |
|------|--------|-------|------|
| import 相关 bug | ~3/月 | ~0/月 | -100% |

---

## 后续步骤

优化 spec 批准后，建议运行 `/plan` 来创建实施计划。
```

## 优先级评估方法

对每个优化项打分：

| 因素 | 权重 | 评分标准 |
|------|------|---------|
| 影响 (Impact) | ×3 | 10=消除最频繁的 bug, 1=微小的体验改善 |
| 成本 (Cost) | ×1 | 10=几天的工作, 1=几分钟的配置改动 |
| 紧迫性 (Urgency) | ×2 | 10=阻塞了日常开发, 1=锦上添花 |

**影响/成本比** = (影响×3) / (成本×1) — 越高越优先。

## Spec 方法论的核心纪律

1. **没有 spec 不写代码** — 每个优化项必须写清楚"问题-方案-预期-验证"
2. **可回滚** — 每个优化要能独立回滚，不影响其他优化
3. **增量验证** — 一个优化完成后验证通过了再开始下一个
4. **数据驱动** — 优化决策基于报告中的数据，不是主观感受

## 下一步

- 呈现优化 spec → 用户批准后 → 建议运行 `/plan`
- 如果用户想跳过 spec 直接优化某个问题 → 提醒 spec 方法论的价值但尊重用户选择
