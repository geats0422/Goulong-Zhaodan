<script setup>
import { nextTick, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import QRCode from 'qrcode'
import { createAlipayPageOrder, createNativeOrder, getOrderStatus } from '../services/paymentApi.js'

const props = defineProps({
  productCode: { type: String, required: true },
  productName: { type: String, default: '' },
  amountLabel: { type: String, default: '' },
})
const emit = defineEmits(['paid', 'close'])

const loading = ref(true)
const error = ref('')
const codeUrl = ref('')
const qrDataUrl = ref('')
const orderId = ref(null)
const status = ref('pending')
const payMethod = ref('wechat')
const alipayUrl = ref('')
const modalRef = ref(null)
const closeButtonRef = ref(null)
let previouslyFocusedElement = null

let pollTimer = null
const QR_SIZE = 240
const FOCUSABLE_SELECTOR = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

async function renderQr(url) {
  if (!url) {
    qrDataUrl.value = ''
    throw new Error('微信支付未返回二维码链接')
  }
  qrDataUrl.value = await QRCode.toDataURL(url, {
    width: QR_SIZE,
    margin: 1,
    color: {
      dark: '#0A0A0A',
      light: '#ffffff',
    },
  })
}

async function initOrder(method = payMethod.value) {
  stopPolling()
  loading.value = true
  error.value = ''
  codeUrl.value = ''
  qrDataUrl.value = ''
  alipayUrl.value = ''
  payMethod.value = method
  try {
    if (method === 'wechat') {
      const data = await createNativeOrder(props.productCode)
      orderId.value = data.order_id
      codeUrl.value = data.code_url
      status.value = 'pending'
      await renderQr(data.code_url)
    } else {
      const data = await createAlipayPageOrder(props.productCode)
      orderId.value = data.order_id
      alipayUrl.value = data.pay_url
      status.value = 'pending'
      window.open(data.pay_url, '_blank', 'noopener,noreferrer')
    }
    startPolling()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!orderId.value) return
    try {
      const data = await getOrderStatus(orderId.value)
      status.value = data.status
      if (data.status === 'paid') {
        stopPolling()
        emit('paid', data)
      } else if (data.status === 'closed') {
        stopPolling()
      } else if (data.status === 'failed') {
        stopPolling()
      }
    } catch {
      // 轮询失败静默忽略
    }
  }, 2500)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function openAlipayCashier() {
  if (alipayUrl.value) {
    window.open(alipayUrl.value, '_blank', 'noopener,noreferrer')
  }
}

function close() {
  emit('close')
}

function trapFocus(event) {
  const focusableElements = [...(modalRef.value?.querySelectorAll(FOCUSABLE_SELECTOR) ?? [])]
  if (!focusableElements.length) return

  const firstElement = focusableElements[0]
  const lastElement = focusableElements.at(-1)

  if (event.shiftKey && (document.activeElement === firstElement || !modalRef.value.contains(document.activeElement))) {
    event.preventDefault()
    lastElement.focus()
  } else if (!event.shiftKey && (document.activeElement === lastElement || !modalRef.value.contains(document.activeElement))) {
    event.preventDefault()
    firstElement.focus()
  }
}

onMounted(() => {
  previouslyFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null
  nextTick(() => closeButtonRef.value?.focus())
  initOrder()
})
onBeforeUnmount(() => {
  stopPolling()
  previouslyFocusedElement?.focus()
})

watch(() => props.productCode, () => initOrder(payMethod.value))
</script>

