<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const capabilities = [
  ['单份工程合同上传', '上传一份 PDF、DOCX 或 TXT 合同，自动解析正文并建立审查记录。'],
  ['工程与合同类别确认', '识别市政道路、房建施工等工程类别，以及劳务分包等合同类别，支持人工确认。'],
  ['合同条款风险检查', '围绕付款、工期、质量、安全、违约责任等条款输出风险问题与修改建议。'],
  ['法规依据与证据定位', '结合默认法规和启用的企业知识库，标注问题来源与正文位置。'],
]

const metrics = [
  ['1 份', '每次审查的合同文档'],
  ['3 步', '解析、确认、审查'],
  ['PDF', '报告下载格式'],
  ['可追溯', '问题与法规依据'],
]

const plans = [
  ['月度订阅', '¥69 / 月', '适合短期项目与临时材料体检'],
  ['年度订阅', '¥599 / 年', '覆盖全年审查窗口，当前最高性价比'],
  ['季度订阅', '¥179 / 季', '适合持续审查与季度合规窗口'],
]
</script>

<template>
  <MarketingShell>
    <main class="marketing-home">
      <section class="home-hero marketing-container">
        <div class="gold-rule"></div>
        <p class="eyebrow">AUTHORIZATION INSPECTION AGENT</p>
        <h1>句龙 · 照胆</h1>
        <p class="hero-subtitle">
          <span>业务提交前审查 <span class="subtitle-agent">Agent：</span></span>
          <span>把明显错误和材料缺口挡在流程外</span>
        </p>
        <p class="lead">
           上传一份工程合同，完成解析、类别确认和法规辅助初审，输出问题清单、修改建议和证据定位。
        </p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="/dashboard">登录进入应用</a>
          <a class="btn btn-ghost" href="/solution">查看解决方案</a>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading">
          <p class="eyebrow">PROBLEM MAP</p>
          <h2>工程合同初审，先把条款风险和法规依据看清楚</h2>
        </div>
        <div class="problem-grid">
           <article><strong>类别确认</strong><span>先确认工程类别与合同类别，避免使用错误的审查依据。</span></article>
           <article><strong>条款风险</strong><span>关注付款、工期、质量、安全和违约责任等关键条款。</span></article>
           <article><strong>依据定位</strong><span>查看问题对应的法规依据和合同正文位置，便于人工复核。</span></article>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading split-heading">
          <div>
            <p class="eyebrow">SOLUTION</p>
            <h2>解决方案：句龙 · 照胆核心能力</h2>
          </div>
          <a href="/solution">进入解决方案</a>
        </div>
        <div class="capability-grid">
          <article v-for="capability in capabilities" :key="capability[0]" class="circuit-card">
            <span class="corner corner-tl"></span>
            <span class="corner corner-br"></span>
            <h3>{{ capability[0] }}</h3>
            <p>{{ capability[1] }}</p>
          </article>
        </div>
      </section>

      <section class="marketing-section security-strip">
        <div class="marketing-container security-layout">
          <div>
            <p class="eyebrow">DIGITAL VAULT</p>
            <h2>静默处理，证据可追溯</h2>
             <p>部署在阿里云 ECS 的 Docker 环境，使用外部 RDS PostgreSQL 保存业务数据；TEE 保护、访问控制和审计机制共同构成合同初审的安全边界。</p>
          </div>
          <a class="btn btn-ghost" href="/security">查看数据安全</a>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading split-heading">
          <div>
            <p class="eyebrow">CASE STUDIES</p>
           <h2>当前产品能力</h2>
          </div>
           <a href="/solution">查看能力说明</a>
        </div>
        <div class="metrics-grid">
          <article v-for="metric in metrics" :key="metric[1]">
            <strong>{{ metric[0] }}</strong>
            <span>{{ metric[1] }}</span>
          </article>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading split-heading">
          <div>
            <p class="eyebrow">AUTHORIZATION TALLY</p>
            <h2>版本与定价</h2>
          </div>
          <a href="/pricing">查看全部定价</a>
        </div>
        <div class="plan-grid">
          <article v-for="plan in plans" :key="plan[0]" class="circuit-card">
            <h3>{{ plan[0] }}</h3>
            <strong>{{ plan[1] }}</strong>
            <p>{{ plan[2] }}</p>
          </article>
        </div>
      </section>

      <section class="final-cta marketing-container">
        <p class="eyebrow">READY FOR INSPECTION</p>
         <h2>把合同初审做在正式提交之前</h2>
        <div class="hero-actions">
          <a class="btn btn-primary" href="/dashboard">进入应用靶场</a>
          <a class="btn btn-ghost" href="/pricing">选择授权周期</a>
        </div>
      </section>
    </main>
  </MarketingShell>
</template>

