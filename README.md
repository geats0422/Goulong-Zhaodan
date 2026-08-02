# 句龙照胆 — 工程文档智能体检平台

> **Goulong Zhaodan** — 让每一份工程合同在签字前先"照"出风险。

一个面向工程合同初审场景的智能文档体检平台。上传一份 Word/PDF/Excel/PPT/纯文本，系统会自动识别工程类别与合同类别、解析正文、对照知识库中的法规依据与用户自定义违禁词，输出一份带风险等级、问题清单和修改建议的结构化审查报告，并支持 PDF 报告导出与历史记录回溯。

## 项目定位

- **目标用户**：合同审查人员、造价工程师、监理工程师、工程法务
- **核心场景**：
  - 合同初审（工程类别与合同类别识别、权利义务不对等、绝对化用语、模糊条款）
  - 跨文件一致性审查（主体、金额、日期、附件完整性）
  - 工程法规知识库（系统默认合同规则包 + 用户私有）实时比对
- **设计风格**：Neo-Chinese Cyberpunk — 黑金主调，12 栏网格，垂直留白，强调"高安全/高密度/古籍电路化"的视觉语言（详见 `DESIGN.md`）

## 功能特性

### 1. 三步式体检工作台

体检台采用向导式三步弹窗，完整还原"上传→审查→报告"的标准工作流。

| 步骤 | 子组件 | 主要交互 |
| --- | --- | --- |
| Step 1：文档解析 | `DocumentPreviewPane.vue` / `InspectionFileSummary.vue` | 大文档分页预览、目录概览、文件信息卡 |
| Step 2：审查准备 | `KnowledgeTogglePanel.vue` | 识别文档类型、按场景筛选知识库、启动多 Agent 审查 |
| Step 3：报告输出 | `InspectionReportPane.vue` | 风险等级、问题清单、修改建议、引用法规、PDF 导出 |

### 2. 智能文档解析（MarkItDown + 内置兜底）

`backend/services/markdown_converter.py` 提供多格式转 Markdown：

- **DOCX**：内置 `zipfile + ElementTree` 直接读取 `word/document.xml`，比 MarkItDown 更快、对中文标点更稳
- **DOC（Word Binary）**：纯 Python 实现 OLE Compound File 解析 + Piece Table 文本提取，无需 LibreOffice
- **PDF / PPTX / XLSX / TXT**：通过 MarkItDown 统一转换
- **清理层**：剥离 `data:image`、Markdown 图片链接、竖排"图/片/占/位/符"等噪声，避免污染审查 prompt

### 3. PageIndex 知识库索引（LLM 驱动的文档树）

知识库文档上传后由 `backend/services/page_indexer.py` 自动构建结构化索引树：

- **顶层**：调用 `pageindex.page_index_md.md_to_tree()`，由 LLM 智能切分章节
- **降级**：失败时自动回退到本地正则 + Markdown 标题层级切分（`#` ~ `######`）
- **节点类型**：`chapter` → `section` → `paragraph` → `sentence`，树状 parent-child
- **历史兼容**：保留 `application_scenario` 字段读取能力，新业务固定合同场景；旧的招投标文档已归档隐藏，不参与检索

### 4. 多 Agent 审查流水线

`backend/agents/inspector.py` 编排三阶段流水线（PydanticAI + LiteLLM，**完全兼容 OpenAI 格式**）：

```
法规分析师 → 合规检查员 → 主协调员
```

- **法规分析师**：基于已启用的知识库内容匹配法规依据
- **合规检查员**：识别低级错误、隐含风险、违禁词、表述问题
- **主协调员**：汇总成 JSON 结构化报告（`overall_risk` / `summary` / `issues` / `regulation_refs`）
- **引用过滤**：禁止 LLM 引用未在知识库中出现的法规名称（`Sanitize` 兜底）

### 5. 历史记录与重审

`/history` 页面提供完整的体检档案管理：

- 列表分页（`page` / `page_size`）、关键词模糊搜索（`ILIKE`）、风险等级筛选
- 单条记录详情弹窗（`text_preview` + `parsed_content` 完整正文）
- **重审**：`pending` 记录可一键重跑审查（直接读已保存的 `parsed_content` 避免重复解析）
- **下载**：审查报告以 PDF 形式导出（手写 PDF 生成器 + STSong-Light CJK 字体）
- **删除**：支持单条记录清理

