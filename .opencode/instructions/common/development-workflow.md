# 开发工作流

> 此文件扩展自 [common/git-workflow.md](./git-workflow.md)，包含 git 操作之前的完整功能开发流程。

功能实现工作流描述了开发管道：规划、TDD、代码审查，然后提交到 git。

## 功能实现工作流

1. **先规划**
   - 使用 **planner** 智能体创建实施计划
   - 识别依赖关系和风险
   - 分解为多个阶段

2. **TDD 方法**
   - 使用 **tdd-guide** 智能体
   - 先写测试（红色）
   - 实现以通过测试（绿色）
   - 重构（改进）
   - 验证覆盖率 80%+

3. **代码审查**
   - 编写代码后立即使用 **code-reviewer** 智能体
   - 解决 CRITICAL 和 HIGH 问题
   - 尽可能修复 MEDIUM 问题

4. **提交与推送**
   - 详细的提交信息
   - 遵循 conventional commits 格式
   - 提交信息格式和 PR 流程见 [git-workflow.md](./git-workflow.md)

## 摩擦预防（2026-07-11 沉淀）

会话 `<learn>` 复盘沉淀。完成任何任务收尾自检，避免反复踩同类低级坑。

### 6 条 AI 低级错误自查清单（提交/部署前逐条勾选）

- [ ] **缓存**：本次是否改了前端？浏览器必须 **强刷**（Ctrl+Shift+R）才能生效；告诉用户一次"请强刷"，而不是反复猜测"为什么没生效"。改完后用 `curl -s $URL | sha256sum` 对比 dist 资源哈希，避免"假部署"。
- [ ] **代理**：本次是否新增前端 API 路由（如 `/payment/`、`/subscription/`）？必须在 `nginx/conf.d/*.conf` 加 `location` 转发。**两套文件都要改**：
  1. 服务器实际生效文件（`/opt/goulong/<repo>/nginx/conf.d/<site>.conf`）
  2. 仓库模板（`repos/<repo>/deploy/nginx/conf.d/<site>.conf`）
     优先级陷阱：`location = /xxx/` 精确匹配在 `location /xxx/` 前缀匹配之前；当前缀会同时拦截 SPA 页面 URL 时必须用精确匹配优先于前缀匹配（SPA fallback vs API 转发）。
- [ ] **硬编码**：不要在 PR 信息、代码注释、会话记忆中留下真实凭证（测试账号、证书、私钥）。错误信息可以贴已被 mask 的指纹（如 `gho_***`）。
- [ ] **环境**：不要假设用户机器上的 `.env` 已经包含这次变动。**让 AI 用 bash 改 `.env` 经常失败**——优先让用户在 Tabby 自己改，并把完整 diff 给到。
- [ ] **证书**：微信 v3 / 支付宝公钥等敏感配置变更，要在**老凭证超时窗口之后**生效；改动后用 ¥0.01 测试包做真实 e2e 验证（不是 unit test），不要假设 Pytest 通过就等于生产链路通。
- [ ] **迁移**：数据库字段/Pydantic 模型变更后，运行 `alembic current` 对照最新迁移版本号 — 如果混用 `str | None` 与 `datetime | None` 之类，序列化会在运行时 500。

### AI 自查前先确认根因

> 任何"为什么 X 不工作"的问题，先问"我修改了什么"——而不是先猜 X 应该工作。

尤其要警惕三种"假成功"：

1. **git push 成功 ≠ 远端更新**：本地沙盒与用户远端是两套独立环境。push 输出成功不代表用户机器已同步，必须让用户 `git pull --ff-only` 后再继续。
2. **commit 成功 ≠ 已部署**：文件改动还在工作树，必须 `docker compose build` + `up -d` 才进容器。
3. **容器 started ≠ 健康**：docker compose up -d 后查看实际 `STATUS`，等 `(healthy)` 才认定为可服务。

**反面案例（本次会话真实发生）**：
- AI 在沙盒 bash 跑 `git push` 假装"已经推送"，用户 Tabby pull 后说"没收到提交" → **浪费一轮往返 + 用户愤怒**。
- AI 改后端 Pydantic `str | None` → `datetime | None`，但用户只重建 nginx **没有重建后端**，部署 1 小时后才生效 → **这是最低级错误**。
- nginx `location /settings/` 同时拦截 SPA 页面 + API，导致前端强刷 URL 404 → 设计代理规则时必须区分精确匹配与前缀匹配。
