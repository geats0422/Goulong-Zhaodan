# Changelog

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
