# /release-check

检查 release 分支和发版准备状态。

## 执行要求

1. 确认当前目录是 Git 仓库；否则输出明确错误并停止。
2. 检查当前是否在 `release/*` 分支，命名示例：`release/v1.2.0`。
3. 检查 release 分支是否应从 `develop` 创建；来源不清时标记风险。
4. 检查是否存在未提交变更、未同步 upstream 或未完成冲突处理。
5. 检查测试、文档、版本准备：
   - 列出实际测试命令、CI 状态或明确待运行项。
   - 列出文档/变更说明文件路径。
   - 列出版本号或 release notes 文件路径。
6. 检查回合并路径：release 应合并到 `main`，并回合并到 `develop`。
7. 使用 `git merge-base`、`git branch --contains`、`git for-each-ref` 等只读命令辅助判断来源；证据不足时不要猜测。
8. 发现 High Risk 时，停止给出可直接执行的合并、推送、发布命令，并询问：`是否确认继续？请回复：确认继续 <原因>`。

## 输出

- release 分支命名检查。
- 测试、文档、版本准备清单。
- 合并到 `main` 与回合并 `develop` 的建议路径。
- 风险等级和继续条件。
- 输出可保存到 `docs/git/YYYY-MM-DD-release-check.md` 的报告内容。
- 报告包含：当前状态、规范检查、风险等级、建议操作。
