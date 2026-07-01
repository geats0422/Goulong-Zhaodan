<template>
  <footer class="marketing-footer">
    <div class="marketing-footer-row">
      <p>© 2024 句龙 · 照胆. ALL RIGHTS RESERVED. SECURED BY TIGER TALLY PROTOCOL.</p>
      <p>
        <a href="/security">隐私政策</a>
        <span>·</span>
        <a href="/pricing">服务条款</a>
        <span>·</span>
        <a href="/solution">技术文档</a>
      </p>
    </div>
    <div class="marketing-footer-icp">
      <span>杭州焕羽格致智能科技有限公司</span>
      <span class="icp-separator">·</span>
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">浙ICP备2026045389号-1</a>
    </div>
  </footer>
</template>

<style scoped>
.marketing-footer {
  border-top: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--bg) 92%, transparent);
}

.marketing-footer-row {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  color: var(--muted);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
}

.marketing-footer a {
  color: var(--muted);
  text-decoration: none;
}

.marketing-footer a:hover {
  color: var(--gold);
}

.marketing-footer-icp {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
  padding-bottom: 16px;
  text-align: center;
}

.marketing-footer-icp a,
.marketing-footer-icp span {
  color: var(--muted);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-decoration: none;
  opacity: 0.7;
}

.marketing-footer-icp .icp-separator {
  margin: 0 6px;
}

.marketing-footer-icp a:hover {
  color: var(--gold);
  opacity: 1;
}

@media (max-width: 760px) {
  .marketing-footer-row {
    min-height: auto;
    padding: 28px 0;
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
