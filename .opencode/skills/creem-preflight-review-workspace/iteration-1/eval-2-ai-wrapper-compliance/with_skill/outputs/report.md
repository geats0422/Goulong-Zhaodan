## Creem 审核预检结论
- 总体状态: Not Ready
- 建议动作: Fix blockers first / Stay in test mode
- 最大风险: 未在当前仓库发现 AI 视频生成/Veo/Gemini wrapper 的落地页与功能实现证据；AI 图像/视频生成产品按 Creem 当前文档必须接入 Creem Moderation API；现有法律/支持/取消订阅信息与 Creem 审核要求仍有明显缺口。

本报告基于本地仓库静态检查与 Creem 当前公开文档读取结果，不构成法律意见。未提供公网 URL、Creem Dashboard 产品配置、截图或真实生产环境，因此公网可访问性、Creem 后台支持邮箱、Store/Product ID、生产密钥配置状态需要人工确认。

## 阻塞项
| 风险 | 位置 | 证据 | 为什么影响 Creem 审核 | 修复建议 |
|---|---|---|---|---|
| BLOCKER | 产品/落地页定位 | `frontend/src/i18n/index.ts:1210-1250` 与 `frontend/src/pages/EasternFantasyLandingPage.vue:425-449` 显示产品为 `Xi Rang` 学习文档游戏化平台；仓库搜索未发现 `Veo`、`Gemini`、AI 视频生成、wrapper、not affiliated/endorsed/sponsored 等营销披露文案。 | 用户目标是 AI 视频生成 wrapper，但当前可审查网站与目标产品不一致。Creem 要求产品清晰可见、描述准确、不得造成消费者误导。 | 在提交前确保审核 URL 指向真实 AI 视频 wrapper 落地页，明确产品做什么、交付什么、如何访问、计费方式；如果此仓库不是待提交站点，需要提供正确仓库或公网 URL 重新审查。 |
| BLOCKER | Creem Moderation API | 全仓搜索 `moderation`/`CREEM_MODERATION` 未发现 Creem Moderation API 客户端、配置或调用；`backend/app/integrations/creem/client.py:28-35` 仅有 checkout/subscription/cancel；`backend/app/api/v1/payments.py:49-77` 仅处理支付和取消订阅。 | Creem 当前 MoR 文档明确：AI image/video generation products 必须集成 CREEM Moderation API，所有进入图像/视频生成模型的用户 prompt 都要先筛查；2026-05-01 起强制。 | 在视频生成请求进入 Veo/Gemini 等模型前调用 Creem Moderation API；拦截不合规 prompt；保存最小审计证据；在报告/复审说明中说明每个 prompt 都先经过 Moderation API。 |
| BLOCKER | Acceptable Use / NSFW 条款 | `frontend/src/i18n/index.ts:731-783` 的 Terms 仅泛泛禁止 harmful/offensive/illegal content，未明确禁止 NSFW、sexually explicit、sexually suggestive、pornographic、deepfake、face-swap、face manipulation、abusive/illegal generation；仓库未发现 AUP 页面。 | Creem 文档要求 AI 生成产品必须有可见 AUP，且 ToS 必须明确禁止 NSFW/explicit/sexually suggestive 内容；同时 Creem 禁售 AI-generated NSFW、deepfake、face-swap。 | 增加公开可访问的 Acceptable Use Policy；在 Terms 中明确禁止 NSFW/色情/性暗示/未成年人性内容/违法/仇恨/骚扰/自伤/暴力/侵权/深伪/换脸/人脸操纵等生成；页脚和 checkout 前路径可访问。 |
| HIGH | AI wrapper 命名与免责声明 | 当前品牌为独立 `Xi Rang`，未见 Veo/Gemini 作为产品名；但也未见 AI wrapper 独立免责声明。 | Creem 允许营销提及模型名，但如果使用 `Veo`/`Gemini`，必须说明产品独立，未获 Google/模型提供方关联、背书或赞助；产品名/域名不能造成商标混淆。 | 保持产品名独立，不要使用 `VEO3Studio`、`GeminiVideo` 等名称；若落地页出现 Veo/Gemini，添加醒目免责声明：平台是独立产品，不隶属、不受 Google/模型提供方背书或赞助，仅通过自定义界面接入相关模型。 |
| HIGH | 功能描述与模型版本准确性 | 当前代码仅显示 OpenAI-compatible LLM、NVIDIA、PageIndex、文档问答/题目生成；未发现 Veo/Gemini 视频生成实现。`backend/app/core/config.py:70-78` 显示 LLM 配置为 OpenAI-compatible/NVIDIA，未见 Veo/Gemini 视频生成配置。 | 如果落地页宣传 Veo/Gemini 视频生成但实现未接入或版本不一致，属于能力不实或模型版本虚假陈述，Creem 对 deceptive content 敏感。 | 只宣称已上线并可交付的模型/版本/限制；明确队列、时长、分辨率、额度、失败退款/重试规则；不要宣称 `Gemini 3.0`、`Veo 3` 等未实际使用版本。 |
| HIGH | 支持邮箱 | `frontend/src/i18n/index.ts:431-434` 设置页文案为 `support@xirang.local`；Terms/Privacy 联系邮箱为 `huanyugezhishe@hotmail.com`，见 `DungeonScholarTermsPage.vue:207-217`、`DungeonScholarPrivacyPolicyPage.vue:136-147`。 | Creem 要求公网网站和 Dashboard 中有可达支持邮箱，且建议使用品牌域名邮箱；`.local` 不可达，个人 Hotmail 与品牌不一致，可能触发 support email mismatch。 | 使用可收信的品牌邮箱，例如 `support@yourdomain.com`；统一落地页、Help Center、Terms、Privacy、Creem Business Details 和收据上的邮箱。 |
| HIGH | 页脚/社交链接 | `frontend/src/pages/EasternFantasyLandingPage.vue:107-116` 与 `DungeonScholarPricingPage.vue:95-103` 包含 Twitter/Discord `href: "#"`。 | Creem 文档要求移除无效社交/社区链接；死链或占位链接会降低审核可信度。 | 删除占位 Twitter/Discord，或替换为真实、活跃、与产品绑定的账号链接。 |
| MEDIUM | 订阅取消路径 | 后端存在 `POST /api/v1/payments/subscription/cancel`，见 `backend/app/api/v1/payments.py:72-77`；客户端 API 存在 `cancelSubscription`，见 `frontend/src/api/payments.ts:18-20`；设置弹窗有取消按钮，见 `SubscriptionManageModal.vue:177-186`。但弹窗 `currentPlan` 以 `subscriptionStatus === "active"` 判断，后端激活状态写为 `"pro"`，见 `backend/app/services/payments/webhook_handler.py:115`。 | Creem 要求订阅用户能直接在产品内取消；若状态值不一致导致 UI 不显示取消按钮，审核或用户体验会失败。 | 验证真实订阅用户在 Dashboard/Settings 中能看到取消按钮并成功调用 Creem Cancel Subscription API；统一前后端订阅状态值或改为兼容 `active/pro`。 |
| MEDIUM | Checkout 取消/失败回跳 | `backend/app/core/config.py:108-109` 定义了 `creem_checkout_success_url` 和 `creem_checkout_cancel_url`，但 `PaymentService.create_checkout` payload 只发送 `success_url`，见 `backend/app/services/payments/service.py:55-59`。 | Creem 预检关注 checkout success/failure/cancel handling；缺少 cancel URL 会让用户取消支付后的路径不清晰。 | 在 Creem checkout payload 中配置取消/失败 URL，并在 `/pricing` 或专门取消页显示下一步和支持入口。 |
| MEDIUM | 隐私政策第三方 AI 提供方不匹配 | Privacy 文案列出 MiniMax/Kimi 等 AI 服务，见 `frontend/src/i18n/index.ts:488-496`；当前代码配置显示 OpenAI-compatible/NVIDIA，见 `backend/app/core/config.py:70-78`；用户目标又提到 Veo/Gemini。 | 法律页面必须匹配真实产品和第三方处理者；AI wrapper 尤其需要披露 prompt/video 生成相关数据如何发送给模型提供方。 | 更新 Privacy：列出实际使用的 Google/Gemini/Veo 或其他提供方、处理的数据类型、用途、保留、训练使用限制、跨境传输与用户权利。 |
| LOW | 公开数字/社交证明 | `frontend/src/i18n/index.ts:1240` 写有 `Join 10,000+ Scholars`，`landing.scholarsJoined` 为 `Scholars joined this week`。 | Creem 明确禁止虚假用户数、假评论和未验证社交证明；如无证据，可能被认定为 inflated user count。 | 若无法证明真实用户数，删除或改为非数量化表达；不要使用 fake testimonials、Product Hunt/press/as seen badges。 |

