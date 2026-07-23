<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { useTheme } from '../composables/useTheme.js'

const { register, sendSmsCode, sendEmailCode } = useAuth()
const router = useRouter()
const { theme, toggleTheme } = useTheme()

const nickname = ref('')
const phone = ref('')
const phoneCode = ref('')
const email = ref('')
const emailCode = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)
const agreedToTerms = ref(false)

const showPassword = ref(false)
const showConfirm = ref(false)
const phoneCountdown = ref(0)
const phoneSending = ref(false)
const emailCountdown = ref(0)
const emailSending = ref(false)

const WEAK_PASSWORDS = new Set([
  'password', 'password1', 'password12', 'password123', 'password1234',
  '123456', '12345678', '1234567890', 'qwerty', 'abc123', 'admin', 'admin123',
  'root', 'test', 'guest', 'welcome', 'sunshine', 'letmein',
])

const ALLOWED_RE = /^[a-zA-Z0-9!@#$%^&*()_\-=\[\]{}|:;<>,.?\/~]*$/

const nicknameValid = computed(() => {
  const n = nickname.value.trim()
  return n.length >= 2 && n.length <= 30
})
const phoneValid = computed(() => /^1[3-9]\d{9}$/.test(phone.value))
const emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value))

const passwordRules = computed(() => {
  const p = password.value
  return [
    { label: '至少 8 个字符', pass: p.length >= 8 },
    { label: '至少一个大写字母', pass: /[A-Z]/.test(p) },
    { label: '至少一个小写字母', pass: /[a-z]/.test(p) },
    { label: '至少一个数字', pass: /[0-9]/.test(p) },
    { label: '不包含空格', pass: p.length === 0 || !/\s/.test(p) },
    { label: '只允许常见特殊字符', pass: ALLOWED_RE.test(p) },
    { label: '非常见弱密码', pass: p.length === 0 || !WEAK_PASSWORDS.has(p.toLowerCase()) },
  ]
})

const passwordStrength = computed(() => passwordRules.value.filter(r => r.pass).length)
const showRules = computed(() => password.value.length > 0)

const passwordValid = computed(() => passwordStrength.value === passwordRules.value.length)
const confirmValid = computed(() => confirmPassword.value.length > 0 && confirmPassword.value === password.value)

const phoneCodeValid = computed(() => phoneCode.value.length === 6)
const emailCodeValid = computed(() => emailCode.value.length === 6)

const canRegister = computed(() =>
  nicknameValid.value &&
  phoneValid.value && phoneCodeValid.value &&
  (emailValid.value ? emailCodeValid.value : true) &&
  passwordValid.value && confirmValid.value && agreedToTerms.value
)

let phoneTimer = null
let emailTimer = null

function startTimer(countdownRef, timerKey) {
  countdownRef.value = 60
  const timer = setInterval(() => {
    countdownRef.value -= 1
    if (countdownRef.value <= 0) {
      clearInterval(timer)
      if (timerKey === 'phone') phoneTimer = null
      else emailTimer = null
    }
  }, 1000)
  if (timerKey === 'phone') phoneTimer = timer
  else emailTimer = timer
}

onUnmounted(() => {
  if (phoneTimer) clearInterval(phoneTimer)
  if (emailTimer) clearInterval(emailTimer)
})

async function startSmsCountdown() {
  if (!phoneValid.value || phoneSending.value || phoneCountdown.value > 0) return
  phoneSending.value = true
  error.value = ''
  try {
    await sendSmsCode(phone.value, 'login')
    startTimer(phoneCountdown, 'phone')
  } catch (e) {
    error.value = e.message
  } finally {
    phoneSending.value = false
  }
}

async function startEmailCountdown() {
  if (!emailValid.value || emailSending.value || emailCountdown.value > 0) return
  emailSending.value = true
  error.value = ''
  try {
    await sendEmailCode(email.value)
    startTimer(emailCountdown, 'email')
  } catch (e) {
    error.value = e.message
  } finally {
    emailSending.value = false
  }
}

