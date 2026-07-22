## Creem 审核预检结论
- 总体状态: Not Ready
- 建议动作: Fix blockers first / Stay in test mode
- 最大风险: 公开网站存在 `#` 社交占位链接，容易触发 Creem 对无效链接/虚假社区入口的审核问题。
- 最大风险: 支持邮箱使用个人邮箱或 `.local` 占位邮箱，未满足 Creem 推荐的品牌化、公开且一致的支持邮箱要求。
- 最大风险: 前端展示价格、后端区域价格、Creem 产品配置无法从仓库确认一致；切 live 前必须逐项对齐 Creem dashboard 产品。

## 审核依据
- Skill: `D:\work\Huanyu Code\Project\Xirang\.opencode\skills\creem-preflight-review\SKILL.md`
- Creem 当前文档: `https://docs.creem.io/merchant-of-record`，已确认账号审核要求包括产品 live、无虚假信息、隐私政策与服务条款可访问、产品清晰、价格可见、支持邮箱、订阅可取消、AI 图片/视频生成需 Moderation API。
- 仓库范围: 前端 `frontend/`，后端 `backend/`；未读取真实 `.env`，未打印任何密钥或 webhook secret。
- 限制: 未提供公网 URL、Creem Store ID、Creem dashboard 产品配置、Business Details 支持邮箱，因此公网可访问性和 dashboard 一致性为人工确认项。

## 阻塞项
| 风险 | 位置 | 证据 | 为什么影响 Creem 审核 | 修复建议 |
|---|---|---|---|---|
| BLOCKER | `frontend/src/pages/EasternFantasyLandingPage.vue:107-116`、`frontend/src/pages/DungeonScholarPricingPage.vue:95-103` | Footer 包含 Twitter、Discord，`href: "#"` | Creem 文档将无效社交/社区链接列为常见风险；空链接会让审核员认为站点未完成或存在虚假社区入口 | 上线前删除 Twitter/Discord 占位项，或替换为真实、活跃且与产品一致的账号链接；同时处理 nav 的 `/community`，避免跳转到不存在路由 |
| BLOCKER | `frontend/src/pages/DungeonScholarPrivacyPolicyPage.vue:145-147`、`frontend/src/pages/DungeonScholarTermsPage.vue:210-216`、`frontend/src/pages/DungeonScholarHelpCenterPage.vue:222-231`、`frontend/src/i18n/index.ts:433/1749/2902/3979/5386` | 法务/帮助页面显示 `huanyugezhishe@hotmail.com`，多语言短隐私文案显示 `support@xirang.local` | Creem 要求公开网站和 dashboard 中有可达支持邮箱，且建议使用品牌化邮箱；`.local` 明显是占位，个人邮箱与品牌/Business Details 不一致会导致返修 | 统一为品牌化邮箱，如 `support@<正式域名>`；更新隐私、条款、帮助中心、设置页、所有 locale 文案，并确保 Creem Business Details/receipt 支持邮箱一致 |
| BLOCKER | `frontend/src/config/pricing.ts:17-39`、`backend/app/services/payments/service.py:17-21`、`backend/app/services/payments/service.py:63-77` | 前端订阅展示 `$8/$20/$70` 与 coin `$6/$30/$68/$120/$245`；后端区域价存在 premium `$9.6/$24/$84`、standard `$8/$20/$70`、developing `$4/$10/$35`；Creem product IDs 只通过环境变量配置 | Creem 要求 checkout 前价格清晰且与产品一致；区域价、前端价和 Creem dashboard 实际价格若不一致，审核员/用户会看到不同金额 | 在 Creem dashboard 中为 monthly/quarterly/yearly 与 coin 包逐一核对价格、币种、周期；若使用区域价，应在 pricing 页说明区域定价或移除未展示的区域倍率；保存一份上线核对表 |
| HIGH | `backend/app/services/payments/service.py:55-59`、`backend/app/core/config.py:108-109` | Checkout payload 只传 `success_url`，未传 `cancel_url`；配置中 `creem_checkout_cancel_url` 存在但未使用 | Creem 审核关注 checkout success/failure/cancel 体验；未传 cancel URL 可能导致取消后用户体验不可控 | 在 checkout payload 中传递 `cancel_url` 或确认 Creem dashboard 已配置取消跳转；上线前用 test mode 实测成功、取消、失败路径 |
| HIGH | `backend/app/services/payments/webhook_handler.py:79-86` | webhook 处理 `subscription.paid/active/trialing/canceled/expired/past_due`，未看到 `subscription.paused` 或 payment failure 事件处理 | Creem 技能要求 webhook 应 grant/revoke access for subscription paid/trialing/expired/paused；暂停/失败状态不处理可能导致订阅权益不准确 | 对照 Creem 当前 webhook 事件名补齐 paused/unpaid/payment_failed 等状态映射，或确认 Creem 不会发送这些事件；增加测试覆盖 |

