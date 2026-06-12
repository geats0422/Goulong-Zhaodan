import { ref, onMounted } from 'vue'
import { applyThemeMode, getStoredThemeMode } from '../theme.js'

const theme = ref('dark')

function syncTheme() {
  const mode = getStoredThemeMode()
  theme.value = mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : mode
}

function toggleTheme() {
  const next = theme.value === 'dark' ? 'light' : 'dark'
  applyThemeMode(next)
  theme.value = next
}

onMounted(() => {
  syncTheme()
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', syncTheme)
})

export function useTheme() {
  return { theme, toggleTheme }
}
