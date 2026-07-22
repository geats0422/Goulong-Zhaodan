---
name: creem-preflight-review
description: Use this skill for Creem go-live/account-review preflight checks before submitting a product for official Creem review or switching from test mode to live/product mode. Trigger whenever the user mentions Creem review, account review, payout account approval, product mode, live mode, payment approval, MoR compliance, landing page audit for Creem, or wants to improve Creem approval pass rate. It audits website/product/legal/support/payment readiness, flags blockers, proposes fixes, and drafts the Creem review or re-review message.
---

# Creem Preflight Review

Use this skill to reduce Creem account-review rejection risk before the user submits a store/product for official review. Treat it as a compliance and launch-readiness review, not as legal advice.

## Core behavior

1. Start by identifying what evidence is available: public URL, local repo, screenshots, product description, Creem product IDs, pricing pages, legal pages, support email, and whether the product is AI image/video generation.
2. If official requirements may have changed, fetch current Creem docs first. Prefer `https://docs.creem.io/merchant-of-record` and `https://docs.creem.io/llms.txt`.
3. Do not switch live/test mode, submit review, request re-review, send emails, or edit payment settings without explicit user approval.
4. Never print API keys, webhook secrets, dashboard tokens, database URLs, or `.env` contents. Check only whether required configuration keys exist when needed.
5. Produce an approval-risk report with evidence, blockers, fixes, and a ready-to-send review/re-review message.

## Review scope

Check these areas every time unless clearly irrelevant.

### 1. Product readiness

- Product is live enough for a reviewer to understand and use.
- Website is publicly accessible, not password-gated, not returning errors, and not only a waitlist unless the store is still in test mode.
- Product URL and Creem store/product information point to the same product.
- Product description is specific: what it does, who it is for, what is delivered, and how delivery/access works.
- Avoid vague claims like "we provide software" without product type, billing model, and customer value.

### 2. Truthfulness and marketing integrity

Creem is sensitive to deceptive content because it acts as Merchant of Record.

- No fake testimonials, fake reviews, fabricated user counts, fake revenue, fake logos, or unearned badges.
- Remove or mark unverifiable testimonials unless the site can show real permission and direct relevance to this product.
- Product Hunt, "as seen on", press, partner, or customer logos must be earned and verifiable.
- Claims about AI models, product capabilities, data sources, uptime, security, or compliance must match the actual implementation.
- Check every language version, not only the default locale.

### 3. Legal pages

- Privacy Policy exists, is accessible, and matches the product domain/brand.
- Terms of Service exists, is accessible, and matches the product domain/brand.
- For AI generation products, Terms or Acceptable Use Policy explicitly prohibit NSFW, sexually explicit, harmful, illegal, and abusive generation.
- Links should appear in footer and/or checkout-relevant pages.
- Legal pages should not be placeholders, empty pages, lorem ipsum, or copied text with wrong company/product names.

### 4. Pricing and checkout transparency

- Pricing is visible before checkout and matches Creem products.
- Billing type is clear: one-time, monthly, quarterly, yearly, usage-based, or credits.
- Subscription renewal/cancellation expectations are clear.
- Refund policy or support path is discoverable.
- Checkout success URL and failure/cancel handling exist if integrated in code.

### 5. Support and customer experience

- A reachable support email is visible on the public website and ideally inside the app dashboard.
- Support email should be branded when possible, such as `support@example.com`, not a random personal inbox.
- The support email in Creem Business Details should match or be consistent with the website.
- Subscription products need a direct cancellation path through the app or Creem Customer Portal.
- Customer requests should be answerable within 3 business days.

### 6. Links and social proof

- Footer, navigation, social links, docs links, app links, and legal links should work.
- Remove inactive Discord, empty Twitter/X, placeholder GitHub, dead docs, and broken community links.
- If a social account is not active or clearly tied to the product, omit it before review.

### 7. Prohibited and restricted products

Flag likely blockers if the product involves any prohibited or high-risk area.

- Pornographic/NSFW content, including AI-generated NSFW and NSFW chatbots.
- Face swap, deepfake, or face manipulation.
- IPTV, third-party content downloaders/rippers, spyware, illegal goods, gambling, weapons, drugs, tobacco/vaping, crypto/NFT assets, dating, MLM, homework/essay mills, PLR/MRR, marketplaces for other sellers, physical goods, in-game items tied to third-party games, donations without a real product, regulated services, or products without IP rights.
- Services such as consulting, marketing, design, job boards, or ads may require stricter due diligence.

### 8. AI wrapper and model compliance

Use this section for products that wrap or expose third-party AI models.

