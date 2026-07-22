# SaaS 切换 Creem Live/Product Mode 上线前审核预检报告

审核日期：2026-05-18

审核范围：当前仓库中的前端落地页、pricing、privacy/terms、Creem checkout、Creem webhook、支付配置与部署文档。未读取真实 `.env` secret，未修改应用代码。

## 结论

当前不建议直接切换到 Creem live/product mode。

主要阻塞来自三类问题：支付配置与代码环境变量命名不一致、checkout/webhook 闭环尚未达到生产可靠性、公开法务/客服信息仍包含占位或本地域名。建议完成下列 P0 阻塞项并用 Creem test mode 跑通端到端后，再提交 live/product mode 审核。

## 阻塞项

| 优先级 | 阻塞项 | 证据 | 风险 | 建议处理 |
|---|---|---|---|---|
| P0 | 生产回跳 URL 配置存在命名不一致，可能导致 live checkout 仍跳回 localhost 或配置失效 | `backend/app/core/config.py:108-109` 使用 `creem_checkout_success_url`、`creem_checkout_cancel_url`；`docs/env-matrix.md:115-116` 记录的是 `CREEM_DEFAULT_SUCCESS_URL`、`CREEM_DEFAULT_CANCEL_URL` | live 支付成功后用户回跳到本地地址，审核或真实支付失败 | 统一环境变量命名，并在 Render/Vercel 生产配置中明确设置真实 HTTPS 前端域名 |
| P0 | checkout payload 未传取消 URL，且配置项 `creem_checkout_cancel_url` 未被使用 | `backend/app/services/payments/service.py:55-59` 只传 `product_id`、`success_url`、`metadata` | 用户取消支付后的回跳体验不可控，Creem 审核可能要求清晰 cancel flow | 在创建 checkout 时加入 cancel URL，并用生产域名验证成功/取消两条路径 |
| P0 | live product ID、价格与前端展示价格没有可验证映射 | 前端价格来自 `frontend/src/config/pricing.ts:17-39`；后端产品 ID 来自 `backend/app/services/payments/service.py:63-77`；没有 live product/price 对照清单 | 用户看到的价格可能与 Creem checkout 实收价格不一致，造成审核、投诉或退款风险 | 建立 live product ID 对照表，逐项核对月/季/年订阅与 5 个代币包的价格、币种、税费展示 |
| P0 | Webhook 签名实现假设为 `hmac_sha256(secret, raw_body).hexdigest()`，未见与 Creem 官方 live 签名格式的适配确认 | `backend/app/services/payments/webhook_handler.py:31-36`；测试仅覆盖同一假设 `backend/tests/api/test_payments_api.py:77-132` | live webhook 可能全部 401，导致付费后不到账或订阅不生效 | 用 Creem test mode 真实 webhook 样本确认 header 名、签名算法、时间戳/前缀格式，并补充测试 |
| P0 | 法务与公开支持信息仍含占位/非生产邮箱 | `frontend/src/i18n/index.ts:433`、`1749` 等使用 `support@xirang.local`；`frontend/src/i18n/index.ts:444` 含 `Unified Social Credit Code to be filled in` | Merchant of Record 审核通常会检查真实商户信息、支持邮箱、隐私/条款可联系性；占位信息会导致驳回 | 替换为真实支持邮箱、公司注册信息、有效联系方式，并同步多语言文案 |
| P0 | 服务条款退款描述过于主观，未与 Creem/MoR 退款、税费、订阅续费规则对齐 | `frontend/src/i18n/index.ts:768` 写明退款由我们自行决定；条款仅泛述订阅 | 审核材料与实际 MoR 政策不一致，容易触发合规风险 | 更新 Terms/Pricing FAQ：自动续费、取消生效时间、退款渠道、税费由 Creem/MoR 计算与展示 |

## 高风险非阻塞项

