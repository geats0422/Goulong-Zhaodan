# 安全审查汇总报告 (第二轮) — Goulong-Zhaodan

**审查时间**: 2026-06-13
**审查范围**: 依赖供应链、业务逻辑授权、数据隐私合规
**总体风险等级**: 🟠 **中高 (3 HIGH + 7 MEDIUM)**

> 本轮审查在第 1-3 次审查（密钥/注入/传输）和 P0 修复之后进行，不重复已知问题。

---

## 问题汇总

| # | 严重程度 | 分类 | 位置 | 问题 | 修复优先级 |
|---|----------|------|------|------|----------|
| 12 | 🔴 HIGH | 业务逻辑 | `settings.py:395-398` | 用户可自行修改 subscription_plan 绕过付费 | P0 |
| 13 | 🔴 HIGH | SSRF | `settings.py:392-393` | avatar_url 无 URL 协议/白名单校验 | P0 |
| 14 | 🔴 HIGH | 供应链 | `pyproject.toml:24-25` | goulong-auth 本地路径依赖无完整性校验 | P1 |
| 15 | 🟡 MEDIUM | 速率限制 | `rate_limit.py` 全局 | 体检上传/API Key 创建/知识库上传/密码修改无速率限制 | P1 |
| 16 | 🟡 MEDIUM | 竞态 | `api_key_service.py:116-127` | API Key 查找无行锁 | P2 |
| 17 | 🟡 MEDIUM | 并发 | `inspection.py:96-127` | 内存会话 dict 无并发保护（多 worker 不安全） | P2 |
| 18 | 🟡 MEDIUM | 版本锁定 | `pyproject.toml:5-21` | 所有依赖 `>=` 无上界 | P1 |
| 19 | 🟡 MEDIUM | 漏洞扫描 | CI/CD | 未集成 pip-audit / npm audit | P1 |
| 20 | 🟡 MEDIUM | 文件解析 | `pyproject.toml:13` | markitdown 插件引入多个有 CVE 历史的解析器 | P2 |
| 21 | 🟡 MEDIUM | 数据库 | `config.py:22` | 数据库连接无 SSL 强制 | P1 |
| 22 | 🟡 MEDIUM | PII | User model | email/phone 明文存储未脱敏 | P1 |
| 23 | 🟡 MEDIUM | 文件加密 | `file_storage.py:29-31` | 上传文件无静态加密 | P2 |
| 24 | 🟡 MEDIUM | 数据保留 | `InspectionRecord` | 体检记录无自动清理策略 | P2 |

---

## 两轮审查汇总 (共 24 项)

| 严重程度 | 第 1-3 次 | P0 修复 | 第 4-6 次 | 合计 |
|----------|----------|---------|----------|------|
| 🔴 HIGH | 4 | 已修复 4 | 3 (新) | 7 |
| 🟡 MEDIUM | 7 | — | 10 | 17 |

### 所有 HIGH 项

| # | 状态 | 问题 | 
|---|------|------|
| 1 | ✅ **已修复** | `verify_api_key_hash` 时序侧信道 → `hmac.compare_digest` |
| 2 | ✅ **已修复** | LIKE 通配符注入 → `escape="\\"` |
| 3 | ✅ **已修复** | 文件 MIME 伪造 → `file_magic.py` magic bytes 校验 |
| 4 | ✅ **已修复** | 无安全响应头 → `security_headers_middleware` |
| 12 | ❌ 未修复 | 用户自行修改 subscription_plan |
| 13 | ❌ 未修复 | avatar_url SSRF 向量 |
| 14 | ❌ 未修复 | goulong-auth 本地依赖无完整性校验 |

---

## 修复优先级建议

### P0 — 本周必修 (2 项)
12. 从 `ProfileUpdateRequest` 移除 `subscription_plan` 或添加权限校验
13. `avatar_url` 添加 HTTPS-only + 内网地址黑名单校验

### P1 — 2 周内修复 (5 项)
14. goulong-auth 发布到私有 PyPI 或添加 hash 校验
15. 关键端点添加速率限制
18. 依赖版本添加上界
19. CI 集成 pip-audit + npm audit
21. 数据库连接 SSL 强制
22. API 响应中 PII 脱敏

### P2 — 1 个月内修复 (5 项)
16. API Key 计费查询加行锁
17. inspection 会话迁移到 Redis
20. 关注 markitdown 插件 CVE
23. 上传文件静态加密
24. 体检记录自动清理策略

---

## 详细报告

### 第一轮
- [审查 #1: 密钥管理与认证授权](./audit-01-secrets-auth.md)
- [审查 #2: 输入验证、注入防护、文件上传](./audit-02-injection-upload.md)
- [审查 #3: 数据传输、CORS、错误处理](./audit-03-transport-cors-errors.md)
- [第一轮汇总](./audit-summary.md)

### 第二轮
- [审查 #4: 依赖安全与供应链风险](./audit-04-dependency-supply-chain.md)
- [审查 #5: 业务逻辑与授权安全](./audit-05-business-logic-authz.md)
- [审查 #6: 数据安全与隐私合规](./audit-06-data-privacy-compliance.md)
