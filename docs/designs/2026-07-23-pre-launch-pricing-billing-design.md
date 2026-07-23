# 上线前定价与账单优化设计文档

## 目标

上线前完成 4 项调整：定价策略更新、额度账单闭环、知识库设置分类简化、AI 模型选择统一。使产品具备完整的商业化能力。

## 用户场景

1. 新用户注册 → 获得 20 万 token/月免费额度 → 体验 1-2 次体检
2. 额度将耗尽 → 前端黄色预警 → 用户购买加购包或订阅
3. 额度耗尽 → API 返 402 → 前端弹窗引导购买
4. 用户在设置页切换 AI 模型（flash/pro）→ 后续体检按新模型计费
5. 用户在设置页管理知识库 → 启用/停用参考依据

---

## 一、定价策略

### 1.1 新定价表

| 套餐 | 类型 | 价格 | Token 额度 | 目标 |
|---|---|---|---|---|
| 免费 | 免费 | ¥0 | 20 万/月 | 试用体验 |
| 轻量包 | 加购 | ¥9 | 100 万 | 偶尔补额 |
| 标准包 | 加购 | ¥29 | 500 万 | 项目期 |
| 大额包 | 加购 | ¥89 | 2000 万 | 高频使用 |
| Pro 月度 | 订阅 | ¥69/月 | 300 万/月 | 持续使用 |
| Pro 季度 | 订阅 | ¥179/季 | 900 万/季 | 季度合规 |
| Pro 年度 | 订阅 | ¥599/年 | 3600 万/年 | 最佳性价比 |

### 1.2 改动文件

- `backend/app/services/payment_catalog.py`：更新 PRODUCTS 字典的 amount_cents + token_quota
- `frontend/src/pages/PricingPage.vue`：前端定价页同步更新价格展示

### 1.3 免费额度实现

- `FREE_MONTHLY_TOKEN_QUOTA = 200_000`
- 免费用户 `membership.token_quota = 0` 时，有效额度兜底为 `FREE_MONTHLY_TOKEN_QUOTA`
- 按月重置（月初 `token_used` 归零）— 通过现有 cron task 或新增定时逻辑

---

## 二、额度账单闭环

### 2.1 后端额度拦截

新建 `backend/app/core/quota.py`（参照文衡）：

```python
FREE_MONTHLY_TOKEN_QUOTA = 200_000

def effective_token_quota(membership) -> int:
    """免费用户兜底 20 万/月"""
    if membership is None:
        return FREE_MONTHLY_TOKEN_QUOTA
    quota = int(membership.token_quota or 0)
    if quota <= 0:
        return FREE_MONTHLY_TOKEN_QUOTA
    return quota

def remaining_tokens(membership) -> int:
    return max(0, effective_token_quota(membership) - int(membership.token_used or 0))

async def require_quota(current_user) -> CurrentUserContext:
    """FastAPI 依赖：额度不足时返 402"""
    if remaining_tokens(current_user.membership) <= 0:
        raise HTTPException(status_code=402, detail={
            "code": "insufficient_quota",
            "message": "算力额度不足，请购买额度包后继续使用",
        })
    return current_user
```

### 2.2 API 拦截点

| API | 加依赖 |
|---|---|
| `POST /inspection/upload` | `Depends(require_quota)` |
| `POST /inspection/parse` | `Depends(require_quota)` |
| `POST /inspection/sessions/{id}/inspect` | `Depends(require_quota)` |
| `POST /api/v1/agent/jobs/inspect` | `Depends(require_quota)` |
| `POST /api/v1/knowledge/upload` | `Depends(require_quota)` |

### 2.3 前端额度展示

- **设置页账单区域**：额度进度条（已用/总量，百分比）+ 剩余 < 10% 时黄色预警
- **体检失败处理**：捕获 402 → 弹窗"额度不足，是否购买？" → 跳转定价页
- **数据来源**：现有 `GET /settings/overview` 返回的 `token_quota` + `token_used`

### 2.4 改动文件