<style scoped>
.marketing-container {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
}

.marketing-home {
  overflow: hidden;
}

.home-hero {
  min-height: 620px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 96px 0 80px;
}

.gold-rule {
  width: 96px;
  height: 1px;
  margin-bottom: 18px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
}

.home-hero h1 {
  margin: 16px 0;
  color: var(--gold);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(4rem, 11vw, 8.8rem);
  line-height: 0.95;
  letter-spacing: -0.06em;
  text-shadow: 0 0 28px color-mix(in srgb, var(--gold) 28%, transparent);
}

.hero-subtitle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.5rem, 3vw, 2.6rem);
  font-weight: 800;
  line-height: 1.18;
  max-width: 900px;
}

.hero-subtitle span {
  display: block;
  max-width: 100%;
}

.subtitle-agent {
  display: inline-block !important;
  white-space: nowrap;
}

.lead {
  max-width: 760px;
  margin-top: 22px;
  color: var(--muted);
  font-size: 18px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px;
  margin-top: 36px;
}

.marketing-section {
  padding: 88px 0;
  border-top: 1px solid color-mix(in srgb, var(--gold) 16%, transparent);
}

.section-heading {
  margin-bottom: 32px;
}

.section-heading h2,
.final-cta h2,
.security-layout h2 {
  margin: 8px 0 0;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(2rem, 4vw, 3.2rem);
  line-height: 1.12;
}

.split-heading {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
}

.split-heading a {
  color: var(--gold);
  text-decoration: none;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.problem-grid,
.capability-grid,
.metrics-grid,
.plan-grid {
  display: grid;
  gap: 18px;
}

.problem-grid {
  grid-template-columns: repeat(3, 1fr);
}

.problem-grid article,
.metrics-grid article,
.circuit-card {
  position: relative;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface-2) 92%, transparent), color-mix(in srgb, var(--bg) 92%, transparent));
}

.problem-grid article {
  min-height: 150px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 28px;
}

.problem-grid strong,
.circuit-card h3,
.plan-grid strong {
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: 24px;
}

.problem-grid span,
.circuit-card p,
.security-layout p,
.metrics-grid span {
  color: var(--muted);
  line-height: 1.7;
}

.capability-grid {
  grid-template-columns: repeat(4, 1fr);
}

.circuit-card {
  min-height: 190px;
  padding: 28px;
}

.corner {
  position: absolute;
  width: 18px;
  height: 18px;
  border-color: var(--gold);
  border-style: solid;
}

.corner-tl {
  top: 10px;
  left: 10px;
  border-width: 1px 0 0 1px;
}

.corner-br {
  right: 10px;
  bottom: 10px;
  border-width: 0 1px 1px 0;
}

.security-strip {
  background: radial-gradient(circle at 72% 50%, color-mix(in srgb, var(--gold) 13%, transparent), transparent 34%), color-mix(in srgb, var(--surface) 64%, transparent);
}

.security-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 32px;
  align-items: center;
}

.metrics-grid {
  grid-template-columns: repeat(4, 1fr);
}

.metrics-grid article {
  padding: 28px;
}

.metrics-grid strong {
  display: block;
  color: var(--gold);
  font-size: 48px;
  line-height: 1;
}

.plan-grid {
  grid-template-columns: repeat(3, 1fr);
}

.plan-grid strong {
  display: block;
  margin: 24px 0 12px;
  color: var(--gold);
  font-size: 34px;
}

.final-cta {
  margin-bottom: 96px;
  padding: 72px 32px;
  text-align: center;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background: radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--gold) 18%, transparent), transparent 45%), var(--surface);
}

:global(html[data-theme="light"]) .problem-grid article,
:global(html[data-theme="light"]) .metrics-grid article,
:global(html[data-theme="light"]) .circuit-card,
:global(html[data-theme="light"]) .final-cta {
  border-color: rgba(95, 71, 16, 0.34);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface) 84%, var(--surface-2)), color-mix(in srgb, var(--bg) 76%, var(--surface-2)));
  box-shadow: 0 18px 44px rgba(36, 26, 6, 0.16), inset 0 0 0 1px rgba(0, 109, 115, 0.06);
}

:global(html[data-theme="light"]) .home-hero h1 {
  color: var(--gold);
  text-shadow: 0 0 18px rgba(0, 109, 115, 0.12);
}

:global(html[data-theme="light"]) .lead {
  color: var(--muted);
}

:global(html[data-theme="light"]) .secondary-link {
  border-color: rgba(95, 71, 16, 0.46);
  background: color-mix(in srgb, var(--surface) 72%, transparent);
}

@media (max-width: 980px) {
  .problem-grid,
  .capability-grid,
  .metrics-grid,
  .plan-grid,
  .security-layout {
    grid-template-columns: 1fr;
  }

  .split-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