## Checklist
| 项目 | 状态 | 证据 | 下一步 |
|---|---|---|---|
| 产品可理解 | PASS | 落地页 hero/feature 文案存在，`EasternFantasyLandingPage.vue:426-449`；功能卡说明在 `EasternFantasyLandingPage.vue:82-104` | 人工确认公网域名可访问且无需登录即可看到产品说明 |
| 产品 live/生产可用 | UNKNOWN | 公共路由含 landing/pricing/legal，`frontend/src/main.ts:12-21`；未提供公网 URL | 部署后用无痕窗口访问正式域名，确认不是密码保护、不是 5xx、不是仅 waitlist |
| Pricing 可见 | PASS | `/pricing` 公开，`frontend/src/main.ts:20`；价格卡与 coin 包显示在 `DungeonScholarPricingPage.vue:409-567` | 与 Creem dashboard 产品价格逐项核对 |
| 订阅续费/取消说明 | MEDIUM | FAQ 显示可随时取消，i18n `pricing.faq1Answer`；设置页有订阅管理入口 `SettingsSupportPanel.vue:24-33`；API 有 `/subscription/cancel` `backend/app/api/v1/payments.py:72-77` | 确认登录后取消路径对真实 Creem live subscription 可用，并补充“续费周期/取消后权益到期”说明 |
| Refund policy | MEDIUM | Terms 写明 case-by-case refund，`frontend/src/i18n/index.ts:768`；pricing FAQ 写 coin non-refundable，`frontend/src/i18n/index.ts:1320-1321` | 将退款/支持路径在 pricing 或 footer 更直接暴露，避免审核员找不到 |
| Privacy Policy | HIGH | `/privacy-policy` 公开，`router/index.ts:115-118`；页面有公司与联系邮箱，`DungeonScholarPrivacyPolicyPage.vue:136-148` | 替换占位/个人邮箱，确认公司统一社会信用代码不再显示“to be filled in”类占位文案 |
| Terms of Service | PASS | `/terms-of-service` 公开，`router/index.ts:135-138`；订阅/取消/退款条款存在，`DungeonScholarTermsPage.vue:177-184` | 如产品支持用户上传内容和 AI 生成，补强可接受使用条款 |
| 支持邮箱 | BLOCKER | `huanyugezhishe@hotmail.com` 与 `support@xirang.local` 同时存在 | 统一品牌化邮箱并与 Creem Business Details 保持一致 |
| Footer/legal links | HIGH | privacy/terms/help links存在；Twitter/Discord 为 `#`；nav 包含 `ROUTES.community` 但 router 未定义 community 路由，`constants/routes.ts:24`、`router/index.ts:155-156` fallback | 删除或修复占位/死链；检查所有语言版本 |
| 虚假背书/评价 | PASS | 未发现 Product Hunt、as seen、testimonial、虚假客户 logo；“scholars joined”是文案变量而非明确人数 | 若上线页面后新增评价/Logo，保留授权证据或先移除 |
| 禁止/限制产品 | PASS | 产品是学习型 SaaS/文档解析/游戏化学习；未发现 NSFW、deepfake、face-swap、IPTV、crypto、dating 等营销词 | 人工确认用户上传资料不用于第三方内容下载/侵权分发 |
| AI wrapper 合规 | MEDIUM | 使用 OpenAI-compatible LLM，`backend/app/integrations/agents/client.py`；设置页展示 GPT-4o/GPT-4o Mini，`backend/app/api/v1/settings.py:180-189`；未发现图片/视频生成 | 若营销页提及 OpenAI/GPT，增加“独立产品，非 OpenAI 关联/背书”免责声明；确认不是 AI 图片/视频生成，无需 Creem Moderation API |
| Creem API 密钥 | UNKNOWN | 配置项存在于 `backend/app/core/config.py:97-109`，产品 ID 通过环境变量配置；未读取真实 `.env` | live 环境设置 production API key、webhook secret、8 个 product IDs；不要提交密钥 |
| Creem test/live mode | UNKNOWN | `CreemApiClient` 检测 `creem_test_` 自动使用 test API，`backend/app/integrations/creem/client.py:19-24` | 审核前保持 test mode；获批后再切 live key 和 live product IDs |
| Webhook 签名 | PASS | raw body + HMAC SHA256，`backend/app/api/v1/payments.py:113-119`、`webhook_handler.py:31-36`；测试覆盖 invalid/valid signature | 对照 Creem 官方签名算法确认 header/签名格式是否完全一致 |
| Checkout metadata/reference | PASS | checkout metadata 包含 `user_id`、`pricing_region`、`product_type`、`plan`，`backend/app/services/payments/service.py:55-59` | 若 Creem 支持独立 `reference_id` 字段，可同步传递，便于 dashboard 排查 |
| Customer Portal/取消 | MEDIUM | 当前用 Cancel Subscription API，`backend/app/services/payments/service.py:104-113` | 确认 Creem API endpoint 与 live 权限可用；如使用 Portal，补充跳转入口 |