## Checklist
| 项目 | 状态 | 证据 | 下一步 |
|---|---|---|---|
| 产品命名独立性 | UNKNOWN | 当前仓库品牌 `Xi Rang` 独立，未发现 Veo/Gemini 命名；但目标 AI 视频产品的实际品牌/域名未提供。 | 人工确认提交给 Creem 的产品名和域名不包含 Google/Veo/Gemini 等易混淆模型名。 |
| Veo/Gemini 免责声明 | BLOCKER | 未发现 `not affiliated`、`endorsed`、`sponsored`、wrapper disclosure。 | 在所有提及 Veo/Gemini 的页面附近加入独立产品免责声明。 |
| Wrapper 性质披露 | BLOCKER | 当前仓库未发现 AI 视频 wrapper 描述；现有产品描述是文档学习游戏。 | 明确写明“我们提供自定义工作流/界面，底层由第三方 AI 模型生成视频”。 |
| 功能描述准确性 | HIGH | 代码未发现 Veo/Gemini 视频生成实现；现有实现偏学习、文档、题目生成。 | 对照真实实现逐条删改能力声明，避免宣称未上线模型、分辨率、时长、无水印、商用授权等。 |
| NSFW/AUP | BLOCKER | Terms 未明确 NSFW/sexually explicit/deepfake/face-swap 禁止；无 AUP 页面证据。 | 新增 AUP 并链接到页脚、注册/checkout 前路径。 |
| Creem Moderation API | BLOCKER | 未发现 Moderation API 代码或配置。 | 在 prompt -> 视频生成模型前强制调用 Creem Moderation API。 |
| 禁售风险 | HIGH | AI 视频生成本身可接受，但若支持 NSFW、deepfake、face swap、第三方 IP 仿冒等会落入禁止列表；当前未见安全限制。 | 明确禁用 deepfake/face-swap/人脸操纵/色情/侵权角色或商标内容，UI 和后端均需限制。 |
| Pricing 可见性 | PASS / NEEDS MATCH | `DungeonScholarPricingPage.vue:345-499` 公开展示免费/Pro 月季年价格；`frontend/src/config/pricing.ts:17-39` 有订阅和金币价格。 | 确认这些价格与 Creem Dashboard 产品一致；AI 视频产品需展示视频额度、续费周期、超额规则。 |
| 订阅取消路径 | MEDIUM | 前后端有取消 API 和按钮，但状态值可能导致按钮不显示。 | 用真实订阅账号端到端验证取消路径；必要时接入 Creem Customer Portal。 |
| Legal pages | MEDIUM | Privacy/Terms 路由存在，见 `router/index.ts:110-137`；内容与 AI 视频产品不匹配。 | 更新为 AI 视频 wrapper 真实品牌、数据处理、AUP、退款、取消、支持邮箱。 |
| 支持邮箱 | HIGH | `support@xirang.local` 与 `huanyugezhishe@hotmail.com` 不一致且前者不可达。 | 统一为品牌域名支持邮箱。 |
| Creem webhook | PASS / NEEDS LIVE VERIFY | `backend/app/api/v1/payments.py:97-124` 使用 raw body 验签；`webhook_handler.py:31-36` HMAC 比较。 | 确认签名算法与 Creem 当前 webhook 规范完全一致，并在生产配置 webhook secret。 |
| Checkout metadata | PASS | `PaymentService.create_checkout` 写入 `user_id`、`pricing_region`、`product_type`、`plan`，见 `backend/app/services/payments/service.py:55-59`。 | 为 AI 视频产品增加额度/plan/product 明确映射。 |
| 公开 URL 可访问 | UNKNOWN | 未提供公网 URL。 | 提交前用无登录浏览器检查 landing/pricing/legal/support 均可访问。 |
| Creem 产品配置 | UNKNOWN | 未读取 Dashboard，且未读取 `.env`/密钥内容。 | 人工确认 Store/Product URL、支持邮箱、产品名、价格、Webhook URL 与网站一致。 |