async function handleRegister() {
  error.value = ''
  if (!canRegister.value) {
    if (!nicknameValid.value) error.value = '请输入有效的昵称（2-30 位）'
    else if (!phoneValid.value) error.value = '请输入有效的手机号'
    else if (!phoneCodeValid.value) error.value = '请先获取并输入手机验证码'
    else if (email.value && !emailValid.value) error.value = '邮箱格式不正确'
    else if (emailValid.value && !emailCodeValid.value) error.value = '请先获取并输入邮箱验证码'
    else if (!passwordValid.value) error.value = '密码不符合要求'
    else if (!confirmValid.value) error.value = '两次输入的密码不一致'
    else error.value = '请检查所有字段并勾选同意条款'
    return
  }
  loading.value = true
  try {
    await register({
      phone: phone.value,
      phoneCode: phoneCode.value,
      email: emailValid.value ? email.value : undefined,
      emailCode: emailValid.value ? emailCode.value : undefined,
      nickname: nickname.value,
      password: password.value,
    })
    await router.push('/dashboard')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function gotoLogin() {
  router.push('/login')
}
</script>

<template>
  <div class="register-page">
    <button class="theme-toggle" type="button" @click="toggleTheme" :aria-label="theme === 'dark' ? '切换到浅色' : '切换到深色'">
      <span class="material-symbols-outlined">{{ theme === 'dark' ? 'light_mode' : 'dark_mode' }}</span>
    </button>

    <div class="register-canvas">
      <aside class="brand-panel">
        <div class="brand-meta">
          <span class="brand-name">句龙·照胆</span>
          <span class="brand-sub">国家合规审查 · AI 代理服务器</span>
        </div>
        <div class="brand-quote">
          <p>执笔文墨，</p>
          <p>字斟句酌。</p>
        </div>
        <div class="brand-footer">
          <p>以数据驱动合规决策，坚持确定性逻辑分析</p>
          <p>Stable Trust · 稳定技术，系统运行中</p>
        </div>
      </aside>

      <section class="form-panel">
        <header class="form-header">
          <span class="form-ref">REF.AUTH-002</span>
          <h1>创建账户</h1>
          <p class="form-sub">手机号验证后设置密码，开启智能合规之旅</p>
        </header>

        <div v-if="error" class="alert alert-error">{{ error }}</div>

        <form class="form-body" @submit.prevent="handleRegister">
          <label class="field">
            <span>昵称</span>
            <input
              v-model="nickname"
              type="text"
              maxlength="30"
              placeholder="请输入您希望被称呼的名字"
              :class="{ invalid: nickname && !nicknameValid }"
            />
          </label>

          <label class="field">
            <span>手机号码</span>
            <div class="phone-input">
              <span class="phone-prefix">+86</span>
              <input
                v-model="phone"
                type="tel"
                inputmode="numeric"
                maxlength="11"
                placeholder="请输入 11 位手机号码"
                :class="{ invalid: phone && !phoneValid }"
              />
            </div>
          </label>

          <label class="field">
            <span>手机验证码</span>
            <div class="sms-input">
              <input
                v-model="phoneCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入短信验证码"
              />
              <button
                type="button"
                class="sms-btn"
                :disabled="!phoneValid || phoneCountdown > 0 || phoneSending"
                @click="startSmsCountdown"
              >
                {{ phoneSending ? '发送中…' : (phoneCountdown > 0 ? `${phoneCountdown}s` : '获取验证码') }}
              </button>
            </div>
          </label>

          <label class="field">
            <span>邮箱（选填）</span>
            <input
              v-model="email"
              type="email"
              placeholder="填写邮箱需完成邮箱验证"
              :class="{ invalid: email && !emailValid }"
            />
          </label>

          <label v-if="emailValid" class="field">
            <span>邮箱验证码</span>
            <div class="sms-input">
              <input
                v-model="emailCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入邮箱验证码"
              />
              <button
                type="button"
                class="sms-btn"
                :disabled="emailCountdown > 0 || emailSending"
                @click="startEmailCountdown"
              >
                {{ emailSending ? '发送中…' : (emailCountdown > 0 ? `${emailCountdown}s` : '获取验证码') }}
              </button>
            </div>
          </label>

          <label class="field">
            <span>密码</span>
            <div class="password-input-wrap">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="8 位以上，含大小写字母和数字"
                :class="{ invalid: password && !passwordValid }"
              />
              <button type="button" class="password-toggle" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                <span class="material-symbols-outlined">{{ showPassword ? 'visibility_off' : 'visibility' }}</span>
              </button>
            </div>
            <div v-if="showRules" class="password-rules">
              <div v-for="rule in passwordRules" :key="rule.label" class="rule-item" :class="{ pass: rule.pass, fail: !rule.pass }">
                <span class="material-symbols-outlined rule-icon">{{ rule.pass ? 'check_circle' : 'cancel' }}</span>
                {{ rule.label }}
              </div>
            </div>
          </label>

          <label class="field">
            <span>确认密码</span>
            <div class="password-input-wrap">
              <input
                v-model="confirmPassword"
                :type="showConfirm ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="再次输入密码"
                :class="{ invalid: confirmPassword && !confirmValid }"
              />
              <button type="button" class="password-toggle" :aria-label="showConfirm ? '隐藏密码' : '显示密码'" @click="showConfirm = !showConfirm">
                <span class="material-symbols-outlined">{{ showConfirm ? 'visibility_off' : 'visibility' }}</span>
              </button>
            </div>
            </label>

          <button type="submit" class="primary-btn primary-btn-block" :disabled="!canRegister || loading">
            {{ loading ? '处理中…' : '立即注册' }}
          </button>
        </form>

        <label class="terms-row">
          <input v-model="agreedToTerms" type="checkbox" />
          <span>注册即代表同意 <a href="#">《服务条款》</a> 与 <a href="#">《隐私政策》</a></span>
        </label>

        <footer class="form-footer">
          已有账号？<button type="button" class="link-btn" @click="gotoLogin">返回登录</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg, #0A0A0A);
  padding: 24px;
  position: relative;
  overflow: hidden;
}

.register-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(212, 175, 55, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(212, 175, 55, 0.04) 1px, transparent 1px);
  background-size: 64px 64px;
  pointer-events: none;
}