| 文件 | 改动 |
|---|---|
| `backend/app/core/quota.py` | 新建：额度检查依赖 |
| `backend/app/api/v1/inspection.py` | 体检端点加 `require_quota` |
| `backend/app/api/v1/knowledge.py` | 入库端点加 `require_quota` |
| `backend/app/services/inspection_runner.py` | 移除内联额度检查（改由依赖统一处理） |
| `frontend/src/pages/SettingsPage.vue` | 账单区域加进度条 + 预警 |
| `frontend/src/pages/DashboardPage.vue` | 402 错误处理弹窗 |

---

## 三、知识库设置分类简化

### 3.1 设计

设置页知识库区域从「按 4 个工程分类分组」改为「上下两个区域」：

```
┌─────────────────────────────────────┐
│ 系统默认知识库                       │
│  ☑ 招标投标法          [招投标]      │
│  ☑ 民法典合同编        [合同]        │
│  ☑ 政府采购法          [招投标]      │
│  ...                                 │
├─────────────────────────────────────┤
│ 我的知识库                           │
│  ☑ 我上传的合同模板    [合同][传统基建]│
│  ☐ 暂停的参考卷宗      [招投标][新基建]│
│  + 上传新卷宗                        │
└─────────────────────────────────────┘
```

- **上部**：`owner_type = "system"` 的文档，带业务标签（场景 + 工程类型）
- **下部**：`owner_type = "user"` 的文档，带业务标签 + 上传入口
- 每个文档有**启用/停用开关**（`KnowledgeDocumentSetting.enabled`），控制体检时是否参考

### 3.2 数据层

- `KnowledgeDocumentSetting` 模型已存在（`user_id` + `document_id` + `enabled`）
- `retrieve_regulation_base()` 已按用户启用的文档检索
- 后端 `GET /settings/overview` 需调整：返回文档时区分 `owner_type` 分组

### 3.3 改动文件

| 文件 | 改动 |
|---|---|
| `backend/app/api/v1/settings.py` | overview 返回分 `system` / `user` 两组 |
| `frontend/src/pages/SettingsPage.vue` | 知识库区域改为上下分区 + 启用/停用开关 |

---

## 四、AI 模型选择统一

### 4.1 设计

- 设置页模型选择卡片**保留**（用户切 flash/pro）
- **删除**服务端 URL + API Key 预览（`SettingsPage.vue` line 946-947）
- 所有体检/入库流程通过 `settings.model_name` 全局生效（现状已满足）
- 计费按所选模型倍率（flash=1x, pro=3x，已实现）

### 4.2 改动文件

| 文件 | 改动 |
|---|---|
| `frontend/src/pages/SettingsPage.vue` | 删除 line 946-947（服务端 URL + API Key 显示） |

---

## 改动范围总览

| # | 文件 | 类型 | 议题 |
|---|---|---|---|
| 1 | `backend/app/services/payment_catalog.py` | 修改 | 定价 |
| 2 | `frontend/src/pages/PricingPage.vue` | 修改 | 定价 |
| 3 | `backend/app/core/quota.py` | **新建** | 账单 |
| 4 | `backend/app/api/v1/inspection.py` | 修改 | 账单 |
| 5 | `backend/app/api/v1/knowledge.py` | 修改 | 账单 |
| 6 | `backend/app/services/inspection_runner.py` | 修改 | 账单 |
| 7 | `backend/app/api/v1/settings.py` | 修改 | 知识库 + 账单 |
| 8 | `frontend/src/pages/SettingsPage.vue` | 修改 | 知识库 + 模型 + 账单 |
| 9 | `frontend/src/pages/DashboardPage.vue` | 修改 | 账单（402 弹窗） |

## 错误处理

| 场景 | 处理 |
|---|---|
| 额度不足 | API 返 402 + `code: "insufficient_quota"` → 前端弹窗引导购买 |
| 免费用户超额 | 同上，402 拦截 |
| 模型切换失败 | 设置页保持上次成功的选择 |

## 测试策略

1. **定价**：验证 `payment_catalog.PRODUCTS` 的价格和额度与新表一致
2. **额度拦截**：mock membership.token_used ≥ quota → 验证返 402
3. **免费兜底**：membership=None 或 token_quota=0 → 验证有效额度 = 20 万
4. **知识库启用/停用**：停用文档后体检 → 验证 regulation_base 不含该文档
5. **前端 402**：模拟 API 返 402 → 验证弹窗出现
