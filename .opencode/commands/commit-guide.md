# /commit-guide

分析 staged diff 或 unstaged diff，建议 Conventional Commit 类型和 message，并提醒提交大小风险。

## 执行要求

1. 确认当前目录是 Git 仓库；否则输出明确错误并停止。
2. 优先分析 staged diff。
3. 如果无 staged diff：提示先 `git add`；如存在 unstaged diff，可说明仅分析 unstaged diff。
4. 根据 diff 内容建议合法 commit type：`feat, fix, docs, style, refactor, perf, test, chore`。
5. 生成 1-3 条 commit message 建议，格式为 `<type>: <description>`。
6. 检查大 diff、多意图变更风险：
   - 变更文件数 > 10：标记 Medium Risk。
   - diff 行数 > 500：标记 Medium Risk。
   - 同时修改前端、后端、文档、配置等多个区域。
7. 若 staged diff 混合多个明显意图，标记 High Risk 并建议拆分。
8. 发现 High Risk 时，停止给出可直接执行的 commit 命令，并询问：`是否确认继续？请回复：确认继续 <原因>`。

## 输出

- diff 摘要。
- 推荐 commit type。
- 推荐 commit message。
- 提交大小风险和是否建议拆分。
- 输出可保存到 `docs/git/YYYY-MM-DD-commit-guide.md` 的报告内容。
- 报告包含：当前状态、diff 摘要、规范检查、风险等级、建议操作。
