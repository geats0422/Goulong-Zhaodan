---
name: github-repo-governance
description: Use when discussing Git 规范、分支、commit、push、merge、release、hotfix、PR or GitHub repository governance checks.
---

# GitHub Repo Governance

用于个人项目的轻量 Git/GitHub 仓库治理规则。遇到 Git 规范、分支、commit、push、merge、release、hotfix、PR 相关任务时使用。

## 分支模型

| 分支 | 作用 | 来源 | 合并目标 |
|------|------|------|----------|
| `main` | 稳定生产分支 | 无 | 不直接开发 |
| `develop` | 日常开发集成分支 | `main` 初始化 | `release/*` 或最终回 `main` |
| `feature/*` | 新功能开发 | `develop` | `develop` |
| `release/*` | 预发布稳定 | `develop` | `main` + `develop` |
| `hotfix/*` | 紧急线上修复 | `main` | `main` + `develop` |

分支命名示例：

```text
feature/user-login
feature/payment-flow
release/v1.2.0
hotfix/auth-token-expiry
```

## Commit 规范

采用混合 Conventional Commits：

```text
<type>: <description>
```

允许的 commit 类型：`feat, fix, docs, style, refactor, perf, test, chore`。

描述可使用中文或英文，例如：

```text
feat: 新增登录页面
fix: handle auth timeout
docs: 更新部署说明
```

## 风险等级

- **Low**：分支和 diff 符合规范，仅需常规确认。
- **Medium**：存在提交过大、缺少 upstream、未同步 develop 等可修复风险。
- **High**：需要用户显式确认后继续。

High Risk 规则：

- 当前在 `main` 上有未提交业务改动。
- `feature/*` 不是从 `develop` 创建。
- `release/*` 不是从 `develop` 创建。
- `hotfix/*` 不是从 `main` 创建。
- commit message 缺少合法 type。
- staged diff 同时混合多个明显意图。
- release 分支有未完成测试或未更新文档。
- `/commit-guide` 中变更文件数 > 10 或 diff 行数 > 500 时至少标记 Medium Risk。

## 命令使用

- `/branch-guide`：开始任务前，建议 `feature/*`、`release/*` 或 `hotfix/*` 分支。
- `/git-check`：开发过程中，检查当前分支、upstream、diff、最近 commits 和风险。
- `/commit-guide`：提交前，分析 staged/unstaged diff 并建议 commit message。
- `/release-check`：发版前，检查 release 分支、测试、文档、版本和回合并路径。
- `/hotfix-check`：紧急修复时，检查 hotfix 来源、范围和回合并路径。

## 错误处理

- 当前目录不是 Git 仓库时，明确报错并停止检查。
- 缺少 `develop` 时，提示从 `main` 初始化 `develop`，不要静默跳过。
- 没有 staged diff 时，`/commit-guide` 提示先 `git add` 或说明仅分析 unstaged diff。
- 无法判断项目名称时，报告输出到当前仓库的 `docs/git/`。