| 优先级 | 问题 | 证据 | 影响 | 建议处理 |
|---|---|---|---|---|
| P1 | `CreemApiError` 未在 checkout API 层统一映射 | `backend/app/api/v1/payments.py:55-60` 只捕获 timeout 与配置错误；`backend/app/integrations/creem/client.py:56-59` 会抛 `CreemApiError` | Creem 4xx/5xx 可能暴露为 500，前端提示差，排障困难 | 将 Creem 非超时错误映射为 502/503，并记录 request context |
| P1 | checkout 响应没有校验 `checkout_url` 为空的异常 | `backend/app/services/payments/service.py:60-61` 直接 `data.get("checkout_url", "")` | 前端可能跳转空 URL，用户停留或跳到当前页 | 空 URL 视为上游错误并返回可读错误 |
| P1 | 订阅状态命名前后端不一致 | Webhook 激活写 `subscription_status = "pro"`：`backend/app/services/payments/webhook_handler.py:115`；设置弹窗用 `props.subscriptionStatus === "active"` 判断 Pro：`frontend/src/components/settings/SubscriptionManageModal.vue:80` | 已付用户在设置页可能仍显示 Free 或错误 CTA | 统一状态枚举：建议后端返回 `active/trialing/past_due/canceled/free`，权益层单独映射 Pro |
| P1 | 价格页未接入地区定价 API，与设计文档不一致 | 设计要求 `docs/designs/2026-05-15-creem-payment-integration-design.md:20-23`；实际 pricing 页使用静态 `PRICING_CONFIG` | pricing 页展示不随用户地区变化，可能与 checkout product 价格不一致 | 在 pricing 页加载 `/payments/region` 并以后端价格为准 |
| P1 | 代币发放依赖 `coin_amount` metadata，但创建 checkout 时未设置该字段 | 创建 checkout metadata：`backend/app/services/payments/service.py:58`；Webhook 发币读取 `coin_amount`：`backend/app/services/payments/webhook_handler.py:67-75` | 代币购买成功后可能不会到账 | 对 coin checkout 写入 `coin_amount`，并为各 coin 包补真实 webhook 样本测试 |
| P1 | 取消订阅语义可能是立即取消而非期末取消 | 设计文档写 scheduled：`docs/designs/2026-05-15-creem-payment-integration-design.md:59`；实现调用 cancel 后立即设 canceled：`backend/app/services/payments/service.py:104-113` | 付费用户可能提前失去权益，或 UI 与 Creem 实际状态不一致 | 确认 Creem cancel API 行为，按 period end 保留权益并展示到期时间 |
| P1 | 环境矩阵列出的 Creem timeout、价格系数、地区变量未在配置类中实现 | `docs/env-matrix.md:114-122`；`backend/app/core/config.py:97-119` | 运维配置与代码不一致，live 切换时容易误配 | 更新代码或文档，保留真实会生效的变量清单 |
| P1 | pricing/landing footer 社交链接为 `#` | `frontend/src/pages/DungeonScholarPricingPage.vue:101-102`，`frontend/src/pages/EasternFantasyLandingPage.vue:114-115` | 审核观感差，公开站点完整性不足 | 替换为真实链接或移除 |

## 已具备的上线基础

| 项目 | 现状 |
|---|---|
| 后端路由 | 已注册 `/api/v1/payments/checkout`、`/subscription`、`/subscription/cancel`、`/region`、`/webhook/creem` |
| Creem API client | 已封装 checkout、查询订阅、取消订阅，且根据 `creem_test_` key 自动走 test API |
| Webhook 幂等 | 使用 `payment_transactions.external_transaction_id` 和 wallet idempotency key 避免重复发币 |
| 订阅字段 | `users` 表迁移已包含订阅状态、tier、到期时间、Creem customer/subscription ID、pricing region |
| 前端入口 | pricing、shop、settings 已调用 checkout/订阅/地区 API |
| 法务页面 | privacy 与 terms 页面存在，并从落地页/pricing footer 可访问 |

## 修复任务清单

