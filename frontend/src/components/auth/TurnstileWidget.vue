<template>
  <div ref="container" class="turnstile-widget"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const SITE_KEY = '0x4AAAAAADstOBdaF-1EZNQZ'
const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'

const container = ref(null)
const widgetId = ref(null)
const token = ref('')

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
    script.onerror = () => reject(new Error('Turnstile script load failed'))
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
    'error-callback': () => { token.value = '' },
  })
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
.turnstile-widget {
  min-height: 65px;
  display: flex;
  justify-content: center;
}
</style>
