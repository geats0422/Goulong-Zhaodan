---
name: insights
description: AI 教练 — 分析过去 30 天的使用数据，识别摩擦模式，自动生成优化建议和配置更新方案。基于 git 历史 + learnings + 现有配置综合诊断。
---

# /insights — 使用分析与优化建议

像一个 AI 教练复盘你的编码习惯。分析你的使用数据，告诉你哪里可以改进，并自动生成具体的配置优化方案。

## 数据来源（本地，零上传）

| 数据源 | 用途 |
|--------|------|
| `git log --since="30 days ago"` | 提交频率、文件改动、fix/revert 模式 |
| `git log --stat` + `git diff` | 高频修改文件（热点分析）、代码增删量 |
| `~/.opencode/learnings/<project>/entries/` | 学习系统健康状况 |
| `Project/{项目名称}/docs/friction-log.md` (如存在) | 手动记录的摩擦事件 |
| `.opencode/AGENTS.md` / `ETHOS.md` / `rules/` / `skills/` | 现有配置完整度诊断 |
| `.opencode/opencode.json` | 命令/Agent 使用覆盖分析 |

## 分析维度

### 1. 活动概览
```bash
# 提交统计
git log --since="30 days ago" --oneline | wc -l

# 活跃天数
git log --since="30 days ago" --format="%ad" --date=short | sort -u | wc -l

# 代码量
git diff --stat HEAD~N..HEAD 2>/dev/null || git log --since="30 days ago" --shortstat

# 涉及语言
git log --since="30 days ago" --name-only --pretty=format: | grep -v "^$" | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -10
```

### 2. 热点文件分析
```bash
# 最常修改的文件 (可能的摩擦点或核心文件)
git log --since="30 days ago" --name-only --pretty=format: | grep -v "^$" | sort | uniq -c | sort -rn | head -15
```
高频率修改可能表明：
- **设计问题**：文件承担了太多职责
- **摩擦点**：反复修复同一个文件
- **活跃开发**：核心功能正常迭代（需要上下文判断）

### 3. 修复 vs 功能模式
```bash
# 修复/回滚比例
git log --since="30 days ago" --oneline --grep="fix\|bug\|revert\|rollback" | wc -l
```
如果 fix 提交占比 > 40%，可能表明：
- 测试覆盖率不足
- 代码审查流程薄弱
- 复杂度过高

### 4. 学习系统诊断
读取 `~/.opencode/learnings/<project>/entries/`，分析：
- 总条目数 vs 已确认数 vs 待升级数
- 各 domain（code-style/testing/debugging/security/workflow）分布
- 是否有 ≥ 0.7 confidence 的条目尚未升级
- 是否存在 0 domain 覆盖盲区

### 5. 配置完整度诊断
检查当前 `.opencode/` 下已有和缺失的配置：

```
已有:             推荐至少拥有:        缺失:
skills/  (11个)   brainstorming ✓     —
                  code-review ✓       —
                  tdd-workflow ✓      —
                  security-review ✓   —
                  systematic-debugging ✓ —
                  insights ✓          —
                  ★ 缺失提示: 考虑添加 frontend/backend 特定 patterns

rules/ (1个)      common.md ✓         —
                  ★ 缺失提示: 如果有 TS/Python/Go 项目，添加对应 rules

agents/ (7个)     build ✓ planner ✓   —
                  reviewer ✓ debugger ✓
                  security-reviewer ✓
                  implementer ✓ learn-agent ✓
                  ★ 评估: Agent 覆盖完整

commands/ (12个)  brainstorm/plan/execute/finish ✓
                  review/debug/security ✓
                  quality ✓ learn ✓ insights ✓
                  ★ 评估: 命令覆盖完整
```

### 6. 摩擦点识别
通过 git 历史识别：
- **Revert 提交** → 具体原因是什么？
- **同一文件反复修改** (> 5 次/月) → 设计问题还是需求变化？
- **Merge conflict 频率** → 团队协作问题？
- **Commit message 中的"again""still""another try"** → 未一次解决的问题？

### 7. 模型效率评估 (如果适用)
- 平均每个任务用了多少次工具调用？
- 是否存在明显的 token 浪费（如重复读取同一文件）？
- 子代理的派发频率和成功率如何？

