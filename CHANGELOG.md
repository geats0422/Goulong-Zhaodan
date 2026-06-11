# Changelog

## v0.3.0 — API Key + Agent API + Arq Worker (2026-06-11)

为 MCP、CLI、Skill、第三方 Agent 助理提供安全可控的调用入口。

### 后端

- API Key 数据模型（api_keys 表）+ Agent Job 数据模型（agent_jobs 表）+ Alembic 迁移 008
- API Key 生成/加密/哈希/认证工具链（Fernet 对称加密 + SHA-256 哈希）
- Scope 权限模型：4 个预定义模板（MCP 只读/CLI 审查/Agent 自动化/高级自定义）+ 7 个 Scopes
- API Key 服务层：创建/列表脱敏/查看完整 Key/更新/撤销/认证
- Agent API 专用认证依赖（Bearer glzd_live_xxx），独立于 Web JWT
- Web API Key 管理路由（5 个端点，JWT 认证）
- Agent API 路由：身份查询/任务创建/任务状态/历史记录/知识库检索
- Redis 封装 + Arq Worker 配置骨架（job_timeout=600, max_tries=3）
- Worker 任务状态流转（queued → running → succeeded/failed）
- 新增依赖：cryptography、arq
- 113 个新增测试全部通过

### 前端

- 设置页新增 API Key 标签：创建表单（名称/客户端类型/权限模板/过期时间）
- API Key 列表展示：脱敏 Key 前缀、状态、权限、创建/使用时间
- 显示/隐藏完整 Key（二次确认）
- 复制完整 Key（二次确认 + navigator.clipboard）
- 撤销 API Key（确认弹窗）

## v0.2.0 — 合同场景启用 (2026-06-11)

支持招投标和合同两大文档类型的智能审查。

### 后端

- 文档类型 `unknown` 兜底策略：无关键词匹配返回 `unknown`，审查时兜底 `bidding`
- 合同关键词扩展：新增 签订/付款/履约/违约金/不可抗力
- 合同专属 Prompt：`CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT` + `CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT`
- `get_prompts_for_scenario()` 调度函数（contract/bidding/unknown 兜底）
- Agent 工厂按 scenario 缓存不同 prompt 实例
- 前端场景切换 UI + 自动识别提示
- 默认知识库补齐：25 bidding + 2 contract = 27 文档
- 153 个测试全部通过

### 前端

- KnowledgeTogglePanel.vue 场景切换 UI
- InspectionReviewModal.vue 审查请求携带 application_scenario

## v0.1.0 — MVP (2026-06-10)

句龙照胆首个 MVP 版本，包含完整的工程文档智能体检功能。

### 后端

- 知识库与体检台数据模型 + 7 个 Alembic 迁移（用户、设置、刷新令牌、知识库所有权、体检记录、解析内容）
- MarkItDown + PageIndex 知识库流水线：多格式文档转 Markdown（DOCX/DOC/PDF/PPTX/XLSX）+ LLM 驱动的结构化索引树
- 多 Agent 审查流水线（PydanticAI + LiteLLM）：法规分析 → 合规检查 → 汇总报告
- 体检台三步弹窗 API：文件解析、会话管理、记录 CRUD、PDF 报告导出
- 账号鉴权：JWT + Refresh Token 双令牌、登录频率限制、弱密码校验
- 知识库管理 + 个人设置 + 违禁词自定义 API
- 文档类型自动识别（招投标/合同）
- 60+ 测试用例覆盖（pytest + aiosqlite）

### 前端

- 体检台三步弹窗组件：DocumentPreviewPane / InspectionFileSummary / KnowledgeTogglePanel / InspectionReportPane / InspectionStepHeader / InspectionReviewModal
- 历史记录管理页：列表分页、关键词搜索、风险等级筛选、详情弹窗、重审、PDF 下载、删除
- 知识库管理页：上传文档、启用/停用、状态展示
- 设置页：个人资料、密码修改、违禁词管理、知识库开关
- 统计页、仪表盘、营销首页、登录/注册页
- Neo-Chinese Cyberpunk 设计系统（黑金主调）

### 基础设施

- .gitattributes 统一 LF 行尾
- .gitignore 补充 *.db / uv.lock
- Vite 代理配置（/auth /settings /inspection /api/v1 → localhost:8000）
- 完整设计文档 + 实施计划归档到 docs/
