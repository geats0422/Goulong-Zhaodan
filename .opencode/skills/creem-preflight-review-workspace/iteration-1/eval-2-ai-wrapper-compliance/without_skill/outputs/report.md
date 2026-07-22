# AI 视频生成 Wrapper Creem Review 合规预检报告

审查日期：2026-05-18

审查范围：当前仓库公开页面、服务条款、隐私政策、定价/订阅管理、Creem 支付集成代码。未修改应用代码。

## 总体结论

当前仓库没有发现实际的 AI 视频生成 wrapper、Veo、Gemini、text-to-video、image-to-video 落地页或产品文案。现有公开页面仍主要描述 `Xi Rang` / `息壤学者` 这类 AI 学习游戏平台，相关文件包括 `frontend/src/pages/EasternFantasyLandingPage.vue`、`frontend/src/pages/DungeonScholarPricingPage.vue`、`frontend/src/pages/DungeonScholarFeaturesPage.vue` 和 `frontend/src/i18n/index.ts`。

如果准备提交 Creem account review 的是“AI 视频生成 wrapper，落地页写了 Veo/Gemini 能力”，则当前仓库证据不足，不能直接判定为可提交。按 Creem/MoR 审核视角，建议先补齐品牌归属、第三方模型免责声明、AUP/NSFW 禁止条款、内容审核机制说明、退款/取消路径和真实联系方式后再提交。

风险等级：高。

主要原因：当前可见条款没有覆盖 AI 视频生成高风险内容；没有 NSFW/成人内容/深伪/未成年人/暴力/仇恨/版权侵权等明确禁止项；没有 Moderation API 或等效审核流程证据；订阅取消路径存在但用户体验和条款描述不够完整；现有支持邮箱含 `support@xirang.local` 这类不可对外审核的占位域名。

## 证据摘要

已检查的关键文件：

- `frontend/src/i18n/index.ts`：落地页、定价、隐私政策、服务条款主要文案。
- `frontend/src/pages/EasternFantasyLandingPage.vue`：公开落地页结构。
- `frontend/src/pages/DungeonScholarPricingPage.vue`：定价、订阅和一次性 coin 购买入口。
- `frontend/src/pages/DungeonScholarTermsPage.vue`：服务条款页面。
- `frontend/src/pages/DungeonScholarPrivacyPolicyPage.vue`：隐私政策页面。
- `frontend/src/components/settings/SubscriptionManageModal.vue`：订阅管理与取消按钮。
- `frontend/src/pages/DungeonScholarSettingsPage.vue`：订阅状态读取、取消订阅调用。
- `frontend/src/api/payments.ts`：前端支付 API。
- `backend/app/api/v1/payments.py`：支付/订阅/Creem webhook 后端路由。
- `backend/app/services/payments/service.py`：checkout、地区定价、取消订阅服务逻辑。
- `backend/app/integrations/creem/client.py`：Creem API 客户端。
- `docs/designs/2026-05-15-creem-payment-integration-design.md`：Creem 集成设计说明。

搜索结果：

- 未发现 `Veo` / `veo` / `AI video` / `video generation` / `text to video` / `image to video` 等产品文案。
- 仅在 `backend/app/api/v1/settings.py` 的模型关键词中发现 `gemini`，不是公开落地页声明。
- 未发现 `NSFW`、`porn`、`adult`、`sexual`、`nude`、`self-harm`、`terror`、`acceptable use`、`AUP`、`OpenAI Moderation`、`omni-moderation` 等明确合规实现或条款文案。

## 分类评估

### 1. 命名与第三方品牌归属

状态：不通过，需补充。

当前仓库没有 Veo/Gemini 落地页，因此没有看到 Google/Veo/Gemini 品牌声明。但如果实际提交页面包含“Veo/Gemini 相关能力”，需要避免暗示官方合作、授权、转售或 Google 自营服务。

建议要求：

- 页面首屏或页脚明确写明：本产品是独立第三方工具，不隶属于、不由 Google、Gemini 或 Veo 官方赞助、认可或运营。
- 避免使用 `Official Veo`、`Google Veo platform`、`Gemini official API`、`powered by Google` 等可能误导审核的表述，除非有授权证明。
- 推荐用语：`uses third-party AI model providers, such as Google's Gemini/Veo where available`，并加 `availability may vary`。

### 2. AI 能力描述与免责声明

状态：部分通过，仅适用于当前学习产品；不覆盖 AI 视频生成。

当前已有 AI 生成内容免责：`frontend/src/i18n/index.ts` 中隐私政策和服务条款声明 AI 题目/解析可能不准确，仅供学习参考，不构成专业建议。

缺口：

