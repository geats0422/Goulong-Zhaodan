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
          <h1>场景记录，见证审查能力</h1>
          <p class="lead">句龙·照胆目前处于早期试用阶段。下文为产品研发与内部验证过程中的真实场景记录，具体客户名称与业务数据将根据实际合作情况持续更新。</p>
        </div>
      </header>

      <section class="case-stage">
        <div class="container">
          <div class="battle-grid">
            <article class="battle-card">
              <span class="corner corner-tl"></span>
              <span class="corner corner-br"></span>
              <p class="case-type">[产品研发]</p>
              <h2>多文件材料包一致性体检</h2>
              <div class="case-metric">
                <strong>4 类</strong>
                <span>主体 · 金额 · 日期 · 编号</span>
              </div>
              <p class="case-copy">
                合同、报价、申请表、证照与说明文件一次载入，自动校验公司名称、统一社会信用代码、联系人、地址是否一致，识别税率、付款节点、项目编号与签署日期的冲突，把退回前的基础错漏拦在流程外。
              </p>
            </article>

            <article class="battle-card featured-battle">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <p class="case-type">[能力验证]</p>
              <h2>附件缺口与证据精准定位</h2>
              <div class="case-metric">
                <strong>100%</strong>
                <span>问题证据可追溯</span>
              </div>
              <p class="case-copy">
                坚决摒弃向量数据库带来的模糊性。采用原生结构解析，将文档拆解为「章-节-段-句」层级索引树，定位正文引用但缺失的附件，并标注问题所在文件与段落，让每一处问题都有据可查。
              </p>
            </article>

            <article class="battle-card">
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <p class="case-type">[产品研发]</p>
              <h2>静默处理与阅后即焚</h2>
              <div class="case-metric">
                <strong>0</strong>
                <span>敏感数据落盘</span>
              </div>
              <p class="case-copy">
                数据流转于 TEE 加密内存中，任务完成后触发物理级内存覆写，绝不落盘。围绕本地脱敏、阅后即焚与审计留痕建立安全边界，让业务经办人可以在正式流转前完成低风险自检。
              </p>
            </article>
          </div>
        </div>
      </section>

      <section class="section case-summary-section">
        <div class="container">
          <article class="case-summary-card">
            <p class="eyebrow">INVITATION</p>
            <h2>我们正在寻找第一批愿意尝试的团队</h2>
            <p>句龙·照胆刚刚起步，能力仍在持续打磨。我们正在与早期试用团队紧密合作，收集真实业务场景下的反馈。如您负责合同审批、采购申请、项目申报或合规初审，欢迎成为我们的首批共创伙伴——您的每一个真实材料包，都会让产品更贴近实际。</p>
          </article>
        </div>
      </section>

      <section id="case-cta" class="section case-cta-section">
        <div class="container case-cta-panel">
          <p class="eyebrow">JOIN EARLY ACCESS</p>
          <h2>成为首批共创伙伴</h2>
          <p style="max-width: 60ch; margin: 14px auto 0; color: var(--muted);">早期试用期间，我们为深度合作团队提供专属支持与功能调优。</p>
          <div class="hero-cta" style="justify-content: center; margin-top: 28px;">
            <a href="/register" class="btn btn-primary">立即注册体验</a>
            <a href="mailto:business@goulong-ai.cn" class="btn btn-ghost">联系商务合作</a>
          </div>
        </div>
      </section>
    </main>

  </MarketingShell>
</template>
