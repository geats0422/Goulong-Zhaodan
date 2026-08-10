<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuth } from '../composables/useAuth.js'
import { bindPhone } from '../services/settingsApi.js'

const props = defineProps({
  title: { type: String, default: '绑定手机号' },
  description: { type: String, default: '绑定后可使用手机号快捷登录，也方便找回账户。' },
  skipLabel: { type: String, default: '稍后绑定' },
})

const emit = defineEmits(['complete', 'skip'])
const { sendSmsCode, updateCurrentUserPhone } = useAuth()

const dialog = ref(null)
const phoneInput = ref(null)
const continueButton = ref(null)
const phone = ref('')
const code = ref('')
const error = ref('')
const success = ref(false)
const sending = ref(false)
const submitting = ref(false)
const countdown = ref(0)

let timer = null
let previouslyFocusedElement = null

const phoneValid = () => /^1[3-9]\d{9}$/.test(phone.value)

function startCountdown(seconds = 60) {
  if (timer) clearInterval(timer)
  countdown.value = Math.max(1, Math.min(Number(seconds) || 60, 60))
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(timer)
      timer = null
      countdown.value = 0
    }
  }, 1000)
}

async function sendCode() {
  if (!phoneValid() || sending.value || countdown.value > 0) return
  error.value = ''
  sending.value = true
  try {
    const result = await sendSmsCode(phone.value, 'login')
    startCountdown(result?.expires_in)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '验证码发送失败'
  } finally {
    sending.value = false
  }
}

async function submit() {
  if (submitting.value) return
  error.value = ''
  if (!phoneValid()) {
    error.value = '手机号格式错误'
    return
  }
  if (!/^\d{6}$/.test(code.value)) {
    error.value = '验证码必须为 6 位数字'
    return
  }

  submitting.value = true
  try {
    const result = await bindPhone({ phone: phone.value, code: code.value })
    updateCurrentUserPhone(result?.phone || phone.value)
    success.value = true
    await nextTick()
    continueButton.value?.focus()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '绑定失败'
  } finally {
    submitting.value = false
  }
}

function skip() {
  if (!submitting.value && !success.value) emit('skip')
}

function complete() {
  emit('complete', { phone: phone.value })
}

function focusableElements() {
  return [...dialog.value?.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
  ) || []]
}

