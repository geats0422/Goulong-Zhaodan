<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const principles = [
  {
    ref: 'REF.GL-P01',
    title: '安全静默',
    desc: 'TEE 保护、访问控制、审计留痕。合同审查过程降低敏感数据泄露风险，让业务经办人的初审没有后顾之忧。',
  },
  {
    ref: 'REF.GL-P02',
    title: '诚恳共创',
    desc: '产品刚刚起步，我们与首批用户一起打磨。每一份真实合同，都让照胆更贴近实际业务。',
  },
  {
    ref: 'REF.GL-P03',
    title: '赋能经办人',
    desc: '让初级经办人拥有资深合规专家的视角，在正式流转前完成低风险自检，把退回挡在流程外。',
  },
]

const matrix = [
  {
    ref: 'REF.GL-M01',
    name: '句龙 · 照胆',
    role: '提交前初审 Agent',
    desc: '在工程合同进入正式审批前，对合同条款做法规辅助审查，识别付款、工期、质量、安全、违约责任等条款风险并给出修改建议。',
    current: true,
  },
  {
    ref: 'REF.GL-M02',
    name: '句龙 · 文衡',
    role: '招投标与合同编写',
    desc: '从合同起草、招标文件生成到投标响应与资质匹配，覆盖工程文本「生成」侧，与照胆的「审查」互补，共同覆盖全生命周期。',
  },
]

const channels = [
  {
    ref: 'REF.GL-C01',
    icon: 'video_library',
    label: 'Bilibili',
    value: '@呼风唤雨的焕羽',
    href: 'https://space.bilibili.com/338267911?spm_id_from=333.1007.0.0',
  },
  {
    ref: 'REF.GL-C02',
    icon: 'code',
    label: 'GitHub',
    value: '@geats0422',
    href: 'https://github.com/geats0422',
  },
  {
    ref: 'REF.GL-C03',
    icon: 'mail',
    label: '商务洽谈',
    value: 'business@goulong-ai.cn',
    href: 'mailto:business@goulong-ai.cn',
  },
]
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section about-hero-section">
        <div class="container pricing-hero-inner">
          <nav class="case-breadcrumb" aria-label="面包屑">
            <a href="/">首页</a>
            <span>/</span>
            <span>关于我们</span>
          </nav>
          <div class="gold-rule"></div>
          <p class="eyebrow">ABOUT US</p>
          <h1>把合同初审做在正式提交之前</h1>
          <p class="lead">我们相信，每一次正式提交都不该被条款风险打回。句龙·照胆在合同正式审批前，对工程合同做法规辅助审查，让退回止步于流程之外。</p>
        </div>
      </header>

      <section class="about-origin-section">
        <div class="container">
          <article class="about-origin-card">
            <span class="corner corner-tl"></span>
            <span class="corner corner-br"></span>
            <p class="eyebrow">WHY WE BUILD</p>
            <h2>为什么做照胆</h2>
            <p>我们亲身经历过合同条款反复争议的痛——付款条件苛刻、工期无条件顺延、违约责任不对等，这些不是能力问题，而是缺少一道「提交前初审」。我们也看到无数企业因此消耗在低效流转里。</p>
            <p>于是有了照胆：一个合同提交前的审查 Agent，用 AI 辅助替代人眼核对，把条款风险和法规依据看清楚。</p>
            <p>团队兼具工程、法务、合规一线经验，同时深耕 AI Agent 技术——既懂合同里的坑，也懂如何用工程化方式把它们逐一填平。</p>
          </article>
        </div>
      </section>

      <section class="section about-principles-section">
        <div class="container">
          <div class="about-section-head">
            <p class="eyebrow">CORE PRINCIPLES</p>
            <h2>我们坚持的三件事</h2>
          </div>
          <div class="about-principle-grid">
            <article v-for="p in principles" :key="p.ref" class="circuit-card about-principle-card">
              <span class="corner corner-tl"></span>
              <span class="corner corner-br"></span>
              <span class="about-card-ref">{{ p.ref }}</span>
              <h3>{{ p.title }}</h3>
              <p>{{ p.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section about-matrix-section">
        <div class="container">
          <div class="about-section-head">
            <p class="eyebrow">PRODUCT MATRIX</p>
            <h2>句龙产品矩阵</h2>
          </div>
          <div class="about-matrix-grid">
            <article v-for="m in matrix" :key="m.ref" class="about-matrix-card" :class="{ current: m.current }">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <span class="about-card-ref">{{ m.ref }}</span>
              <p class="about-matrix-role">{{ m.role }}</p>
              <h3>{{ m.name }}</h3>
              <p class="about-matrix-desc">{{ m.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section about-build-section">
        <div class="container">
          <div class="about-section-head">
            <p class="eyebrow">BUILD IN PUBLIC</p>
            <h2>公开构建，持续演进</h2>
            <p class="about-build-sub">我们坚持公开构建（Build in Public）。产品从零到一的每一步，都在社区里留下记录——欢迎围观、反馈、参与。</p>
          </div>
          <div class="about-channel-grid">
            <a v-for="c in channels" :key="c.ref" :href="c.href" class="about-channel-card" :target="c.icon === 'mail' ? '_self' : '_blank'" rel="noopener noreferrer">
              <span class="corner corner-tl"></span>
              <span class="corner corner-br"></span>
              <span class="about-card-ref">{{ c.ref }}</span>
              <span class="material-symbols-outlined about-channel-icon">{{ c.icon }}</span>
              <span class="about-channel-label">{{ c.label }}</span>
              <span class="about-channel-value">{{ c.value }}</span>
            </a>
          </div>
        </div>
      </section>

      <section class="section case-cta-section">
        <div class="container case-cta-panel">
          <p class="eyebrow">GET IN TOUCH</p>
          <h2>和我们一起，把退回挡在流程之外</h2>
          <div class="hero-cta" style="justify-content: center; margin-top: 28px;">
            <a href="/register" class="btn btn-primary">立即注册体验</a>
            <a href="mailto:business@goulong-ai.cn" class="btn btn-ghost">联系商务合作</a>
          </div>
        </div>
      </section>
    </main>
  </MarketingShell>
</template>

<style scoped>
.about-hero-section {
  padding-bottom: 58px;
}

.about-origin-section {
  padding: 28px 0 72px;
}

.about-origin-card {
  position: relative;
  max-width: 880px;
  margin: 0 auto;
  padding: 48px 44px;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background:
    radial-gradient(520px 220px at 50% 0%, color-mix(in srgb, var(--gold) 12%, transparent), transparent 64%),
    linear-gradient(180deg, color-mix(in srgb, var(--surface) 94%, transparent), color-mix(in srgb, var(--bg) 94%, transparent));
}

.about-origin-card h2 {
  margin: 8px 0 20px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.8rem, 3vw, 2.4rem);
}

.about-origin-card p {
  color: var(--muted);
  line-height: 1.85;
  font-size: 1.02rem;
}

.about-origin-card p + p {
  margin-top: 14px;
}

.about-section-head {
  max-width: 760px;
  margin-bottom: 36px;
}

.about-section-head h2 {
  margin: 8px 0 0;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.8rem, 3vw, 2.6rem);
}

.about-build-sub {
  margin-top: 14px;
  color: var(--muted);
  line-height: 1.8;
}

.about-card-ref {
  display: block;
  margin-bottom: 14px;
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.about-principle-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
}

.about-principle-card {
  min-height: 220px;
  padding: 32px 28px;
}

.about-principle-card h3 {
  margin-bottom: 12px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: 22px;
}

.about-principle-card p {
  color: var(--muted);
  line-height: 1.75;
}

.about-matrix-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}

.about-matrix-card {
  position: relative;
  padding: 38px 32px;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--surface) 94%, transparent), color-mix(in srgb, var(--bg) 94%, transparent));
}

