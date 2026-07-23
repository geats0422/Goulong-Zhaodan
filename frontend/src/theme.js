export const THEME_STORAGE_KEY = 'goulong-theme-mode'

export const themeModes = ['dark', 'light', 'system']

export const getSystemTheme = () => (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')

export const getStoredThemeMode = () => {
  const savedThemeMode = localStorage.getItem(THEME_STORAGE_KEY)

  return themeModes.includes(savedThemeMode) ? savedThemeMode : 'system'
}

export const applyThemeMode = (mode) => {
  const resolvedTheme = mode === 'system' ? getSystemTheme() : mode

  document.documentElement.dataset.themeMode = mode
  document.documentElement.dataset.theme = resolvedTheme
}

export const persistThemeMode = (mode) => {
  if (!themeModes.includes(mode)) return
  localStorage.setItem(THEME_STORAGE_KEY, mode)
  applyThemeMode(mode)
}
