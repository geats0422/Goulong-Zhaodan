<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
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
const orderId = ref(null)
const status = ref('pending')
const payMethod = ref('wechat')
const alipayUrl = ref('')
const qrContainer = ref(null)

let pollTimer = null
let qrInstance = null

const QR_CDN = 'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js'

function loadQrScript() {
  if (window.QRCode) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = QR_CDN
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

function renderQr(url) {
  if (!qrContainer.value || !window.QRCode) return
  qrContainer.value.innerHTML = ''
  qrInstance = new window.QRCode(qrContainer.value, {
    text: url,
    width: 200,
    height: 200,
    colorDark: '#0A0A0A',
    colorLight: '#ffffff',
  })
}

async function initOrder(method = payMethod.value) {
  stopPolling()
  loading.value = true
  error.value = ''
  codeUrl.value = ''
  alipayUrl.value = ''
  payMethod.value = method
  try {
    if (method === 'wechat') {
      const data = await createNativeOrder(props.productCode)
      orderId.value = data.order_id
      codeUrl.value = data.code_url
      status.value = 'pending'
      await loadQrScript()
      renderQr(data.code_url)
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

onMounted(initOrder)
onBeforeUnmount(() => {
  stopPolling()
  if (qrInstance && qrContainer.value) {
    qrContainer.value.innerHTML = ''
  }
})

watch(() => props.productCode, () => initOrder(payMethod.value))
</script>

<template>
  <div class="payment-overlay" @click.self="emit('close')">
    <div class="payment-modal">
      <button class="close-btn" @click="emit('close')" aria-label="关闭">
        <span class="material-symbols-outlined">close</span>
      </button>

      <header class="modal-header">
        <span class="modal-ref">REF.PAY-001</span>
        <h2>选择支付方式</h2>
        <p class="modal-sub" v-if="productName">{{ productName }}<span v-if="amountLabel"> · {{ amountLabel }}</span></p>
      </header>

      <div class="method-tabs">
        <button :class="{ active: payMethod === 'wechat' }" @click="initOrder('wechat')">微信</button>
        <button :class="{ active: payMethod === 'alipay' }" @click="initOrder('alipay')">支付宝</button>
      </div>

      <div v-if="error" class="error-box">{{ error }}</div>

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
        <button class="alipay-btn" @click="openAlipayCashier">打开支付宝收银台</button>
        <p class="qr-hint">支付后请返回本页，系统会自动确认到账</p>
        <div class="status-row">
          <span class="dot pulse"></span>
          <span>等待支付…</span>
        </div>
      </div>

      <div v-else class="qr-section">
        <div ref="qrContainer" class="qr-box"></div>
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
  width: min(420px, 90vw);
  background: #121212;
  border: 1px solid rgba(212, 175, 55, 0.25);
  box-shadow: 0 0 60px rgba(212, 175, 55, 0.1);
  padding: 32px 28px;
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
  padding: 16px;
  background: #fff;
}

.qr-box :deep(canvas), .qr-box :deep(img) {
  display: block;
}

.qr-hint {
  font-size: 13px;
  color: #e5e2e1;
}

.alipay-icon {
  font-size: 48px;
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
