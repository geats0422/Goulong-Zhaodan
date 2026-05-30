<template>
  <nav class="marketing-nav">
    <div class="marketing-container marketing-nav-row">
      <a class="marketing-brand" href="/" aria-label="返回句龙 · 照胆着陆页首页">
        <span class="marketing-brand-mark">句</span>
        <span>句龙 · 照胆 <small>GOULONG ZHAODAN</small></span>
      </a>

      <div class="marketing-links" aria-label="着陆页导航">
        <a href="/solution.html">解决方案</a>
        <a href="/security.html">数据安全</a>
        <a href="/cases.html">客户案例</a>
        <a href="/pricing.html">版本与定价</a>
      </div>

      <div class="marketing-actions">
        <a class="btn btn-ghost" href="/dashboard">登录</a>
        <a class="btn btn-primary" href="/pricing.html">开始体验</a>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.marketing-nav {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: 1px solid rgba(212, 175, 55, 0.25);
  background: rgba(10, 10, 10, 0.88);
  backdrop-filter: blur(16px);
}

.marketing-container {
  width: min(1200px, calc(100% - 40px));
  margin: 0 auto;
}

.marketing-nav-row {
  min-height: 72px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 32px;
  align-items: center;
}

.marketing-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: #e5e2e1;
  text-decoration: none;
  font-family: "Syne", "Noto Serif SC", serif;
  font-weight: 800;
}

.marketing-brand-mark {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ffe088, #d4af37 58%, #735c00);
  color: #0a0a0a;
  box-shadow: 0 0 16px rgba(212, 175, 55, 0.28);
}

.marketing-brand small {
  display: block;
  margin-top: 2px;
  color: #d0c5af;
  font-family: "JetBrains Mono", monospace;
  font-size: 8px;
  letter-spacing: 0.18em;
}

.marketing-links {
  display: flex;
  justify-content: center;
  gap: 28px;
}

.marketing-links a {
  color: #d0c5af;
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.marketing-links a:hover {
  color: #f2ca50;
}

.marketing-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

@media (max-width: 860px) {
  .marketing-nav-row {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 14px 0;
  }

  .marketing-links {
    justify-content: flex-start;
    gap: 18px;
    overflow-x: auto;
  }

  .marketing-actions {
    flex-wrap: wrap;
  }
}
</style>