### 6. 用户知识库管理

- 知识库按工程类别（房建施工、市政道路、装饰装修、机电安装、钢结构、通用工程）与合同类别（劳务分包、专业工程分包、其他类）组织
- 用户可上传私有文档、启用/停用系统默认知识库
- 新业务固定合同场景；旧的招投标资料已归档隐藏，可在设置页查看与永久删除本人归档资料
- 所有工程类别首期共享「通用工程合同规则包」，承载《民法典》合同编、《建筑法》、《建设工程质量管理条例》等国家级法规

### 7. 设置中枢（系统设置 / 账单订阅 / AI 模型 / 知识库 / 违禁词）

`/settings` 页面采用 5 个 tab 统一管理账号与平台设置：

- **系统设置**：基础档案（用户名 / 手机 / 邮箱，唯一性校验）、账户安全（弹窗改密含眼睛图标 + 确认密码）、数据安全锁（阅后即焚开关）、第三方账号绑定展示
- **账单订阅与管理**：当前订阅卡（计划名 + 价格 + 周期 + 配额进度条 `quota_used / monthly_quota`）、算力补充包（轻量/标准/企业）、升级弹窗（月度试剑/季度常驻/年度大匠）
- **AI 模型与偏好**：从 `MODEL_CATALOG` 选择推理模型（DeepSeek V4 Pro / Flash）、查看模型信息条、数据脱敏开关（与系统设置数据安全锁双向同步）、模型 API Key 预览
- **开发者 API Key**：4 种权限模板（MCP 只读 / CLI 审查 / Agent 自动化 / 高级自定义）、创建时自定义有效期（30/90/180/365 天 / 永不过期）、查看/隐藏/复制/吊销、二次确认弹窗
- **知识库设置**：按工程分类展示系统 + 用户文档树
- **违禁词设置**：用户级 CRUD（创建 / 编辑 / 删除）+ 体检上传时临时合并

### 8. 营销着陆页

4 个 Vue 路由驱动的着陆页，共享 `MarketingShell` 壳组件（支持浅色主题）：

- `/` 营销首页（`MarketingHomePage.vue`）
- `/solutions` 解决方案（`SolutionPage.vue`）
- `/security` 安全合规（`SecurityPage.vue`）
- `/cases` 客户案例（`CasesPage.vue`）
- `/pricing` 版本与定价（`PricingPage.vue`，团队/企业区消费 `PLAN_CATALOG`）

### 9. 主题切换

`composables/useTheme.js` 持久化用户偏好到 `localStorage`，支持 `dark` / `light` 两种主题：

- **深色**：Neo-Chinese Cyberpunk — `gold-on-obsidian`（`#0A0A0A` 背景 / `#d4af37` 金 / `#f2ca50` 金色文字）
- **浅色**：暖玉纸面 — `#f7f1e3` 背景 / `#9b7416` 古铜金 / `#1f1a12` 墨色文字
- 主题变量集中在 `frontend/src/style.css` 的 `:root` / `[data-theme="light"]` 选择器中
- 所有交互组件（按钮、输入、下拉、卡片、导航）均完成两套主题适配

## 技术栈

### 后端（`backend/`）

| 类别 | 选型 |
| --- | --- |
| Web 框架 | FastAPI 0.115+ |
| 异步 ORM | SQLAlchemy 2.0 async + asyncpg |
| 数据库 | PostgreSQL（生产）/ SQLite aiosqlite（测试） |
| 迁移 | Alembic |
| AI 编排 | PydanticAI + LiteLLM（兼容 OpenAI 格式） |
| 文档解析 | markitdown[docx,pdf,pptx,xlsx] + 自研 DOCX/DOC 兜底 |
| 知识库索引 | PageIndex（vendor 子模块） + 正则降级 |
| 鉴权 | PyJWT + bcrypt |
| 测试 | pytest + pytest-asyncio（> 60 个测试用例） |
| 包管理 | uv（虚拟环境 + 依赖锁定） |
| Lint | ruff |

### 前端（`frontend/`）

| 类别 | 选型 |
| --- | --- |
| 框架 | Vue 3 `<script setup>` |
| 构建 | Vite 8 |
| 路由 | vue-router 4 |
| HTTP | 原生 `fetch` + Bearer Token 拦截器（`composables/useAuth.js`） |
| 样式 | 原生 CSS（自定义设计令牌）+ Material Symbols |
| 设计系统 | Neo-Chinese Cyberpunk（详见 `DESIGN.md`） |

