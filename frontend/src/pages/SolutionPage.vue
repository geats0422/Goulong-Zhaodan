<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section solution-hero-section">
      <div class="container pricing-hero-inner">
        <nav class="case-breadcrumb" aria-label="面包屑">
          <a href="/">首页</a>
          <span>/</span>
          <span>解决方案</span>
        </nav>
        <div class="gold-rule"></div>
        <p class="eyebrow">ARCHITECTURAL SUPERIORITY</p>
        <h1>重塑规矩，确立初审法度</h1>
        <p class="lead">深入业务经办人的「第零步」防线，用绝对确定的工程级架构，消解文档流转中的逻辑矛盾。</p>
      </div>
    </header>

    <main>
      <section class="solution-stage">
        <div class="container solution-layout">
          <aside class="solution-diagram" aria-label="前置初审架构示意">
            <span class="corner corner-tl"></span>
            <span class="corner corner-tr"></span>
            <span class="corner corner-bl"></span>
            <span class="corner corner-br"></span>
            <div class="diagram-node source">业务材料包</div>
            <div class="diagram-path"><span></span><span></span><span></span></div>
            <div class="diagram-node service">前置初审服务层</div>
            <div class="diagram-path"><span></span><span></span><span></span></div>
            <div class="diagram-node target">OA / ERP 正式流转</div>
          </aside>

          <div class="solution-feature-list">
            <article class="solution-feature-card">
              <p class="solution-icon">crossword</p>
              <h2>第零步防线：免责护城河</h2>
              <p>不触碰、不干预企业现有的 OA 或 ERP 最终审批流。在进入正式流转前，构建一道坚实的初审屏障，确保基础合规与逻辑自洽。</p>
              <div class="solution-tags">
                <span>前置化初审定位</span>
                <span>不越权最终裁决</span>
              </div>
            </article>

            <article class="solution-feature-card featured-solution-card">
              <p class="solution-icon">account_tree</p>
              <h2>原生解构：绝对空间坐标</h2>
              <p>坚决摒弃向量数据库带来的模糊性。采用原生结构解析，将文档精准拆解为「章-节-段-句」层级索引，实现像素级定位。</p>
              <div class="solution-tags">
                <span>层级树状寻址</span>
                <span>零向量碎片拼接</span>
              </div>
            </article>

            <article class="solution-feature-card">
              <p class="solution-icon">explore</p>
              <h2>私域红线：智能规避航标</h2>
              <p>重新定义为 LLM 必须绕行的「编写与审查规避标准」。结合企业私域知识库，自动标识敏感词汇与逻辑冲突，提前排雷。</p>
              <div class="solution-tags">
                <span>规避标准确立</span>
                <span>引导式私域排雷</span>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="solution-cta" class="section case-cta-section">
        <div class="container case-cta-panel solution-cta-panel">
          <p class="eyebrow">BEFORE FORMAL APPROVAL</p>
          <h2>把每一次正式提交，先交给第零步初审层完成排雷。</h2>
          <a href="/dashboard" class="btn btn-primary">预约解决方案演示</a>
        </div>
      </section>
    </main>

    </main>
  </MarketingShell>
</template>
