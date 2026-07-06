import { ref } from 'vue'

const ACCESS_TOKEN_KEY = 'goulong_access_token'
const USER_KEY = 'goulong_current_user'

let _accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY)
const currentUser = ref(null)

function clearAuthState() {
  _accessToken = null
  currentUser.value = null
  sessionStorage.removeItem(ACCESS_TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
}

try {
  const savedUser = sessionStorage.getItem(USER_KEY)
  currentUser.value = savedUser ? JSON.parse(savedUser) : null
} catch {
  currentUser.value = null
}

function isLoggedIn() {
  return !!_accessToken
}

function getAuthHeaders() {
  if (!_accessToken) return {}
  return { Authorization: `Bearer ${_accessToken}` }
}

async function fetchWithAuth(url, options = {}) {
  const headers = { ...options.headers, ...getAuthHeaders() }
  let response = await fetch(url, { ...options, headers, credentials: 'include' })

  if (response.status === 401 && _accessToken) {
    const refreshed = await refreshToken()
    if (refreshed) {
      headers.Authorization = `Bearer ${_accessToken}`
      response = await fetch(url, { ...options, headers, credentials: 'include' })
    } else {
      clearAuthState()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
  }

  return response
}

async function readError(response) {
  try {
    return await response.json()
  } catch {
    return { detail: `请求失败（HTTP ${response.status}）` }
  }
}

function saveSession(data) {
  _accessToken = data.access_token
  currentUser.value = { id: data.id, nickname: data.nickname, email: data.email, phone: data.phone }
  sessionStorage.setItem(ACCESS_TOKEN_KEY, _accessToken)
  sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser.value))
}

async function login(identity, password) {
  // 自动判断 identity 是 email 还是 phone
  const body = identity.includes('@')
    ? { email: identity, password }
    : { phone: identity, password }

  const response = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })

  if (!response.ok) {
    const data = await readError(response)
    throw new Error(data.detail || '登录失败')
  }

  const data = await response.json()
  saveSession(data)
  return data
}

async function loginByCode({ phone, email, code }) {
  const body = { code }
  if (phone) body.phone = phone
  if (email) body.email = email

  const response = await fetch('/auth/login/code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })

  if (!response.ok) {
    const data = await readError(response)
    throw new Error(data.detail || '验证码登录失败')
  }

  const data = await response.json()
  saveSession(data)
  return data
}

async function sendSmsCode(phone, scene = 'login') {
  const response = await fetch('/auth/send-sms-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, scene }),
    credentials: 'include',
  })

  if (!response.ok) {
    const data = await readError(response)
    throw new Error(data.detail || '验证码发送失败')
  }
  return response.json()
}

async function sendEmailCode(email) {
  const response = await fetch('/auth/send-email-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    credentials: 'include',
  })

  if (!response.ok) {
    const data = await readError(response)
    throw new Error(data.detail || '验证码发送失败')
  }
  return response.json()
}

async function register({ email, phone, nickname, password, phoneCode, emailCode }) {
  const body = { nickname, password }
  if (phone) {
    body.phone = phone
    body.phone_code = phoneCode
  }
  if (email) {
    body.email = email
    body.email_code = emailCode
  }

  const response = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })

  if (!response.ok) {
    const data = await readError(response)
    throw new Error(data.detail || '注册失败')
  }

  const data = await response.json()
  saveSession(data)
  return data
}

async function refreshToken() {
  try {
    const response = await fetch('/auth/refresh', { method: 'POST', credentials: 'include' })
    if (!response.ok) return false
    const data = await response.json()
    _accessToken = data.access_token
    sessionStorage.setItem(ACCESS_TOKEN_KEY, _accessToken)
    return true
  } catch {
    return false
  }
}

function logout() {
  clearAuthState()
  window.location.href = '/login'
}

export function useAuth() {
  return {
    currentUser,
    isLoggedIn,
    getAuthHeaders,
    fetchWithAuth,
    login,
    loginByCode,
    sendSmsCode,
    sendEmailCode,
    register,
    refreshToken,
    logout,
  }
}
