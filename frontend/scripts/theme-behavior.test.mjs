import assert from 'node:assert/strict'

const storage = new Map()
globalThis.localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
}
globalThis.document = { documentElement: { dataset: {} } }
globalThis.window = {
  matchMedia: () => ({ matches: false }),
}

const { THEME_STORAGE_KEY, getStoredThemeMode, persistThemeMode } = await import('../src/theme.js')

assert.equal(getStoredThemeMode(), 'system')
persistThemeMode('light')
assert.equal(storage.get(THEME_STORAGE_KEY), 'light')
assert.equal(document.documentElement.dataset.themeMode, 'light')
assert.equal(document.documentElement.dataset.theme, 'light')
persistThemeMode('system')
assert.equal(document.documentElement.dataset.themeMode, 'system')
assert.equal(document.documentElement.dataset.theme, 'dark')

console.log('theme behavior passed')
