# 安全审查汇总报告 — Goulong-Zhaodan

**审查时间**: 2026-06-13
**审查者**: opencode (security-review skill × 3)
**审查范围**: `backend/` + `frontend/` (commit `884bbb9`)
**总体风险等级**: 🟠 **中高 (4 HIGH + 7 MEDIUM)**

---

## 总体评估

照胆后端整体安全实践良好：参数化查询、密码 bcrypt、Fernet 加密、JWT 签名一致、refresh token 持久化。**但在 4 个关键防护层级存在高危缺陷**：

1. **加密原语使用方式** — `==` 比较哈希（时序侧信道）
2. **用户输入处理** — LIKE 通配符注入
3. **文件上传信任链** — 缺 MIME 校验
4. **传输层保护** — 无 HTTPS/HSTS/安全响应头

这些都不构成即时数据泄露，但组合起来构成生产部署前的必修项。

---

## 问题汇总

| # | 严重程度 | 分类 | 位置 | 问题 | 修复优先级 |
|---|----------|------|------|------|----------|
| 1 | 🔴 HIGH | 认证 | `core/api_key_crypto.py:23` | `verify_api_key_hash` 使用 `==` 而非 `hmac.compare_digest` | P0 |
| 2 | 🔴 HIGH | 注入 | `api/v1/inspection.py:758` | LIKE 查询 `%`/`_` 未转义 | P0 |
| 3 | 🔴 HIGH | 上传 | `api/v1/knowledge.py:284`, `inspection.py:197` | 仅校验扩展名，未校验 MIME magic bytes | P0 |
| 4 | 🔴 HIGH | 传输 | `main.py` (整个应用) | 无 HTTPS 强制、无 HSTS、无安全响应头 | P0 |
| 5 | 🟡 MEDIUM | 配置 | `core/config.py:65` | `assert_production_security` 漏检 DATA_ENCRYPTION_KEY / DB URL / CORS | P1 |
| 6 | 🟡 MEDIUM | 认证 | `core/auth.py:74`, `agent_auth.py:15` | 手写 Bearer 解析，未用 OAuth2PasswordBearer | P2 |
| 7 | 🟡 MEDIUM | 临时文件 | `inspection.py:225`, `page_indexer.py:51` | `delete=False` + 手动 unlink，进程崩溃遗留文件 | P2 |
| 8 | 🟡 MEDIUM | 环境变量 | `services/page_indexer.py:81` | `os.environ.setdefault` 污染全局 | P2 |
| 9 | 🟡 MEDIUM | 部署 | `api/v1/auth.py:67-75` | Cookie `secure` 仅在 production | P1 |
| 10 | 🟡 MEDIUM | 错误处理 | `inspection.py:206, 591` | 错误消息泄露内部异常文本 | P1 |
| 11 | 🟡 MEDIUM | 客户端 | `useAuth.js:6` | access token 存于 sessionStorage (XSS 风险) | P2 |

---

## 修复优先级建议

### P0 — 上线前必修 (4 项)
1. `hmac.compare_digest` 替换 `==`
2. LIKE 通配符 `re.escape` + `escape="\\"`
3. 文件 MIME 校验（`python-magic-bin`）
4. 添加 SecurityHeadersMiddleware + HTTPS 强制

### P1 — 1 周内修复 (3 项)
5. 扩展 `assert_production_security` 覆盖 DATA_ENCRYPTION_KEY / DB URL / CORS
9. Cookie `secure` 改为非 development 即可
10. 错误消息通用化 + 记录到 logger

### P2 — 1 个月内修复 (4 项)
6. 迁移到 `OAuth2PasswordBearer`
7. 临时文件用 `delete=True` 或加守护进程清理
8. 移除 `os.environ.setdefault`
11. access token 改 HttpOnly Cookie 或内存存储

---

## 通过的安全实践 ✅

- 密码 bcrypt 哈希 (goulong_auth)
- JWT 包含 user_id/product/exp/iat 字段
- bcrypt/HS256/JWT/Fernet 加密原语选择正确
- Refresh token 通过 jti 持久化 + 可主动撤销
- `.env` 在 `.gitignore` 中
- 开发密钥默认值显式标记 `*-change-in-production`
- CORS 默认白名单（无 `*` 通配符）
- Cookie `httponly=True`, `samesite="lax"`
- 所有 SQLAlchemy 查询使用 ORM 参数化
- 无字符串拼接 SQL
- 无 subprocess / shell 字符串调用
- 无 v-html / innerHTML / dangerouslySetInnerHTML
- 无敏感信息打印到日志
- Pydantic 验证 email/phone/plan/nickname/password
- 文件大小硬限制（50MB / 20MB）
- `safe_path_segment` 防路径遍历
- API Key 加密使用 Fernet (AES-128-CBC + HMAC)
- FastAPI 自动校验 Content-Type

---

## 详细报告

- [审查 #1: 密钥管理与认证授权](./audit-01-secrets-auth.md)
- [审查 #2: 输入验证、注入防护、文件上传](./audit-02-injection-upload.md)
- [审查 #3: 数据传输、CORS、错误处理、信息泄露](./audit-03-transport-cors-errors.md)

---

## 与文衡对比

文衡 (origin/develop) 已有 13 项安全加固（4d71b05）但**未合并到照胆 main**。该 commit 覆盖：
- 生产环境断言（已包含 P0 #5 修复）
- refresh token 仅 Cookie（覆盖 P1 #9）
- LIKE 通配符转义（覆盖 P0 #2）
- MIME 白名单（覆盖 P0 #3）
- hmac.compare_digest（覆盖 P0 #1）
- 安全响应头中间件（覆盖 P0 #4）
- hmac.compare_digest API Key（覆盖 P0 #1）
- 通用错误消息（覆盖 P1 #10）

**建议**：将 4d71b05 安全加固在照胆新路径（`app/core/...`）上手动重做一次，因为 commit 路径是旧的（`core/...`）。

---

## 结论

照胆后端达到了 MVP 可用水平，但距离生产部署需完成 4 项 P0 修复 + 3 项 P1 修复。建议在下个迭代周期集中修复 P0/P1，然后引入自动化安全扫描（bandit/safety）作为 CI 环节。
