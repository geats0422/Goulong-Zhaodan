<script setup>
import { ref } from 'vue'
import MarketingShell from '../components/marketing/MarketingShell.vue'
import { PLAN_CATALOG } from '../data/plans.js'

const activeTab = ref('personal')
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section">
      <div class="container pricing-hero-inner">
        <div class="gold-rule"></div>
        <p class="eyebrow">AUTHORIZATION TALLY</p>
        <h1>获取您的初步授权</h1>
        <p class="lead">完整功能，无门槛解锁。按需选择您的调遣周期。</p>
      </div>
    </header>

    <main>
      <section class="pricing-stage pricing-upgrade-stage">
        <div class="container">
          <div class="pricing-tabs" role="tablist" aria-label="套餐类型">
            <button class="pricing-tab" :class="{ active: activeTab === 'personal' }" type="button" role="tab" :aria-selected="activeTab === 'personal'" @click="activeTab = 'personal'">个人</button>
            <button class="pricing-tab" :class="{ active: activeTab === 'team' }" type="button" role="tab" :aria-selected="activeTab === 'team'" @click="activeTab = 'team'">团队</button>
            <button class="pricing-tab" :class="{ active: activeTab === 'enterprise' }" type="button" role="tab" :aria-selected="activeTab === 'enterprise'" @click="activeTab = 'enterprise'">企业</button>
          </div>

          <div v-if="activeTab === 'personal'" class="pricing-panel active" role="tabpanel">
            <div class="pricing-cards pricing-cards-restored">
              <article class="pricing-card restored-card">
                <span class="corner corner-tl"></span>
                <span class="corner corner-br"></span>
                <p class="plan-kicker">MONTHLY ACCESS</p>
                <h2 class="plan-name">月度订阅</h2>
                <p class="plan-copy">适合短期项目与临时材料体检</p>
                <p class="plan-price">¥39 <span class="per">/ 月</span></p>
                <ul class="plan-features">
                  <li>无限次多文件材料包体检</li>
                  <li>核心漏洞精准定位与离线</li>
                  <li>Markdown/PDF 诊断报告导出</li>
                  <li>本地脱敏与阅后即焚保障</li>
                </ul>
                <a href="/dashboard" class="btn btn-ghost btn-full">按月调遣</a>
              </article>

              <article class="pricing-card restored-card featured featured-restored">
                <span class="corner corner-tl"></span>
                <span class="corner corner-tr"></span>
                <span class="corner corner-bl"></span>
                <span class="corner corner-br"></span>
                <p class="plan-badge">最高性价比</p>
                <p class="plan-kicker">ANNUAL TALLY</p>
                <h2 class="plan-name">年度订阅</h2>
                <p class="plan-copy">专属授权令，覆盖全年审查窗口</p>
                <p class="plan-price">¥299 <span class="per">/ 年</span></p>
                <p class="plan-save"><span>¥468</span> 节省 36%</p>
                <ul class="plan-features">
                  <li>无限次多文件材料包体检</li>
                  <li>核心漏洞精准定位与离线</li>
                  <li>Markdown/PDF 诊断报告导出</li>
                  <li>本地脱敏与阅后即焚保障</li>
                  <li>优先队列与专属授权令</li>
                </ul>
                <a href="/dashboard" class="btn btn-primary btn-full">获取年度特符</a>
              </article>

              <article class="pricing-card restored-card">
                <span class="corner corner-tr"></span>
                <span class="corner corner-bl"></span>
                <p class="plan-kicker">QUARTERLY WINDOW</p>
                <h2 class="plan-name">季度订阅</h2>
                <p class="plan-copy">适合持续审查与季度合规窗口</p>
                <p class="plan-price">¥99 <span class="per">/ 季</span></p>
                <ul class="plan-features">
                  <li>无限次多文件材料包体检</li>
                  <li>核心漏洞精准定位与离线</li>
                  <li>Markdown/PDF 诊断报告导出</li>
                  <li>本地脱敏与阅后即焚保障</li>
                </ul>
                <a href="/dashboard" class="btn btn-ghost btn-full">按季调遣</a>
              </article>
            </div>
          </div>

          <div v-if="activeTab === 'team'" class="pricing-panel active" role="tabpanel">
            <article class="future-plan-card">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <p class="plan-kicker">TEAM WORKSPACE</p>
              <h2>团队协作版开发中</h2>
              <p>当前产品处于 MVP 早期阶段，优先打磨个人材料包审查体验。团队版将围绕多人协作、统一订阅和权限边界逐步开放。</p>
              <div class="future-feature-grid">
                <span v-for="f in PLAN_CATALOG.team.features" :key="f">{{ f }}</span>
              </div>
              <a class="btn btn-ghost" href="#">留下团队需求</a>
            </article>
          </div>

          <div v-if="activeTab === 'enterprise'" class="pricing-panel active" role="tabpanel">
            <article class="future-plan-card enterprise-card">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <p class="plan-kicker">ENTERPRISE DEPLOYMENT</p>
              <h2>企业私有化能力后续支持</h2>
              <p>企业版会在个人订阅验证完成后推进，重点覆盖高安全场景下的私有部署、内网数据边界、审计留痕和专属合规策略。</p>
              <div class="future-feature-grid">
                <span v-for="f in PLAN_CATALOG.enterprise.features" :key="f">{{ f }}</span>
              </div>
              <a class="btn btn-ghost" href="#">预约企业沟通</a>
            </article>
          </div>

          <p class="pricing-note">
            <span></span>
            MVP 阶段优先开放个人订阅；团队与企业能力会在个人体验稳定后逐步支持。
          </p>
        </div>
      </section>

      <section class="section faq-restored-section">
        <div class="container">
          <p class="eyebrow">QUESTIONS</p>
          <h2>授权疑问</h2>
          <div class="faq-grid">
            <article class="faq-item">
              <h3>是否需要上传原始文件？</h3>
              <p>不强制上传原始明文。可先执行本地脱敏策略，再进入材料包体检流程。</p>
            </article>
            <article class="faq-item">
              <h3>能否导出审查报告？</h3>
              <p>支持 Markdown 与 PDF 诊断报告导出，便于提交业务、法务或合规复核。</p>
            </article>
            <article class="faq-item">
              <h3>是否支持企业内网部署？</h3>
              <p>支持从 SaaS 试点演进至私有化部署，适配企业级数据边界要求。</p>
            </article>
            <article class="faq-item">
              <h3>订阅后是否可随时取消？</h3>
              <p>订阅周期灵活，按月、按季、按年调遣，后续周期可按需调整。</p>
            </article>
          </div>
        </div>
      </section>
    </main>

    </main>
  </MarketingShell>
</template>