<template>
  <div class="payment-overlay" @click.self="close">
    <div ref="modalRef" class="payment-modal" role="dialog" aria-modal="true" aria-labelledby="payment-modal-title" tabindex="-1" @keydown.esc="close" @keydown.tab="trapFocus">
      <button ref="closeButtonRef" type="button" class="close-btn" @click="close" aria-label="关闭">
        <span class="material-symbols-outlined">close</span>
      </button>

      <header class="modal-header">
        <span class="modal-ref">REF.PAY-001</span>
        <h2 id="payment-modal-title">选择支付方式</h2>
        <p class="modal-sub" v-if="productName">{{ productName }}<span v-if="amountLabel"> · {{ amountLabel }}</span></p>
      </header>

      <div class="method-tabs">
        <button type="button" :class="{ active: payMethod === 'wechat' }" @click="initOrder('wechat')">微信</button>
        <button type="button" :class="{ active: payMethod === 'alipay' }" @click="initOrder('alipay')">支付宝</button>
      </div>

      <div v-if="error" class="error-box" role="alert">{{ error }}</div>

      <div v-if="loading" class="loading-box">
        <span class="material-symbols-outlined spin">progress_activity</span>
        <p>正在生成订单…</p>
      </div>

      <div v-else-if="status === 'paid'" class="success-box">
        <span class="material-symbols-outlined success-icon">check_circle</span>
        <p>支付成功</p>
      </div>

      <div v-else-if="status === 'closed'" class="closed-box">
        <span class="material-symbols-outlined">cancel</span>
        <p>订单已关闭</p>
      </div>

      <div v-else-if="status === 'failed'" class="closed-box">
        <span class="material-symbols-outlined" style="color:#c62828;">error</span>
        <p style="color:#c62828;">支付失败</p>
      </div>

      <div v-else-if="payMethod === 'alipay'" class="qr-section">
        <span class="material-symbols-outlined alipay-icon">open_in_new</span>
        <button type="button" class="alipay-btn" @click="openAlipayCashier">打开支付宝收银台</button>
        <p class="qr-hint">支付后请返回本页，系统会自动确认到账</p>
        <div class="status-row">
          <span class="dot pulse"></span>
          <span>等待支付…</span>
        </div>
      </div>

      <div v-else class="qr-section">
        <div class="qr-box">
          <img v-if="qrDataUrl" :src="qrDataUrl" alt="微信支付二维码">
        </div>
        <p class="qr-hint">请使用微信扫描二维码完成支付</p>
        <div class="status-row">
          <span class="dot pulse"></span>
          <span>等待支付…</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.payment-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.payment-modal {
  position: relative;
  width: min(560px, 92vw);
  background: #121212;
  border: 1px solid rgba(212, 175, 55, 0.25);
  box-shadow: 0 0 60px rgba(212, 175, 55, 0.1);
  padding: 40px 44px;
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  border: 0;
  background: transparent;
  color: #99907c;
  cursor: pointer;
  padding: 4px;
  transition: color 0.2s;
}

.close-btn:hover { color: #d4af37; }

.modal-header {
  text-align: center;
  margin-bottom: 24px;
}

.modal-ref {
  display: block;
  font: 500 10px/1 "JetBrains Mono", monospace;
  color: #d4af37;
  letter-spacing: 0.18em;
  margin-bottom: 8px;
}

.modal-header h2 {
  margin: 0 0 6px;
  font-family: "Syne", sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: #d4af37;
  letter-spacing: -0.01em;
}

.modal-sub {
  margin: 0;
  font-size: 13px;
  color: #99907c;
}

.method-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 18px;
}

.method-tabs button {
  padding: 10px 12px;
  border: 1px solid rgba(212, 175, 55, 0.3);
  background: transparent;
  color: #99907c;
  cursor: pointer;
  font-weight: 600;
}

.method-tabs button.active {
  background: #d4af37;
  color: #121212;
}

.error-box {
  padding: 12px 16px;
  margin-bottom: 16px;
  color: #ffb4ab;
  background: rgba(255, 180, 171, 0.08);
  border: 1px solid rgba(255, 180, 171, 0.3);
  font-size: 13px;
  text-align: center;
}

.loading-box, .success-box, .closed-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
  color: #99907c;
}

.loading-box .material-symbols-outlined {
  font-size: 32px;
  color: #d4af37;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.success-icon {
  font-size: 48px !important;
  color: #66bb6a !important;
}

.qr-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.qr-box {
  width: 272px;
  height: 272px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #fff;
}

.qr-box :deep(canvas), .qr-box :deep(img) {
  display: block;
  width: 240px !important;
  height: 240px !important;
}

.qr-hint {
  font-size: 13px;
  color: #e5e2e1;
}

.alipay-icon {
  font-size: 64px;
  color: #1677ff;
}

.alipay-btn {
  padding: 12px 18px;
  border: 1px solid #1677ff;
  background: #1677ff;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #99907c;
  letter-spacing: 0.1em;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d4af37;
}

.pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
