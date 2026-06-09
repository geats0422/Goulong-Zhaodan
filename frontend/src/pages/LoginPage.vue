<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const { login, register } = useAuth()
const router = useRouter()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

const WEAK_PASSWORDS = new Set([
  'password', 'password1', 'password12', 'password123', 'password1234',
  'password12345', 'password123456', '123456', '1234567', '12345678',
  '123456789', '1234567890', 'qwerty', 'qwerty12', 'qwerty123',
  'qwerty1234', 'abc123', 'abc1234', 'abcd1234', 'iloveyou',
  'trustno1', 'sunshine', 'princess', 'football', 'shadow',
  'superman', 'dragon', 'master', 'monkey', 'letmein',
  'login', 'welcome', 'welcome1', 'welcome12', 'welcome123',
  'admin', 'admin1', 'admin12', 'admin123', 'admin1234',
  'root', 'root123', 'pass', 'pass12', 'pass123',
  'test', 'test12', 'test123', 'guest', 'guest123',
  'default', 'changeme', 'secret', 'hunter2', 'baseball',
  'starwars', 'passw0rd', 'flower', 'charlie', 'robert',
  'hockey', 'ranger', 'daniel', 'matrix', 'freedom',
  'whatever', 'mustang', 'ferrari', 'soccer', 'hannah',
  'william', 'dallas', 'yankees', 'jordan', 'harley',
  'access', 'hello', 'killer', 'arsenal', 'cookie',
  'buster', 'thunder', 'joshua', 'amanda', 'nicole',
  'silver', 'tigers', 'marine', 'eagles', 'samsung',
  '1q2w3e4r', 'asdfgh', 'asdfghjk', 'asdf1234', 'zxcvbn',
  'zxcvbnm', '1qaz2wsx', 'abcdef', 'abcdefg', 'abcdefgh',
])

const SPECIAL_CHARS = '!@#$%^&*()_-+=[]{}|:;<>,.?/~'
const ALLOWED_RE = /^[a-zA-Z0-9!@#$%^&*()_\-=\[\]{}|:;<>,.?\/~]*$/

const passwordRules = computed(() => {
  const p = password.value
  return [
    { label: '至少 8 个字符', pass: p.length >= 8 },
    { label: '至少一个大写字母', pass: /[A-Z]/.test(p) },
    { label: '至少一个小写字母', pass: /[a-z]/.test(p) },
    { label: '至少一个数字', pass: /[0-9]/.test(p) },
    { label: '不能包含空格', pass: p.length === 0 || !/\s/.test(p) },
    { label: '只能使用允许的特殊字符', pass: ALLOWED_RE.test(p) },
    { label: '不是常见弱密码', pass: p.length === 0 || !WEAK_PASSWORDS.has(p.toLowerCase()) },
  ]
})

const passwordStrength = computed(() => {
  if (!password.value) return 0
  const passed = passwordRules.value.filter(r => r.pass).length
  return passed
})

const showRules = computed(() => isRegister.value && password.value.length > 0)

async function handleSubmit() {
  error.value = ''
  loading.value = true

  try {
    if (isRegister.value) {
      if (password.value !== confirmPassword.value) {
        error.value = '两次密码不一致'
        return
      }
      await register(username.value, password.value)
    } else {
      await login(username.value, password.value)
    }
    await router.push('/dashboard')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <header class="login-header">
        <span class="login-icon">✦</span>
        <h1>{{ isRegister ? '创建账号' : '系统登录' }}</h1>
        <p>句龙照胆 · 工程文档智能体检平台</p>
      </header>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div v-if="error" class="login-error">{{ error }}</div>

        <label>
          <span>用户名</span>
          <input v-model="username" type="text" placeholder="3-50 字符" autocomplete="username" required minlength="3" maxlength="50" />
        </label>

        <label>
          <span>密码</span>
          <input v-model="password" type="password" :placeholder="isRegister ? '8-128 位，需含大小写字母和数字' : '输入密码'" autocomplete="current-password" required minlength="8" maxlength="128" />
        </label>

        <div v-if="showRules" class="password-rules">
          <div v-for="rule in passwordRules" :key="rule.label" class="rule-item" :class="{ pass: rule.pass, fail: !rule.pass }">
            <span class="rule-icon">{{ rule.pass ? '✓' : '✗' }}</span>
            {{ rule.label }}
          </div>
        </div>

        <label v-if="isRegister">
          <span>确认密码</span>
          <input v-model="confirmPassword" type="password" placeholder="再次输入密码" autocomplete="new-password" required minlength="8" />
        </label>

        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? '处理中...' : (isRegister ? '注 册' : '登 录') }}
        </button>
      </form>

      <footer class="login-footer">
        <button type="button" @click="toggleMode">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f1115;
}

.login-card {
  width: min(420px, calc(100% - 40px));
  border: 1px solid rgba(212, 175, 55, 0.2);
  padding: 40px 32px;
  background: rgba(18, 18, 18, 0.92);
  backdrop-filter: blur(20px);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header .login-icon {
  font-size: 48px;
  color: #f2ca50;
}

.login-header h1 {
  margin: 12px 0 4px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 28px;
}

.login-header p {
  margin: 0;
  color: #99907c;
  font-size: 13px;
  letter-spacing: 0.1em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.login-error {
  padding: 10px 14px;
  border: 1px solid #ffb4ab;
  background: rgba(255, 180, 171, 0.08);
  color: #ffb4ab;
  font-size: 14px;
}

.login-form label span {
  display: block;
  margin-bottom: 6px;
  color: #99907c;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.login-form input {
  width: 100%;
  border: 0;
  border-bottom: 1px solid #4d4635;
  padding: 0 0 10px;
  background: transparent;
  color: #d0c5af;
  font-size: 15px;
  outline: none;
}

.login-form input:focus {
  border-bottom-color: #d4af37;
}

.password-rules {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(212, 175, 55, 0.15);
  background: rgba(18, 18, 18, 0.5);
  font-size: 12px;
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
  color: #ef5350;
}

.rule-icon {
  font-size: 13px;
  width: 16px;
  text-align: center;
}

.login-btn {
  margin-top: 8px;
  border: 1px solid #d4af37;
  padding: 12px;
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
  font-size: 16px;
  letter-spacing: 0.2em;
  cursor: pointer;
  transition: background 0.2s;
}

.login-btn:hover:not(:disabled) {
  background: rgba(212, 175, 55, 0.2);
}

.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
}

.login-footer button {
  border: 0;
  background: transparent;
  color: #99907c;
  font-size: 13px;
  cursor: pointer;
}

.login-footer button:hover {
  color: #f2ca50;
}
</style>