## 修复任务
1. 公开落地页/产品文案 - 将提交 Creem 的 URL 改为真实 AI 视频 wrapper 页面，明确产品名、目标用户、交付内容、视频生成流程、模型限制、额度与计费周期 - 用无登录窗口访问并截图留证。
2. Veo/Gemini 合规文案 - 在所有提及模型处加入独立免责声明，避免产品名/域名/Logo 混淆 Google、Veo、Gemini - 搜索 `Veo|Gemini|Google` 验证每处都有上下文免责声明。
3. AUP/Terms - 新增或更新 Acceptable Use Policy 与 Terms，明确禁止 NSFW、色情、性暗示、违法、仇恨、骚扰、自伤、暴力、侵权、deepfake、face-swap、人脸操纵等 - 从页脚、注册/checkout 前路径可点击访问。
4. Creem Moderation API - 在每个文本 prompt 进入 AI 视频/图像生成模型前调用 Creem Moderation API，拒绝违规 prompt 并返回清晰提示 - 用合规/违规 prompt 做集成测试或手动测试留证。
5. 支持邮箱 - 替换 `support@xirang.local` 和个人邮箱为统一品牌支持邮箱，并同步 Creem Business Details - 发送测试邮件确认可收信。
6. 订阅取消路径 - 用真实订阅账号验证 Settings/Dashboard 中取消按钮可见并成功取消，修复 `active`/`pro` 状态不一致 - 记录取消前后状态和 Creem 订阅状态。
7. Checkout 取消路径 - 给 Creem checkout payload 增加取消/失败 URL 或 Customer Portal 路径 - 手动取消 checkout 验证能回到可理解页面。
8. 删除占位链接和不可证实数字 - 删除 `href: "#"` 社交链接及无法证明的 `10,000+` 用户数 - 全站搜索占位链接和社交证明。
9. Privacy 更新 - 披露真实视频模型提供方、prompt/生成结果处理、保留、第三方传输、训练使用限制和用户删除权利 - 与实际后端配置和生产模型供应商逐项比对。

