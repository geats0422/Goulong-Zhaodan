# 安全审查报告 #4 — 依赖安全与供应链风险

**审查时间**: 2026-06-13
**审查范围**: `backend/pyproject.toml`, `frontend/package.json`, `uv.lock`, `package-lock.json`
**风险等级**: 🟡 **中等 (1 HIGH + 3 MEDIUM)**

---

## 总体评估

| 维度 | 评估 | 备注 |
|------|------|------|
| 依赖版本固定 | 🟡 中危 | pyproject.toml 使用 `>=` 下界，uv.lock 提供精确锁定 |
| 前端依赖面 | ✅ 良好 | 仅 vue + vue-router，极小攻击面 |
| 后端依赖面 | 🟡 中危 | 21 个直接依赖（含 markitdown+插件），攻击面中等 |
| 本地路径依赖 | 🔴 **高危** | `goulong-auth` 通过相对路径 `../../goulong-auth` 引入 |
| lockfile 完整性 | ✅ 良好 | `uv.lock` 含 hash 校验，`package-lock.json` 含 integrity |
| .env 保护 | ✅ 良好 | `.env` 在 `.gitignore` 中 |
| dev 依赖隔离 | ✅ 良好 | pytest/ruff 在 `[project.optional-dependencies]` 中 |
| 已知漏洞扫描 | 🟡 中危 | 未集成 `pip-audit` / `npm audit` 到 CI |

---

## 发现的问题

### 🔴 HIGH — goulong-auth 本地路径依赖缺乏完整性校验

**位置**: `backend/pyproject.toml:24-25`

```toml
[tool.uv.sources]
goulong-auth = { path = "../../goulong-auth" }
```

**问题**:
- `goulong-auth` 通过相对路径引用，不在 PyPI 上，无法利用 PyPI 的供应链保护机制
- 如果 `goulong-auth` 目录被替换或注入恶意代码，照胆无法感知
- 部署时需要确保 `goulong-auth` 包与照胆代码同步

**修复建议**:
1. 将 `goulong-auth` 发布到私有 PyPI 仓库（阿里云 PyPI 镜像或 self-hosted）
2. 或在 CI 中添加 hash 校验：`sha256sum -c goulong-auth.sha256`
3. 或使用 git subrepo + 固定 commit hash

---

### 🟡 MEDIUM — 依赖版本下界 `>=` 无上界锁定

**位置**: `backend/pyproject.toml:5-21`

```toml
dependencies = [
    "fastapi>=0.115.0",
    "pydantic-ai>=0.0.15",
    "litellm>=1.83.0",
    ...
]
```

**问题**: 所有 21 个依赖使用 `>=` 下界，无上界。虽然有 `uv.lock` 锁定具体版本，但：
- `pip install` (非 uv) 会拉取最新版
- 依赖作者可能发布破坏性更新（如 left-pad 事件）
- 特别是 `pydantic-ai>=0.0.15` — 0.x 版本不承诺兼容性

**修复建议**:
- 对关键依赖加上上界：`"fastapi>=0.115.0,<1.0.0"`
- CI 中使用 `uv sync --frozen` 确保使用 lockfile

---

### 🟡 MEDIUM — 未集成自动化漏洞扫描

**问题**:
- 后端未配置 `pip-audit` / `safety` / `bandit`
- 前端未配置 `npm audit` CI 环节
- 依赖更新没有自动安全检查

**修复建议**:
```yaml
# GitHub Actions
- name: Security audit
  run: |
    cd backend && uv run pip-audit
    cd frontend && npm audit --audit-level=high
```

---

### 🟡 MEDIUM — markitdown 插件引入多个文件解析器

**位置**: `backend/pyproject.toml:13`

```toml
"markitdown[docx,pdf,pptx,xlsx]>=0.1.6",
```

**问题**: `markitdown[docx,pdf,pptx,xlsx]` 会引入 `python-docx`、`python-pptx`、`openpyxl`、`pymupdf` 等。这些解析器历史上出现过 CVE（如 python-docx XXE、pymupdf 缓冲区溢出）。如果攻击者上传恶意构造的 docx/pdf，可能触发解析器漏洞。

**修复建议**:
1. 关注这些库的安全公告
2. 对上传文件做更严格的沙箱处理（已在 P0-3 中添加 magic bytes 校验）
3. 考虑在独立进程中运行文件解析

---

## 通过的检查 ✅

- ✅ `.env` 在 `.gitignore`（根 + backend 两个层级）
- ✅ 前端仅 2 个运行时依赖（vue, vue-router），攻击面极小
- ✅ `package-lock.json` 含 integrity hash
- ✅ `uv.lock` 含所有 wheel hash 校验
- ✅ dev 依赖（pytest, ruff）不在生产依赖列表中
- ✅ 无 `*` 通配符版本（如 `fastapi==*`）
- ✅ 无已知弃用库（如 `pickle`, `yaml.load` 无 Loader）
- ✅ `cryptography>=44.0.0` 版本足够新（含当前安全补丁）
- ✅ 无 subprocess 调用不受控的第三方工具
- ✅ `uv.lock` 不在 git 中（`.gitignore` 包含 `uv.lock`）— 但这在部署时需确保锁文件一致
