# /git-check

综合检查当前 Git 状态，并输出可保存到 `docs/git/YYYY-MM-DD-git-check.md` 的报告内容。

## 执行要求

1. 确认当前目录是 Git 仓库；否则输出明确错误并停止。
2. 检查当前分支、upstream、远端同步状态和最近 commits。
3. 检查 staged / unstaged 文件与 diff 摘要。
4. 检查是否存在 `develop` 分支；缺失时提示从 `main` 初始化。
5. 识别 `main` 直改风险：如果当前在 `main` 且有未提交业务改动，标记 High Risk。
6. 根据分支模型和 diff 内容输出 Low / Medium / High 风险等级。
7. 输出建议操作：是否切换分支、是否拆分提交、是否先同步远端。
8. 发现 High Risk 时，停止给出可直接执行的提交、合并、推送、发布命令，并询问：`是否确认继续？请回复：确认继续 <原因>`。

## 报告结构

```text
# Git Check Report

## 当前状态
- 当前分支
- upstream
- staged / unstaged 文件
- 最近 commits

## 规范检查
- 分支命名
- main/develop 使用风险
- commit 类型建议
- 提交大小提醒

## 风险等级
- Low / Medium / High

## 建议操作
```
