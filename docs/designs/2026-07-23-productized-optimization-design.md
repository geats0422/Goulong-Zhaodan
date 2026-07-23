# 句龙照胆产品化优化设计文档

## 目标

本轮以一个大版本完成照胆产品化优化：恢复文档体检可用性，确保数据统计来自真实使用数据，修复统计页状态和 footer 布局，并将 `DESIGN.md` 落成可维护的明暗双主题设计系统。

本轮采用“代码实施可分阶段、产品验收一次性”的节奏。实施时可以先完成并验证 `/inspection/parse` 本地存储修复，降低核心链路不可用风险；但对外交付以存储、统计、主题和设计规范检查全部完成为准。

## 用户场景

用户上传文档后，照胆应在当前前期阶段默认使用本地存储完成解析和体检，不因为环境中残留 OSS 配置而误走 OSS。

用户进入数据统计页时，应看到自己近 7 天真实使用情况。上传、完成、命中、失败、待处理和额度消耗需要有明确口径；接口失败不能伪装成真实的 0 数据。

用户在任意页面切换深色、浅色或系统主题后，整个应用都应保持一致。跳转到统计页、设置页、历史页、体检台、登录页或营销页时，不应出现局部页面主题与全局主题冲突。

## 技术方案

### 存储模式

新增显式配置 `STORAGE_BACKEND=local|oss`，默认值为 `local`，包括生产环境。

`is_oss_enabled()` 只有在以下条件同时满足时才返回 true：

- `STORAGE_BACKEND=oss`
- OSS bucket 配置完整
- OSS endpoint 配置完整
- OSS access key 可用

如果 `STORAGE_BACKEND` 未配置，或配置为 `local`，即使环境中存在 OSS bucket/endpoint，也必须走本地 `UPLOAD_DIR`。

生产环境中如果显式配置 `STORAGE_BACKEND=oss`，但 OSS 必要配置不完整，应在启动安全检查中失败，而不是运行时才暴露为上传 500。

本轮不做 OSS 到本地的历史对象迁移。当前没有真实用户数据；如果某个环境确实已有 OSS 对象且需要读取，必须显式设置 `STORAGE_BACKEND=oss`。

### 文档体检上传链路

`/inspection/parse` 继续保存后端无关的相对 `storage_path`。数据库不保存本地绝对路径，也不保存 OSS URL。

本地模式下，`save_file()` 将相对路径解析到 `UPLOAD_DIR` 下，并继续执行路径遍历防护。OSS 模式下，相对路径通过 `OSS_PREFIX` 转换为 OSS key。

OSS 写入、读取、删除失败时，应转换为稳定业务错误，例如“文件存储服务暂时不可用”。不得让 OSS SDK 原始 502 或内部异常直接冒泡成不可读 500。

### 统计数据源

`/inspection/stats/history` 改为直接查询数据库中的 `InspectionRecord`，不再读取进程内 `_inspection_records`。

统计接口支持两个模式：

- 不传 `project_id`：统计当前用户全部项目或场景的近 7 天使用数据。
- 传 `project_id`：只统计该项目。

前端本轮先使用全局统计，不展示项目筛选；后端保留参数能力，供未来项目维度统计 UI 使用。

### 体检记录状态

新增 `InspectionRecord.status` 作为体检记录主状态字段，统计、历史列表和前端状态展示优先使用该字段。

允许状态：

- `uploaded`
- `processing`
- `completed`
- `failed`
- `cancelled`

`DocumentProcessingJob.status` 继续表示异步任务状态。同步体检、异步体检和未来 agent 体检都应同步维护 `InspectionRecord.status`，避免统计接口通过 `issues is null` 或 join job 做脆弱推断。

迁移历史数据时采用以下规则：

- `overall_risk = 'pending'`，或 `issues = []` 且 `parsed_content` 为空：标记为 `processing`
- 有明确报告结果的记录：标记为 `completed`
- 已关联失败 job 的记录：标记为 `failed`

新创建的 `/inspection/parse` 记录由于会立即创建处理任务，推荐初始状态为 `processing`。同步体检入口成功后直接标记 `completed`；如果失败且已创建记录，则标记 `failed`。

### 新统计契约

由于当前没有真实用户，本轮允许前后端同步切换到新契约，不保留旧字段兼容。