:global(html[data-theme="light"]) .register-page::before {
  background-image:
    linear-gradient(rgba(155, 116, 22, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(155, 116, 22, 0.05) 1px, transparent 1px);
}

.theme-toggle {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 5;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(212, 175, 55, 0.3);
  background: transparent;
  color: #d4af37;
  cursor: pointer;
  border-radius: 0.25rem;
  transition: background 0.2s, border-color 0.2s;
}

:global(html[data-theme="light"]) .register-page .theme-toggle {
  border-color: rgba(155, 116, 22, 0.4);
  color: #9b7416;
}

.theme-toggle:hover {
  background: rgba(212, 175, 55, 0.12);
  border-color: rgba(212, 175, 55, 0.6);
}

.theme-toggle .material-symbols-outlined {
  font-size: 20px;
}

.register-canvas {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  width: min(960px, 100%);
  min-height: 600px;
  border: 1px solid rgba(212, 175, 55, 0.18);
  background: var(--surface, #121212);
  box-shadow: 0 0 60px rgba(212, 175, 55, 0.06);
}

:global(html[data-theme="light"]) .register-page .register-canvas {
  border-color: rgba(155, 116, 22, 0.28);
  background: var(--surface, #fffaf0);
  box-shadow: 0 20px 60px rgba(88, 65, 15, 0.12);
}

.brand-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 48px 40px;
  border-right: 1px solid rgba(212, 175, 55, 0.18);
  background:
    radial-gradient(circle at 30% 20%, rgba(212, 175, 55, 0.1), transparent 50%),
    linear-gradient(180deg, rgba(18, 18, 18, 0.4), rgba(10, 10, 10, 0.6));
}

:global(html[data-theme="light"]) .register-page .brand-panel {
  border-right-color: rgba(155, 116, 22, 0.28);
  background:
    radial-gradient(circle at 30% 20%, rgba(155, 116, 22, 0.08), transparent 50%),
    linear-gradient(180deg, rgba(255, 250, 240, 0.6), rgba(247, 241, 227, 0.8));
}

.brand-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 64px;
}

.brand-name {
  font-family: "Noto Serif SC", serif;
  font-size: 24px;
  color: #f3c94d;
  letter-spacing: 0.08em;
}

:global(html[data-theme="light"]) .register-page .brand-name {
  color: #735c00;
}

.brand-sub {
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #99907c;
  letter-spacing: 0.18em;
}

.brand-quote {
  margin-top: auto;
  margin-bottom: auto;
  padding: 0 0 0 16px;
  border-left: 2px solid #d4af37;
}

:global(html[data-theme="light"]) .register-page .brand-quote {
  border-left-color: #9b7416;
}

.brand-quote p {
  margin: 0;
  font-family: "Noto Serif SC", serif;
  color: #fff8e7;
  font-size: 28px;
  letter-spacing: 0.06em;
  line-height: 1.4;
}

:global(html[data-theme="light"]) .register-page .brand-quote p {
  color: #1f1a12;
}

.brand-footer {
  font: 500 10px/1.6 "JetBrains Mono", monospace;
  color: #99907c;
  letter-spacing: 0.14em;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-footer p {
  margin: 0;
}

.form-panel {
  display: flex;
  flex-direction: column;
  padding: 48px 40px;
  max-height: 90vh;
  overflow-y: auto;
}

.form-header {
  margin-bottom: 20px;
}

.form-ref {
  display: block;
  margin-bottom: 6px;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #d4af37;
  letter-spacing: 0.18em;
}

:global(html[data-theme="light"]) .register-page .form-ref {
  color: #9b7416;
}

.form-header h1 {
  margin: 0 0 6px;
  font-family: "Noto Serif SC", serif;
  font-size: 28px;
  color: #fff8e7;
  letter-spacing: 0.06em;
}

:global(html[data-theme="light"]) .register-page .form-header h1 {
  color: #1f1a12;
}

.form-sub {
  margin: 0;
  font-size: 13px;
  color: #99907c;
}

.alert {
  padding: 10px 14px;
  margin-bottom: 16px;
  font-size: 13px;
  border-radius: 0.25rem;
}

.alert-error {
  color: #ffb4ab;
  background: rgba(255, 180, 171, 0.08);
  border: 1px solid rgba(255, 180, 171, 0.3);
}

.form-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > span {
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #99907c;
  letter-spacing: 0.18em;
}

.field input {
  width: 100%;
  border: 0;
  border-bottom: 2px solid #4d4635;
  padding: 8px 0;
  background: transparent;
  color: #e5e2e1;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  border-radius: 0;
}

:global(html[data-theme="light"]) .register-page .field input {
  border-bottom-color: rgba(155, 116, 22, 0.3);
  color: #1f1a12;
}

.field input::placeholder {
  color: #66563a;
  opacity: 0.5;
}

.field input:focus {
  border-bottom-color: #d4af37;
  box-shadow: 0 4px 0 -2px rgba(212, 175, 55, 0.3);
}

:global(html[data-theme="light"]) .register-page .field input:focus {
  border-bottom-color: #9b7416;
  box-shadow: 0 4px 0 -2px rgba(155, 116, 22, 0.2);
}

.field input.invalid {
  border-bottom-color: #ffb4ab;
}

.phone-input,
.sms-input,
.password-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
  border-bottom: 2px solid #4d4635;
  transition: border-color 0.2s, box-shadow 0.2s;
}

:global(html[data-theme="light"]) .register-page .phone-input,
:global(html[data-theme="light"]) .register-page .sms-input,
:global(html[data-theme="light"]) .register-page .password-input-wrap {
  border-bottom-color: rgba(155, 116, 22, 0.3);
}

.phone-input:focus-within,
.sms-input:focus-within,
.password-input-wrap:focus-within {
  border-bottom-color: #d4af37;
  box-shadow: 0 4px 0 -2px rgba(212, 175, 55, 0.3);
}

:global(html[data-theme="light"]) .register-page .phone-input:focus-within,
:global(html[data-theme="light"]) .register-page .sms-input:focus-within,
:global(html[data-theme="light"]) .register-page .password-input-wrap:focus-within {
  border-bottom-color: #9b7416;
  box-shadow: 0 4px 0 -2px rgba(155, 116, 22, 0.2);
}

.phone-input input,
.sms-input input,
.password-input-wrap input {
  flex: 1;
  border: 0;
  border-bottom: 0;
  box-shadow: none;
  padding: 8px 0;
}

.phone-input input:focus,
.sms-input input:focus,
.password-input-wrap input:focus {
  border-bottom: 0;
  box-shadow: none;
}

.phone-prefix {
  padding-right: 10px;
  margin-right: 10px;
  border-right: 1px solid rgba(212, 175, 55, 0.18);
  color: #d4af37;
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
}

:global(html[data-theme="light"]) .register-page .phone-prefix {
  border-right-color: rgba(155, 116, 22, 0.3);
  color: #9b7416;
}

.sms-btn,
.password-toggle {
  border: 0;
  background: transparent;
  color: #d4af37;
  font: 500 13px/1 "Hanken Grotesk", sans-serif;
  cursor: pointer;
  padding: 6px 10px;
  margin-left: 6px;
  white-space: nowrap;
  border-radius: 0.25rem;
  transition: color 0.2s, background 0.2s;
}

:global(html[data-theme="light"]) .register-page .sms-btn,
:global(html[data-theme="light"]) .register-page .password-toggle {
  color: #9b7416;
}

.sms-btn:hover:not(:disabled),
.password-toggle:hover {
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
}

:global(html[data-theme="light"]) .register-page .sms-btn:hover:not(:disabled),
:global(html[data-theme="light"]) .register-page .password-toggle:hover {
  background: rgba(155, 116, 22, 0.1);
  color: #735c00;
}

.sms-btn:disabled {
  color: #66563a;
  cursor: not-allowed;
}

.password-toggle {
  margin-left: auto;
}

.password-toggle .material-symbols-outlined {
  font-size: 18px;
}

.password-rules {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
  padding: 8px 12px;
  border: 1px solid rgba(212, 175, 55, 0.15);
  background: rgba(18, 18, 18, 0.5);
  font-size: 12px;
}

:global(html[data-theme="light"]) .register-page .password-rules {
  border-color: rgba(155, 116, 22, 0.2);
  background: rgba(255, 250, 240, 0.5);
}

.rule-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.rule-item.pass {
  color: #66bb6a;
}

.rule-item.fail {
  color: #99907c;
}

:global(html[data-theme="light"]) .register-page .rule-item.fail {
  color: #66563a;
}

.rule-icon {
  font-size: 14px;
  width: 16px;
  text-align: center;
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border: 1px solid #d4af37;
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.1em;
  cursor: pointer;
  border-radius: 0.25rem;
  transition: background 0.2s, box-shadow 0.2s;
}

.primary-btn:hover:not(:disabled) {
  background: rgba(212, 175, 55, 0.2);
  box-shadow: 0 0 18px rgba(212, 175, 55, 0.25);
}

.primary-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.primary-btn-block {
  width: 100%;
  margin-top: 8px;
}

.terms-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 12px;
  color: #99907c;
}

