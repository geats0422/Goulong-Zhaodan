<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const capabilities = [
  ['多文件材料包上传', '合同、报价、申请、证照与说明文件一次载入，形成可追溯审查对象。'],
  ['主体一致性检查', '校验公司名称、统一社会信用代码、联系人、地址与签署主体是否一致。'],
  ['金额/日期/编号检查', '识别税率、付款节点、项目编号、签署日期等冲突信息。'],
  ['附件完整性与证据定位', '定位正文引用但缺失的附件，并标注问题所在文件与段落。'],
]

const metrics = [
  ['62%', '退回前置拦截率提升'],
  ['2.6x', '材料包审查效率提升'],
  ['89%', '问题建议采纳率'],
  ['100%', '问题证据可追溯'],
]

const plans = [
  ['月度订阅', '¥39 / 月', '适合短期项目与临时材料体检'],
  ['年度订阅', '¥299 / 年', '覆盖全年审查窗口，当前最高性价比'],
  ['季度订阅', '¥99 / 季', '适合持续审查与季度合规窗口'],
]
</script>

<template>
  <MarketingShell>
    <main class="marketing-home">
      <section class="home-hero marketing-container">
        <div class="gold-rule"></div>
        <p class="eyebrow">AUTHORIZATION INSPECTION AGENT</p>
        <h1>句龙 · 照胆</h1>
        <p class="hero-subtitle">业务提交前审查 Agent：把明显错误和材料缺口挡在流程外</p>
        <p class="lead">
          在 OA、合同审批、采购申请、项目审批、付款申请正式提交前，对多文件材料包进行一致性与完整性审查，输出可执行问题清单、修改建议和证据定位。
        </p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="/dashboard">登录进入应用</a>
          <a class="btn btn-ghost" href="/solution.html">查看解决方案</a>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading">
          <p class="eyebrow">PROBLEM MAP</p>
          <h2>企业材料包退回，常常不是大问题，而是基础错漏没有前置拦截</h2>
        </div>
        <div class="problem-grid">
          <article><strong>主体冲突</strong><span>合同、报价、申请表内主体信息不一致。</span></article>
          <article><strong>附件缺口</strong><span>正文引用附件，但材料包中没有对应文件。</span></article>
          <article><strong>节点错配</strong><span>金额、日期、编号与付款节点出现冲突。</span></article>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading split-heading">
          <div>
            <p class="eyebrow">SOLUTION</p>
            <h2>解决方案：句龙 · 照胆核心能力</h2>
          </div>
          <a href="/solution.html">进入解决方案</a>
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
            <p>围绕 TEE、本地脱敏、阅后即焚与审计留痕建立安全边界，让业务经办人可以在正式流转前完成低风险自检。</p>
          </div>
          <a class="btn btn-ghost" href="/security.html">查看数据安全</a>
        </div>
      </section>

      <section class="marketing-section marketing-container">
        <div class="section-heading split-heading">
          <div>
            <p class="eyebrow">CASE STUDIES</p>
            <h2>客户案例</h2>
          </div>
          <a href="/cases.html">查看完整案例</a>
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
          <a href="/pricing.html">查看全部定价</a>
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
        <h2>把材料包问题拦在提交之前</h2>
        <div class="hero-actions">
          <a class="btn btn-primary" href="/dashboard">进入应用靶场</a>
          <a class="btn btn-ghost" href="/pricing.html">选择授权周期</a>
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
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.5rem, 3vw, 2.6rem);
  font-weight: 800;
  max-width: 900px;
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

[data-theme="light"] .problem-grid article,
[data-theme="light"] .metrics-grid article,
[data-theme="light"] .circuit-card,
[data-theme="light"] .final-cta {
  box-shadow: 0 16px 42px rgba(88, 65, 15, 0.08);
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