响应示例：

```json
{
  "range": "7d",
  "summary": {
    "uploaded_docs": 12,
    "completed_docs": 10,
    "hit_docs": 5,
    "failed_docs": 1,
    "pending_docs": 1,
    "hit_rate": 0.5,
    "quota_consumed": 38
  },
  "trend": {
    "dates": ["2026-07-17", "2026-07-18"],
    "uploaded_docs": [2, 10],
    "completed_docs": [2, 8],
    "hit_docs": [1, 4],
    "failed_docs": [0, 1],
    "pending_docs": [0, 1],
    "hit_rate": [0.5, 0.5],
    "quota_consumed": [6, 32]
  }
}
```

字段口径：

- `uploaded_docs`：已创建 `InspectionRecord`，进入体检流程的文档数。
- `completed_docs`：完成体检并有明确结果的文档数。
- `hit_docs`：完成体检且命中问题的文档数。
- `failed_docs`：解析或体检失败的文档数。
- `pending_docs`：仍在上传后处理、解析或审查中的文档数。
- `hit_rate`：`hit_docs / completed_docs`。当 `completed_docs = 0` 时返回 0。
- `quota_consumed`：真实落库额度消耗。

统计图中上传数照常计入，命中文档数只统计有明确结果的已完成记录。失败或待处理文档不应被误算为“未命中”。

额度算法本轮不重做，只确保统计读取真实落库值。同步体检和 worker 体检的额度计算口径统一作为后续独立事项。

## 前端设计系统

### Token 层

建立正式 token 层，包含 dark/light 两套语义变量：

- `--color-bg`
- `--color-surface`
- `--color-surface-raised`
- `--color-border`
- `--color-text`
- `--color-muted`
- `--color-primary`
- `--color-primary-glow`
- `--font-display`
- `--font-body`
- `--font-mono`

Dark theme 贴合 `DESIGN.md` 的 Obsidian、Deep Charcoal、Brushed Gold、Metallic Bronze。Light theme 定义为高可读浅色工作模式，而不是另一个品牌风格；仍保留金色权威感、锐利边界、细线分割和低圆角。

字体统一映射：

- Display：Syne
- Body：Hanken Grotesk
- Mono：JetBrains Mono

页面和组件不再直接硬编码 `Geist`、`Noto Serif`、`Source Serif 4` 等非规范字体。

### 全局主题行为

主题以 `localStorage[goulong-theme-mode]` 和 `html[data-theme]` 为唯一来源。所有组件读取全局 `html[data-theme]`，不维护局部独立主题状态。

保留三种模式：

- `dark`
- `light`
- `system`

用户显式选择 `dark` 或 `light` 时，全站固定该主题。用户选择 `system` 时，`localStorage` 保存 `system`，并监听 `prefers-color-scheme`；系统主题变化时立即更新 `html[data-theme]`，但不把 `system` 覆写成 `dark` 或 `light`。

顶栏、营销导航、登录页、注册页等所有主题切换入口必须调用同一主题 API。任意页面切换主题后，跳转到其他页面应保持同一模式。

### 应用布局

统一 app 内页布局结构：顶栏、主内容、footer。主内容容器必须吸收剩余高度，避免统计页等空数据页面 footer 漂在页面中部。

统计页、设置页、知识库页、历史页、体检台应复用一致的 app shell 布局规则。

### 统计页体验

统计页需要区分三种状态：

- 加载中
- 真实无数据
- 接口失败

请求失败时不得把 summary 重置为 0。可显示 `--` 或保留上一次成功数据，并在 summary 上方显示明确错误态，例如“统计暂不可用”。401/403 应引导重新登录，500 或网络错误提示稍后重试。

### 核心迁移范围

本轮核心迁移范围：

- `frontend/src/pages/StatisticsPage.vue`
- `frontend/src/components/app/AppTopNav.vue`
- `frontend/src/components/app/DashboardFooter.vue`
- `frontend/src/pages/KnowledgeBasePage.vue`
- `frontend/src/pages/HistoryPage.vue`
- `frontend/src/pages/InspectionDeskPage.vue`
- `frontend/src/pages/SettingsPage.vue`
- `frontend/src/components/inspection/InspectionReviewModal.vue`
- `frontend/src/components/inspection/InspectionReportPane.vue`
- `frontend/src/components/inspection/DocumentPreviewPane.vue`
- `frontend/src/components/inspection/InspectionFileSummary.vue`
- `frontend/src/components/inspection/KnowledgeTogglePanel.vue`

