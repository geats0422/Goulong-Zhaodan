# Creem Rejection Triage Report

Date: 2026-05-18
Scope: repository-only review, no application code changes made.

## Executive Summary

Creem's rejection reason, "misleading information and links not working", is consistent with several issues in the current frontend marketing surface.

Highest-risk findings:

1. Footer social links are broken placeholders: `Twitter` and `Discord` use `href="#"` on landing, features, and pricing pages.
2. The marketing nav includes `Community` at `/community`, but the router does not define a `/community` page; it falls through to the catch-all redirect back to `/`.
3. Marketing copy contains unverifiable scale claims: `Join 10,000+ Scholars`, `Join thousands of scholars`, and `Scholars joined this week` without a visible metric or proof.
4. Pricing FAQ says the product accepts `WeChat Pay, Alipay, credit cards, and more`, while Creem's public docs currently describe cards, PayPal, Apple Pay, Google Pay, and local methods, with WeChat Pay and Alipay "coming soon". This is likely misleading for a Creem review.
5. Non-English landing pages are inconsistent with English/Chinese: several locales still describe only PDFs, use old `Dungeon Scholar` branding, and show `© 2023`, while English/Chinese use `Xi Rang`, `© 2026`, and broader file format support.
6. Product Hunt badge and testimonials were not found in the repo. If they exist on production via CMS/manual HTML, they should be removed unless verified; if not present, Creem can be told they are not displayed.

Recommended re-review posture: do not ask Creem to re-review until the broken links and misleading claims are fixed or removed in production. The email draft below assumes fixes have been deployed; update the deployment URL and specific social/GitHub URLs before sending.

## Official Review Lens Used

Creem is acting as Merchant of Record, so public product pages should be safe for checkout review:

1. No fake or unverifiable social proof, badges, logos, user counts, testimonials, or launch claims.
2. All public links used in headers, footers, legal pages, contact pages, and pricing flows should work and should not be `#` placeholders.
3. Product, pricing, payment methods, refunds, subscriptions, and support statements should match what the app and Creem checkout actually support.
4. All localized pages should describe the same product, brand, supported formats, legal/contact routes, and billing terms.
5. Privacy Policy, Terms of Service, Help/Contact, and pricing should be reachable without login.

## Findings

### P0 - Broken Footer Social Links

Status: confirmed.

Evidence:

1. `frontend/src/pages/EasternFantasyLandingPage.vue:107-116` footer links include `Twitter` and `Discord` with `href: "#"`.
2. `frontend/src/pages/DungeonScholarFeaturesPage.vue:121-129` repeats the same placeholder links.
3. `frontend/src/pages/DungeonScholarPricingPage.vue:95-103` repeats the same placeholder links.

Impact:

Creem reviewers can click these from the public marketing/pricing pages and observe non-working links. This directly matches the rejection reason.

Required fix before re-review:

Replace placeholders with real public URLs, or remove those social links entirely until official accounts exist. Include GitHub only if there is a real public repository or organization page intended for customers.

Suggested acceptance criteria:

1. No marketing footer link uses `href="#"`.
2. Twitter/X, Discord, and GitHub either point to real public pages or are absent.
3. Links open successfully in production and do not require a private invite unless clearly labeled.

### P0 - `/community` Nav Link Has No Route

Status: confirmed.

Evidence:

1. `frontend/src/constants/routes.ts:24` defines `community: "/community"`.
2. `frontend/src/pages/EasternFantasyLandingPage.vue:71-80`, `DungeonScholarFeaturesPage.vue:69-77`, and `DungeonScholarPricingPage.vue:85-93` include `Community` in the top nav.
3. `frontend/src/router/index.ts:145-153` defines `/features` and `/pricing`, but no `/community` route.
4. `frontend/src/router/index.ts:155-157` redirects unknown routes to `/`, so `/community` will not load a community page.

Impact:

This is another public broken link. It may look like a working route in the UI, but it silently redirects to the landing page.

Required fix before re-review:

Either add a real community page or remove the nav item until the page exists.

### P0 - Payment Method Claim Likely Conflicts With Creem

Status: confirmed in repository copy; needs business confirmation.

Evidence:

1. `frontend/src/i18n/index.ts:1322-1323` English pricing FAQ says: `We accept WeChat Pay, Alipay, credit cards, and more to serve users worldwide.`
2. Creem public docs fetched during review say payment methods include cards, PayPal, Apple Pay, Google Pay, and local payment methods based on customer location; WeChat Pay and Alipay are described as coming soon.

