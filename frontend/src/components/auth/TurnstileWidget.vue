<template>
  <div class="turnstile-shell" :class="{ 'has-error': hasError }">
    <div ref="container" class="turnstile-widget"></div>
    <div v-if="statusMessage" class="turnstile-status" role="status">
      <span>{{ statusMessage }}</span>
      <button v-if="hasError" type="button" class="turnstile-retry" @click="retry">
        重新加载
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const DEFAULT_SITE_KEY = '0x4AAAAAADstOBdaF-1EZNQZ'
const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const LOAD_TIMEOUT_MS = 8000

const container = ref(null)
const widgetId = ref(null)
const token = ref('')
const statusMessage = ref('正在载入人机验证…')
const hasError = ref(false)

let scriptLoadPromise = null
let timeoutId = null

function getSiteKey() {
  return window.TURNSTILE_SITE_KEY || DEFAULT_SITE_KEY
}

function clearLoadTimeout() {
  if (timeoutId) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
}

function loadScript() {
  if (window.turnstile) return Promise.resolve()
  if (scriptLoadPromise) return scriptLoadPromise
  scriptLoadPromise = new Promise((resolve, reject) => {
    timeoutId = setTimeout(() => reject(new Error('Turnstile script load timed out')), LOAD_TIMEOUT_MS)
    const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => { clearLoadTimeout(); resolve() }, { once: true })
      existing.addEventListener('error', reject, { once: true })
      return
    }
    const script = document.createElement('script')
    script.src = SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => { clearLoadTimeout(); resolve() }
    script.onerror = () => {
      scriptLoadPromise = null
      reject(new Error('Turnstile script load failed'))
    }
    document.head.appendChild(script)
  })
  return scriptLoadPromise
}

function renderWidget() {
  if (!container.value || !window.turnstile) return
  widgetId.value = window.turnstile.render(container.value, {
    sitekey: getSiteKey(),
    theme: 'dark',
    callback: (val) => {
      token.value = val
      hasError.value = false
      statusMessage.value = ''
    },
    'expired-callback': () => {
      token.value = ''
      statusMessage.value = '人机验证已过期，请重新验证'
    },
    'error-callback': () => {
      token.value = ''
      hasError.value = true
      statusMessage.value = '人机验证加载异常，请检查网络后重试'
    },
  })
  if (widgetId.value === undefined || widgetId.value === null) {
    hasError.value = true
    statusMessage.value = '人机验证加载异常，请刷新页面后重试'
    return
  }
  hasError.value = false
  statusMessage.value = ''
}

function reset() {
  token.value = ''
  if (widgetId.value !== null && window.turnstile) {
    window.turnstile.reset(widgetId.value)
  }
}

function removeWidget() {
  if (widgetId.value !== null && window.turnstile) {
    window.turnstile.remove(widgetId.value)
  }
  widgetId.value = null
}

async function init() {
  hasError.value = false
  statusMessage.value = '正在载入人机验证…'
  try {
    await loadScript()
    renderWidget()
  } catch (e) {
    hasError.value = true
    statusMessage.value = '人机验证无法加载，请检查网络后重试'
    scriptLoadPromise = null
    clearLoadTimeout()
    console.error('Turnstile init failed:', e)
  }
}

function retry() {
  token.value = ''
  removeWidget()
  document.querySelector(`script[src="${SCRIPT_SRC}"]`)?.remove()
  scriptLoadPromise = null
  init()
}

defineExpose({ token, reset })

onMounted(init)

onBeforeUnmount(() => {
  clearLoadTimeout()
  removeWidget()
})
</script>

<style scoped>
.turnstile-shell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.turnstile-widget {
  min-height: 65px;
  display: flex;
  justify-content: center;
}

.turnstile-status {
  margin: 0;
  color: #d0c5af;
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.turnstile-retry {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
  padding: 0;
}

.turnstile-shell.has-error .turnstile-status {
  color: #ffb4a8;
}

[data-theme="light"] .turnstile-status {
  color: #66563a;
}

[data-theme="light"] .turnstile-shell.has-error .turnstile-status {
  color: #8f2c24;
}
</style>
