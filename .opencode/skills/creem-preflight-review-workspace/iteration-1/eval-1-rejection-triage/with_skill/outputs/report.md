## Creem 审核预检结论
- 总体状态: Not Ready
- 建议动作: Fix blockers first; Stay in test mode; 修完后再通过 Creem Dashboard 的 Request Re-Review 提交复审
- 最大风险: 页脚 Twitter/Discord 链接是 `#` 空链接，会直接命中 Creem “links not working” 拒审点
- 最大风险: 落地页多语言文案包含 `Join 10,000+ Scholars`、`Join thousands of scholars` 等未验证用户数量/社交证明，会命中 Creem “No false information / inflated user counts” 要求
- 最大风险: 导航包含 `Community` 指向 `/community`，但路由未注册该页面，实际会被 catch-all 重定向回首页，容易被审核员判定为无效或误导链接

## 官方审核依据
- Creem 官方 Account Reviews 文档要求产品网站不得包含 fake reviews、testimonials、inflated user/customer counts。
- Creem 官方文档明确列出常见拒审原因包括 false information、missing/broken website content、product not clear、support email mismatch。
- Creem 官方文档明确指出 unearned badges，例如 Product Hunt、As Seen On，会导致 rejected。
- Creem 官方 Customer Experience 要求 public website 和用户 dashboard 有可达 support email；订阅产品需要可取消路径。
- 本次审计只基于当前本地仓库和 Creem 官方文档；未提供 public URL、Store ID、线上截图或 Creem Dashboard 配置，线上状态仍需人工确认。

## 阻塞项
| 风险 | 位置 | 证据 | 为什么影响 Creem 审核 | 修复建议 |
|---|---|---|---|---|
| BLOCKER | `frontend/src/pages/EasternFantasyLandingPage.vue:107-116` | Footer links 中 Twitter、Discord 的 `href` 都是 `#` | Creem 明确要求 links should work；空链接会被视为 links not working | 删除 Twitter/Discord，或替换为真实、公开、活跃且与 Xi Rang 绑定的 URL |
| BLOCKER | `frontend/src/pages/DungeonScholarPricingPage.vue:95-103` | Pricing 页 footer Twitter、Discord 也是 `#` | 定价页是审核高频页面，失效社交链接会直接触发拒审 | 与落地页一致删除或替换真实链接 |
| BLOCKER | `frontend/src/pages/DungeonScholarFeaturesPage.vue:121-129` | Features 页 footer Twitter、Discord 也是 `#` | 所有公开营销页都需要链接一致可用 | 与落地页一致删除或替换真实链接 |
| HIGH | `frontend/src/constants/routes.ts:24`, `frontend/src/pages/EasternFantasyLandingPage.vue:71-80`, `frontend/src/pages/DungeonScholarPricingPage.vue:85-92` | 导航有 `Community` -> `/community`，但 `frontend/src/router/index.ts` 未注册 `ROUTES.community` | 审核员点击 Community 会被 catch-all 重定向首页，不是有效社区页面 | 删除 Community 导航，或实现真实社区页面/外链并验证可访问 |
| BLOCKER | `frontend/src/i18n/index.ts:1240`, `2555`, `3579`, `3772`, `4285`, `4583`, `4881`, `5179`, `5692`, `6205`, `6717` | 多语言 landing 文案均包含 `10,000+` 学者/用户数量 | Creem 明确禁止 inflated user/customer counts；如果无法证明真实数据，应视为误导 | 改成不可量化表述，如 “Join the beta” / “Start learning with Xi Rang” |
| HIGH | `frontend/src/i18n/index.ts:1276`, `1326`, `2591`, `2641`, `3615`, `3665` | 英文、简中、繁中 pricing/features CTA 中有 “thousands / 数千名” 类用户数量 | 与用户数/社交证明相关，若无证据会触发 misleading information | 全部替换为功能导向文案，避免数量承诺 |
| HIGH | `frontend/src/i18n/index.ts:433`, `1749`, `2902`, `3979`, `5386`, `5899`, `6412`, `6924` | Help Center/settings doc 文案使用 `support@xirang.local` | `.local` 不是真实可达支持邮箱；Creem 要求 visible reachable support email | 改为真实邮箱，并确保与 Creem Business Details 一致；建议使用品牌域名邮箱 |
| MEDIUM | `frontend/src/pages/DungeonScholarPrivacyPolicyPage.vue:146`, `516`; `DungeonScholarTermsPage.vue:212`; `DungeonScholarHelpCenterPage.vue:224` | 法务/帮助页面显示 `huanyugezhishe@hotmail.com`，与 `support@xirang.local` 不一致 | Creem 常见拒审原因之一是 support email mismatch | 统一 public website、app dashboard、Creem Business Details 的支持邮箱 |

