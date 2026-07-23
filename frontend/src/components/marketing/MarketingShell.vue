<script setup>
import MarketingFooter from './MarketingFooter.vue'
import MarketingNavbar from './MarketingNavbar.vue'
</script>

<template>
  <div class="marketing-shell">
    <MarketingNavbar />
    <slot />
    <MarketingFooter />
  </div>
</template>

<style scoped>
.marketing-shell {
  min-height: 100vh;
  color: var(--text);
  background:
    radial-gradient(circle at 50% 8%, color-mix(in srgb, var(--gold) 16%, transparent), transparent 28%),
    linear-gradient(color-mix(in srgb, var(--gold) 3.5%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--gold) 3.5%, transparent) 1px, transparent 1px),
    var(--bg);
  background-size: auto, 64px 64px, 64px 64px, auto;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
}

:global(html[data-theme="light"]) .marketing-shell {
  background:
    radial-gradient(circle at 78% 4%, var(--color-cyber-glow), transparent 28%),
    radial-gradient(circle at 18% 18%, var(--color-primary-glow), transparent 32%),
    linear-gradient(rgba(115, 88, 23, 0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 109, 115, 0.12) 1px, transparent 1px),
    linear-gradient(180deg, var(--surface) 0%, var(--bg) 48%, var(--surface-2) 100%);
  background-size: auto, auto, 64px 64px, 64px 64px, auto;
}
</style>