- 免责对象是 quiz/questions/explanations，不是视频、图像、音频、人物肖像或生成媒体。
- 没有说明生成结果可能失败、延迟、排队、质量不稳定、第三方模型不可用、输出不保证唯一性或版权可商用性。
- 没有说明用户需对 prompt、上传素材、生成结果及其发布承担责任。

建议补充：

- AI 视频生成结果可能不准确、不完整、不符合预期或不可用。
- 不保证用户生成视频拥有可商用版权；用户需确保输入素材、人物肖像、商标、音乐、文本和输出用途合法。
- 模型能力、时长、分辨率、生成速度和可用地区可能随供应商变化。

### 3. NSFW / AUP / 禁止内容政策

状态：不通过。

当前服务条款只有泛化条款：不得传输 harmful/offensive/illegal content。该表述不足以覆盖 AI 视频生成高风险类别。

必须补齐的禁止项：

- 成人、色情、露骨性内容、性暗示未成年人、任何儿童性虐待材料。
- 非自愿亲密内容、deepfake 色情、未经同意的人脸替换或肖像滥用。
- 仇恨、骚扰、威胁、暴力极端主义、恐怖主义宣传。
- 血腥、虐待、自残、自杀指导、真实暴力美化。
- 违法活动指导、武器制造、毒品、诈骗、钓鱼、恶意软件。
- 侵犯版权、商标、隐私、肖像权或冒充他人的内容。
- 政治操纵、误导性公共事件、伪造证据或欺骗性媒体。

建议在公开页页脚链接新增 `Acceptable Use Policy`，并在生成页面提交按钮附近放置简短安全提示。

### 4. Moderation API / 内容审核机制

状态：不通过。

当前仓库未发现 Moderation API、审核队列、内容分类器、人工复核、举报入口、封禁策略或审核日志的实现证据。

AI 视频 wrapper 提交 Creem review 时，建议至少具备并能解释：

- 输入 prompt 审核：提交生成前拦截 NSFW、未成年人、暴力、仇恨、违法和侵权高风险 prompt。
- 上传素材审核：对图片/视频参考图进行安全检测，尤其是裸露、未成年人、人脸滥用和暴力血腥。
- 输出审核：对生成结果做供应商 safety signal 检查或抽样复核。
- 用户举报：对公开作品提供 report abuse 或 contact abuse 邮箱。
- 处置策略：违规拒绝生成、不退款滥用行为、暂停账号、保留必要日志。

如果使用 OpenAI Moderation 或 Google/Vertex safety filters，应在后台实现层面保留可审计日志，但不要在公开页夸大“100% safe”。

### 5. 禁售 / 高拒付风险

状态：高风险，需明确边界。

AI 视频生成容易被支付审核归入高风险数字内容，特别是 deepfake、成人内容、虚拟币/积分、不可退款数字商品和滥用素材生成。当前价格页还包含 coin packages，且文案写明 purchased coins non-refundable，这可能被审核关注。

当前证据：

- `frontend/src/i18n/index.ts` 定价 FAQ 写明 coin purchases are non-refundable。
- `frontend/src/config/pricing.ts` 包含 60、300、680、1500、3500 coins 的一次性购买包。
- Creem 设计文档说明同时支持代币充值和订阅。

建议：

- 若 AI 视频 wrapper 不需要虚拟币，优先去掉 coin 包或将其改为清晰的 `credits`，并说明 credit 与生成次数/额度对应关系、有效期和退款条件。
- 禁止成人/NSFW/deepfake 变现，不提供“绕过审核”“无限制生成”等卖点。
- 明确不销售受管制品、金融/医疗/法律建议、赌博、仿冒、黑灰产服务。
- 对一次性数字额度写清楚：未使用额度退款条件、已消耗额度不可退、滥用/违规不退款。

### 6. 订阅取消路径

状态：部分通过，仍需改善。

当前已有技术路径：

- 前端 `frontend/src/api/payments.ts` 提供 `cancelSubscription()`，调用 `/api/v1/payments/subscription/cancel`。
- 设置页 `frontend/src/pages/DungeonScholarSettingsPage.vue` 打开订阅管理弹窗并调用取消逻辑。
- 弹窗 `frontend/src/components/settings/SubscriptionManageModal.vue` 有 `data-testid="cancel-subscription"` 按钮。
- 后端 `backend/app/api/v1/payments.py` 暴露 `POST /payments/subscription/cancel`。
- 后端 `backend/app/services/payments/service.py` 调用 `client.cancel_subscription()` 并将用户状态置为 `canceled`。

缺口：

