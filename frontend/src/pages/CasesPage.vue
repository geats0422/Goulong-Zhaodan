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
              <h2>单份工程合同条款初审</h2>
              <div class="case-metric">
                <strong>1 份</strong>
                <span>每次审查的合同文档</span>
              </div>
              <p class="case-copy">
                上传一份 PDF、DOCX 或 TXT 工程合同，系统自动解析正文、识别工程与合同类别，围绕付款、工期、质量、安全、违约责任等条款输出风险问题与修改建议，并标注法规依据与正文位置。
              </p>
            </article>

            <article class="battle-card featured-battle">
              <span class="corner corner-tl"></span>
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <span class="corner corner-br"></span>
              <p class="case-type">[能力验证]</p>
              <h2>法规依据与证据定位</h2>
              <div class="case-metric">
                <strong>可追溯</strong>
                <span>问题与法规依据</span>
              </div>
              <p class="case-copy">
                采用原生结构解析，将合同拆解为层级索引，定位问题所在的章节位置，并关联默认法规与企业知识库中的参考条款，让每一处问题都有据可查。
              </p>
            </article>

            <article class="battle-card">
              <span class="corner corner-tr"></span>
              <span class="corner corner-bl"></span>
              <p class="case-type">[产品研发]</p>
              <h2>审查过程安全保护</h2>
              <p class="case-copy">
                合同审查过程在 TEE 保护下进行，结合访问控制与审计留痕建立安全边界，让业务经办人可以在正式流转前完成低风险初审。文件暂存于 ECS 本地存储，用户可随时删除历史记录。
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
            <p>句龙·照胆刚刚起步，能力仍在持续打磨。我们正在与早期试用团队紧密合作，收集真实业务场景下的反馈。如您负责合同审批或合规初审，欢迎成为我们的首批共创伙伴——您的每一份真实合同，都会让产品更贴近实际。</p>
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