### 基础设施

- 阿里云（合规/部署可选）
- Redis（计划中，用于大文件解析缓冲 + 长时间任务队列）

## 仓库结构

```
Goulong-Zhaodan/
├── backend/                  # Python + FastAPI 后端
│   ├── agents/               # 多 Agent 流水线（inspector.py 协调器）
│   ├── alembic/              # 数据库迁移（001~011）
│   ├── app/prompts/          # Agent 提示词管理（按场景模板化）
│   ├── core/                 # 基础设施（auth, config, database, login_throttle, ...）
│   ├── models/               # SQLAlchemy 模型（knowledge.py 集中式）
│   ├── routers/              # API 路由（auth/inspection/knowledge/settings）
│   ├── services/             # 业务服务（page_indexer, knowledge_ingestion, markdown_converter）
│   ├── scripts/              # 运维脚本（import_default_knowledge.py）
│   ├── tests/                # pytest 测试套件
│   ├── vendor/pageindex/     # PageIndex 子模块
│   ├── workers/              # Arq Worker 异步任务配置
│   ├── main.py               # FastAPI 入口
│   ├── pyproject.toml
│   └── env.example
├── frontend/                 # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── components/       # 业务组件（inspection/、app/、marketing/）
│   │   ├── composables/      # 组合式函数（useAuth.js）
│   │   ├── pages/            # 页面（Dashboard / KnowledgeBase / History / Statistics / Settings / Login / MarketingHome / Solution / Cases / Security / Pricing）
│   │   ├── services/         # API 封装（inspectionApi.js / settingsApi.js）
│   │   ├── router.js
│   │   └── style.css         # 全局样式（含设计令牌）
│   ├── vite.config.ts
│   └── package.json
├── docs/                     # 项目文档（designs/ plans/ git/）
├── .opencode/                # OpenCode AI Agent 配置
├── AGENTS.md                 # Agent 工作约定（中文优先、技术栈约束）
├── DESIGN.md                 # 设计系统规范（Neo-Chinese Cyberpunk）
└── README.md                 # 当前文件
```

## 快速开始

### 0. 前置要求

