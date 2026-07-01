<template>
  <div class="turnstile-shell" :class="{ 'has-error': hasError }">
    <div ref="container" class="turnstile-widget"></div>
    <p v-if="statusMessage" class="turnstile-status" role="status">
      {{ statusMessage }}
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const SITE_KEY = '0x4AAAAAADstOBdaF-1EZNQZ'
const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

const container = ref(null)
const widgetId = ref(null)
const token = ref('')
const statusMessage = ref('正在载入人机验证…')
const hasError = ref(false)

let scriptLoadPromise = null

function loadScript() {
  if (window.turnstile) return Promise.resolve()
  if (scriptLoadPromise) return scriptLoadPromise
  scriptLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
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
    sitekey: SITE_KEY,
    theme: 'dark',
    callback: (val) => { token.value = val },
    'expired-callback': () => { token.value = '' },
    'error-callback': () => {
      token.value = ''
      hasError.value = true
      statusMessage.value = '人机验证加载异常，请刷新页面后重试'
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

defineExpose({ token, reset })

onMounted(async () => {
  try {
    await loadScript()
    renderWidget()
  } catch (e) {
    hasError.value = true
    statusMessage.value = '人机验证无法加载，请检查网络后刷新页面'
    console.error('Turnstile init failed:', e)
  }
})

onBeforeUnmount(() => {
  if (widgetId.value !== null && window.turnstile) {
    window.turnstile.remove(widgetId.value)
  }
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