Impact:

If checkout is through Creem, advertising WeChat Pay and Alipay before Creem supports them is misleading. It can also trigger payment-method mismatch in underwriting review.

Required fix before re-review:

Make FAQ match actual production checkout methods. Suggested neutral copy: `We accept the payment methods available in Creem Checkout for your region, including major cards and supported local methods.`

### P1 - Unverified User Count / Social Proof Claims

Status: confirmed.

Evidence:

1. `frontend/src/i18n/index.ts:1231` says `Scholars joined this week`.
2. `frontend/src/i18n/index.ts:1240` says `Join 10,000+ Scholars`.
3. `frontend/src/i18n/index.ts:1276` says `Join thousands of scholars who have already discovered the joy of gamified learning.`
4. `frontend/src/i18n/index.ts:1326` says `Join thousands of scholars making learning fun with gamification.`
5. Chinese and Traditional Chinese repeat the `10,000+` claim at `frontend/src/i18n/index.ts:2555` and `frontend/src/i18n/index.ts:3579`.
6. Korean locales repeat `10,000+` at `frontend/src/i18n/index.ts:6205` and `frontend/src/i18n/index.ts:6717`.

Impact:

These are testimonial-adjacent social proof claims. Without a visible source or real analytics backing, they can be considered misleading.

Required fix before re-review:

Remove or soften all unverifiable scale claims. Suggested copy: `Start learning with Xi Rang` or `Join the open beta`.

### P1 - Testimonials Not Found, But Social Proof Still Exists

Status: no testimonial components or testimonial strings found in current repo.

Evidence:

1. Repo search for `testimonial`, `Testimonials`, `quote`, and related marketing terms did not identify a testimonial section on the marketing pages.
2. The closest risk is the user-count/social-proof copy above.

Impact:

If Creem specifically mentioned testimonials, they may have seen production-only content, cached content, or interpreted `10,000+ Scholars` as a social proof claim.

Required fix before re-review:

Confirm production does not include CMS/manual testimonials. If testimonials exist outside this repo, remove them unless each quote is real, permissioned, and attributable.

### P1 - Product Hunt Badge Not Found

Status: no Product Hunt badge found in current repo.

Evidence:

1. Repo search for `Product Hunt`, `producthunt`, `badge`, and related variants found no Product Hunt badge implementation on marketing pages.

Impact:

If production shows a Product Hunt badge, it likely comes from a different deployment source or manual embed. A Product Hunt badge is misleading unless the product has a real Product Hunt listing and the badge points to it.

Required fix before re-review:

If no real Product Hunt listing exists, ensure production does not show the badge. If a listing exists, link the badge to the real listing.

### P1 - Localized Landing Pages Describe Different Product Capabilities

Status: confirmed.

Evidence:

1. English landing copy at `frontend/src/i18n/index.ts:1230` says Xi Rang supports `PPT, PDF, Word, Markdown, and TXT`.
2. Simplified Chinese at `frontend/src/i18n/index.ts:2545` and Traditional Chinese at `frontend/src/i18n/index.ts:3569` match the broader file support.
3. Italian at `frontend/src/i18n/index.ts:3762`, German at `frontend/src/i18n/index.ts:4275`, Russian at `frontend/src/i18n/index.ts:5682`, and Korean at `frontend/src/i18n/index.ts:6195` describe only PDFs on landing.
4. Several mode descriptions also say game modes are based on PDFs only, for example Italian `frontend/src/i18n/index.ts:3767`, German `frontend/src/i18n/index.ts:4280`, Russian `frontend/src/i18n/index.ts:5687`, and Korean `frontend/src/i18n/index.ts:6200`.
5. In-app upload support copy in multiple locales says `PDF, MD, TXT` only, for example English `frontend/src/i18n/index.ts:214-215`, German `frontend/src/i18n/index.ts:4316`, and Korean `frontend/src/i18n/index.ts:6236`.

Impact:

Reviewers switching languages may see inconsistent supported formats. If Word/PPT support is not actually available in production, English/Chinese overstate capabilities. If Word/PPT support is available, other locales understate capabilities and look stale.

Required fix before re-review:

Choose the true production-supported file list and align all locales and upload UI copy to it.

### P1 - Localized Branding Is Stale