## 修复任务
1. `frontend/src/pages/EasternFantasyLandingPage.vue` 和 `frontend/src/pages/DungeonScholarPricingPage.vue` - 删除 `href: "#"` 的 Twitter/Discord footer 项，或替换为真实活跃账号；同时删除/修复 `/community` 导航 - 验证方式: 本地打开 landing/pricing，点击 footer/nav 无死链。
2. `frontend/src/i18n/index.ts`、`DungeonScholarPrivacyPolicyPage.vue`、`DungeonScholarTermsPage.vue`、`DungeonScholarHelpCenterPage.vue`、设置页相关文案 - 将 `support@xirang.local` 和 `huanyugezhishe@hotmail.com` 统一替换为正式品牌支持邮箱 - 验证方式: 全仓搜索不再出现 `.local` 支持邮箱，所有公开 legal/support 页面显示同一邮箱。
3. Creem dashboard + `frontend/src/config/pricing.ts` + `backend/app/services/payments/service.py` - 核对 monthly/quarterly/yearly 和 coin pack 价格、币种、周期、产品 ID；决定是否展示区域定价 - 验证方式: test mode 创建每个 checkout，checkout 页面金额与 pricing 页一致。
4. `backend/app/services/payments/service.py` - 在 checkout payload 中接入取消跳转 URL，或记录 dashboard 已配置 cancel URL 的证据 - 验证方式: test mode 点击取消后返回 `/pricing` 或指定失败页。
5. `backend/app/services/payments/webhook_handler.py` 和对应 tests - 对照 Creem live webhook 事件补齐 subscription paused/unpaid/payment_failed 等状态处理 - 验证方式: pytest 覆盖 paused/expired/canceled/past_due/paid 的权益变更。
6. Legal 内容 - 确认 Privacy Policy 中公司信息不含 “to be filled in” 占位，Terms/AUP 对用户上传、AI 生成题目、违法/侵权/滥用内容有明确限制 - 验证方式: 公开页面无占位文本，条款能说明服务边界。
7. 上线环境 - 配置 live `CREEM_API_KEY`、`CREEM_WEBHOOK_SECRET`、全部 `CREEM_PRODUCT_*`、正式 success/cancel URLs、Creem webhook URL `/api/v1/payments/webhook/creem` - 验证方式: 不读取/打印密钥，仅在平台确认变量存在并完成 test/live smoke。

## 提交审核邮件草稿
Subject: Creem account review request for Xi Rang

Dear Creem Team,

We are preparing to switch Xi Rang to live mode and would like to submit our store for account review.

Product summary: Xi Rang is a SaaS learning product that lets users upload learning materials, generate study quests, review mistakes, and use game-like learning modes. We sell digital SaaS subscriptions and optional in-app coin packages fulfilled inside the product.

Public product URL: [正式产品 URL]
Pricing URL: [正式产品 URL]/pricing
Privacy Policy: [正式产品 URL]/privacy-policy
Terms of Service: [正式产品 URL]/terms-of-service
Support email: support@[正式域名]
Store ID: [Creem Store ID]

Pre-review confirmations:

1. The product website, pricing page, Privacy Policy, Terms of Service, and support page are publicly accessible.
2. Pricing is shown before checkout and matches the Creem products configured in the dashboard.
3. Users can manage or cancel subscriptions from inside the product.
4. Checkout metadata maps purchases to internal users, and webhook handling grants or revokes access for subscription events.
5. The website does not use fake testimonials, unearned badges, or inflated user/customer counts.
6. Xi Rang is an independent SaaS product. It may use third-party AI/LLM providers for learning assistance, but it is not affiliated with, endorsed by, or sponsored by those providers.
7. The product does not provide AI image/video generation, NSFW generation, face-swap, deepfake, IPTV, crypto/NFT, gambling, dating, or other prohibited products.

We will remain in test mode until the account review is approved. Please let us know if you need any additional information.

Best regards,
[Name]
[Role / Company]

## 仍需人工确认
- 正式公网 URL 是否可访问、无密码保护、无 4xx/5xx、移动端可正常加载。
- Creem Store ID、Product IDs、dashboard 产品名称、价格、币种、周期是否与 `/pricing` 完全一致。
- Creem Business Details 中的 support email 是否与网站展示邮箱一致，并会显示在 receipt 上。
- live 环境变量是否已在部署平台配置，尤其是 `CREEM_API_KEY`、`CREEM_WEBHOOK_SECRET`、`CREEM_PRODUCT_COIN_60/300/680/1500/3500`、`CREEM_PRODUCT_SUB_MONTHLY/QUARTERLY/YEARLY`、正式 success/cancel URLs。
- Creem webhook endpoint 是否已在 dashboard 配置为 `https://<api-domain>/api/v1/payments/webhook/creem`，并订阅了 payment/checkout/subscription 相关事件。
- 是否确认产品不属于 AI 图片/视频生成；如果未来加入 prompt-to-image/video，必须先接入 Creem Moderation API，并在 Terms/AUP 明确禁止 NSFW、sexually explicit、harmful、illegal 和 abusive generation。
- 是否确认公司主体、隐私政策中的公司注册信息、域名所有权和 Creem 申请主体一致。
