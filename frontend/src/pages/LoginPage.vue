<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { useTheme } from '../composables/useTheme.js'

const { login } = useAuth()
const router = useRouter()
const { theme, toggleTheme } = useTheme()

const activeTab = ref('password')
const error = ref('')
const loading = ref(false)

const account = ref('')
const password = ref('')
const phone = ref('')
const smsCode = ref('')
const smsCountdown = ref(0)
const smsSending = ref(false)

const showPassword = ref(false)
const agreedToTerms = ref(false)

const emailValid = computed(() => {
  if (!account.value) return false
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.value)
})
const usernameValid = computed(() => {
  if (!account.value) return false
  return /^[A-Za-z0-9_]{3,50}$/.test(account.value)
})
const passwordValid = computed(() => password.value.length >= 8)
const phoneValid = computed(() => /^1[3-9]\d{9}$/.test(phone.value))

const canSubmitPassword = computed(() =>
  (emailValid.value || usernameValid.value) && passwordValid.value
)
const canSubmitSms = computed(() => phoneValid.value && smsCode.value.length === 6)

async function startSmsCountdown() {
  if (!phoneValid.value || smsSending.value) return
  smsSending.value = true
  error.value = ''
  try {
    await new Promise((resolve, reject) => {
      setTimeout(() => {
        error.value = '短信验证服务暂未上线，请使用账号密码登录'
        reject(new Error('sms_not_available'))
      }, 600)
    })
  } catch {
  } finally {
    smsSending.value = false
  }
}

async function handleSmsLogin() {
  error.value = '短信验证服务暂未上线，请使用账号密码登录'
}

