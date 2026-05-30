# F3 知识库 — 入库链路 MVP 设计

## 1. 目标与范围

基于功能列表 F3，实现知识库的**数据入库链路 MVP**：
文件上传 → MarkItDown 转换 → PageIndex 结构化索引 → PostgreSQL 元数据 + 本地文件存储。

本期（MVP）范围：
- 文档上传入库（同步处理）
- 工程大类/子类管理
- 文档版本管理（仅保留，不提供删除/回滚）
- 结构化索引节点持久化

不在 MVP 范围：
- 检索与召回链路
- 知识库管理后台 UI
- 异步入队处理
- 文档版本删除/回滚
- 向量化与语义检索

## 2. 已确认产品决策

| 编号 | 决策项 | 结论 |
|:---:|------|------|
| D1 | 入库范围 | A. 数据入库链路 |
| D2 | 入库触发方式 | 同步入库 |
| D3 | 切分策略 | 按文本天然结构：章节 → 小节 → 段落 → 句子 |
| D4 | 管理单位 | 文档级入库，按工程大类组织知识库 |
| D5 | 分类结构 | 固定 3 大类（新基建、传统基建、城市更新），子类可自定义 |
| D6 | 组织层级 | `工程大类 → 工程子类 → 文档 → 文档版本 → PageIndex 结构节点` |
| D7 | 索引粒度 | 混合级：段落级主检索单元 + 句子级引用定位 |
| D8 | 文件类型 | `.docx/.doc/.pptx/.xlsx/.pdf` |
| D9 | 同名处理 | 新版本策略：`xxx.pdf → xxx(1).pdf → xxx(2).pdf` |
| D10 | 版本操作 | MVP 只保留版本，不做删除/回滚 |
| D11 | 存储方式 | PostgreSQL 元数据 + 本地文件/索引目录 |
| D12 | 失败处理 | 部分保留：MarkItDown 成功则保留 Markdown；PageIndex 失败标记 `index_failed`；整体失败标记 `convert_failed` |

## 3. 分类模型

### 3.1 工程大类（固定 3 类）

```python
ENGINEERING_CATEGORIES = {
    "new_infrastructure": "新基建",      # 算力网建设、数据中心等
    "traditional":        "传统基建",     # 房建、路桥、市政、公路、铁路等
    "urban_renewal":      "城市更新",     # 旧改、棚改、城市更新等
}
```

### 3.2 工程子类（可自定义）

- 每个大类下可创建多个子类
- 示例：传统基建 → 路桥、房建、市政、公路、铁路
- 子类由用户在上传时选择或新建
- 子类名称在同一大类内唯一

## 4. 组织层级

```
工程大类 (engineering_category)
  └── 工程子类 (engineering_subcategories)
        └── 知识文档 (knowledge_documents)
              └── 文档版本 (document_versions)
                    └── 索引节点 (index_nodes)
                          ├── 章节 (chapter)
                          ├── 小节 (section)
                          ├── 段落 (paragraph) ← 主检索单元
                          └── 句子 (sentence)  ← 引用定位单元
```

## 5. 技术栈

### 5.1 MarkItDown（微软）

- 版本：`markitdown>=0.1.6`
- 作用：将 Office/PDF 文件转换为 Markdown
- 核心用法：
  ```python
  from markitdown import MarkItDown
  md = MarkItDown()
  result = md.convert("path/to/file.pdf")
  markdown_text = result.text_content
  ```
- 支持格式：`.docx/.doc/.pptx/.xlsx/.pdf`（需安装对应 extras）

### 5.2 PageIndex（VectifyAI）

- 版本：`pageindex>=0.2.8`
- 作用：按文档天然结构（章节-小节-段落-句子）切分 Markdown/文本
- 输出：结构化节点树，每个节点包含层级路径、正文、子节点

### 5.3 依赖安装

```bash
pip install "markitdown[docx,pdf,pptx,xlsx]"
pip install pageindex
```

## 6. 数据模型

### 6.1 PostgreSQL 表结构

#### engineering_subcategories（工程子类）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| category_key | VARCHAR(50) | 大类标识（new_infrastructure/traditional/urban_renewal） |
| name | VARCHAR(100) | 子类名称 |
| created_at | TIMESTAMP | 创建时间 |

约束：`(category_key, name)` UNIQUE

#### knowledge_documents（知识文档）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| title | VARCHAR(255) | 文档标题（不含版本后缀） |
| subcategory_id | INT FK | 所属子类 |
| current_version_id | INT FK nullable | 当前生效版本 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### document_versions（文档版本）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| document_id | INT FK | 所属文档 |
| version_number | INT | 版本序号（1, 2, 3...） |
| display_name | VARCHAR(255) | 展示文件名，如 `xxx.pdf` / `xxx(1).pdf` |
| original_file_path | VARCHAR(500) | 原始文件本地路径 |
| markdown_path | VARCHAR(500) nullable | MarkItDown 转换后的 Markdown 路径 |
| status | VARCHAR(20) | `pending` / `converting` / `indexing` / `completed` / `convert_failed` / `index_failed` |
| error_message | TEXT nullable | 失败时的错误信息 |
| file_size_bytes | BIGINT | 原始文件大小 |
| file_type | VARCHAR(10) | 文件扩展名 |
| created_at | TIMESTAMP | 创建时间 |

#### index_nodes（索引节点）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| version_id | INT FK | 所属文档版本 |
| parent_id | INT FK nullable | 父节点（章节→小节→段落→句子层级） |
| node_type | VARCHAR(20) | `chapter` / `section` / `paragraph` / `sentence` |
| path_label | VARCHAR(500) | 层级路径标签，如 `第3章 > 3.2节 > 第1段 > 第2句` |
| content | TEXT | 节点正文 |
| position | INT | 同级排序位置 |
| page_index_id | VARCHAR(100) nullable | PageIndex 返回的节点 ID |
| created_at | TIMESTAMP | 创建时间 |