function trapFocus(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    skip()
    return
  }
  if (event.key !== 'Tab') return
  const elements = focusableElements()
  if (!elements.length) return
  const first = elements[0]
  const last = elements[elements.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(async () => {
  previouslyFocusedElement = document.activeElement
  await nextTick()
  phoneInput.value?.focus()
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (previouslyFocusedElement?.isConnected) previouslyFocusedElement.focus()
})
</script>

<template>
  <div
    ref="dialog"
    class="phone-binding-modal modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="phone-binding-title"
    tabindex="-1"
    @keydown="trapFocus"
  >
    <div class="phone-binding-card modal-card modal-card-sm" @click.stop>
      <header class="modal-header">
        <div>
          <h2 id="phone-binding-title">{{ props.title }}</h2>
          <p class="modal-subtitle">{{ props.description }}</p>
        </div>
        <button v-if="!success" class="icon-btn" type="button" aria-label="关闭手机号绑定" @click="skip">
          <span class="material-symbols-outlined" aria-hidden="true">close</span>
        </button>
      </header>

      <div v-if="success" class="phone-binding-success modal-body" aria-live="polite">
        <strong>手机号绑定成功</strong>
        <span>账户安全信息已更新。</span>
        <button ref="continueButton" class="primary-btn" type="button" @click="complete">继续使用</button>
      </div>

      <form v-else class="phone-binding-form modal-body" @submit.prevent="submit">
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <label class="form-row" for="phone-binding-phone">
          <span>手机号码</span>
          <div class="phone-binding-input-row">
            <span class="phone-binding-prefix">+86</span>
            <input
              id="phone-binding-phone"
              ref="phoneInput"
              v-model="phone"
              name="phone-binding-phone"
              class="form-input"
              type="tel"
              inputmode="numeric"
              maxlength="11"
              autocomplete="tel"
              placeholder="请输入 11 位手机号码"
            />
          </div>
        </label>
        <label class="form-row" for="phone-binding-code">
          <span>验证码</span>
          <div class="code-input-row">
            <input
              id="phone-binding-code"
              v-model="code"
              name="phone-binding-code"
              class="form-input"
              type="text"
              inputmode="numeric"
              maxlength="6"
              autocomplete="one-time-code"
              placeholder="请输入短信验证码"
            />
            <button
              class="ghost-btn code-btn phone-binding-send"
              type="button"
              :disabled="!phoneValid() || sending || countdown > 0"
              @click="sendCode"
            >
              {{ sending ? '发送中...' : (countdown > 0 ? `${countdown}s` : '获取验证码') }}
            </button>
          </div>
        </label>
        <footer class="phone-binding-footer modal-footer">
          <button class="ghost-btn phone-binding-skip" type="button" @click="skip">{{ props.skipLabel }}</button>
          <button class="primary-btn phone-binding-confirm" type="submit" :disabled="submitting">
            {{ submitting ? '绑定中...' : '确认绑定' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<style scoped>
.phone-binding-modal {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.7);
  color: #e5e2e1;
}

.phone-binding-card {
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow: auto;
  border: 1px solid rgba(212, 175, 55, 0.3);
  background: #121212;
}

.phone-binding-card h2 { margin: 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 22px; }
.phone-binding-card .modal-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 20px 28px; border-bottom: 1px solid rgba(155, 116, 22, 0.2); }
.phone-binding-card .modal-subtitle { margin: 4px 0 0; color: #99907c; font-size: 13px; }
.phone-binding-card .modal-body { padding: 20px 28px; }
.phone-binding-card .modal-footer { display: flex; justify-content: flex-end; align-items: center; gap: 12px; padding: 16px 28px; border-top: 1px solid rgba(155, 116, 22, 0.2); }
.phone-binding-card .icon-btn { border: 0; padding: 4px; background: transparent; color: #99907c; cursor: pointer; }
.phone-binding-card .form-row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.phone-binding-card .form-row > span { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.08em; }
.phone-binding-card .form-input { width: 100%; box-sizing: border-box; border: 1px solid #4d4635; padding: 10px 14px; background: #0a0a0a; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; outline: none; border-radius: 0.25rem; }
.phone-binding-card .form-input:focus { border-color: #d4af37; box-shadow: 0 0 12px rgba(212, 175, 55, 0.3); }
.phone-binding-card .ghost-btn,
.phone-binding-card .primary-btn { border-radius: 0.25rem; padding: 10px 18px; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; cursor: pointer; }
.phone-binding-card .ghost-btn { border: 1px solid rgba(212, 175, 55, 0.4); background: transparent; color: #f2ca50; }
.phone-binding-card .primary-btn { border: 1px solid #d4af37; background: #d4af37; color: #1a1410; }
.phone-binding-card button:disabled { cursor: not-allowed; opacity: 0.5; }
.phone-binding-card .form-error { margin: 0 0 16px; padding: 8px 12px; border: 1px solid rgba(255, 180, 171, 0.3); background: rgba(255, 180, 171, 0.05); color: #ffb4ab; font-size: 13px; }
.phone-binding-card .code-input-row { display: flex; align-items: center; gap: 10px; }
.phone-binding-card .code-input-row .form-input { flex: 1; }
.phone-binding-card .code-btn { min-width: 104px; white-space: nowrap; }
.phone-binding-input-row { display: flex; align-items: center; gap: 10px; }
.phone-binding-input-row .form-input { flex: 1; }
.phone-binding-prefix { color: #f2ca50; font-family: "JetBrains Mono", monospace; font-size: 13px; }
.phone-binding-footer { margin: 0 -28px -20px; }
.phone-binding-success { display: flex; flex-direction: column; gap: 12px; }
.phone-binding-success strong { color: #34d399; font-size: 16px; }
.phone-binding-success span { color: #99907c; font-size: 13px; }
@media (max-width: 520px) {
  .phone-binding-modal { align-items: flex-end; padding: 12px; }
  .phone-binding-card { max-height: calc(100vh - 24px); }
  .phone-binding-footer { flex-wrap: wrap; }
  .phone-binding-footer button { flex: 1; }
}
</style>
