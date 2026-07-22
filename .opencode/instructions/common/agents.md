# 智能体编排

## 可用智能体

位于 `.opencode/agents/`：

### 主智能体

| 智能体 | 用途 | 使用场景 |
|--------|------|----------|
| planner | 任务规划 | 复杂功能、重构 |
| architect | 系统设计 | 架构决策 |
| code-reviewer | 代码审查 | 代码编写后 |
| security-reviewer | 安全分析 | 提交前 |

### 子智能体

| 智能体 | 用途 | 使用场景 |
|--------|------|----------|
| tdd-guide | 测试驱动开发 | 新功能、Bug 修复 |
| build-error-resolver | 修复构建错误 | 构建失败时 |
| e2e-runner | 端到端测试 | 关键用户流程 |
| refactor-cleaner | 死代码清理 | 代码维护 |
| doc-updater | 文档更新 | 更新文档 |
| python-reviewer | Python 代码审查 | Python 代码编写后 |
| python-build-resolver | 修复 Python 构建错误 | Python 构建失败时 |
| database-reviewer | 数据库审查 | 数据库相关审查 |

## 立即使用智能体

无需用户提示：
1. 复杂功能请求 - 使用 **planner** 智能体
2. 代码编写/修改后 - 使用 **code-reviewer** 智能体
3. Bug 修复或新功能 - 使用 **tdd-guide** 智能体
4. 架构决策 - 使用 **architect** 智能体
5. Python 代码审查 - 使用 **python-reviewer** 智能体
6. Python 构建错误 - 使用 **python-build-resolver** 智能体

## 并行任务执行

对于独立操作，始终使用并行智能体执行：

```markdown
# 好的做法：并行执行
并行启动 3 个智能体：
1. 智能体 1：认证模块安全分析
2. 智能体 2：缓存系统性能审查
3. 智能体 3：工具类型检查

# 不好的做法：不必要的串行
先智能体 1，再智能体 2，再智能体 3
```

## 多视角分析

对于复杂问题，使用角色分离的子智能体：
- 事实审查员
- 高级工程师
- 安全专家
- 一致性审查员
- 冗余检查器
