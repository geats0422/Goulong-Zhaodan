# /branch-guide

根据用户任务类型建议分支，并检查来源分支是否合理。

## 执行要求

1. 确认当前目录是 Git 仓库；否则输出明确错误并停止。
2. 读取用户任务描述：`$ARGUMENTS`。
3. 检查当前分支和是否存在 `develop`。
4. 根据任务类型建议：
   - 新功能：`feature/<short-name>`，建议从 `develop` 创建。
   - 预发布：`release/v<version>`，建议从 `develop` 创建。
   - 线上紧急修复：`hotfix/<short-name>`，建议从 `main` 创建。
5. 如果缺少 `develop`，提示先从 `main` 初始化 `develop`。
6. 使用 `git merge-base`、`git branch --contains`、`git for-each-ref` 等只读命令辅助判断当前分支来源；证据不足时不要猜测。
7. 发现 High Risk 时，停止给出可直接执行的创建、合并、推送命令，并询问：`是否确认继续？请回复：确认继续 <原因>`。

## 命名示例

```text
feature/user-login
feature/payment-flow
release/v1.2.0
hotfix/auth-token-expiry
```

## 输出

- 推荐分支名。
- 推荐来源分支。
- 当前分支是否适合作为来源。
- 创建分支前的注意事项。
- 输出可保存到 `docs/git/YYYY-MM-DD-branch-guide.md` 的报告内容。
- 报告包含：当前状态、推荐分支、规范检查、风险等级、建议操作。
