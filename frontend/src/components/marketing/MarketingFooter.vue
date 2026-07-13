<template>
  <footer class="marketing-footer">
    <div class="marketing-footer-row">
      <p>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">杭州焕羽格致智能科技有限公司 · 浙ICP备2026045389号-1</a>
        <span>·</span>
        <a href="http://www.beian.gov.cn/portal/registerSystemInfo?recordcode=33011002020045" target="_blank" rel="noopener">浙公网安备33011002020045号</a>
      </p>
      <p>
        <a href="/help">帮助中心</a>
        <span>·</span>
        <a href="/privacy">隐私政策</a>
        <span>·</span>
        <a href="/terms">服务条款</a>
        <span>·</span>
        <a href="/docs">技术文档</a>
        <span>·</span>
        <a href="mailto:business@goulong-ai.cn">商务合作</a>
      </p>
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

@media (max-width: 760px) {
  .marketing-footer-row {
    min-height: auto;
    padding: 28px 0;
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
