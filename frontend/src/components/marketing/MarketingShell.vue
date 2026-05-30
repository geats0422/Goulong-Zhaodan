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
  color: #e5e2e1;
  background:
    radial-gradient(circle at 50% 8%, rgba(212, 175, 55, 0.16), transparent 28%),
    linear-gradient(rgba(212, 175, 55, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(212, 175, 55, 0.035) 1px, transparent 1px),
    #0a0a0a;
  background-size: auto, 64px 64px, 64px 64px, auto;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
}
</style>
