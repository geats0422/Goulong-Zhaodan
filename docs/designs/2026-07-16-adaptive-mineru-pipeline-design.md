# 照胆自适应 MinerU 文档处理链路设计

## 目标

为照胆建立统一、可恢复的文档处理链路。普通文本型文档优先使用本地解析，扫描件、混合 PDF 和低质量解析结果使用 MinerU OCR；所有成功结果统一转换为 Markdown，经 PageIndex 建立结构后供 DeepSeek 审查。

## 用户场景

- 用户上传 TXT、Markdown、Word、PDF、PPTX 或 XLSX 文件后立即获得后台任务编号和可恢复进度。
- 普通文本型文件快速完成本地解析，扫描 PDF 自动进入 MinerU OCR。
- 解析失败时用户看到明确阶段和可读原因，可复用原文件重试。
- 页面刷新后仍可查询任务进度和失败状态。

## 支持范围

| 文件类型 | 首选解析 | 失败处理 |
| --- | --- | --- |
| `.txt` / `.md` | UTF-8 直接读取和 Markdown 规范化 | 编码或内容无效时失败 |
| `.doc` / `.docx` | MarkItDown | 质量不合格时 MinerU |
| 文本型 `.pdf` | MarkItDown | 质量不合格时 MinerU |
| 扫描/混合 `.pdf` | MinerU OCR | 失败后提示重试 |
| `.pptx` / `.xlsx` | MarkItDown | 提示转为 PDF 后重传 |

不支持直接上传 `.png`、`.jpg`、`.jpeg`、`.webp` 等图片文件。

## 技术方案

### 统一解析服务

新增独立文档解析服务，输入为已校验的本地临时文件或存储路径，输出包含：

- Markdown 正文
- 实际解析引擎：`text`、`markitdown`、`mineru`
- 文件内容 SHA-256
- 文本质量指标
- MinerU 任务标识（若使用）

解析路由：

1. TXT/Markdown 直接读取。
2. Word 先 MarkItDown，再执行 Markdown 质量检测；不合格时调用 MinerU。
3. PDF 先检测文本层与有效文本页比例。扫描、混合或低文本质量 PDF 直接调用 MinerU；其余 PDF 使用 MarkItDown，并对产物再次检测。
4. PPTX/XLSX 仅使用 MarkItDown，失败时返回明确的格式转换提示。

### MinerU 客户端

复用文衡 MinerU API v4 的申请上传、PUT 上传、轮询、下载 ZIP 和提取 Markdown 流程，在照胆内独立封装：

- Token、模型版本、OCR、语言和超时均来自环境变量。
- 不记录 Token，不把内部响应或堆栈直接返回前端。
- MinerU 错误转换为稳定的业务错误代码。

### 质量检测

质量检测集中在纯函数模块，并允许通过配置调优：

- 非空字符总量
- 可打印字符比例
- Unicode 替换字符和乱码比例
- 图片占位符比例
- PDF 有效文本页比例和每页平均文字量

检测结果只决定解析路由，不把未经校验的低质量文本送入 PageIndex 或 DeepSeek。

### 后台任务

新增通用文档处理任务表，不复用仅面向 API Key 的 `AgentJob`：

- `job_id`、`user_id`、任务类型
- 原文件存储路径、内容哈希、文件类型
- 当前阶段、状态、进度和用户可读消息
- 解析引擎、Markdown 存储路径
- 关联的知识库版本或体检记录
- 错误代码、错误消息、重试次数和时间戳

状态阶段：

```text
queued → detecting → parsing_local/parsing_mineru → indexing → inspecting → succeeded
                                                                    ↘ failed
```

新增 `zhaodan-worker` Compose 服务运行 ARQ。HTTP 上传接口只负责校验、保存原文件、创建任务并返回 `202 + job_id`。

### 阶段续跑

- 原文件始终先保存到受用户隔离的存储路径。
- Markdown 成功后持久化路径和内容哈希。
- PageIndex 或 DeepSeek 阶段失败时，从已有 Markdown 继续，不重复调用 MinerU。
- 同一用户、相同内容哈希和解析配置可复用成功 Markdown；缓存损坏视为未命中。

### 业务流程

体检文件：

```text
上传 → 解析任务 → Markdown → PageIndex → DeepSeek 审查 → 体检记录
```

知识库文件：

```text
上传 → 解析任务 → Markdown → PageIndex → 可供后续 DeepSeek 审查检索
```

## 数据模型

- 新增文档处理任务表及必要索引。
- 现有 `DocumentVersion` 状态与任务阶段同步，保持知识库列表兼容。
- 现有 `InspectionRecord` 只在审查阶段创建或更新，避免产生半成品成功记录。
- 原始文件、Markdown 和索引节点继续通过现有存储与数据库抽象管理。

## 接口设计

- 上传接口返回 `202`、`job_id`、初始状态和关联资源 ID。
- 新增登录用户可用的任务状态查询接口，按 `user_id` 隔离。
- 新增任务重试接口，只允许任务所有者重试失败任务。
- 状态响应包含阶段、进度、消息、错误代码和完成后的资源引用，不包含凭据或内部堆栈。
- 旧的 Agent API Job 接口保持兼容，内部逐步复用统一解析服务。

## 前端交互

- 上传后展示阶段进度：上传、识别、解析、索引、审查。
- 轮询采用可清理定时器，完成、失败或页面卸载时停止。
- MinerU 或解析失败时显示设计系统风格弹窗：失败阶段、可读原因、`重新解析`、`稍后处理`。
- 重试不要求用户重新选择文件。
- 知识库列表继续显示 `待处理 / 解析中 / 索引中 / 已完成 / 失败`。

## 错误处理

- MinerU 超时、配额不足或服务不可用：停止后续流程并允许重试，不自动回退低质量文本。
- PPTX/XLSX 本地解析失败：提示转为 PDF，不调用 MinerU。
- 文件扩展名、Magic Bytes、大小、用户所有权和存储路径校验失败：任务创建前拒绝。
- Worker 重启后可重新获取 queued/running 任务，阶段产物确保幂等。

## 安全

- MinerU Token 仅由服务端环境变量读取。
- 日志不得包含 Token、预签名上传 URL、原始文档正文或完整 MinerU 响应。
- 状态和重试接口必须验证任务所有权。
- 文件名、MIME、Magic Bytes 和大小实行双重校验。
- 原始文件和解析产物沿用用户隔离存储。

## 部署

- 为 `zhaodan-backend` 和新 `zhaodan-worker` 注入 MinerU 配置。
- Worker 与后端使用同一代码镜像、Redis、数据库和文件存储卷。
- 部署按数据库迁移、镜像构建、Worker/后端更新、健康检查顺序进行。
- 上线前完成 Compose 静态检查、容器配置回读和真实小文件 MinerU 解析。

## 测试策略

- 单元测试：文件路由、PDF/Markdown 质量判定、错误映射、内容哈希和阶段续跑。
- 服务测试：MarkItDown 成功、Word/PDF MinerU 兜底、扫描 PDF 直达 MinerU、PPTX/XLSX 失败提示。
- API 测试：上传 202、状态查询、重试、用户隔离、非法文件。
- Worker 测试：阶段进度、幂等、失败恢复、不重复 OCR。
- 前端测试：进度轮询、完成停止、失败弹窗、重试和页面卸载清理。
- 生产验证：真实 MinerU 小文件解析、PageIndex 建树和 DeepSeek 审查闭环。