## 输出格式

保存到 `Project/{项目名称}/docs/insights/YYYY-MM-DD-insights.md`：

```markdown
# Usage Insights Report

**日期**: YYYY-MM-DD
**项目**: [project-name]
**分析周期**: 过去 30 天

---

## 📊 活动概览

| 指标 | 数值 |
|------|------|
| 总提交数 | X |
| 活跃天数 | Y |
| 新增代码行 | +A |
| 删除代码行 | -B |
| 主要语言 | TS(60%), CSS(20%), JSON(20%) |
| fix/revert 占比 | Z% |

---

## 🔥 热点文件 Top 10

| 文件 | 修改次数 | 可能原因 |
|------|---------|---------|
| src/App.tsx | 12 | 核心组件 — 正常 |
| src/utils/api.ts | 11 | ⚠ 高频率 — 检查是否承担过多职责 |
| ... | | |

---

## 🐛 修复模式分析

- 修复/功能比: X/Y (Z%)
- 最常见的修复类型:
  - "类型错误" (5 次) → 建议: 启用 strict mode
  - "导入缺失" (3 次) → 建议: 配置 auto-import
  - "样式异常" (2 次) → 建议: 添加设计规范 rule

---

## 🧠 学习系统健康度

| 指标 | 数值 |
|------|------|
| 总条目 | 15 |
| 已确认 (≥0.4) | 8 |
| 待升级 (≥0.7) | 3 ⚡ |
| 已升级 | 2 |
| 盲区 domain | testing (0条), performance (0条) |

**建议**: 3 个条目 ready to promote → 运行 `/learn-evolve`

---

## ⚙️ 配置完整度

| 组件 | 现状 | 建议 |
|------|------|------|
| Skills | 11 个 ✅ | 考虑添加 frontend-patterns |
| Rules | 1 个 ⚠ | 建议添加 typescript.md |
| Agents | 7 个 ✅ | 覆盖完整 |
| Commands | 12 个 ✅ | 覆盖完整 |

---

## 🔍 摩擦点

| 模式 | 证据 | 建议 |
|------|------|------|
| 类型错误反复出现 | 5 次 "fix: type error" 提交 | 启用 tsc strict mode，添加 pre-commit hook |
| 导入缺失 | 3 次 import 修复 | 配置 organize-imports on save |
| 样式调整多轮 | 4 次同一 CSS 文件修改 | 设计评审前移，在 brainstorming 阶段确认视觉 |

---

## 🎯 优化建议（可直接操作）

### 立即执行（高优先级）
1. **[配置] 启用 TypeScript strict mode**
   - 原因: 5 次类型错误修复
   - 操作: 修改 tsconfig.json → strict: true
   - 影响: 减少 80% 类型相关 bug

2. **[学习升级] 3 个 learnings ready to promote**
   - 原因: confidence ≥ 0.7
   - 操作: 运行 `/learn-evolve`
   - 影响: 将经验固化为永久规则

### 计划执行（中优先级）
3. **[新技能] 创建 frontend-patterns skill**
   - 原因: 多次重复的组件模式
   - 操作: 运行 `skill create` 或参考 ECC 的 frontend-patterns
```

---

## 自动生成的配置建议

在报告末尾，列出可以直接复制粘贴的配置更新：

```markdown
## 📝 建议添加到 rules/common.md

### 类型安全
- 所有 TypeScript 项目必须启用 strict mode
- 禁止使用 `any` 除非有明确注释说明原因

### 导入管理  
- 每次文件编辑后检查 import 是否完整
- 未使用的 import 必须删除

---

## 📝 建议添加到 AGENTS.md

### 样式修改规则
- 修改 UI 时先确认设计方向再进行代码修改
- 不要在一个任务中混合样式修改和逻辑修改
```

## 触发条件

- 用户运行 `/insights`
- 用户说"分析我的使用情况"、"复盘编码习惯"、"AI 教练"、"insights"

## 注意事项

- 如果项目没有 git 历史 → 说明限制，仅做配置诊断和学习系统诊断
- 不做 git push，不上传任何数据
- 报告保存在 `Project/{项目名称}/docs/insights/` 目录（gitignorable）
- 聚焦可操作的优化建议，不要泛泛而谈