- Brand name and domain must not create confusion with model providers, such as Google, OpenAI, Anthropic, VEO, Gemini, Claude, or Midjourney.
- The product may say it is "powered by" or "integrates with" a model, but the product name should be independently branded.
- If marketing mentions model names, include a disclaimer that the product is independent and not affiliated with, endorsed by, or sponsored by the model provider.
- Feature claims must match the actual model/version used. Do not claim "Gemini 3.0" if the app uses "Gemini 2.5".
- Clearly disclose wrapper nature: the product provides a custom interface or workflow on top of underlying AI models.
- If users type prompts that generate AI images or videos, verify Creem Moderation API integration and an Acceptable Use Policy. This does not apply to pure text, audio/music, upscaling, background removal, translation, or non-generative processing.

### 9. Creem integration readiness

- Test mode should remain active until approval unless the user explicitly has approval and wants live rollout.
- Production API keys, webhook secrets, and product IDs should be stored in environment variables or platform dashboard secrets, never committed.
- Webhook signature verification should use the raw body and the Creem webhook secret.
- Webhook handlers should grant and revoke access for relevant events, especially subscription paid/trialing/expired/paused.
- Checkout metadata/reference IDs should map purchases to internal users.
- Customer Portal or Cancel Subscription API should be available for subscriptions.

## Audit workflow

1. Gather inputs. Ask for missing public URL, target product, and whether it is AI image/video generation if not obvious.
2. Inspect the codebase if available. Search for landing pages, footer links, pricing, legal pages, support email, Creem integration, checkout, webhooks, and subscription cancellation.
3. Inspect public URLs if provided. Check accessibility, content accuracy, legal links, pricing visibility, footer links, and social links.
4. Compare public claims against implementation and Creem product configuration evidence available in the repo.
5. Classify findings using the risk scale below.
6. If the user asks for fixes, make minimal code/content changes and verify them. Otherwise, provide a precise action plan.
7. Draft the review submission or re-review response only after the audit findings are clear.

## Risk scale

- `BLOCKER`: Likely rejection or suspension risk. Fix before submitting.
- `HIGH`: Material review risk. Strongly recommended before submitting.
- `MEDIUM`: Could slow approval or trigger questions.
- `LOW`: Polish or clarity improvement.
- `PASS`: Evidence looks compliant.
- `UNKNOWN`: Evidence unavailable; ask user or mark as manual check.

## Report format

Use this structure for final reports:

```markdown
## Creem 审核预检结论
- 总体状态: Ready / Not Ready / Needs Manual Confirmation
- 建议动作: Submit / Fix blockers first / Stay in test mode / Contact Creem support first
- 最大风险: [1-3 bullets]

## 阻塞项
| 风险 | 位置 | 证据 | 为什么影响 Creem 审核 | 修复建议 |
|---|---|---|---|---|

## Checklist
| 项目 | 状态 | 证据 | 下一步 |
|---|---|---|---|

## 修复任务
1. [具体文件/页面/设置] - [要改什么] - [验证方式]

## 提交/复审说明草稿
[正式、简洁、逐条说明准备情况或已修复内容]

## 仍需人工确认
- [无法从代码或网页确认的事项]
```

## Re-review reply template

Use this when Creem requested changes:

```text
Dear Creem Team,

Thank you for the review. We have addressed the requested changes:

1. Content compliance: [removed/updated testimonials, badges, claims, or unsupported marketing copy].
2. Contact channels: [removed inactive links and confirmed reachable support email].
3. Product accuracy: [corrected product descriptions, model/version claims, pricing, and legal pages].
4. Customer experience: [confirmed Privacy Policy, Terms of Service, pricing, support, and subscription cancellation path].

We will remain in test mode until the account review is approved.

Store ID: [store id if available]
Product URL: [url]

Best regards,
[name]
```

## Practical checks

When working in a repo, useful searches include:

- `Creem`, `CREEM_`, `checkout`, `webhook`, `subscription`, `portal`, `cancel`
- `Privacy`, `Terms`, `Refund`, `support@`, `mailto:`
- `testimonial`, `review`, `Product Hunt`, `badge`, `as seen`, `users`, `customers`
- model names such as `Gemini`, `VEO`, `Claude`, `OpenAI`, `GPT`, `Midjourney`, `Stable Diffusion`

When checking URLs, prefer safe read-only requests. Do not crawl aggressively. For dead-link checks, include status code and final URL evidence when available.

## Escalation guidance

Recommend contacting `support@creem.io` before submission when the product is near a prohibited/restricted category, has complex AI generation features, uses third-party IP, or has ambiguous service/marketplace behavior.
