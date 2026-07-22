---
name: continuous-learning
description: 复利学习系统。从每个会话中提取可复用模式，经过置信度积累自动进化为规则/技能/Agent。贯彻"每次对话都在为下一次充电"的复利效应。
---

# 持续学习 /learn — 复利效应引擎

每次运行 `/learn`，你都在为未来的会话注入更多智能。

## 核心理念

```
会话 1: "这个项目用函数式风格"     → learning (confidence 0.3)
会话 2: "用户又纠正到函数式风格"    → confirmed (confidence 0.5)
会话 3: "函数式风格已成为团队规范"   → confirmed (confidence 0.7)
  → 自动建议: "要升级为 rule 吗？"
  → 用户批准 → 写入 rules/common.md
  → 从此所有会话自动遵循
```

这是 AI 编码的复利：**每次经验提取都在降低未来的认知成本。**

## 学习条目格式

保存到 `~/.opencode/learnings/<project>/entries/*.md`：

```yaml
---
id: "20260511-a1b2c3"
type: pattern | fix | convention | tool | architecture
domain: code-style | testing | debugging | security | workflow | performance
scope: project | global
confidence: 0.3
confirmed_in: 1
sessions: ["2026-05-10-用户认证", "2026-05-11-API重构"]
---
# What
[描述这个学习到的模式/经验]

# Trigger  
[什么场景下应该回想这个经验]

# Why It Matters
[不遵循会出什么问题]

# Evidence
- [日期]: [从哪个事件中学到]
- [日期]: [再次确认的事件]
```

## 频次与阈值

```
学习     ← /learn (每次会话至少一次)
   ↓
确认     ← 同一模式被 2+ 次会话确认 → confidence 0.4-0.6
   ↓
建议升级 ← confidence ≥ 0.7 → 向用户建议 promotion
   ↓
升级     ← 用户批准 → 固化为 skill / rule / agent prompt
```

**阈值表：**
| confidence | 状态 | 行为 |
|-----------|------|------|
| 0.1-0.3 | tentative | 仅记录 |
| 0.4-0.6 | likely | 下次会话自动加载提醒 |
| 0.7-0.8 | confident | 建议升级为 rule |
| 0.9-1.0 | near-certain | 自动升级（静默） |

## 提取什么

当你运行 `/learn` 时，分析当前会话并提取：

### 1. 错误解决模式
- 什么错误？根因是什么？怎么修的？
- 能否复用？下次类似错误应该怎么做？

### 2. 项目约定发现
- 代码库中的隐藏约定（命名、文件组织、测试风格）
- 架构决策及其原因
- 哪些模式被反复使用？

### 3. 调试技巧
- 非显而易见的排查步骤
- 有效的工具组合

### 4. 变通方案
- 库的特殊行为
- API 限制及其绕过方式
- 版本特定修复

### 5. 工作流优化
- 什么命令组合效果好
- 什么顺序效率高

## 不要提取的

- ❌ 琐事（typo 修复、简单语法错误）
- ❌ 一次性事件（特定 API 故障等）
- ❌ 通用常识（先搜再写这是 ETHOS.md 已经说了的）
- ❌ 已经有 skill 覆盖的内容

## 升级目标

当一个学习条目的 confidence 达到 0.7+，建议将其升级为：

| 类型 | 升级为 | 写入位置 |
|------|--------|---------|
| `convention` / `pattern` | rule | `rules/common.md` 或 `rules/<lang>.md` |
| `fix` / `tool` / `workflow` | skill | `skills/<name>/SKILL.md` |
| `architecture` | agent prompt | `prompts/<agent>.txt` |
| `workflow` (跨项目通用) | command | `opencode.json` → command 段 |

## 复利自强化

每次运行 `/learn` 时：

1. **加载已有学习** — 先读取 `~/.opencode/learnings/<project>/entries/` 中的已有条目
2. **对比并确认** — 本次提取的模式与已有条目对比
   - 匹配 → confidence += 0.2, confirmed_in += 1
   - 新发现 → 新建条目 (confidence 0.3)
3. **检查升级阈值** — 任何条目达到 0.7 → 输出升级建议
4. **报告复利积累** — 总结当前项目的学习积累状态

## 输出格式

```markdown
## /learn 报告 — [项目名]

### 本次新增
- [domain] [描述] (confidence 0.3)

### 已确认 (confidence 提升)
- [domain] [描述] (0.5 → 0.7 ⚡ 建议升级)

### 建议升级
- ⚡ **[convention] 函数式风格优先** → 升级为 rule？(confidence 0.7, 3 sessions)
- ⚡ **[fix] 避免在 useEffect 中做同步 fetch** → 升级为 skill？(confidence 0.7, 2 sessions)

### 复利统计
| 总学习条目 | 已确认(≥0.4) | 待升级(≥0.7) | 已升级 |
|-----------|-------------|-------------|--------|
| 12 | 5 | 2 | 1 |
```

## 下一步

- 如果有升级建议 → 询问用户 "要升级 X 吗？(y/n)"
- 如果用户批准 → 执行升级（写入对应文件）
- 保存本次提取结果