.terms-row input {
  accent-color: #d4af37;
}

.terms-row a {
  color: #d4af37;
  text-decoration: none;
}

.terms-row a:hover {
  text-decoration: underline;
}

:global(html[data-theme="light"]) .register-page .terms-row a {
  color: #9b7416;
}

.form-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #99907c;
}

.link-btn {
  border: 0;
  background: transparent;
  color: #d4af37;
  cursor: pointer;
  font-size: inherit;
  font-family: inherit;
  padding: 0;
}

.link-btn:hover {
  color: #f2ca50;
  text-decoration: underline;
}

:global(html[data-theme="light"]) .register-page .link-btn {
  color: #9b7416;
}

:global(html[data-theme="light"]) .register-page .brand-sub,
:global(html[data-theme="light"]) .register-page .brand-footer,
:global(html[data-theme="light"]) .register-page .form-sub,
:global(html[data-theme="light"]) .register-page .field > span,
:global(html[data-theme="light"]) .register-page .terms-row,
:global(html[data-theme="light"]) .register-page .form-footer {
  color: #66563a;
}

:global(html[data-theme="light"] .register-page .field input::placeholder) {
  color: #7a6a4d;
  opacity: 0.8;
}

:global(html[data-theme="light"]) .register-page .sms-btn:disabled {
  color: #99907c;
}

:global(html[data-theme="light"]) .register-page .primary-btn {
  border-color: #9b7416;
  background: #9b7416;
  color: #fffaf0;
}

:global(html[data-theme="light"]) .register-page .primary-btn:hover:not(:disabled) {
  background: #735c00;
  border-color: #735c00;
  box-shadow: 0 0 18px rgba(155, 116, 22, 0.25);
}

:global(html[data-theme="light"] .register-page .primary-btn:disabled) {
  opacity: 0.5;
}

@media (max-width: 720px) {
  .register-canvas {
    grid-template-columns: 1fr;
  }
  .brand-panel {
    display: none;
  }
  .form-panel {
    padding: 32px 24px;
    max-height: none;
  }
  .theme-toggle {
    top: 12px;
    right: 12px;
  }
}
</style>
