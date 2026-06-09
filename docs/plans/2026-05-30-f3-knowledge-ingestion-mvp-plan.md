# F3 知识库 — 入库链路 MVP 实施计划

## 总览

实现知识库数据入库链路 MVP：文件上传 → MarkItDown 转换 → PageIndex 结构化索引 → PostgreSQL 元数据 + 本地文件存储。按「后端基础设施 → 核心服务 → API → 前端对接」的顺序，分阶段交付。共 16 个任务，预计总工时 ~55 分钟。

## 前置准备

- [x] 设计文档已批准：`docs/designs/F3-知识库-入库链路-MVP-设计.md`
- [ ] 本地 PostgreSQL 可用（设计文档 D11：PostgreSQL 元数据 + 本地文件）
- [ ] 验证命令基线：
  - 后端：`ruff check backend`、`pytest backend`
  - 前端：`npm run build`（在 `frontend/`）

## 任务列表

### 阶段一：基础设施与数据模型

### 任务 1: 添加项目依赖 (~3 min)

- 文件：修改 `backend/pyproject.toml`
- 内容：新增 `markitdown[docx,pdf,pptx,xlsx]>=0.1.6`、`pageindex>=0.2.8`、`sqlalchemy>=2.0.0`、`asyncpg>=0.29.0`、`alembic>=1.13.0`
- 验证：`pip install -e ".[dev]"` 成功安装所有依赖
- 依赖：无

### 任务 2: 数据库连接配置 (~3 min)

- 文件：修改 `backend/core/config.py`，创建 `backend/core/database.py`
- 内容：`Settings.database_url` 配置项，SQLAlchemy async engine + session 工厂，`init_db()` 初始化函数
- 验证：启动后端不报数据库相关导入错误
- 依赖：任务 1

### 任务 3: 创建数据库模型（4 张表） (~5 min)

- 文件：创建 `backend/models/__init__.py`，创建 `backend/models/knowledge.py`
- 内容：`EngineeringSubcategory`、`KnowledgeDocument`、`DocumentVersion`、`IndexNode` ORM 类
- 验证：`from models.knowledge import EngineeringSubcategory, KnowledgeDocument, DocumentVersion, IndexNode` 无报错
- 依赖：任务 2

### 任务 4: Alembic 初始化与首次迁移 (~3 min)

- 文件：创建 `backend/alembic.ini`、`backend/alembic/` 目录（env.py, versions/）、迁移脚本
- 验证：`alembic upgrade head` 在空库中成功创建 4 张表
- 依赖：任务 3

### 任务 5: 本地文件存储工具函数 (~3 min)

- 文件：创建 `backend/services/__init__.py`、`backend/services/file_storage.py`
- 内容：`build_storage_path()`、`save_upload_file()`、`ensure_storage_dir()`，常量 `STORAGE_ROOT = "data/knowledge"`
- 验证：`build_storage_path("traditional", "房建", "招标文件", 1)` 返回 `data/knowledge/traditional/房建/招标文件/v1`
- 依赖：无（可与任务 1-4 并行）

### 任务 6: 工程大类常量与校验 (~2 min)

- 文件：创建 `backend/core/constants.py`
- 内容：`ENGINEERING_CATEGORIES` 字典、`ALLOWED_FILE_EXTENSIONS` 列表、`validate_category()`、`validate_file_type()` 函数
- 验证：`validate_category("traditional")` 返回 True；`validate_category("xxx")` 抛 ValueError
- 依赖：无（可与任务 1-5 并行）

### 阶段二：核心转换服务

### 任务 7: MarkItDown 转换服务 (~3 min)

- 文件：创建 `backend/services/markdown_converter.py`
- 内容：`convert_to_markdown(file_path: str) -> str`，异常捕获，空内容检测
- 验证：传入文件路径可返回 Markdown 文本
- 依赖：任务 1

### 任务 8: PageIndex 索引服务 (~4 min)

- 文件：创建 `backend/services/page_indexer.py`
- 内容：`build_index_nodes(markdown_text: str) -> list[IndexNodeCreate]`，递归解析节点树，异常捕获
- 验证：传入带标题的 Markdown 文本，返回包含章节/段落层级的节点列表
- 依赖：任务 1

### 阶段三：API 路由

### 任务 9: 知识库路由骨架与 Pydantic 模型 (~3 min)

- 文件：创建 `backend/routers/knowledge.py`
- 内容：路由前缀 `/knowledge`，Pydantic 模型（UploadResponse、SubcategoryResponse、DocumentListResponse、NodeTreeResponse）
- 验证：`from routers.knowledge import router` 无报错
- 依赖：任务 3

### 任务 10: 子类管理 API (~3 min)

- 文件：修改 `backend/routers/knowledge.py`
- 内容：`GET /api/v1/knowledge/subcategories?category=xxx`，内部函数 `_get_or_create_subcategory()`
- 验证：查询子类列表返回正确结构
- 依赖：任务 9

