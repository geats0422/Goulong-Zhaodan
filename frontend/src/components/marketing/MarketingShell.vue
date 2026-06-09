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

[data-theme="light"] .marketing-shell {
  background:
    radial-gradient(circle at 75% 0%, rgba(155, 116, 22, 0.12), transparent 30%),
    linear-gradient(rgba(155, 116, 22, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(155, 116, 22, 0.055) 1px, transparent 1px),
    linear-gradient(180deg, var(--surface) 0%, var(--bg) 46%, var(--surface-2) 100%);
  background-size: auto, 64px 64px, 64px 64px, auto;
}
</style>
