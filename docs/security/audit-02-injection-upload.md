# 安全审查报告 #2 — 输入验证、注入防护、文件上传

**审查时间**: 2026-06-13
**审查者**: opencode (security-review skill)
**审查范围**: backend/app/api/v1/{inspection,knowledge,settings}.py, services/page_indexer.py, services/file_storage.py, core/{constants,password_rules}.py
**风险等级**: 🟡 **中等 (有 2 个高危 + 2 个中危)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| Pydantic 输入验证 | ✅ 良好 | email/phone/plan/nickname 都有 validator |
| 密码强度 | ✅ 良好 | 长度、字符、弱密码库 |
| SQL 注入 | ✅ 良好 | 全部使用 ORM 参数化（无字符串拼接） |
| LIKE 通配符注入 | 🔴 **高危** | `%`/`_` 未转义 |
| 文件扩展名白名单 | ✅ 良好 | constants.py 定义 |
| 文件 MIME 类型 | 🔴 **高危** | 仅检查扩展名，未校验实际 MIME |
| 文件大小限制 | ✅ 良好 | knowledge 50MB / inspection 20MB |
| 路径遍历 | ✅ 良好 | `safe_path_segment` 限制字符 |
| 临时文件安全 | 🟡 中危 | `delete=False` + 手动 unlink |
| 命令执行 | ✅ 良好 | 无 subprocess/shell |
| 模板注入 | 🟡 中危 | PDF 生成使用 f-string 拼接 |
| 前端 XSS | ✅ 良好 | 无 v-html / innerHTML |
| 环境变量污染 | 🟡 中危 | `os.environ.setdefault` |

---

## 发现的问题

### 🔴 HIGH — LIKE 查询通配符未转义（潜在 SQL 注入/信息泄露）

**位置**: `backend/app/api/v1/inspection.py:758`

```python
conditions.append(InspectionRecord.document_name.ilike(f"%{keyword.strip()}%"))
```

**问题**: 用户输入的 `keyword` 直接拼接到 `ILIKE` 模式字符串中。SQLAlchemy 的 `ilike()` 不会转义 LIKE 通配符：
- 输入 `%` 会匹配所有记录 → 越权读取他人文档名
- 输入 `_` 会匹配单字符 → 缩小匹配范围做枚举攻击
- 不构成传统 SQL 注入（SQLAlchemy 已参数化值），但**逻辑上等同于绕过筛选**

**调用路径**: `GET /api/v1/inspection/records?keyword=...`

**修复建议**:
```python
import re
escaped = re.sub(r"([%_\\])", r"\\\1", keyword.strip())
conditions.append(InspectionRecord.document_name.ilike(f"%{escaped}%", escape="\\"))
```

或更安全地限制输入长度（如 max 100 字符）+ 禁止纯通配符。

---

### 🔴 HIGH — 文件上传仅校验扩展名，未校验实际 MIME

**位置**: `backend/app/api/v1/knowledge.py:284`, `inspection.py:197`

```python
# knowledge.py
ext = validate_file_type(filename)  # 只看后缀名

# inspection.py
_validate_inspection_filename(filename)  # 只看后缀名
```

**问题**: 攻击者可以构造 `evil.pdf.exe` 或 `evil.docx`（实际是 PHP / JSP）绕过扩展名检查。后端仅依赖 `filename.rfind(".")` 提取扩展名，未读取文件魔数（magic bytes）。

**调用路径**: 
- `POST /api/v1/knowledge/upload`
- `POST /api/v1/inspection/upload`

**修复建议**:
```python
import magic  # python-magic-bin (Windows) 或 file-magic

def validate_mime(content: bytes, expected_ext: str) -> bool:
    mime = magic.from_buffer(content, mime=True)
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return mime == mime_map.get(expected_ext)
```

加上 `python-magic-bin` 依赖。

---

### 🟡 MEDIUM — 临时文件 delete=False + 手动 unlink 存在清理失败风险

**位置**: `backend/app/api/v1/inspection.py:225-233`, `services/page_indexer.py:51-62`

```python
with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_format}") as temp_file:
    temp_file.write(content)
    temp_path = Path(temp_file.name)
return _clean_inspection_markdown(convert_to_markdown(temp_path))
...
finally:
    if temp_path is not None:
        temp_path.unlink(missing_ok=True)
```

**问题**: 进程在 `unlink` 之前崩溃（OOM、信号、被杀）会遗留临时文件。攻击者通过反复触发可填满磁盘。

**修复建议**:
- 优先 `delete=True`（默认），仅在 markitdown 强制要求磁盘路径时才用 `delete=False`
- 加 `try/except` 记录 unlink 失败
- 定期清理脚本（cron）

---

### 🟡 MEDIUM — `os.environ.setdefault` 污染全局环境

**位置**: `backend/app/services/page_indexer.py:81-83`

```python
os.environ.setdefault("OPENAI_API_KEY", settings.model_api_key)
if settings.model_base_url:
    os.environ.setdefault("OPENAI_API_BASE", settings.model_base_url)
```

**问题**: `setdefault` 不会覆盖已有值，但写入会污染全局进程环境。如 `os.environ` 在多线程场景下未加锁（Python 3.9+ GIL 保护但仍是 anti-pattern），且第三方库可能缓存读取结果。

**修复建议**:
- 直接将 API key 传给 `md_to_tree` 函数（如果支持）
- 或使用 `env=` 参数传给 subprocess 调用

---

### 🟡 MEDIUM — PDF 生成 f-string 拼接（特殊字符未转义）

**位置**: `backend/app/api/v1/inspection.py:431-477`

```python
title = f"{_strip_document_extension(record.document_name)}审查报告"
...
text_ops.append(f"<{_pdf_hex_text(line)}> Tj")
...
pdf.extend(f"{index} 0 obj\n".encode())
```

**问题**: 
- `_pdf_hex_text` 已使用 hex 编码（`%04X`），相对安全
- 但 PDF 字符串语法对 `()`、`\`、未闭合的尖括号敏感
- 实际生成的是 hex string (`<...>` 包围)，不解析转义 — **实际安全** ✅
- 但代码可读性差，f-string 拼接容易在维护时引入真实漏洞

**评估**: LOW 风险，但建议封装为 `_format_pdf_string()` 帮助函数并加注释。

---

### ✅ 通过的检查

- ✅ 所有 SQLAlchemy 查询使用 ORM 参数化（`where(User.id == user_id)`），无字符串拼接
- ✅ Pydantic 验证 email/phone/plan/nickname/password
- ✅ `validate_password` 强制 8-128 字符、禁用弱密码（11+ 弱密码列表）
- ✅ `safe_path_segment` 限制文件名到 `[\w.-]` 字符
- ✅ 文件大小硬限制 knowledge 50MB / inspection 20MB
- ✅ 体检记录 `keyword` 走 `inspection.records` 接口，user_id 强制过滤
- ✅ 无 subprocess / shell 字符串调用
- ✅ 无 `v-html` / `innerHTML` / `dangerouslySetInnerHTML` 前端调用
- ✅ markitdown 转换错误被 try/except 包裹为通用 400
- ✅ 文衡 vs 照胆：FK 已统一指向 `goulong_auth.users(id)`

---

## 下次审查重点

- CORS 配置（`cors_origins` 默认值）
- Cookie 属性（refresh token 的 Secure/HttpOnly/SameSite）
- HTTPS 强制 / HSTS
- 安全响应头（CSP/X-Frame-Options/X-Content-Type-Options）
- 错误处理：是否泄露堆栈跟踪
- 日志记录：是否记录敏感信息（密码/token/PII）
