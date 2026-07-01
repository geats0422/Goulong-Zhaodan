<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { applyThemeMode, getStoredThemeMode, persistThemeMode } from '../../theme'

const showThemeMenu = ref(false)
const themeMode = ref('system')
let systemThemeQuery

const themeOptions = [
  { label: '深色', value: 'dark', icon: 'dark_mode' },
  { label: '浅色', value: 'light', icon: 'light_mode' },
  { label: '系统配置', value: 'system', icon: 'routine' },
]

const activeThemeOption = computed(() => themeOptions.find((item) => item.value === themeMode.value) ?? themeOptions[2])

const toggleThemeMenu = () => {
  showThemeMenu.value = !showThemeMenu.value
}

const selectThemeMode = (mode) => {
  themeMode.value = mode
  persistThemeMode(mode)
  showThemeMenu.value = false
}

const handleSystemThemeChange = () => {
  if (themeMode.value === 'system') {
    applyThemeMode('system')
  }
}

onMounted(() => {
  themeMode.value = getStoredThemeMode()
  systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)')
  systemThemeQuery.addEventListener('change', handleSystemThemeChange)
  applyThemeMode(themeMode.value)
})

onBeforeUnmount(() => {
  systemThemeQuery?.removeEventListener('change', handleSystemThemeChange)
})
</script>

<template>
  <nav class="marketing-nav">
    <div class="marketing-container marketing-nav-row">
      <a class="marketing-brand" href="/" aria-label="返回句龙 · 照胆着陆页首页">
        <span class="marketing-brand-mark">句</span>
        <span>句龙 · 照胆 <small>GOULONG ZHAODAN</small></span>
      </a>

      <div class="marketing-links" aria-label="着陆页导航">
        <a href="/solution">解决方案</a>
        <a href="/security">数据安全</a>
        <a href="/cases">客户案例</a>
        <a href="/pricing">版本与定价</a>
        <a href="/docs">开发文档</a>
      </div>

      <div class="marketing-actions">
        <div class="marketing-popover-anchor">
          <button class="marketing-theme-button" type="button" :aria-label="`主题：${activeThemeOption.label}`" :aria-expanded="showThemeMenu" @click="toggleThemeMenu">
            <span class="material-symbols-outlined">{{ activeThemeOption.icon }}</span>
          </button>
          <div v-if="showThemeMenu" class="marketing-theme-menu" role="menu" aria-label="主题切换">
            <p>THEME MODE</p>
            <button v-for="option in themeOptions" :key="option.value" type="button" role="menuitemradio" :aria-checked="themeMode === option.value" :class="{ active: themeMode === option.value }" @click="selectThemeMode(option.value)">
              <span class="material-symbols-outlined">{{ option.icon }}</span>
              {{ option.label }}
            </button>
          </div>
        </div>
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
  border-bottom: 1px solid color-mix(in srgb, var(--gold) 25%, transparent);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
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
  color: var(--text);
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
  background: linear-gradient(135deg, #ffe088, var(--gold) 58%, #735c00);
  color: var(--text);
  box-shadow: 0 0 16px rgba(212, 175, 55, 0.28);
}

.marketing-brand small {
  display: block;
  margin-top: 2px;
  color: var(--muted);
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
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.marketing-links a:hover {
  color: var(--gold);
}

.marketing-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.marketing-popover-anchor {
  position: relative;
  display: inline-flex;
}

.marketing-theme-button {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface-2) 68%, transparent);
  color: var(--muted);
  cursor: pointer;
}

.marketing-theme-button:hover,
.marketing-theme-button:focus-visible {
  border-color: var(--gold);
  color: var(--gold);
  outline: none;
}

.marketing-theme-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 80;
  width: 210px;
  border: 1px solid color-mix(in srgb, var(--gold) 46%, transparent);
  padding: 16px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface-2) 98%, transparent), color-mix(in srgb, var(--bg) 98%, transparent));
  color: var(--text);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28), 0 0 18px color-mix(in srgb, var(--gold) 14%, transparent);
  backdrop-filter: blur(20px);
}

.marketing-theme-menu p {
  margin: 0 0 12px;
  color: var(--muted);
  font-family: "Geist", monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-align: center;
}

.marketing-theme-menu button {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 76%, transparent);
  color: var(--text);
  cursor: pointer;
}

.marketing-theme-menu button:hover,
.marketing-theme-menu button.active {
  border-color: var(--gold);
  background: var(--gold-soft);
  color: var(--gold);
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

  .marketing-theme-menu {
    right: auto;
    left: 0;
  }
}
</style>