.about-matrix-card.current {
  border-color: color-mix(in srgb, var(--gold) 60%, transparent);
  background:
    radial-gradient(420px 190px at 50% 0%, color-mix(in srgb, var(--gold) 14%, transparent), transparent 64%),
    linear-gradient(180deg, color-mix(in srgb, var(--surface) 96%, transparent), color-mix(in srgb, var(--bg) 96%, transparent));
  box-shadow: inset 0 2px 0 color-mix(in srgb, var(--gold) 50%, transparent);
}

.about-matrix-role {
  margin-bottom: 8px;
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.about-matrix-card h3 {
  margin-bottom: 14px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.5rem, 2.2vw, 2rem);
}

.about-matrix-desc {
  color: var(--muted);
  line-height: 1.8;
}

.about-channel-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
}

.about-channel-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 32px 28px;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface) 94%, transparent), color-mix(in srgb, var(--bg) 94%, transparent));
  text-decoration: none;
  transition: border-color 0.2s;
}

.about-channel-card:hover {
  border-color: color-mix(in srgb, var(--gold) 56%, transparent);
}

.about-channel-icon {
  color: var(--gold);
  font-size: 32px;
  font-variation-settings: 'FILL' 1;
}

.about-channel-label {
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.about-channel-value {
  color: var(--text);
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 16px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .about-principle-grid,
  .about-channel-grid {
    grid-template-columns: 1fr;
  }

  .about-matrix-grid {
    grid-template-columns: 1fr;
  }

  .about-origin-card {
    padding: 32px 24px;
  }
}
</style>