营销页、帮助页、隐私页和条款页接入 token，但本轮不要求全面视觉重排。

## DESIGN.md 更新

本轮需要更新 `DESIGN.md`，补充两节：

- Light Theme Extension
- Theme Behavior

补充内容应明确：暗色仍是主品牌基调；浅色是高可读工作模式；所有页面必须使用 token；主题状态必须来自全局单一来源。

## 接口设计

### `GET /inspection/stats/history`

查询参数：

- `range=7d`：本轮仍只支持 7 天。
- `project_id`：可选。不传表示当前用户全局统计。

响应使用新统计契约，详见“新统计契约”章节。

错误处理：

- 不支持的 range 返回 400。
- 未登录或 token 失效返回 401。
- 无权限访问指定项目返回 403。
- 数据库异常返回稳定 500 错误，不暴露内部 SQL 或驱动异常。

### `/inspection/parse`

上传成功返回 202，并返回文档处理 job 和 inspection record 标识。存储失败返回稳定业务错误，不暴露 OSS SDK 原始异常。

## 数据模型

### `InspectionRecord`

新增字段：

```text
status varchar(20) not null default 'processing'
```

约束：

```text
status in ('uploaded', 'processing', 'completed', 'failed', 'cancelled')
```

建议索引：

```text
(user_id, created_at)
(user_id, project_id, created_at)
(user_id, status, created_at)
```

具体索引是否全部新增，可在实施计划中结合现有索引和查询计划裁剪。

## 错误处理

存储错误统一转换为业务错误，不泄露 OSS request id、bucket、endpoint、access key 或本地绝对路径。

统计错误在前端显示为“统计暂不可用”，不能伪装成 0 数据。认证错误需要引导用户重新登录。

主题错误以全局状态为准。如果局部页面无法读取主题状态，应回退到 `system` 解析结果，而不是维护第二套持久化逻辑。

## 测试策略

后端测试：

- 默认 `STORAGE_BACKEND` 为空或 `local` 时，文件写入本地。
- OSS 配置残留但 `STORAGE_BACKEND=local` 时，仍写入本地。
- `STORAGE_BACKEND=oss` 且配置不完整时，生产安全检查失败。
- OSS 模式写入失败时返回稳定业务错误。
- `/inspection/stats/history` 从数据库聚合新契约字段。
- `InspectionRecord.status` 在同步体检、异步体检成功、异步体检失败时正确更新。

前端测试：

- 主题切换会更新 `localStorage[goulong-theme-mode]`。
- 主题切换会更新 `html[data-theme]`。
- 路由切换后主题保持一致。
- `system` 模式响应 `prefers-color-scheme` 变化。
- 统计页加载中、真实空数据、接口失败三种状态分开渲染。
- 接口失败不把 summary 伪装成 0。

视觉验收：

- 核心页面 dark/light 截图。
- footer 在统计页空数据状态贴底。
- 无明显旧浅色硬编码漏出。
- 无局部主题与全局主题冲突。

设计规范检查：

- 增加 `npm run design:check`。
- 检查新增未知 `#hex` 色值和未知 `font-family`。
- 初期使用 baseline 策略：核心迁移范围尽量清零，非核心页面允许分批收敛。

## 复杂度评估

| 维度 | 判定 | 理由 |
| --- | --- | --- |
| 需求边界 | B | 覆盖后端存储、统计契约、数据库迁移、前端主题和设计规范检查 |
| 技术栈 | A | 现有 FastAPI/Vue 结构清晰，文衡已有存储参考 |
| 改动范围 | B | 横跨 backend config/service/API/tests、数据库迁移和多个前端页面组件 |
| 隐藏假设 | B | 明暗双主题、状态口径、OSS 启用时机和统计契约都已通过压力测试明确 |
| 方案确定性 | A | 技术路线明确，可按模块验证 |

判定：路径 2。已完成 `grill-me` 压力测试，下一步可以运行 `$writing-plans` 拆分实施任务。
