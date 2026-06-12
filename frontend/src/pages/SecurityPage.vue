<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section security-hero-section">
      <div class="container pricing-hero-inner">
        <nav class="case-breadcrumb" aria-label="面包屑">
          <a href="/">首页</a>
          <span>/</span>
          <span>数据安全</span>
        </nav>
        <div class="gold-rule"></div>
        <p class="eyebrow">DIGITAL VAULT</p>
        <h1>绝对静默与密档壁垒</h1>
        <p class="lead">作为企业文档的独立初审服务层，我们深知商业机密是企业的生命线。</p>
      </div>
    </header>

    <main>
      <section class="security-vault-section">
        <div class="container security-vault-grid">
          <aside class="vault-core" aria-label="安全核心示意">
            <span class="corner corner-tl"></span>
            <span class="corner corner-tr"></span>
            <span class="corner corner-bl"></span>
            <span class="corner corner-br"></span>
            <div class="vault-ring">
              <span>shield_lock</span>
            </div>
            <p>Trust Shield Compliance</p>
            <div class="vault-icons">
              <span>verified_user</span>
              <span>security</span>
              <span>policy</span>
            </div>
          </aside>

          <div class="security-features">
            <article class="security-feature-card">
              <p class="security-icon">local_fire_department</p>
              <h2>内存级阅后即焚</h2>
              <p>数据流转于 TEE (Trusted Execution Environment) 级加密内存中。任务完成后触发物理级内存覆写，绝不落盘。</p>
              <div class="security-tags">
                <span>[ TEE 内存加密流 ]</span>
                <span>[ 物理级绝密销毁 ]</span>
              </div>
            </article>

            <article class="security-feature-card">
              <p class="security-icon">account_tree</p>
              <h2>层级索引树不留痕</h2>
              <p>采用专有层级树状结构进行确定性寻址，彻底杜绝敏感数据被清洗进公有云大模型向量数据库的风险。</p>
              <div class="security-tags">
                <span>[ 确定性树状寻址 ]</span>
                <span>[ 拒绝公有云向量沉淀 ]</span>
              </div>
            </article>

            <article class="security-feature-card">
              <p class="security-icon">router</p>
              <h2>业务服务层天然隔离</h2>
              <p>作为独立的前置初审层，系统从网络架构设计上与核心 OA/ERP 系统实施物理+逻辑双重隔离。</p>
              <div class="security-tags">
                <span>[ 独立服务层边界 ]</span>
                <span>[ OA内核无痕隔离 ]</span>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="security-cta" class="section case-cta-section">
        <div class="container case-cta-panel security-cta-panel">
          <p class="eyebrow">SECURITY FIRST</p>
          <h2>让初审 Agent 成为核心系统之外的安全缓冲层。</h2>
          <a href="/dashboard" class="btn btn-primary">预约安全架构演示</a>
        </div>
      </section>
    </main>

    </main>
  </MarketingShell>
</template>