| 编号 | 优先级 | 任务 | 涉及文件 | 验收标准 |
|---|---|---|---|---|
| T1 | P0 | 统一 Creem 生产环境变量命名与文档 | `backend/app/core/config.py`、`docs/env-matrix.md`、部署平台变量 | 生产配置中 success/cancel URL 均为真实 HTTPS 域名，代码与文档变量名一致 |
| T2 | P0 | 完善 checkout payload | `backend/app/services/payments/service.py`、相关测试 | payload 包含 success URL、cancel URL、user metadata、coin amount；空 checkout URL 会报错 |
| T3 | P0 | 建立 live product/price 对照并核对 | 新增运维审核文档或 release checklist | 8 个产品 ID 与前端价格、币种、周期、代币数一一匹配 |
| T4 | P0 | 用真实 Creem test webhook 样本校验签名与事件结构 | `backend/app/services/payments/webhook_handler.py`、`backend/tests/api/test_payments_api.py` | test mode 真实事件可验签通过，订阅和代币事件均能正确回写 |
| T5 | P0 | 替换占位法务与支持信息 | `frontend/src/i18n/index.ts`、privacy/terms 展示页 | 无 `support@xirang.local`、无 `to be filled in`；支持邮箱可收信，公司信息真实 |
| T6 | P0 | 更新退款、订阅、税费条款 | `frontend/src/i18n/index.ts`、pricing FAQ | 明确续费、取消、退款处理渠道、税费由 Creem/MoR 结账页展示 |
| T7 | P1 | 统一订阅状态语义 | 后端 payments service/webhook、前端 settings modal | 已付订阅在设置页显示为 Pro，取消后展示到期权益状态 |
| T8 | P1 | pricing 页以后端地区价格为准 | `frontend/src/pages/DungeonScholarPricingPage.vue`、相关测试 | 切换/加载地区后价格与 `/payments/region` 一致 |
| T9 | P1 | 改善 Creem API 错误映射与前端提示 | `backend/app/api/v1/payments.py`、前端调用处 | Creem 4xx/5xx 返回明确 502/503，前端显示可读错误 |
| T10 | P1 | 完成上线烟测脚本/清单 | `docs/smoke-checklist.md` 或新增支付 smoke checklist | 覆盖 checkout 创建、取消回跳、成功回跳、webhook 回写、重复 webhook、订阅取消 |

## 上线前验证建议

| 阶段 | 验证项 | 通过标准 |
|---|---|---|
| 配置 | Render API 环境变量 | `CREEM_API_KEY` 为 live key，webhook secret 与 Creem dashboard 一致，product IDs 为 live product |
| 配置 | Vercel/前端域名 | pricing、privacy、terms、help/support 均为公开 HTTPS 可访问 |
| Creem test mode | checkout 创建 | 月/季/年订阅与 5 个代币包均能跳转到正确 checkout |
| Creem test mode | webhook | 支付成功后代币到账、订阅变 Pro；重复事件不重复发币 |
| Creem test mode | 取消 | 用户取消支付返回 pricing；取消订阅后权益与到期时间符合预期 |
| 合规 | 法务 | 隐私政策、服务条款、退款/订阅说明、支持邮箱、公司信息无占位 |
| 生产预演 | live 小额验证 | 用内部账号完成一次 live 真实支付并确认账单、税费、到账、回跳、邮件通知 |

## 提交 Creem 审核邮件草稿

主题：Request to enable live/product mode for Xi Rang SaaS

正文：

Hi Creem Team,

We would like to request live/product mode approval for our SaaS product, Xi Rang.

Product name: Xi Rang

Website: [填写生产落地页 URL]

Pricing page: [填写生产 pricing URL]

Privacy Policy: [填写生产 privacy policy URL]

Terms of Service: [填写生产 terms URL]

Support email: [填写真实支持邮箱]

Company/legal entity: Hangzhou Huanyu Gezhi Intelligent Technology Co., Ltd. [补充真实注册信息]

Business model: SaaS subscription with optional virtual coin purchases for in-product learning/gameplay features.

Products to enable:

| Product | Billing | Price | Creem live product ID |
|---|---|---|---|
| Pro Monthly | Monthly subscription | [填写] | [填写] |
| Pro Quarterly | Quarterly subscription | [填写] | [填写] |
| Pro Yearly | Yearly subscription | [填写] | [填写] |
| 60 Coins | One-time purchase | [填写] | [填写] |
| 300 Coins | One-time purchase | [填写] | [填写] |
| 680 Coins | One-time purchase | [填写] | [填写] |
| 1500 Coins | One-time purchase | [填写] | [填写] |
| 3500 Coins | One-time purchase | [填写] | [填写] |

Checkout success URL: [填写]

Checkout cancel URL: [填写]

Webhook endpoint: [填写，例如 https://api.example.com/api/v1/payments/webhook/creem]

We have completed test mode validation for checkout creation, success/cancel redirects, webhook signature verification, subscription activation/cancellation, and one-time coin purchase fulfillment. Our privacy policy, terms of service, refund/subscription disclosures, and customer support contact are publicly available at the URLs above.

Please let us know if you need any additional information for review.

Best regards,

[姓名]

[职位 / 团队]

## 审核备注

本报告是代码与文档静态审核结果，不包含真实 dashboard 配置核验。切换 live/product mode 前必须在 Creem dashboard、Render、Vercel 上逐项核对真实值，并保存 test mode 端到端验证证据。
