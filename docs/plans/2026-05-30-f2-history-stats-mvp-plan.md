# F2 历史数据统计 MVP 实施计划

## 1. 目标

交付“近 7 天历史统计”MVP，包含 3 个指标与 7 天趋势：

- 上传文档数
- 违禁词出现率（按文档命中率）
- 额度消耗

实现策略：后端先提供单一聚合接口（summary + trend），前端再接入展示并补齐加载/空/错状态。

## 2. 前置准备

- 设计文档已批准：`docs/designs/F2-历史数据统计-MVP-设计.md`
- 本地可运行前后端
- 验证命令基线：
  - 后端：`ruff check backend`、`pytest backend`
  - 前端：`npm run build`、`npm run test:routes`（在 `frontend/`）

## 3. 任务清单（2-5 分钟粒度）

### 任务 1：补充后端统计响应模型

- 文件：`backend/routers/inspection.py`
- 内容：定义 history stats 的 Pydantic 响应模型（`range/timezone/summary/trend`）
- 验证：字段与设计文档示例一致

### 任务 2：实现 7 天分桶与补零工具函数

- 文件：`backend/routers/inspection.py`
- 内容：日期序列生成、按天聚合、缺失日期补零
- 验证：固定返回 7 点；`total_docs=0` 时 `banned_rate=0`

### 任务 3：新增 `GET /inspection/stats/history` 接口

- 文件：`backend/routers/inspection.py`
- 内容：基于当前用户隔离返回 summary + trend（MVP 可先按当前隔离实现）
- 验证：`GET /inspection/stats/history?range=7d` 返回结构正确，汇总与趋势可对账

### 任务 4：接入主应用路由与最小文档说明

- 文件：`backend/main.py`（核对/必要时修改），`backend/routers/inspection.py`
- 内容：确认路由暴露并补接口注释
- 验证：本地启动后可访问新接口

### 任务 5：前端统计页改为接口驱动状态

- 文件：`frontend/src/pages/StatisticsPage.vue`
- 内容：硬编码数据改为响应式状态（summary/trend/loading/error/empty）
- 验证：页面首次自动请求 7d，默认值可回退为 0

### 任务 6：实现统计接口调用与字段映射

- 文件：`frontend/src/pages/StatisticsPage.vue`
- 可选：`frontend/src/composables/useHistoryStats.js`
- 内容：请求后端并映射到卡片和图表
- 验证：`banned_rate` 百分比展示；日期与 7 天序列对应

### 任务 7：页面收敛到 MVP 范围

- 文件：`frontend/src/pages/StatisticsPage.vue`
- 内容：移除/隐藏非 MVP 模块，仅保留三卡片 + 趋势
- 验证：页面与设计范围一致，无布局破坏

### 任务 8：补充后端接口测试

- 文件：`backend/tests/test_history_stats_api.py`（新建）
- 内容：覆盖无数据/有数据/比率口径
- 验证：`pytest backend/tests/test_history_stats_api.py` 通过；关键口径断言通过

### 任务 9：补充前端手工验收清单

- 文件：`docs/plans/2026-05-30-f2-history-stats-qa-checklist.md`（新建）
- 内容：加载态、空态、错误态、正常态检查步骤
- 验证：按清单可复现四类状态

### 任务 10：全量验收与交付记录

- 命令：
  - `ruff check backend`
  - `pytest backend`
  - `npm run build`（frontend）
  - `npm run test:routes`（frontend）
- 验证：命令全部通过，满足 MVP 验收标准

## 4. 依赖关系

- 任务 2 依赖任务 1
- 任务 3 依赖任务 2
- 任务 4 依赖任务 3
- 任务 6 依赖任务 5
- 任务 7 依赖任务 6
- 任务 10 依赖任务 8 与任务 9

## 5. 并行建议

- 任务 8 可与任务 5/6 并行
- 任务 9 可与任务 8 并行
- 任务 10 作为最终串行收口

## 6. 风险与缓解

- 历史字段不足：缺失字段按 0 降级，保持响应结构稳定
- 时区边界偏移：统一后端业务时区，覆盖当天边界测试
- 口径不一致：强制校验 `trend` 聚合结果与 `summary` 一致

## 7. 执行状态

- [x] 任务 1：补充后端统计响应模型
- [x] 任务 2：实现 7 天分桶与补零工具函数
- [x] 任务 3：新增 `GET /inspection/stats/history` 接口
- [x] 任务 4：接入主应用路由与最小文档说明（主路由已包含，接口已补注释）
- [x] 任务 5：前端统计页改为接口驱动状态
- [x] 任务 6：实现统计接口调用与字段映射
- [x] 任务 7：页面收敛到 MVP 范围
- [x] 任务 8：补充后端接口测试
- [x] 任务 9：补充前端手工验收清单
- [x] 任务 10：全量验收与交付记录（已完成）
