<template>
  <footer class="marketing-footer">
    <div class="marketing-footer-row">
      <p>© 2024 句龙 · 照胆. ALL RIGHTS RESERVED. SECURED BY TIGER TALLY PROTOCOL.</p>
      <p>
        <a href="/security.html">隐私政策</a>
        <span>·</span>
        <a href="/pricing.html">服务条款</a>
        <span>·</span>
        <a href="/solution.html">技术文档</a>
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
