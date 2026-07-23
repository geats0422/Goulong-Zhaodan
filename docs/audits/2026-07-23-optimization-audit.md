# 句龙照胆优化审计报告

**日期**: 2026-07-23  
**范围**: 文档体检存储链路、数据统计真实性、统计页 footer 布局、`DESIGN.md` 设计规范符合度
**结论**: 需要优先修复当前阶段误启 OSS 导致文档体检不可用的问题，其次修复统计数据源，再统一应用壳布局和设计 token。

## 评分概览

| 维度 | 评分 | 主要原因 |
| --- | --- | --- |
| 文档体检可用性 | 2/10 | `/inspection/parse` 上传链路仍走 OSS，OSS 502 直接导致文档体检 500 |
| 数据统计真实性 | 3/10 | 统计接口读取进程内缓存 `_inspection_records`，不是数据库真实记录；异步 worker 与 API 进程内存不共享 |
| 统计页布局 | 6/10 | 页面使用 flex 外壳，但 `statistics-main` 未占据剩余高度，空数据时 footer 不贴底 |
| 设计规范符合度 | 5/10 | 多处仍使用旧暖色/浅色方案、`Geist`/`Noto Serif` 字体和非设计色值 |
| 可验证性 | 6/10 | 前端构建通过；后端统计测试受本地 PostgreSQL 连接失败阻塞 |

## 高优先级问题

### 1. 当前阶段误启 OSS，导致文档体检不可用

- 位置: `backend/app/api/v1/inspection.py:490`、`backend/app/services/file_storage.py:46`、`backend/app/services/file_storage.py:105`
- 当前行为: `/inspection/parse` 读取上传内容后调用 `save_file(source_path, content)`；`save_file()` 只要检测到 `oss_bucket_name` 和 `oss_endpoint` 非空，就直接走 OSS `put_object()`。
- 观察到的错误: `oss2.exceptions.ServerError: {'status': 502, 'x-oss-request-id': '', 'details': {}}`，请求最终返回 `POST /inspection/parse` 500。
- 根因判断:
  - 设计意图是“OSS 留空时使用 ECS/本机本地存储 UPLOAD_DIR；配置完整时才启用 OSS”，见 `backend/env.example:52`。
  - 当前项目仍处于前期阶段，预期应和文衡一样先走本地存储；但实际运行环境配置了 OSS bucket/endpoint，触发 OSS 分支。
  - OSS 调用失败没有被转换为可恢复的本地存储路径，也没有返回可读的业务错误，因此直接阻断文档体检。
- 风险:
  - 用户无法上传文档进入体检流程。
  - OSS 网络、凭据、endpoint 或代理波动会把核心体检能力打挂。
  - 环境配置稍有残留就会误启 OSS，本地开发和早期部署不可控。
- 建议:
  - 增加显式存储模式开关，例如 `FILE_STORAGE_BACKEND=local|oss`，当前默认 `local`。
  - 在早期阶段即使存在 OSS 配置，也应由显式开关决定是否启用 OSS，而不是仅靠 bucket/endpoint 非空。
  - 本地模式统一使用 `UPLOAD_DIR`，并在启动时输出当前存储后端的只读诊断日志。
  - 对 `save_file()` 的 OSS 异常转换为稳定业务错误，避免原始 SDK 异常冒泡成 500。
  - 增加测试: OSS 配置存在但 `FILE_STORAGE_BACKEND=local` 时，`save_file()` 必须写入本地；`FILE_STORAGE_BACKEND=oss` 且 OSS 失败时返回可控错误。

### 2. 统计接口不是数据库真实数据

- 位置: `backend/app/api/v1/inspection.py:716`
- 当前行为: `get_history_stats()` 从 `_inspection_records` 过滤统计。
- 风险:
  - 服务重启后统计丢失。
  - API 进程与 ARQ worker 进程内存隔离，worker 中 `append_history_record()` 对 API 统计不可见。
  - 多实例部署时各实例统计不一致。
- 证据:
  - `backend/app/services/inspection_runner.py:47` 明确标注 `_inspection_records` 是“内存中的体检记录缓存”。
  - `backend/app/workers/tasks.py:818` worker 完成后调用 `append_history_record(record)`，但这是 worker 进程内存。
  - `backend/app/models/knowledge.py:169` 已有 `InspectionRecord` 数据库模型，具备 `user_id`、`project_id`、`issues`、`quota_consumed`、`created_at` 字段。
- 建议:
  - 将 `/inspection/stats/history` 改为依赖 `db=Depends(get_db_session)`，直接查询 `InspectionRecord`。
  - 用 SQL 按 `created_at` 日期聚合 `total_docs`、`hit_docs`、`quota_consumed`。
  - 过滤条件必须包含当前 `user_id`、`project_id`、最近 7 天，以及排除未完成/待处理记录。
  - 保留 `_aggregate_history_stats()` 作为纯函数时，应输入数据库查询结果，而不是进程缓存。

### 3. 错误兜底会把真实问题表现成“0 数据”

- 位置: `frontend/src/pages/StatisticsPage.vue:57`
- 当前行为: 请求失败时把 `stats` 重置为全 0，同时页面只在趋势区显示“加载失败”。
- 风险: 用户可能误判为没有使用数据，截图中的 0 无法区分“真实为空”和“接口失败/认证失败”。
- 建议:
  - 请求失败时保留上一份成功数据，summary 卡片显示错误态或 `--`。
  - 将错误提示提升到 summary 上方，明确“统计暂不可用”，不要静默覆盖为 0。
  - 记录响应状态码，401/403 应引导重新登录，500 应提示稍后重试。