async function handlePasswordLogin() {
  error.value = ''
  if (!canSubmitPassword.value) {
    error.value = '请输入有效的账号和密码（密码至少 8 位）'
    return
  }
  if (!agreedToTerms.value) {
    error.value = '请先勾选同意《服务条款》与《隐私政策》'
    return
  }
  loading.value = true
  try {
    await login(account.value, password.value)
    await router.push('/dashboard')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function switchTab(tab) {
  activeTab.value = tab
  error.value = ''
}

function gotoRegister() {
  router.push('/register')
}
</script>

<template>
  <div class="login-page" :data-theme="theme">
    <button class="theme-toggle" type="button" @click="toggleTheme" :aria-label="theme === 'dark' ? '切换到浅色' : '切换到深色'">
      <span class="material-symbols-outlined">{{ theme === 'dark' ? 'light_mode' : 'dark_mode' }}</span>
    </button>

    <div class="login-canvas">
      <aside class="brand-panel">
        <div class="brand-meta">
          <span class="brand-name">句龙·照胆</span>
          <span class="brand-sub">国家合规审查 · AI 代理服务器</span>
        </div>
        <div class="brand-quote">
          <p>欢迎执笔，</p>
          <p>今日宜定分止争。</p>
        </div>
        <div class="brand-footer">
          <p>以数据驱动合规决策，坚持确定性逻辑分析</p>
          <p>Stable Trust · 稳定技术，系统运行中</p>
        </div>
      </aside>

      <section class="form-panel">
        <header class="form-header">
          <span class="form-ref">REF.AUTH-001</span>
          <h1>登录</h1>
        </header>

        <nav class="tab-bar" role="tablist">
          <button
            type="button"
            role="tab"
            :aria-selected="activeTab === 'sms'"
            :class="{ active: activeTab === 'sms' }"
            @click="switchTab('sms')"
          >
            手机号快捷登录
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="activeTab === 'password'"
            :class="{ active: activeTab === 'password' }"
            @click="switchTab('password')"
          >
            账号密码登录
          </button>
        </nav>

        <div v-if="error" class="alert alert-error">{{ error }}</div>

        <form v-if="activeTab === 'sms'" class="form-body" @submit.prevent="handleSmsLogin">
          <p class="form-hint">未注册的手机号验证后请前往注册</p>

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
            <span>验证码</span>
            <div class="sms-input">
              <input
                v-model="smsCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入短信验证码"
              />
              <button
                type="button"
                class="sms-btn"
                :disabled="!phoneValid || smsCountdown > 0 || smsSending"
                @click="startSmsCountdown"
              >
                {{ smsSending ? '发送中…' : (smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码') }}
              </button>
            </div>
          </label>

          <button type="submit" class="primary-btn primary-btn-block" :disabled="!canSubmitSms">
            立即登录
          </button>
        </form>

        <form v-else class="form-body" @submit.prevent="handlePasswordLogin">
          <p class="form-hint">使用注册时填写的邮箱或用户名登录</p>

          <label class="field">
            <span>邮箱 / 用户名</span>
            <input
              v-model="account"
              type="text"
              autocomplete="username"
              placeholder="请输入邮箱或用户名"
            />
          </label>

          <label class="field">
            <span>密码</span>
            <div class="password-input-wrap">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="请输入密码"
              />
              <button type="button" class="password-toggle" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
                <span class="material-symbols-outlined">{{ showPassword ? 'visibility_off' : 'visibility' }}</span>
              </button>
            </div>
          </label>

          <button type="submit" class="primary-btn primary-btn-block" :disabled="loading">
            {{ loading ? '处理中…' : '立即登录' }}
          </button>
        </form>

        <label class="terms-row">
          <input v-model="agreedToTerms" type="checkbox" />
          <span>登录即代表同意 <a href="#">《服务条款》</a> 与 <a href="#">《隐私政策》</a></span>
        </label>

        <div class="oauth-divider"><span>使用以下方式快捷登录</span></div>

        <div class="oauth-row" aria-hidden="true">
          <button type="button" class="oauth-btn" disabled title="微信登录暂未上线">
            <span class="material-symbols-outlined">chat</span>
          </button>
          <button type="button" class="oauth-btn" disabled title="QQ 登录暂未上线">
            <span class="material-symbols-outlined">visibility</span>
          </button>
          <button type="button" class="oauth-btn" disabled title="GitHub 登录暂未上线">
            <span class="material-symbols-outlined">code</span>
          </button>
          <button type="button" class="oauth-btn" disabled title="企业 SSO 暂未上线">
            <span class="material-symbols-outlined">shield</span>
          </button>
        </div>

        <footer class="form-footer">
          还没有账号？<button type="button" class="link-btn" @click="gotoRegister">立即注册</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0A0A0A;
  padding: 24px;
  position: relative;
  overflow: hidden;
}

.login-page[data-theme="light"] {
  background: #f7f1e3;
}

.login-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(212, 175, 55, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(212, 175, 55, 0.04) 1px, transparent 1px);
  background-size: 64px 64px;
  pointer-events: none;
}

.login-page[data-theme="light"]::before {
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

.login-page[data-theme="light"] .theme-toggle {
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

.login-canvas {
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

.login-page[data-theme="light"] .login-canvas {
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

.login-page[data-theme="light"] .brand-panel {
  border-right-color: rgba(155, 116, 22, 0.28);
  background:
    radial-gradient(circle at 30% 20%, rgba(155, 116, 22, 0.1), transparent 50%),
    linear-gradient(180deg, #eadbb9 0%, #f7f1e3 60%, #efe2c6 100%);
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

.login-page[data-theme="light"] .brand-name {
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

.login-page[data-theme="light"] .brand-quote {
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

.login-page[data-theme="light"] .brand-quote p {
  color: #1f1a12 !important;
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
  padding: 56px 48px;
}

.form-header {
  margin-bottom: 24px;
}

.form-ref {
  display: block;
  margin-bottom: 6px;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: #d4af37;
  letter-spacing: 0.18em;
}

.login-page[data-theme="light"] .form-ref {
  color: #9b7416;
}

.form-header h1 {
  margin: 0;
  font-family: "Noto Serif SC", serif;
  font-size: 32px;
  color: #fff8e7;
  letter-spacing: 0.06em;
}

.login-page[data-theme="light"] .form-header h1 {
  color: #1f1a12;
}

.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid rgba(212, 175, 55, 0.18);
  margin-bottom: 24px;
}

.login-page[data-theme="light"] .tab-bar {
  border-bottom-color: rgba(155, 116, 22, 0.28);
}

.tab-bar button {
  flex: 1;
  padding: 12px 0;
  border: 0;
  background: transparent;
  color: #99907c;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.tab-bar button.active {
  color: #d4af37;
  font-weight: 600;
}

.login-page[data-theme="light"] .tab-bar button.active {
  color: #9b7416;
}

.tab-bar button.active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #d4af37, transparent);
  box-shadow: 0 0 8px rgba(212, 175, 55, 0.5);
}

.login-page[data-theme="light"] .tab-bar button.active::after {
  background: linear-gradient(90deg, transparent, #9b7416, transparent);
  box-shadow: none;
}

.form-hint {
  margin: 0 0 16px;
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
  gap: 18px;
  flex-grow: 1;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  padding: 10px 0;
  background: transparent;
  color: #e5e2e1;
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  border-radius: 0;
}

.login-page[data-theme="light"] .field input {
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

.login-page[data-theme="light"] .field input:focus {
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

.login-page[data-theme="light"] .phone-input,
.login-page[data-theme="light"] .sms-input,
.login-page[data-theme="light"] .password-input-wrap {
  border-bottom-color: rgba(155, 116, 22, 0.3);
}

.phone-input:focus-within,
.sms-input:focus-within,
.password-input-wrap:focus-within {
  border-bottom-color: #d4af37;
  box-shadow: 0 4px 0 -2px rgba(212, 175, 55, 0.3);
}

.login-page[data-theme="light"] .phone-input:focus-within,
.login-page[data-theme="light"] .sms-input:focus-within,
.login-page[data-theme="light"] .password-input-wrap:focus-within {
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
  padding: 10px 0;
}

.phone-input input:focus,
.sms-input input:focus,
.password-input-wrap input:focus {
  border-bottom: 0;
  box-shadow: none;
}

.phone-prefix {
  padding-right: 12px;
  margin-right: 12px;
  border-right: 1px solid rgba(212, 175, 55, 0.18);
  color: #d4af37;
  font-family: "JetBrains Mono", monospace;
  font-size: 14px;
}

.login-page[data-theme="light"] .phone-prefix {
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
  padding: 8px 12px;
  margin-left: 8px;
  white-space: nowrap;
  border-radius: 0.25rem;
  transition: color 0.2s, background 0.2s;
}

.login-page[data-theme="light"] .sms-btn,
.login-page[data-theme="light"] .password-toggle {
  color: #9b7416;
}

.sms-btn:hover:not(:disabled),
.password-toggle:hover {
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
}

.login-page[data-theme="light"] .sms-btn:hover:not(:disabled),
.login-page[data-theme="light"] .password-toggle:hover {
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

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 13px 24px;
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
  margin-top: auto;
}

.terms-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
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

.login-page[data-theme="light"] .terms-row a {
  color: #9b7416;
}

.oauth-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 12px;
  color: #66563a;
  font-size: 12px;
  letter-spacing: 0.06em;
}

.oauth-divider::before,
.oauth-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.3), transparent);
}

.login-page[data-theme="light"] .oauth-divider::before,
.login-page[data-theme="light"] .oauth-divider::after {
  background: linear-gradient(90deg, transparent, rgba(155, 116, 22, 0.3), transparent);
}

.oauth-row {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.oauth-btn {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(212, 175, 55, 0.2);
  background: transparent;
  color: #99907c;
  cursor: not-allowed;
  border-radius: 0.25rem;
  opacity: 0.5;
  transition: opacity 0.2s, color 0.2s, border-color 0.2s;
}

.login-page[data-theme="light"] .oauth-btn {
  border-color: rgba(155, 116, 22, 0.28);
  color: #66563a;
}

.oauth-btn .material-symbols-outlined {
  font-size: 20px;
}

.form-footer {
  text-align: center;
  margin-top: 24px;
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

.login-page[data-theme="light"] .link-btn {
  color: #9b7416;
}

@media (max-width: 720px) {
  .login-canvas {
    grid-template-columns: 1fr;
  }
  .brand-panel {
    display: none;
  }
  .form-panel {
    padding: 32px 24px;
  }
  .theme-toggle {
    top: 12px;
    right: 12px;
  }
}
</style>