## Checklist
| 项目 | 状态 | 证据 | 下一步 |
|---|---|---|---|
| Testimonials | PASS/UNKNOWN | 仓库搜索 `testimonial`、`Testimonials`、`review` 未发现公开营销 testimonial 模块；大量 `review` 是学习复习功能文案 | 如果线上/CMS/截图中有 testimonials，需删除或保留证明材料 |
| Product Hunt badge | PASS/UNKNOWN | 仓库搜索 `Product Hunt`、`producthunt`、`as seen` 未发现徽章或相关链接 | 如果线上有 Product Hunt badge，必须移除，除非已有可验证发布页 |
| Footer Twitter/Discord | BLOCKER | 三个公开营销页 footer 均含 `href: "#"` | 删除或替换真实活跃链接 |
| Footer GitHub | PASS | 公开营销页 footer 未发现 GitHub 社交链接；GitHub 仅用于 OAuth 登录文案 | 无需处理；如果线上 footer 有 GitHub，需验证仓库/组织真实可访问 |
| Community link | HIGH | 导航指向 `/community`，路由未注册 | 删除 Community 导航或补真实页面 |
| 多语言描述一致性 | HIGH | 11 个 landing locale 都有 `10,000+`；部分 locale 有 `thousands/数千`，部分没有完整 legal 内容 | 移除所有量化社交证明；补齐或隐藏未完成语言版本 |
| Pricing visibility | PASS/MEDIUM | `frontend/src/config/pricing.ts` 显示 monthly/quarterly/yearly Pro 与 coin packages；pricing 页面有 FAQ | 需确认 Creem Dashboard 产品价格与网站价格一致 |
| Legal pages | PASS/MEDIUM | `/privacy-policy`、`/terms-of-service` 路由已注册并有页面 | 多语言部分显示 “Full localized content coming soon”，复审前建议默认英文或补全本地化 |
| Subscription cancellation | PASS/UNKNOWN | `frontend/src/api/payments.ts:18-20` 有 cancel API；设置页有订阅管理文案 | 需人工确认用户 dashboard 可以实际取消订阅，且 Creem webhook/portal 在生产可用 |
| Support email | BLOCKER | 同时存在 `support@xirang.local` 和 `huanyugezhishe@hotmail.com` | 统一为真实可达支持邮箱，并同步 Creem Business Details |
| AI image/video moderation | PASS | 产品是文档转学习游戏，不是 AI image/video generation；未见图像/视频生成营销 | 若未来加入 AI 图像/视频生成功能，需要 Creem Moderation API 和 AUP |