### 任务 11: 上传入库主流程 API (~5 min)

- 文件：修改 `backend/routers/knowledge.py`
- 内容：`POST /api/v1/knowledge/upload`，参数校验 → 查找/创建子类 → 查找/创建文档 → 保存文件 → MarkItDown → PageIndex → 写库，状态流转，错误处理（部分保留策略）
- 验证：上传 PDF 文件后返回 `UploadResponse`，状态为 `completed`，`node_count > 0`
- 依赖：任务 7, 任务 8, 任务 10

### 任务 12: 文档列表查询 API (~3 min)

- 文件：修改 `backend/routers/knowledge.py`
- 内容：`GET /api/v1/knowledge/documents?subcategory_id=xxx`
- 验证：上传文件后查询对应子类，返回包含该文档的列表
- 依赖：任务 9

### 任务 13: 索引节点树查询 API (~3 min)

- 文件：修改 `backend/routers/knowledge.py`
- 内容：`GET /api/v1/knowledge/documents/{document_id}/nodes?version_number=N`，组装嵌套树结构
- 验证：返回 chapter → section → paragraph → sentence 嵌套结构
- 依赖：任务 9

### 任务 14: 注册路由到主应用 (~2 min)

- 文件：修改 `backend/main.py`
- 内容：`from routers.knowledge import router as knowledge_router`，`app.include_router(knowledge_router, prefix="/api/v1")`
- 验证：启动后访问 `GET /api/v1/knowledge/subcategories?category=traditional` 返回 200
- 依赖：任务 10, 任务 11, 任务 12, 任务 13

### 阶段四：后端测试

### 任务 15: 知识库 API 集成测试 (~5 min)

- 文件：创建 `backend/tests/test_knowledge_api.py`
- 内容：上传成功、同名版本、无效文件类型、无效大类、子类 CRUD、文档列表、节点树共 7 个测试用例
- 验证：`pytest backend/tests/test_knowledge_api.py` 全部通过
- 依赖：任务 14

### 阶段五：前端对接

### 任务 16: 知识库页面对接后端 API (~5 min)

- 文件：修改 `frontend/src/pages/KnowledgeBasePage.vue`，可选创建 `frontend/src/composables/useKnowledge.js`
- 内容：页面加载调子类列表 → 按子类调文档列表 → 上传按钮绑定上传 API → 状态展示 → 加载/空/错误态
- 验证：页面上传 PDF 后列表刷新，新文档出现且状态为 ready
- 依赖：任务 14

## 并行机会

- 任务 5 (文件存储) / 任务 6 (常量校验) 可与任务 1-4 并行
- 任务 7 (MarkItDown) / 任务 8 (PageIndex) 依赖任务 1，可与任务 3-4 并行
- 任务 15 (后端测试) 可与任务 16 (前端对接) 并行

## 依赖关系

- 任务 2 依赖任务 1
- 任务 3 依赖任务 2
- 任务 4 依赖任务 3
- 任务 7/8 依赖任务 1
- 任务 9 依赖任务 3
- 任务 10 依赖任务 9
- 任务 11 依赖任务 7/8/10 + 任务 5/6
- 任务 12/13 依赖任务 9
- 任务 14 依赖任务 10-13
- 任务 15 依赖任务 14
- 任务 16 依赖任务 14

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| MarkItDown 安装失败或依赖冲突 | 先在虚拟环境独立验证；MVP 可先 mock 转换结果 |
| PageIndex 对某些格式输出为空 | 设计文档 D12 已定义部分保留策略 |
| PostgreSQL 未本地安装 | 先启动本地 PostgreSQL 或配置远程开发库；不使用 SQLite 作为业务数据库 |
| 同步处理大文件超时 | MVP 先限制文件大小 50MB |
| 子类名称唯一约束冲突 | 数据库 UNIQUE 约束 + API 层提前校验 |

## 执行状态

- [x] 任务 1：添加项目依赖
- [x] 任务 2：数据库连接配置
- [x] 任务 3：创建数据库模型（4 张表）
- [x] 任务 4：Alembic 初始化与首次迁移
- [x] 任务 5：本地文件存储工具函数
- [x] 任务 6：工程大类常量与校验
- [x] 任务 7：MarkItDown 转换服务
- [x] 任务 8：PageIndex 索引服务
- [x] 任务 9：知识库路由骨架与 Pydantic 模型
- [x] 任务 10：子类管理 API
- [x] 任务 11：上传入库主流程 API
- [x] 任务 12：文档列表查询 API
- [x] 任务 13：索引节点树查询 API
- [x] 任务 14：注册路由到主应用
- [x] 任务 15：知识库 API 集成测试
- [x] 任务 16：知识库页面对接后端 API