## 提交/复审说明草稿
Dear Creem Team,

We are preparing our AI video generation wrapper for account review. Before submission, we will remain in test mode and complete the following compliance items:

1. Product transparency: the public website will clearly describe the product as an independent AI video generation workflow/interface built on top of third-party models such as Veo/Gemini, with no affiliation, endorsement, or sponsorship by Google or the model providers.
2. Content safety: every user prompt routed to AI image/video generation will be screened through the Creem Moderation API before generation.
3. Acceptable use: our Terms and Acceptable Use Policy will explicitly prohibit NSFW, sexually explicit or suggestive content, illegal or abusive generation, deepfakes, face-swap, and face manipulation.
4. Customer experience: the website will include accessible Privacy Policy, Terms of Service, Acceptable Use Policy, pricing, a branded support email, and an in-product subscription cancellation path through the Creem cancellation flow or Customer Portal.
5. Product accuracy: our marketing will only claim model versions and features that are actually available in production, and our pricing will match the Creem product configuration.

We will submit for review only after these items are live and verified.

Product URL: [production URL]
Store ID: [store id]

Best regards,
[name]

## 仍需人工确认
- 提交给 Creem 的真实公网 URL、产品名、域名、Logo 和所有语言版本。
- 落地页实际是否已经包含 Veo/Gemini 文案；当前仓库未发现相关文案。
- Creem Dashboard 中的 Store ID、Product ID、产品名称、价格、支持邮箱、Webhook URL、Customer Portal/Cancel API 配置。
- 生产环境是否仍在 test mode，是否存在真实密钥、Webhook secret、Moderation API key 等平台密钥配置。
- AI 视频模型实际供应商、版本、能力限制、生成时长/分辨率、队列/失败处理、用户额度规则。
- 是否存在任何 gallery/showcase、示例 prompt 或 SEO 页面使用 `uncensored`、`unfiltered`、`NSFW`、`18+`、deepfake、face-swap 等高风险词。
- 是否有可证明的用户数、客户 Logo、评价、媒体徽章；无法证明的应在审核前删除。
