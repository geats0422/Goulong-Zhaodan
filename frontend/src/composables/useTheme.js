import { computed, ref } from 'vue'
import { applyThemeMode, getStoredThemeMode, getSystemTheme, persistThemeMode } from '../theme.js'

const themeMode = ref(getStoredThemeMode())
const theme = ref(getSystemTheme())
let initialized = false
let systemThemeQuery

function syncTheme() {
  theme.value = themeMode.value === 'system' ? getSystemTheme() : themeMode.value
  applyThemeMode(themeMode.value)
}

function initializeTheme() {
  if (initialized) return
  initialized = true
  themeMode.value = getStoredThemeMode()
  syncTheme()
  systemThemeQuery = window.matchMedia('(prefers-color-scheme: light)')
  systemThemeQuery.addEventListener('change', syncTheme)
}

function setThemeMode(mode) {
  if (!['dark', 'light', 'system'].includes(mode)) return
  themeMode.value = mode
  persistThemeMode(mode)
  syncTheme()
}

function toggleTheme() {
  const next = theme.value === 'dark' ? 'light' : 'dark'
  setThemeMode(next)
}

export { initializeTheme }

export function useTheme() {
  initializeTheme()
  return { theme, themeMode: computed(() => themeMode.value), setThemeMode, toggleTheme }
}
