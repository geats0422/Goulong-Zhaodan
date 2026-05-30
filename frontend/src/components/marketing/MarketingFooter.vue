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
  border-top: 1px solid rgba(212, 175, 55, 0.18);
  background: rgba(10, 10, 10, 0.92);
}

.marketing-footer-row {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  color: #99907c;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  letter-spacing: 0.04em;
}

.marketing-footer a {
  color: #d0c5af;
  text-decoration: none;
}

.marketing-footer a:hover {
  color: #f2ca50;
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
