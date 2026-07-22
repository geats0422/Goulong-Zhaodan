# /hotfix-check

检查 hotfix 分支、紧急修复范围和回合并路径。

## 执行要求

1. 确认当前目录是 Git 仓库；否则输出明确错误并停止。
2. 检查当前是否在 `hotfix/*` 分支，命名示例：`hotfix/auth-token-expiry`。
3. 检查 hotfix 分支是否应从 `main` 创建；若不是，标记 High Risk。
4. 检查修复范围是否聚焦紧急问题，避免混入新功能或无关重构。
5. 检查 staged/unstaged diff 是否只包含紧急修复必要文件。
6. 检查回合并路径：hotfix 应合并回 `main`，并回合并到 `develop`。
7. 使用 `git merge-base`、`git branch --contains`、`git for-each-ref` 等只读命令辅助判断来源；证据不足时不要猜测。
8. 发现 High Risk 时，停止给出可直接执行的合并、推送、发布命令，并询问：`是否确认继续？请回复：确认继续 <原因>`。

## 输出

- hotfix 分支来源检查。
- 紧急修复范围检查。
- 回合并 `main` 和 `develop` 的建议路径。
- 风险等级和继续条件。
- 输出可保存到 `docs/git/YYYY-MM-DD-hotfix-check.md` 的报告内容。
- 报告包含：当前状态、规范检查、风险等级、建议操作。
