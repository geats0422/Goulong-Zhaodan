<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const toc = [
  ['account', '账号与使用资格'],
  ['content', '用户内容与授权'],
  ['ai', 'AI 输出与人工复核'],
  ['billing', '订阅与费用'],
  ['security', '安全与禁止行为'],
  ['liability', '责任限制'],
]

const sections = [
  {
    id: 'account',
    tag: '§ 01',
    title: '账号与使用资格',
    body: '您应提供真实、准确的注册信息，妥善保管账号凭证，并对注册年满 18 周岁作出确认。因账号共享、泄露或非授权使用产生的风险由账号持有人承担。如发现账号被盗用，请立即联系我们。',
  },
  {
    id: 'content',
    tag: '§ 02',
    title: '用户内容与授权',
    body: '您保留上传文件、材料包和业务数据的合法权益。为提供一致性与完整性审查、证据定位、报告导出等服务，您授权平台在必要范围内处理相关内容。审查完成后，文档处理方式（即焚或保留）由您自主选择。',
  },
  {
    id: 'ai',
    tag: '§ 03',
    title: 'AI 输出与人工复核',
    body: '本服务提供的一致性检查、完整性审查、问题清单和修改建议属于 AI 辅助输出，可能存在偏差或遗漏。AI 审查结果仅供参考，不构成正式法律或合规意见；正式提交前应由具备相应资质的人员进行人工复核。',
  },
  {
    id: 'billing',
    tag: '§ 04',
    title: '订阅与费用',
    body: '订阅套餐、额度包、计费与续费规则以页面展示或双方签署的协议为准。额度包一经购买永久有效、不过期。企业客户可根据合同约定启用专属部署或私有化服务。退款与争议以页面公示规则或协议约定处理。',
  },
  {
    id: 'security',
    tag: '§ 05',
    title: '安全与禁止行为',
    body: '您不得利用本服务上传违法或侵权内容、绕过访问控制、攻击或扰乱系统、批量抓取数据，或以任何方式侵犯第三方合法权益。我们有权对违反上述规定的行为限制或终止服务。',
  },
  {
    id: 'liability',
    tag: '§ 06',
    title: '责任限制',
    body: '在法律允许的范围内，平台不对因用户未复核 AI 输出、错误输入资料或超出授权范围使用服务而造成的直接或间接损失承担责任。本服务作为「提交前初审」辅助层，不替代正式的审批与合规决策。',
  },
]
</script>

<template>
  <MarketingShell>
    <main class="legal-page">
      <header class="legal-hero">
        <div class="container pricing-hero-inner">
          <div class="legal-hero-meta">
            <span class="legal-ref">REF.GL-LEGAL-TERMS</span>
            <span class="legal-update">最后更新 · 2026-07-01</span>
          </div>
          <div class="gold-rule"></div>
          <p class="eyebrow">TERMS OF SERVICE</p>
          <h1>服务条款</h1>
          <p class="lead">本条款说明您使用句龙·照胆时的账号、内容、AI 辅助输出、订阅与责任边界。使用本服务即表示您理解并同意遵守本条款。</p>
          <div class="legal-stamps">
            <span class="legal-stamp">账号合规</span>
            <span class="legal-stamp">AI 辅助说明</span>
            <span class="legal-stamp">内容责任</span>
            <span class="legal-stamp">服务连续性</span>
          </div>
        </div>
      </header>

      <nav class="legal-toc container" aria-label="目录">
        <div class="legal-toc-title">目录 / CONTENTS</div>
        <ol>
          <li v-for="(t, i) in toc" :key="t[0]">
            <a :href="`#${t[0]}`"><span class="legal-toc-num">{{ String(i + 1).padStart(2, '0') }}</span>{{ t[1] }}</a>
          </li>
        </ol>
      </nav>

      <article class="legal-article container">
        <section v-for="s in sections" :key="s.id" :id="s.id" class="legal-section">
          <div class="legal-section-tag">{{ s.tag }}</div>
          <h2>{{ s.title }}</h2>
          <p>{{ s.body }}</p>
        </section>

        <section class="legal-section legal-section-cta">
          <div class="legal-section-tag">§ 07</div>
          <h2>联系方式</h2>
          <p>如您对本条款有任何疑问，请通过以下方式联系我们：</p>
          <a href="mailto:business@goulong-ai.cn" class="legal-contact-card">
            <span class="material-symbols-outlined">mail</span>
            <span>business@goulong-ai.cn</span>
          </a>
        </section>
      </article>

      <div class="legal-back container">
        <a href="/about" class="legal-back-link">
          <span class="material-symbols-outlined">arrow_back</span>
          返回关于我们
        </a>
      </div>
    </main>
  </MarketingShell>
</template>

<style scoped>
.legal-page {
  padding-bottom: 72px;
}

.legal-hero {
  padding: 96px 0 48px;
  text-align: center;
}

.legal-hero-meta {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.legal-ref {
  color: var(--gold);
  font: 500 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-update {
  color: var(--muted);
  font: 500 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-hero h1 {
  margin: 12px 0;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(2.4rem, 5vw, 3.6rem);
}

.legal-stamps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.legal-stamp {
  padding: 6px 12px;
  border: 1px solid color-mix(in srgb, var(--gold) 30%, transparent);
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
}

.legal-toc {
  max-width: 880px;
  margin: 0 auto 48px;
  padding: 28px 32px;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface) 92%, transparent), color-mix(in srgb, var(--bg) 92%, transparent));
}

.legal-toc-title {
  margin-bottom: 16px;
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-toc ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 24px;
}

.legal-toc a {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.legal-toc a:hover {
  color: var(--gold);
}

.legal-toc-num {
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
}

.legal-article {
  max-width: 880px;
  margin: 0 auto;
}

.legal-section {
  position: relative;
  padding: 36px 0;
  border-top: 1px solid color-mix(in srgb, var(--gold) 16%, transparent);
}

.legal-section-tag {
  position: absolute;
  top: 36px;
  left: 0;
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-section h2 {
  margin: 0 0 18px;
  padding-left: 56px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.4rem, 2.4vw, 1.8rem);
}

.legal-section p {
  color: var(--muted);
  line-height: 1.85;
}

.legal-section-cta {
  text-align: center;
}

.legal-section-cta h2,
.legal-section-cta p {
  padding-left: 0;
}

.legal-contact-card {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 24px;
  border: 1px solid var(--gold);
  color: var(--gold);
  text-decoration: none;
  font: 600 14px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
  transition: background 0.2s;
}

.legal-contact-card:hover {
  background: color-mix(in srgb, var(--gold) 14%, transparent);
}

.legal-back {
  max-width: 880px;
  margin: 24px auto 0;
}

.legal-back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.legal-back-link:hover {
  color: var(--gold);
}

@media (max-width: 820px) {
  .legal-section-tag {
    position: static;
    margin-bottom: 8px;
  }

  .legal-section h2 {
    padding-left: 0;
  }

  .legal-toc ol {
    grid-template-columns: 1fr;
  }
}
</style>
