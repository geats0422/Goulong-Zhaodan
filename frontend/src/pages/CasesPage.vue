<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section cases-hero-section">
        <div class="container pricing-hero-inner">
          <nav class="case-breadcrumb" aria-label="面包屑">
            <a href="/">首页</a>
            <span>/</span>
            <span>客户案例</span>
          </nav>
          <div class="gold-rule"></div>
          <p class="eyebrow">CASE STUDIES</p>
          <h1>行业令鉴与实战战报</h1>
          <p class="lead">深入市政、房建与新基建业务腹地，前置构筑业务提交审批前的智能防线。</p>
        </div>
      </header>

      <section class="case-stage">
        <div class="container">
          <div class="battle-grid">
            <article class="battle-card">
              <span class="corner corner-tl"></span>
              <span class="corner corner-br"></span>
              <p class="case-type">[某中字头大型市政建设集团]</p>
              <h2>法规索引树挂载</h2>
              <div class="case-metric">
                <strong>100%</strong>
                <span>重大合规错漏前置拦截率</span>
              </div>
              <p class="case-copy">
                全量挂载《招标投标法》及行业地方规范的「章-节-段-句」层级索引树，实现从海量废标条款到项目具体履约指标的毫米级审查，将潜在法律风险扼杀在摇篮之中。
              </p>
              <div class="case-footer">
                <strong>日均自动化体检量: 150+ 份</strong>
                <a href="#case-cta" aria-label="查看市政建设案例">arrow_forward</a>
              </div>
            </article>

            <article class="battle-card featured-battle">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <p class="case-type">[头部新基建算力高新企业]</p>
              <h2>私有红线防火墙</h2>
              <div class="case-metric">
                <strong>0 事故</strong>
                <span>内部商业红线违规触碰</span>
              </div>
              <p class="case-copy">
                将集团历史曾用名、未发布项目内部绝密代号（如 X7 计划）以及商务敏感报价底线进行高维度特征提取，构建专属敏感词防火墙，确保每一次对外交涉滴水不漏。
              </p>
              <div class="case-footer">
                <strong>规避私有红线标准: 420+ 条</strong>
                <a href="#case-cta" aria-label="查看新基建案例">arrow_forward</a>
              </div>
            </article>

            <article class="battle-card">
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <p class="case-type">[区域建筑标杆开发集团]</p>
              <h2>绝密材料隔离层</h2>
              <div class="case-metric">
                <strong>-85%</strong>
                <span>单项目初审流转耗时</span>
              </div>
              <p class="case-copy">
                针对多流派、多附件的复杂联合体合同材料包，开启「阅后即焚」安全隔离服务层模式。在保障绝密设计图纸和核心标书不落地的同时，实现异构文档的秒级并行解析与合规比对。
              </p>
              <div class="case-footer">
                <strong>数据安全锁状态: TEE 内存断网即焚</strong>
                <a href="#case-cta" aria-label="查看建筑开发案例">arrow_forward</a>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="section case-summary-section">
        <div class="container case-summary-grid">
          <article class="case-summary-card">
            <p class="eyebrow">AUDIT IMPACT</p>
            <h2>让初级经办人拥有资深合规专家的免责视角</h2>
            <p>句龙将行业法规、私有禁忌词、材料包一致性检查合并为可追溯的初审战报，让业务团队在正式提交前完成高风险排雷。</p>
          </article>
          <article class="case-mini-stat"><strong>150+</strong><span>日均自动化体检量</span></article>
          <article class="case-mini-stat"><strong>420+</strong><span>私有红线标准</span></article>
          <article class="case-mini-stat"><strong>-85%</strong><span>单项目流转耗时</span></article>
        </div>
      </section>

      <section id="case-cta" class="section case-cta-section">
        <div class="container case-cta-panel">
          <p class="eyebrow">DEPLOY YOUR AGENT</p>
          <h2>让您的初级经办人，也能拥有资深合规专家的免责视角。</h2>
          <a href="/dashboard" class="btn btn-primary">调遣您的初审 Agent</a>
        </div>
      </section>
    </main>

  </MarketingShell>
</template>