### 6.2 本地文件目录结构

```
data/
  knowledge/
    {category_key}/
      {subcategory_name}/
        {document_title}/
          v1/
            original.ext          # 原始上传文件
            converted.md          # MarkItDown 产物
            pageindex/            # PageIndex 产物
              nodes.json          # 结构化节点 JSON
          v2/
            ...
```

## 7. 处理流程

```
用户上传文件
    │
    ├── 1. 参数校验
    │     ├── 文件类型：.docx/.doc/.pptx/.xlsx/.pdf
    │     ├── 工程大类：必须为固定 3 类之一
    │     └── 子类：已有子类 ID 或新子类名称
    │
    ├── 2. 查找/创建子类
    │
    ├── 3. 查找/创建知识文档
    │     ├── 同名文档 → 获取现有 document，version_number + 1
    │     └── 新文档 → 创建新 document，version_number = 1
    │
    ├── 4. 保存原始文件到本地目录
    │
    ├── 5. MarkItDown 转换
    │     ├── 成功 → 保存 Markdown 文件，status = converting
    │     └── 失败 → status = convert_failed，保留原文件，返回错误
    │
    ├── 6. PageIndex 结构化索引
    │     ├── 输入：Markdown 文本
    │     ├── 输出：章节 → 小节 → 段落 → 句子 节点树
    │     ├── 成功 → 保存 nodes.json，写入 index_node 表，status = completed
    │     └── 失败 → status = index_failed，保留 Markdown，返回错误
    │
    └── 7. 更新 document.current_version_id 指向新版本
```

## 8. API 设计

### 8.1 上传并入库

```
POST /api/v1/knowledge/upload
Content-Type: multipart/form-data

参数：
  file: UploadFile（必填）
  category: str（必填，大类 key）
  subcategory_id: int | None（已有子类）
  subcategory_name: str | None（新建子类名称）

响应：
{
  "document_id": 1,
  "version_id": 1,
  "version_number": 1,
  "display_name": "xxx.pdf",
  "status": "completed",
  "category": "traditional",
  "subcategory": "房建",
  "node_count": 128,
  "error": null
}
```

### 8.2 查询子类列表

```
GET /api/v1/knowledge/subcategories?category=traditional

响应：
{
  "category": "traditional",
  "category_label": "传统基建",
  "subcategories": [
    { "id": 1, "name": "路桥" },
    { "id": 2, "name": "房建" },
    { "id": 3, "name": "市政" }
  ]
}
```

### 8.3 查询文档列表

```
GET /api/v1/knowledge/documents?subcategory_id=2

响应：
{
  "documents": [
    {
      "id": 1,
      "title": "xxx招标文件",
      "current_version": { "version_number": 2, "display_name": "xxx(1).pdf", "status": "completed" },
      "subcategory": "房建",
      "created_at": "2026-05-30T10:00:00"
    }
  ]
}
```

### 8.4 查询文档索引节点

```
GET /api/v1/knowledge/documents/{document_id}/nodes?version_number=2

响应：
{
  "document_id": 1,
  "version_number": 2,
  "nodes": [
    {
      "id": 1,
      "node_type": "chapter",
      "path_label": "第1章",
      "content": "...",
      "children": [...]
    }
  ]
}
```

## 9. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 文件类型不支持 | 400，提示支持的格式 |
| 大类 key 不合法 | 400，提示合法的大类列表 |
| 子类名称为空且未提供 ID | 400，提示选择或新建子类 |
| 文件内容为空 | 400，拒绝入库 |
| MarkItDown 转换失败 | 保留原文件，版本状态 `convert_failed`，记录错误 |
| PageIndex 索引失败 | 保留 Markdown，版本状态 `index_failed`，记录错误 |
| 文件保存失败 | 500，整体回滚（不保留元数据） |

## 10. 验收标准（MVP）

- 上传 `.pdf/.docx` 文件可成功完成 MarkItDown 转换和 PageIndex 索引
- 同一子类下同名文件上传生成新版本（文件名带 `(N)` 后缀）
- 大类固定 3 类，子类可新建且在同一大类内唯一
- 索引节点按 `章节 → 小节 → 段落 → 句子` 四级存储
- 查询文档列表返回当前生效版本信息
- 查询索引节点返回完整层级树
- 转换/索引失败时前端可看到失败状态和错误信息

## 11. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| MarkItDown 对某些 PDF 解析质量差 | 保留原始文件，支持后续重新转换 |
| PageIndex 无法识别文档结构 | 降级为固定长度切分（第二期） |
| 同步处理大文件超时 | MVP 先限制文件大小（建议 50MB），后续升级异步 |
| 本地文件目录磁盘不足 | 监控磁盘空间，后续迁移 OSS |
| 子类名称冲突 | 数据库 UNIQUE 约束 + API 层校验 |

## 12. 后续迭代方向

- 检索与召回链路（基于索引节点的关键词/语义检索）
- 异步入队处理（Redis + Worker）
- 文档版本删除/回滚
- 知识库管理后台 UI
- 向量化嵌入 + 语义检索
- 迁移到对象存储（OSS/S3）
- 支持更多文件格式（图片 OCR 等）

## 13. 实施建议

按以下顺序落地：

1. 数据库表结构迁移（4 张表）
2. 本地文件目录初始化与工具函数
3. MarkItDown 转换服务
4. PageIndex 索引服务
5. 上传入库主流程 API
6. 查询 API（子类列表、文档列表、节点树）
7. 前端知识库页面改造（对接上传和列表 API）
8. 集成测试与验收
