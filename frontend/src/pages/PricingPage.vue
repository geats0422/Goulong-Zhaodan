<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import MarketingShell from '../components/marketing/MarketingShell.vue'
import PaymentModal from '../components/PaymentModal.vue'
import { useAuth } from '../composables/useAuth.js'
import { PLAN_CATALOG } from '../data/plans.js'

const { isLoggedIn } = useAuth()
const router = useRouter()
const activeTab = ref('personal')
const modalProduct = ref(null)

const addons = [
  { code: 'light', name: '轻量包', price: '¥5', quota: '100万 Token', desc: '适合轻度试用与体验' },
  { code: 'standard', name: '标准包', price: '¥18', quota: '500万 Token', desc: '适合常规项目审查' },
  { code: 'large', name: '大额包', price: '¥58', quota: '2000万 Token', desc: '适合高频深度审查（仅 Pro 用户）' },
]

const subscriptions = [
  {
    code: 'pro_monthly', name: 'Pro 月度', kicker: 'MONTHLY ACCESS', period: '/ 月', price: '¥49',
    copy: '适合短期项目与临时材料体检',
    features: ['200万 Token 月度额度', '无限次多文件材料包体检', '核心漏洞精准定位', 'Markdown/PDF 报告导出'],
    featured: false,
  },
  {
    code: 'pro_quarterly', name: 'Pro 季度', kicker: 'QUARTERLY WINDOW', period: '/ 季', price: '¥139',
    copy: '适合持续审查与季度合规窗口',
    features: ['600万 Token 季度额度', '无限次多文件材料包体检', '核心漏洞精准定位', 'Markdown/PDF 报告导出'],
    featured: false,
  },
  {
    code: 'pro_yearly', name: 'Pro 年度', kicker: 'ANNUAL TALLY', period: '/ 年', price: '¥499',
    copy: '专属授权令，覆盖全年审查窗口',
    features: ['2400万 Token 年度额度', '无限次多文件材料包体检', '核心漏洞精准定位', 'Markdown/PDF 报告导出', '优先队列与专属授权令'],
    featured: true,
  },
]

function handleBuy(product) {
  if (!isLoggedIn()) {
    router.push('/login')
    return
  }
  modalProduct.value = product
}

function closeModal() {
  modalProduct.value = null
}

function onPaid() {
  modalProduct.value = null
  router.push('/dashboard')
}
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
              <div class="addon-section">
                <p class="eyebrow addon-eyebrow">TOKEN ADDON</p>
                <h2 class="addon-title">额度包 · 按需补充</h2>
                <div class="addon-grid">
                  <article v-for="a in addons" :key="a.code" class="addon-card">
                    <span class="corner corner-tl"></span>
                    <span class="corner corner-br"></span>
                    <h3 class="addon-name">{{ a.name }}</h3>
                    <p class="addon-price">{{ a.price }}</p>
                    <p class="addon-quota">{{ a.quota }}</p>
                    <p class="addon-desc">{{ a.desc }}</p>
                    <button class="btn btn-ghost btn-full" @click="handleBuy(a)">立即购买</button>
                  </article>
                </div>
              </div>

              <div class="pricing-cards pricing-cards-restored">
                <article v-for="(s, i) in subscriptions" :key="s.code" class="pricing-card restored-card" :class="{ featured: s.featured, 'featured-restored': s.featured }">
                  <template v-if="s.featured">
                    <span class="corner corner-tl"></span><span class="corner corner-tr"></span>
                    <span class="corner corner-bl"></span><span class="corner corner-br"></span>
                    <p class="plan-badge">最高性价比</p>
                  </template>
                  <template v-else>
                    <span class="corner corner-tl"></span>
                    <span class="corner corner-br" v-if="i === 0"></span>
                    <span class="corner corner-tr" v-if="i === 2"></span>
                    <span class="corner corner-bl" v-if="i === 2"></span>
                  </template>
                  <p class="plan-kicker">{{ s.kicker }}</p>
                  <h2 class="plan-name">{{ s.name }}</h2>
                  <p class="plan-copy">{{ s.copy }}</p>
                  <p class="plan-price">{{ s.price }} <span class="per">{{ s.period }}</span></p>
                  <ul class="plan-features">
                    <li v-for="f in s.features" :key="f">{{ f }}</li>
                  </ul>
                  <button :class="['btn', 'btn-full', s.featured ? 'btn-primary' : 'btn-ghost']" @click="handleBuy(s)">
                    {{ s.featured ? '获取年度特符' : '立即订阅' }}
                  </button>
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
              支持微信扫码支付，额度包永久有效，订阅周期内无限次体检。
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
                <p>订阅周期灵活，按月、按季、按年调遣，额度包永久有效不过期。</p>
              </article>
            </div>
          </div>
        </section>
      </main>

      <PaymentModal
        v-if="modalProduct"
        :product-code="modalProduct.code"
        :product-name="modalProduct.name"
        :amount-label="modalProduct.price"
        @paid="onPaid"
        @close="closeModal"
      />
    </main>
  </MarketingShell>
</template>

<style scoped>
.addon-section {
  margin-bottom: 48px;
}

.addon-eyebrow {
  margin-bottom: 4px;
}

.addon-title {
  margin: 0 0 24px;
  font-size: 24px;
}

.addon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
}

.addon-card {
  position: relative;
  padding: 28px 24px;
  background: rgba(18, 18, 18, 0.6);
  border: 1px solid rgba(212, 175, 55, 0.18);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
}

.addon-name {
  margin: 0;
  font-size: 18px;
  color: #fff8e7;
}

.addon-price {
  margin: 4px 0;
  font-family: "Syne", sans-serif;
  font-size: 32px;
  font-weight: 700;
  color: #d4af37;
}

.addon-quota {
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #99907c;
  letter-spacing: 0.12em;
}

.addon-desc {
  font-size: 12px;
  color: #99907c;
  margin: 4px 0 12px;
}

.addon-card .btn {
  margin-top: auto;
}

[data-theme="light"] .addon-card {
  background: rgba(255, 250, 240, 0.86);
  border-color: rgba(155, 116, 22, 0.22);
}

[data-theme="light"] .addon-name {
  color: #1f1a12;
}

[data-theme="light"] .addon-price {
  color: #9b7416;
}

[data-theme="light"] .addon-quota,
[data-theme="light"] .addon-desc {
  color: #66563a;
}
</style>
