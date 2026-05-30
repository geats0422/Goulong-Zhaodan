<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { applyThemeMode, getStoredThemeMode, persistThemeMode } from '../../theme'

defineProps({
  active: { type: String, required: true },
})

const router = useRouter()
const showNotifications = ref(false)
const showAccountMenu = ref(false)
const showThemeMenu = ref(false)
const themeMode = ref('system')
let systemThemeQuery

const themeOptions = [
  { label: '深色', value: 'dark', icon: 'dark_mode' },
  { label: '浅色', value: 'light', icon: 'light_mode' },
  { label: '系统配置', value: 'system', icon: 'routine' },
]

const navItems = [
  { label: '靶场', href: '/dashboard', key: 'dashboard' },
  { label: '体检台', href: '/history', key: 'inspection' },
  { label: '知识库', href: '/knowledge-base', key: 'knowledge' },
  { label: '数据统计', href: '/statistics', key: 'statistics' },
  { label: '设置', href: '/settings', key: 'settings' },
]

const toggleNotifications = () => {
  showNotifications.value = !showNotifications.value
  showAccountMenu.value = false
  showThemeMenu.value = false
}

const toggleAccountMenu = () => {
  showAccountMenu.value = !showAccountMenu.value
  showNotifications.value = false
  showThemeMenu.value = false
}

const selectThemeMode = (mode) => {
  themeMode.value = mode
  persistThemeMode(mode)
  showThemeMenu.value = false
}

const toggleThemeMenu = () => {
  showThemeMenu.value = !showThemeMenu.value
  showNotifications.value = false
  showAccountMenu.value = false
}

const goToSettings = () => {
  showNotifications.value = false
  showAccountMenu.value = false
  showThemeMenu.value = false
  router.push('/settings')
}

const activeThemeOption = computed(() => themeOptions.find((item) => item.value === themeMode.value) ?? themeOptions[2])

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
  <nav class="dashboard-nav">
    <div class="dashboard-nav-inner">
      <a class="dashboard-brand" href="/dashboard">
        <span class="material-symbols-outlined">security</span>
        <span>句龙 · 照胆</span>
      </a>

      <div class="dashboard-links">
        <a v-for="item in navItems" :key="item.key" :class="{ active: item.key === active }" :href="item.href">
          {{ item.label }}
        </a>
      </div>

      <div class="dashboard-actions">
        <div class="nav-popover-anchor">
          <button class="icon-button" type="button" :aria-label="`主题：${activeThemeOption.label}`" :aria-expanded="showThemeMenu" @click="toggleThemeMenu">
            <span class="material-symbols-outlined">{{ activeThemeOption.icon }}</span>
          </button>
          <div v-if="showThemeMenu" class="theme-menu" role="menu" aria-label="主题切换">
            <span class="hud-corner corner-tl"></span>
            <span class="hud-corner corner-br"></span>
            <p class="popover-kicker">THEME MODE</p>
            <button v-for="option in themeOptions" :key="option.value" type="button" role="menuitemradio" :aria-checked="themeMode === option.value" :class="{ active: themeMode === option.value }" @click="selectThemeMode(option.value)">
              <span class="material-symbols-outlined">{{ option.icon }}</span>
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="nav-popover-anchor">
          <button class="icon-button" type="button" aria-label="通知" :aria-expanded="showNotifications" @click="toggleNotifications">
            <span class="material-symbols-outlined">notifications</span>
          </button>
          <div v-if="showNotifications" class="notification-panel" role="dialog" aria-label="通知">
            <span class="hud-corner corner-tl"></span>
            <span class="hud-corner corner-br"></span>
            <p class="popover-kicker">NOTIFICATION NODE</p>
            <div class="notification-empty">无待处理工作</div>
          </div>
        </div>

        <button class="icon-button" type="button" aria-label="进入设置页面" @click="goToSettings">
          <span class="material-symbols-outlined">settings</span>
        </button>

        <div class="nav-popover-anchor">
          <button class="avatar-button" type="button" aria-label="用户菜单" :aria-expanded="showAccountMenu" @click="toggleAccountMenu">张</button>
          <div v-if="showAccountMenu" class="account-menu" role="menu" aria-label="用户菜单">
            <span class="hud-corner corner-tl"></span>
            <span class="hud-corner corner-br"></span>
            <button type="button" role="menuitem">
              <span class="material-symbols-outlined">switch_account</span>
              切换账号
            </button>
            <button type="button" role="menuitem">
              <span class="material-symbols-outlined">logout</span>
              退出账号
            </button>
            <div class="account-menu-links">
              <a href="/security.html" role="menuitem">隐私协议</a>
              <a href="/pricing.html" role="menuitem">服务条款</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.nav-popover-anchor {
  position: relative;
  display: inline-flex;
}

.icon-button:focus-visible,
.avatar-button:focus-visible,
.notification-panel:focus-visible,
.account-menu button:focus-visible,
.theme-menu button:focus-visible,
.account-menu a:focus-visible {
  outline: 2px solid #f2ca50;
  outline-offset: 2px;
}

.notification-panel,
.theme-menu,
.account-menu {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 80;
  border: 1px solid rgba(212, 175, 55, 0.46);
  background: linear-gradient(180deg, rgba(32, 31, 31, 0.98), rgba(14, 14, 14, 0.98));
  color: #e5e2e1;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.44), 0 0 18px rgba(212, 175, 55, 0.14);
  backdrop-filter: blur(20px);
}

.notification-panel {
  width: 260px;
  padding: 18px;
}

.popover-kicker {
  margin: 0 0 12px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-align: center;
}

.hud-corner {
  position: absolute;
  width: 10px;
  height: 10px;
  border-color: #d4af37;
  border-style: solid;
}

.corner-tl {
  top: -1px;
  left: -1px;
  border-width: 1px 0 0 1px;
}

.corner-br {
  right: -1px;
  bottom: -1px;
  border-width: 0 1px 1px 0;
}

.notification-empty {
  min-height: 74px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(212, 175, 55, 0.2);
  background: rgba(229, 226, 225, 0.04);
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 16px;
}

.account-menu {
  width: 260px;
  padding: 16px;
}

.theme-menu {
  width: 210px;
  padding: 16px;
}

.account-menu::before,
.theme-menu::before {
  content: "";
  position: absolute;
  top: 0;
  left: 18px;
  right: 18px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.82), transparent);
}

.account-menu button,
.theme-menu button {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 10px;
  border: 1px solid rgba(153, 144, 124, 0.42);
  border-radius: 999px;
  background: rgba(229, 226, 225, 0.08);
  color: #e5e2e1;
  cursor: pointer;
  font-size: 14px;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.account-menu button:hover,
.theme-menu button:hover,
.theme-menu button.active,
.account-menu a:hover {
  border-color: #d4af37;
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
}

.account-menu button .material-symbols-outlined,
.theme-menu button .material-symbols-outlined {
  font-size: 18px;
}

.account-menu-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 16px;
}

.account-menu-links a {
  border: 0;
  padding: 8px 0;
  color: #99907c;
  text-align: center;
  text-decoration: none;
  font-family: "Geist", monospace;
  font-size: 12px;
}

@media (max-width: 640px) {
  .notification-panel,
  .theme-menu,
  .account-menu {
    right: auto;
    left: 0;
  }
}
</style>