Status: confirmed.

Evidence:

1. English footer brand is `Xi Rang` and copyright is `© 2026 Xi Rang` at `frontend/src/i18n/index.ts:1249-1250`.
2. Simplified/Traditional Chinese use `息壤` with `© 2026 Xi Rang` at `frontend/src/i18n/index.ts:2564-2565` and `frontend/src/i18n/index.ts:3588-3589`.
3. Italian, German, Portuguese, Spanish, Russian, Korean, and North Korean Korean still use `✧ Dungeon Scholar` and `© 2023 Dungeon Scholar`, for example `frontend/src/i18n/index.ts:3781-3782`, `4294-4295`, `4592-4593`, `4890-4891`, `5701-5702`, `6214-6215`, and `6726-6727`.

Impact:

This can make the site look like it is representing two different products or an old product identity, which is a misleading-information risk.

Required fix before re-review:

Standardize all locales to the current legal/product brand and current copyright year.

### P2 - Some Locale Navigation Keys Are Missing Or Inconsistent

Status: likely confirmed from landing object snippets.

Evidence:

1. English and Chinese landing objects define `home`, but Italian and German landing snippets start with `features`, `pricing`, and `community` and do not show `home` in the landing object.
2. The marketing pages call `t("landing.home")` for every locale.

Impact:

Depending on vue-i18n fallback behavior, non-English pages may show fallback English or raw key text. This is lower priority than broken links, but it contributes to inconsistent localized marketing pages.

Required fix before re-review:

Ensure every `SUPPORTED_LOCALES` landing object has the same key set.

## Re-Review Blockers Checklist

Do not send the re-review request until all items below are true in production:

1. `Twitter`, `Discord`, and `GitHub` links are either real working URLs or removed.
2. `/community` either serves a real page or is removed from nav.
3. Product Hunt badge is absent unless it links to a real Product Hunt listing.
4. Testimonials are absent unless real, permissioned, and attributable.
5. `10,000+`, `thousands of scholars`, and similar claims are removed or backed by visible evidence.
6. Pricing FAQ payment methods match actual Creem Checkout methods.
7. All locales use the same brand, year, product description, file support, and footer/legal links.
8. Public legal pages `/privacy-policy`, `/terms-of-service`, `/help-center`, `/features`, and `/pricing` are reachable without login.

## Suggested Fix Plan

1. Replace or remove social footer placeholders in all three marketing pages.
2. Remove `Community` from nav or implement `/community`.
3. Replace social proof claims with beta-safe wording.
4. Update pricing FAQ payment-method copy to match Creem-supported methods.
5. Normalize all `landing`, `features`, and `pricing` locale strings against English.
6. Verify the production deployment with a link checker and manual language switch pass.

## Re-Review Reply Draft

Subject: Re-review request for Xi Rang - misleading information and broken links fixed

Hi Creem team,

Thank you for reviewing Xi Rang and for flagging the issues around misleading information and non-working links.

We completed a full public-site compliance pass and updated the marketing pages to address the review feedback:

1. Removed or replaced placeholder footer links so Twitter/X, Discord, and GitHub no longer point to non-working `#` links.
2. Removed non-functional navigation links, including the community link until a public community page is available.
3. Removed unverifiable social-proof claims such as `10,000+ scholars`, `thousands of scholars`, Product Hunt-style badges, and any testimonial-style claims that were not independently verifiable.
4. Updated pricing and payment-method copy so it matches the payment methods actually available through Creem Checkout.
5. Aligned localized marketing pages so the product name, supported formats, footer branding, legal links, and subscription/pricing descriptions are consistent across languages.
6. Rechecked that Privacy Policy, Terms of Service, Help Center, Features, and Pricing pages are publicly reachable without login.

Production URL for re-review: [insert production URL]

We would appreciate a re-review when convenient. Please let us know if there are any remaining concerns or specific pages you would like us to adjust further.

Best regards,

Xi Rang team

## Notes For Sender

Before sending the draft:

1. Replace `[insert production URL]` with the deployed production URL.
2. Only keep the sentence about GitHub if a real public GitHub link exists or the GitHub footer item was removed.
3. Only say Product Hunt/testimonials were removed if production actually had them; otherwise use `confirmed there are no Product Hunt badges or testimonials displayed`.
4. Attach screenshots or a short Loom only if Creem asks for proof; the first re-review email can stay concise.