- **Python 3.11+** + [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** + npm
- **PostgreSQL 14+**（生产）；SQLite 已自动用于测试

### 1. 启动后端

```powershell
cd backend
Copy-Item env.example .env
# 编辑 .env 填入 MODEL_API_KEY、DATABASE_URL 等必填项

uv sync                                # 安装依赖
uv run alembic upgrade head            # 初始化数据库
uv run python scripts/import_default_knowledge.py   # （可选）导入系统默认知识库
uv run uvicorn main:app --reload --port 8000
```

默认本地文件存储目录为 `knowledge-base/uploads`。生产部署由 `Goulong-Wenheng/deploy` 注入 `UPLOAD_DIR=/app/knowledge-base/uploads` 并挂载 ECS 本地目录；`OSS_BUCKET_NAME` 和 `OSS_ENDPOINT` 留空时不会访问 OSS。

后端默认监听 `http://localhost:8000`，Swagger UI 在 `/docs`。

如需异步审查任务（Agent API），需额外启动 Worker：

```powershell
cd backend
uv run arq app.workers.config.WorkerSettings
```

前提：Redis 服务已启动，且 `.env` 中 `REDIS_URL` 和 `API_KEY_ENCRYPTION_SECRET` 已配置。

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认监听 `http://localhost:5174`，Vite 已配置代理把 `/auth` / `/settings` / `/inspection` / `/api/v1` 透传到 `http://localhost:8000`。

### 3. 登录

浏览器打开 `http://localhost:5174/login`，使用注册过的账号登录（首次启动可走 `/login` 的"去注册"入口）。

## 配置说明（`backend/.env`）

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `MODEL_API_KEY` | ✅ | — | LLM API 密钥（兼容 OpenAI 格式） |
| `MODEL_BASE_URL` | — | `https://api.deepseek.com/v1` | DeepSeek 官方 API 地址 |
| `MODEL_NAME` | — | `deepseek-v4-pro` | 模型标识 |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://...` | 数据库连接串 |
| `JWT_SECRET_KEY` | ✅ | `dev-secret` | JWT 签名密钥（**生产务必修改**） |
| `JWT_ALGORITHM` | — | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `30` | 访问令牌过期时间 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | `7` | 刷新令牌过期时间 |
| `MAX_DOCUMENT_LENGTH` | — | `8000` | 单次体检最大字符数 |
| `INSPECTION_PROMPT_CHAR_BUDGET` | — | `60000` | Agent 提示词字符预算 |
| `PAGEINDEX_VENDOR_PATH` | — | `vendor/pageindex` | PageIndex 子模块路径 |
| `CORS_ORIGINS` | — | `http://localhost:5174,http://localhost:5173` | 允许跨域来源 |
| `LOG_LEVEL` | — | `INFO` | 日志级别 |
| `API_KEY_ENCRYPTION_SECRET` | ✅ | — | API Key 加密密钥（**生产务必修改为随机强密码**） |
| `REDIS_URL` | — | `redis://localhost:6379` | Redis 连接地址（Worker 异步任务队列） |

### 常见 LLM 提供商

```env
# OpenAI
MODEL_API_KEY=sk-xxx
MODEL_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# DeepSeek
MODEL_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-v4-pro

# 通义千问
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-max

# 智谱 GLM
MODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_NAME=glm-4
```

## API 概览

后端默认无统一前缀（部分模块挂 `/api/v1`），完整路径以 `http://localhost:8000/docs` 为准。

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 健康检查 | `GET /health` | 服务存活 |
| 账号 | `/auth/register` `/auth/login` `/auth/refresh` `/auth/me` | 注册 / 登录 / 刷新 / 当前用户 |
| 体检台 | `/inspection/parse` `/inspection/sessions/{id}/inspect` | 解析 + 审查 |
| 体检台 | `/inspection/records` `/inspection/records/{id}` `/inspection/records/{id}/inspect` `/inspection/records/{id}/report.pdf` | 列表 / 详情 / 重审 / PDF 导出 |
| 体检台 | `DELETE /inspection/records/{id}` | 删除记录 |
| 体检台 | `/inspection/stats/history?range=7d` | 统计 |
| 知识库 | `/api/v1/knowledge/overview` `/api/v1/knowledge/upload` `/api/v1/knowledge/documents/{id}` `/api/v1/knowledge/retrieval` | 概览 / 上传 / 启停 / 检索 |
| 设置 | `/settings/overview` `/settings/profile` `/settings/password` `/settings/taboo-words` | 概览 / 资料 / 密码 / 违禁词 |
| 设置 | `/settings/knowledge/documents/{id}` | 知识库文档启停 |
| 设置 | `/settings/api-keys` `/settings/api-keys` `/settings/api-keys/{id}/secret` `/settings/api-keys/{id}` | 开发者 API Key 列表 / 创建 / 读取密钥 / 启停与吊销 |
| Agent API | `/api/v1/agent/me` | 身份查询（按 API Key） |
| Agent API | `/api/v1/agent/jobs/inspect` `/api/v1/agent/jobs/parse` `/api/v1/agent/jobs/{job_id}` | 创建审查 / 创建解析 / 查询任务状态 |
| Agent API | `/api/v1/agent/records` `/api/v1/agent/records/{id}` `/api/v1/agent/knowledge/search` | 记录列表 / 详情 / 知识检索 |

## 开发与验证

```powershell
# 后端
cd backend
uv run ruff check .                    # Lint
uv run pytest -q                        # 完整测试（> 60 用例）
uv run pytest tests/test_inspection_api.py -q   # 单独跑某模块

# 前端
cd frontend
npm run dev                             # 开发
npm run build                           # 生产构建
npm run test:routes                     # 路由表自检
```

更多开发约定参见 `AGENTS.md`，设计系统规范参见 `DESIGN.md`。

## 路线图

- [x] Redis 缓存层：长任务进度推送 + 大文件解析缓冲
- [x] 异步队列（Arq）替代同步审查
- [x] API Key 认证：支持第三方程序通过 Agent API 集成
- [ ] PydanticAI → LangGraph 迁移（复杂状态流）
- [ ] 阿里云 OSS 存储适配（私有化部署）
- [ ] 阿里云短信 / 邮件验证（替换 `send-code` mock）

## 许可

仓库未声明开源协议，请联系仓库所有者获取授权。