### 4. 统计页 footer 不贴底

- 位置: `frontend/src/pages/StatisticsPage.vue:170`
- 当前行为: `.statistics-main` 只有固定 padding，没有 `flex: 1`。
- 相关外壳: `frontend/src/style.css:16` 的 `.dashboard-page` 是 `display:flex; flex-direction:column; min-height:100vh`。
- 风险: 空数据页内容高度不足时，footer 跟随内容漂在页面中部。
- 建议:
  - 给 `.statistics-main` 增加 `flex: 1`，让主内容吸收剩余高度。
  - 或抽出统一 `.app-main` / `.dashboard-main` 布局类，统计页、设置页、知识库页统一复用。

## 设计规范偏差

### 1. 字体系统未完全应用

- `DESIGN.md` 规定: 标题 `Syne`，正文 `Hanken Grotesk`，标签/元数据 `JetBrains Mono`。
- 当前全局字体导入 `frontend/src/style.css:1` 包含 `Geist` 和 `Noto Serif`，但没有导入 `Syne` 或 `JetBrains Mono`。
- 统计页仍使用 `Geist` 和 `Noto Serif`: `frontend/src/pages/StatisticsPage.vue:188`、`:196`、`:203`、`:227`、`:235`。
- 导航仍使用 `Geist` 和 `Noto Serif`: `frontend/src/components/app/AppTopNav.vue:201`、`:235`、`:305`。
- 建议:
  - 全局 import 改为实际设计字体。
  - 建立 CSS 变量: `--font-display`、`--font-body`、`--font-mono`。
  - 将页面内硬编码字体替换为变量。

### 2. 暖色浅色旧主题仍在多个业务页存在

- 明显偏离 `Neo-Chinese Cyberpunk` 深色规范的文件:
  - `frontend/src/pages/HistoryPage.vue:362` 使用 `#faf6ea` 到 `#efe5c7` 浅色背景。
  - `frontend/src/pages/LoginPage.vue:359`、`frontend/src/pages/RegisterPage.vue:399` 使用浅色/米色表面。
  - `frontend/src/components/inspection/InspectionReviewModal.vue:661`、`:667`、`:683`、`:692` 使用 `#faf8f4` / `#fff`。
  - `frontend/src/components/inspection/InspectionReportPane.vue:436` 使用 `#faf8f4`。
  - `frontend/src/components/inspection/DocumentPreviewPane.vue:128` 使用 `#fff`。
- 建议:
  - 先统一 app 内页和核心审查组件，营销页可单独评估。
  - 明确 light theme 是否仍属于产品能力；若保留，需要在 `DESIGN.md` 增补 light token，而不是散落硬编码。

### 3. 颜色 token 分散，设计系统难以落地

- `frontend/src/style.css` 中存在大量非 `DESIGN.md` 色值；静态统计显示非规范色值主要集中在:
  - `frontend/src/style.css`: 239 处
  - `frontend/src/pages/SettingsPage.vue`: 29 处
  - `frontend/src/pages/LoginPage.vue`: 29 处
  - `frontend/src/pages/HistoryPage.vue`: 26 处
  - `frontend/src/components/inspection/InspectionReviewModal.vue`: 24 处
- 建议:
  - 建立 `frontend/src/styles/tokens.css` 或在 `style.css` 顶部完整映射 `DESIGN.md` token。
  - 新增轻量脚本检查未知 hex 色值和未知 font-family，作为设计规范回归测试。

## 中优先级问题

1. `backend/app/api/router.py` 只挂了 `document_jobs_router`，而主应用直接 include 多个 v1 router，API 前缀不统一；统计接口当前是 `/inspection/stats/history`，设计文档曾写 `/api/v1/stats/history`，需要统一公开契约。
2. 统计图 `bannedPercent` 直接用百分比数值作为柱高，低百分比靠 `Math.max(..., 6)` 强制可见，适合 MVP，但不适合精确数据图表。
3. `quota_consumed` 口径不统一: 同步审查用 `result.total_quota_consumed or max(1, len(text)//500)`，worker 用 `max(1, len(markdown)//500)`，真实额度统计会混合两种算法。

## 验证记录

- `npx gitnexus analyze`: 通过，索引已更新到当前仓库状态。
- `npm run build`（frontend）: 通过。
- `uv run pytest tests/test_history_stats_api.py -q`（backend）: 未通过，失败在测试夹具连接本地 PostgreSQL `goulong_test` 时连接中途关闭，不是统计断言失败。
- 用户提供的 `/inspection/parse` 异常栈: 已确认失败点为 `file_storage.save_file()` 调用 OSS `put_object()` 返回 502。

## 建议修复顺序

1. 增加显式本地/OSS 存储模式开关，当前阶段默认本地存储，恢复文档体检可用性。
2. 改造统计接口为数据库聚合，并补齐数据库级测试。
3. 修复统计页错误态和 footer 贴底。
4. 统一字体导入和 CSS token，先覆盖统计页、导航、footer。
5. 分批迁移历史页、审查弹窗、报告面板、登录注册页的旧浅色硬编码。
6. 增加设计规范静态检查脚本，防止后续再引入非规范字体/颜色。