## 多语言页面一致性复盘
| Locale | 落地页主要问题 | 定价/功能页主要问题 | 备注 |
|---|---|---|---|
| `en` | `Join 10,000+ Scholars`; “Scholars joined this week” 未展示真实计数 | `Join thousands...` | 需要删除量化用户数 |
| `zh-CN` | `加入 10,000+ 学者`; “本周新加入的学者” | `加入数千名...` | 需要删除量化用户数 |
| `zh-TW` | `加入 10,000+ 學者` | `加入數千名...` | 需要删除量化用户数 |
| `it` | `Unisciti a 10.000+ Scienziati` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `de` | `Treten Sie 10.000+ Gelehrten bei` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `pt` | `Junte-se a 10.000+ Estudantes` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `es` | `Únete a 10.000+ Eruditos` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `fr` | `Rejoignez 10.000+ Scholaires` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `ru` | `Присоединяйтесь к 10.000+ Учёным` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `ko-KR` | `10,000+ 학자와 함께하세요` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |
| `ko-KP` | `10,000+ 학자와 함께하시오` | 未在本次片段中确认完整 pricing CTA | 需要全局替换量化用户数 |

## 修复任务
1. `frontend/src/pages/EasternFantasyLandingPage.vue`, `DungeonScholarPricingPage.vue`, `DungeonScholarFeaturesPage.vue` - 删除 footer 中 Twitter/Discord 空链接，或替换成真实 URL - 验证页面底部不存在 `href="#"` 社交链接。
2. `frontend/src/pages/*Landing/Pricing/Features*` 和 `frontend/src/constants/routes.ts` - 删除 `Community` 导航，或新增真实 `/community` 路由页面 - 验证点击 Community 不会重定向首页。
3. `frontend/src/i18n/index.ts` - 将所有 `10,000+`、`thousands/数千/數千` 用户数量文案改为非量化表述 - 验证搜索 `10,000|10\.000|thousands|数千|數千` 无营销社交证明残留。
4. `frontend/src/i18n/index.ts`, `DungeonScholarPrivacyPolicyPage.vue`, `DungeonScholarTermsPage.vue`, `DungeonScholarHelpCenterPage.vue` - 统一为真实可达支持邮箱 - 验证 public site、app dashboard、Creem Business Details 三处一致。
5. 线上站点/CMS/部署配置 - 人工确认没有 Product Hunt badge、As Seen On、press logos、customer logos 或 testimonials - 需要保留截图或 URL 证据。
6. Creem Dashboard - 确认产品 URL、价格、支持邮箱、订阅取消路径与网站一致 - 复审前截图留档。

## 提交/复审说明草稿
Dear Creem Team,

Thank you for the review. We reviewed the site against your Merchant of Record account review requirements and addressed the issues around misleading information and non-working links.

1. Content compliance: We removed unsupported social-proof claims, including inflated user-count wording such as “10,000+ scholars” and “thousands of scholars.” We also confirmed that the site does not display fake testimonials, fake reviews, or an unearned Product Hunt badge.
2. Links and contact channels: We removed or corrected inactive footer social links, including placeholder Twitter/Discord links, and verified that public footer/legal/help links are accessible. We also aligned the visible support email with our Creem Business Details support contact.
3. Product accuracy: We reviewed the English and localized landing/pricing/features pages to keep the product description consistent: Xi Rang is a document-to-gamified-learning SaaS that turns user-uploaded learning materials into study modes, review loops, and progress rewards. We removed wording that could be interpreted as unsupported traction or misleading social proof.
4. Customer experience: We confirmed that Privacy Policy, Terms of Service, pricing, support, and subscription cancellation information are available from the public website and user dashboard.

We will remain in test mode until the account review is approved.

Store ID: [add Store ID]
Product URL: [add production URL]
Support email: [add support email]

Best regards,
[name]

## 仍需人工确认
- 当前任务未提供 public URL，因此无法用 HTTP 状态码验证线上页面和外链是否真实可访问。
- 当前任务未提供 Store ID、Creem Dashboard 产品配置或截图，因此无法确认网站价格与 Creem 产品价格完全一致。
- 当前仓库未发现 Product Hunt badge/testimonials；如果生产站、CMS、营销截图或第三方落地页中存在，需要同步移除或提供可验证证据。
- 需要确认真实支持邮箱可收信，并与 Creem Business Details 中的 support email 一致。
- 需要确认复审前线上部署已经包含上述内容修复；本报告没有修改应用代码。