- 页面文案只说 “cancel anytime”，没有明确取消步骤：Settings -> Subscription Management -> Cancel Subscription。
- 后端取消后立即把本地状态设为 `canceled`，但设计文档写的是 scheduled cancel，条款也写 access continues until end of current billing period；实现和承诺可能不一致。
- 取消按钮没有二次确认、取消生效日期、剩余权益到期时间或 Creem portal 链接。
- 没有公开客服邮箱的可用支付支持地址；`support@xirang.local` 是占位域名，不适合提交审核。

建议：

- 定价页 FAQ、服务条款和设置页统一写明取消路径。
- 明确取消后是否保留权益至当前账期结束，并让后端状态/权限实现与文案一致。
- 增加确认弹窗、取消成功反馈、到期时间展示和账单支持联系方式。
- 如果 Creem 提供 Customer Portal，建议提供 portal 链接作为备选取消方式。

### 7. 隐私政策与第三方处理

状态：部分通过，但 AI 视频 wrapper 需重写。

当前隐私政策有第三方 AI 服务处理说明，列出 MiniMax/Kimi 等，并说明文档内容会被发送给 AI API。该政策不覆盖 Veo/Gemini，也不覆盖视频生成所需的参考图、人脸、上传视频、prompt、生成视频、公开分享链接、内容审核日志等。

建议补充：

- 第三方提供商：Google Gemini/Veo、云存储、CDN、支付服务、邮件服务、分析服务。
- 数据类型：prompt、上传图片/视频/音频、生成结果、用户反馈、审核标签、滥用日志。
- 保留期限：生成任务、输出文件、失败任务、审核记录和删除请求的保留规则。
- 用户删除：如何删除生成视频、素材和账号数据。

### 8. 联系方式、公司信息和审核可信度

状态：不通过。

当前问题：

- Help Center 文案含 `support@xirang.local`，不是可联系邮箱。
- 隐私政策公司统一社会信用代码仍为 “to be filled in”。
- 条款、隐私、产品名均是 `Xi Rang` 学习产品，不是 AI 视频 wrapper。

建议：

- 用真实域名邮箱，例如 `support@yourdomain.com`、`abuse@yourdomain.com`、`privacy@yourdomain.com`。
- 填写完整公司主体、注册地址或至少可核验的运营实体信息。
- 提交 Creem 前确保 checkout 产品名、落地页产品名、条款产品名、隐私政策产品名、账单描述一致。

## Creem 提交前最小修复清单

优先级 P0：

- 确认实际要审核的产品页面已在仓库或部署环境中，且产品名、定价、条款一致。
- 增加 AI 视频生成专用服务条款或 AUP，明确禁止 NSFW、deepfake、未成年人、暴力、仇恨、违法、侵权内容。
- 增加 Google/Veo/Gemini 非官方从属免责声明。
- 公开说明内容审核机制：输入审核、上传素材审核、输出审核/供应商 safety、举报与封禁。
- 替换 `support@xirang.local` 和 “Unified Social Credit Code to be filled in” 等占位内容。
- 统一订阅取消承诺和实现，公开写明取消路径与账期权益。

优先级 P1：

- 补充退款政策：订阅、试用、一次性 credits/coins、违规使用、生成失败场景。
- 补充隐私政策的数据类别：prompt、素材、输出视频、审核日志、第三方模型处理。
- 如果保留 credits/coins，说明额度消耗规则、有效期、退款边界，避免虚拟币式表述。
- 在生成页和上传页加入“仅上传你有权使用的素材”的提示。

优先级 P2：

- 增加 abuse/report 联系入口。
- 增加年龄限制，AI 视频建议至少 13+ 或 16+/18+，并明确未成年人限制。
- 增加服务可用性说明：模型地区限制、排队、失败重试、供应商变更。

## 建议提交用简短说明

可在 Creem review 中使用的产品描述草案：

> We provide an independent AI video generation workflow tool that helps users create videos from prompts and user-provided assets using third-party AI model providers where available. We are not affiliated with, endorsed by, or sponsored by Google, Gemini, or Veo. Users must only upload content they have rights to use. We prohibit NSFW, non-consensual intimate content, deepfake abuse, minor sexual content, hate, violence, illegal activities, and IP-infringing content. Prompts and uploaded assets are subject to automated safety checks and may be blocked or reviewed. Subscriptions can be cancelled from Settings > Subscription Management > Cancel Subscription, with access continuing until the end of the current billing period unless otherwise stated.

## 最终判断

不建议直接提交当前仓库状态进行“AI 视频生成 wrapper + Veo/Gemini 能力”的 Creem account review。当前代码和文案更像 AI 学习产品，且 AI 视频生成所需的 AUP、NSFW 禁止、moderation、第三方品牌免责声明、真实联系方式和订阅取消细节不足。建议完成 P0 清单后再提交。
