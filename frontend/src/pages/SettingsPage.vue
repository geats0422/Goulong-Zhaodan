<script setup>
import { computed, onMounted, ref } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'
import DashboardFooter from '../components/app/DashboardFooter.vue'
import PaymentModal from '../components/PaymentModal.vue'
import {
  API_KEY_SCOPES,
  MODEL_CATALOG,
  POWER_PACKS,
  SCOPE_TEMPLATES,
  SUB_PLANS,
} from '../data/plans.js'
import {
  createApiKey,
  createTabooWord,
  deleteTabooWord,
  getApiKeySecret,
  getSettingsOverview,
  listApiKeys,
  recoverPassword,
  revokeApiKey,
  sendPasswordRecoverCode,
  updateKnowledgeDocument,
  updatePassword,
  updateProfile,
  updateTabooWord,
} from '../services/settingsApi.js'
import { listOrders } from '../services/paymentApi.js'

const activeTab = ref('system')
const tabs = [
  { key: 'system', label: '系统设置' },
  { key: 'billing', label: '账单与订阅管理' },
  { key: 'model', label: 'AI 模型与偏好' },
  { key: 'knowledge', label: '知识库设置' },
  { key: 'taboo', label: '违禁词设置' },
]

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const message = ref('')
const profile = ref(null)
const knowledge = ref([])
const tabooWords = ref([])

const editingIdentity = ref(false)
const identityForm = ref({ nickname: '', phone: '', email: '' })

const showChangePasswordDialog = ref(false)
const passwordForm = ref({ old_password: '', new_password: '', confirm_new_password: '' })
const passwordError = ref('')
const showOldPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)
const showRecoverPasswordDialog = ref(false)
const recoverPasswordForm = ref({ phone_code: '', new_password: '', confirm_new_password: '' })
const recoverPasswordError = ref('')
const showRecoverNewPassword = ref(false)
const showRecoverConfirmPassword = ref(false)
const recoverCodeCountdown = ref(0)
let recoverCodeTimer = null

const showHistoryDialog = ref(false)
const historyOrders = ref([])
const historyLoading = ref(false)
const historyError = ref('')

const ORDER_STATUS_LABELS = {
  pending: '待支付',
  paid: '已支付',
  closed: '已关闭',
  failed: '支付失败',
}
const ORDER_METHOD_LABELS = {
  wechat: '微信',
  alipay: '支付宝',
}

const burnAfterRead = ref(true)

const showUpgradeDialog = ref(false)
const upgradingPlanKey = ref(null)
const modalProduct = ref(null)

const apiKeys = ref([])
const secretCache = ref({})
const confirmingKeyId = ref(null)
const confirmAction = ref(null)
const confirmMessage = ref('')
const showApiKeyForm = ref(false)
const newKeyForm = ref({ name: '', scope_template: 'mcp_readonly', expires_in_days: 90, custom_scopes: [] })
const newlyCreatedKey = ref(null)
const showExpiryDropdown = ref(false)
const expiryOptions = [
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天', recommended: true },
  { value: 180, label: '180 天' },
  { value: 365, label: '365 天' },
  { value: 0, label: '永不过期' },
]

const tabooForm = ref({ word: '', replacement: '', note: '' })
const editingTabooId = ref(null)

const quotaPercent = computed(() => {
  if (!profile.value?.monthly_quota) return 0
  return Math.min(100, (profile.value.quota_used / profile.value.monthly_quota) * 100)
})

const canSubmitApiKey = computed(() => {
  if (saving.value) return false
  if (newKeyForm.value.scope_template !== 'advanced_custom') return true
  return newKeyForm.value.custom_scopes.length > 0
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const data = await getSettingsOverview()
    profile.value = data.profile
    knowledge.value = data.knowledge || []
    tabooWords.value = data.taboo_words || []
    burnAfterRead.value = data.profile.burn_after_read
    identityForm.value = {
      nickname: data.profile.nickname,
      phone: data.profile.phone || '',
      email: data.profile.email || '',
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设置加载失败'
  } finally {
    loading.value = false
  }
}

async function loadApiKeys() {
  try {
    apiKeys.value = await listApiKeys()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'API Key 加载失败'
  }
}

function startEditingIdentity() {
  identityForm.value = {
    nickname: profile.value.nickname,
    phone: profile.value.phone || '',
    email: profile.value.email || '',
  }
  editingIdentity.value = true
}

function cancelEditingIdentity() {
  editingIdentity.value = false
}

async function saveIdentity() {
  saving.value = true
  message.value = ''
  try {
    profile.value = await updateProfile({
      nickname: identityForm.value.nickname,
      phone: identityForm.value.phone || null,
      email: identityForm.value.email || null,
    })
    editingIdentity.value = false
    message.value = '身份信息已更新'
    const stored = sessionStorage.getItem('goulong_current_user')
    if (stored) {
      const u = JSON.parse(stored)
      u.nickname = identityForm.value.nickname
      sessionStorage.setItem('goulong_current_user', JSON.stringify(u))
    }
  } catch (err) {
    if (err.message?.includes('409') || err.message?.includes('已被') || err.message?.includes('占用')) {
      error.value = '该手机号/邮箱已被使用'
    } else {
      error.value = err.message
    }
  } finally {
    saving.value = false
  }
}

function openChangePasswordDialog() {
  passwordForm.value = { old_password: '', new_password: '', confirm_new_password: '' }
  passwordError.value = ''
  showOldPassword.value = false
  showNewPassword.value = false
  showConfirmPassword.value = false
  showChangePasswordDialog.value = true
}

function cancelChangePassword() {
  showChangePasswordDialog.value = false
}

function openRecoverPasswordDialog() {
  recoverPasswordForm.value = { phone_code: '', new_password: '', confirm_new_password: '' }
  recoverPasswordError.value = ''
  showRecoverNewPassword.value = false
  showRecoverConfirmPassword.value = false
  recoverCodeCountdown.value = 0
  if (recoverCodeTimer) {
    clearInterval(recoverCodeTimer)
    recoverCodeTimer = null
  }
  showRecoverPasswordDialog.value = true
}

function cancelRecoverPassword() {
  showRecoverPasswordDialog.value = false
}

function startRecoverCodeCountdown(seconds = 60) {
  if (recoverCodeTimer) clearInterval(recoverCodeTimer)
  recoverCodeCountdown.value = seconds
  recoverCodeTimer = setInterval(() => {
    recoverCodeCountdown.value -= 1
    if (recoverCodeCountdown.value <= 0) {
      clearInterval(recoverCodeTimer)
      recoverCodeTimer = null
      recoverCodeCountdown.value = 0
    }
  }, 1000)
}

async function sendRecoverPasswordCode() {
  if (recoverCodeCountdown.value > 0) return
  recoverPasswordError.value = ''
  saving.value = true
  try {
    const result = await sendPasswordRecoverCode()
    startRecoverCodeCountdown(result?.expires_in && result.expires_in < 60 ? result.expires_in : 60)
    message.value = '验证码已发送'
  } catch (err) {
    recoverPasswordError.value = err.message
  } finally {
    saving.value = false
  }
}

async function submitRecoverPassword() {
  if (!/^\d{6}$/.test(recoverPasswordForm.value.phone_code)) {
    recoverPasswordError.value = '验证码必须为 6 位数字'
    return
  }
  if (recoverPasswordForm.value.new_password !== recoverPasswordForm.value.confirm_new_password) {
    recoverPasswordError.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  recoverPasswordError.value = ''
  try {
    await recoverPassword({
      phone_code: recoverPasswordForm.value.phone_code,
      new_password: recoverPasswordForm.value.new_password,
    })
    showRecoverPasswordDialog.value = false
    message.value = '密码已重设，请重新登录'
    setTimeout(() => { window.location.href = '/login' }, 1500)
  } catch (err) {
    recoverPasswordError.value = err.message
  } finally {
    saving.value = false
  }
}

async function submitChangePassword() {
  if (passwordForm.value.new_password !== passwordForm.value.confirm_new_password) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  passwordError.value = ''
  try {
    await updatePassword({
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password,
    })
    showChangePasswordDialog.value = false
    message.value = '密码已更新，请重新登录'
    setTimeout(() => { window.location.href = '/login' }, 1500)
  } catch (err) {
    passwordError.value = err.message
  } finally {
    saving.value = false
  }
}

async function toggleBurnAfterRead() {
  burnAfterRead.value = !burnAfterRead.value
  saving.value = true
  try {
    profile.value = await updateProfile({ burn_after_read: burnAfterRead.value })
    message.value = burnAfterRead.value ? '已开启数据脱敏' : '已关闭数据脱敏'
  } catch (err) {
    burnAfterRead.value = !burnAfterRead.value
    error.value = err.message
  } finally {
    saving.value = false
  }
}

async function selectModel(modelName) {
  saving.value = true
  message.value = ''
  try {
    profile.value = await updateProfile({ model_name: modelName })
    message.value = '模型已切换'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

function openUpgradeDialog() {
  upgradingPlanKey.value = null
  showUpgradeDialog.value = true
}

function closeUpgradeDialog() {
  showUpgradeDialog.value = false
}

function openPaymentModal(pack) {
  modalProduct.value = {
    code: pack.key,
    name: pack.name,
    price: pack.price,
  }
}

async function openHistory() {
  showHistoryDialog.value = true
  historyError.value = ''
  historyLoading.value = true
  try {
    const data = await listOrders()
    historyOrders.value = Array.isArray(data) ? data : []
  } catch (err) {
    historyError.value = err instanceof Error ? err.message : '历史订单加载失败'
    historyOrders.value = []
  } finally {
    historyLoading.value = false
  }
}

function closeHistory() {
  showHistoryDialog.value = false
}

function historyAmount(order) {
  const cents = order?.amount_cents
  const yuan = typeof cents === 'number' ? cents / 100 : 0
  return `¥${yuan.toFixed(2)}`
}

function historyDate(value) {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN', { hour12: false })
}

function historyStatusLabel(status) {
  return ORDER_STATUS_LABELS[status] || status || '--'
}

function historyMethodLabel(method) {
  return ORDER_METHOD_LABELS[method] || method || '--'
}

function closePaymentModal() {
  modalProduct.value = null
}

async function handlePaymentSuccess() {
  modalProduct.value = null
  await loadSettings()
}

function selectUpgradePlan(key) {
  upgradingPlanKey.value = key
}

async function confirmUpgrade() {
  if (!upgradingPlanKey.value) return
  saving.value = true
  try {
    profile.value = await updateProfile({ subscription_plan: upgradingPlanKey.value })
    showUpgradeDialog.value = false
    message.value = '订阅方案已更新'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

async function handleEyeClick(keyId) {
  if (secretCache.value[keyId]) {
    delete secretCache.value[keyId]
    return
  }
  confirmAction.value = 'reveal'
  confirmingKeyId.value = keyId
  confirmMessage.value = '显示完整密钥存在泄露风险，确认显示？'
}

async function handleCopyClick(keyId) {
  if (secretCache.value[keyId]) {
    await copyApiKey(secretCache.value[keyId])
    return
  }
  try {
    const data = await getApiKeySecret(keyId)
    secretCache.value[keyId] = data.full_key
    await copyApiKey(data.full_key)
    await loadApiKeys()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '复制失败'
  }
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // 降级到 execCommand，兼容非 HTTPS、本地调试或剪贴板权限受限场景。
    }
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!ok) {
    throw new Error('浏览器拒绝写入剪贴板')
  }
}

async function copyApiKey(fullKey) {
  try {
    await copyTextToClipboard(fullKey)
    error.value = ''
    message.value = '已复制到剪贴板'
  } catch (err) {
    error.value = err instanceof Error ? err.message : '复制失败，请手动选中复制'
  }
}

async function handleRevokeClick(keyId) {
  confirmAction.value = 'revoke'
  confirmingKeyId.value = keyId
  confirmMessage.value = '撤销后该密钥将立即失效，无法恢复。确认撤销？'
}

async function confirmAction2() {
  const id = confirmingKeyId.value
  const action = confirmAction.value
  confirmingKeyId.value = null
  confirmAction.value = null
  confirmMessage.value = ''
  if (!id) return
  if (action === 'revoke') {
    try {
      await revokeApiKey(id)
      delete secretCache.value[id]
      await loadApiKeys()
      message.value = 'API Key 已撤销'
    } catch (err) {
      error.value = err.message
    }
    return
  }
  try {
    const data = await getApiKeySecret(id)
    secretCache.value[id] = data.full_key
    if (action === 'copy') {
      await copyApiKey(data.full_key)
    }
    await loadApiKeys()
  } catch (err) {
    error.value = err.message
  }
}

function cancelConfirm() {
  confirmingKeyId.value = null
  confirmAction.value = null
  confirmMessage.value = ''
}

function openCreateApiKey() {
  newKeyForm.value = { name: '', scope_template: 'mcp_readonly', expires_in_days: 90, custom_scopes: [] }
  showApiKeyForm.value = true
  newlyCreatedKey.value = null
}

function cancelCreateApiKey() {
  showApiKeyForm.value = false
}

async function submitCreateApiKey() {
  if (newKeyForm.value.scope_template === 'advanced_custom' && !newKeyForm.value.custom_scopes.length) {
    error.value = '请至少选择一个自定义权限'
    return
  }
  saving.value = true
  message.value = ''
  try {
    const payload = {
      name: newKeyForm.value.name,
      client_type: 'agent',
      scope_template: newKeyForm.value.scope_template,
    }
    if (newKeyForm.value.scope_template === 'advanced_custom') {
      payload.scopes = newKeyForm.value.custom_scopes
    }
    if (newKeyForm.value.expires_in_days) {
      payload.expires_at = new Date(Date.now() + newKeyForm.value.expires_in_days * 24 * 60 * 60 * 1000).toISOString()
    }
    const created = await createApiKey(payload)
    newlyCreatedKey.value = created
    showApiKeyForm.value = false
    await loadApiKeys()
    message.value = 'API Key 已创建'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

async function toggleDocument(doc) {
  const next = !doc.enabled
  doc.enabled = next
  try {
    await updateKnowledgeDocument(doc.id, next)
    message.value = next ? '知识库文档已启用' : '知识库文档已停用'
  } catch (err) {
    doc.enabled = !next
    error.value = err instanceof Error ? err.message : '知识库设置保存失败'
  }
}

function editTaboo(word) {
  editingTabooId.value = word.id
  tabooForm.value = { word: word.word, replacement: word.replacement || '', note: word.note || '' }
}

function resetTabooForm() {
  editingTabooId.value = null
  tabooForm.value = { word: '', replacement: '', note: '' }
}

async function submitTabooWord() {
  saving.value = true
  message.value = ''
  try {
    if (editingTabooId.value) {
      const updated = await updateTabooWord(editingTabooId.value, tabooForm.value)
      tabooWords.value = tabooWords.value.map((item) => (item.id === updated.id ? updated : item))
      message.value = '违禁词已更新'
    } else {
      const created = await createTabooWord(tabooForm.value)
      tabooWords.value.push(created)
      message.value = '违禁词已添加'
    }
    resetTabooForm()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '违禁词保存失败'
  } finally {
    saving.value = false
  }
}

async function removeTabooWord(wordId) {
  try {
    await deleteTabooWord(wordId)
    tabooWords.value = tabooWords.value.filter((item) => item.id !== wordId)
    message.value = '违禁词已删除'
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

onMounted(() => {
  loadSettings()
  loadApiKeys()
})
</script>

<template>
  <div class="settings-page">
    <AppTopNav active="settings" />

    <main class="settings-main">
      <div class="settings-breadcrumb">
        <a href="/dashboard">首页</a>
        <span class="material-symbols-outlined">chevron_right</span>
        <strong>设置中枢</strong>
      </div>

      <header class="settings-header">
        <h1>系统配置与个人设置</h1>
      </header>

      <div v-if="loading" class="settings-state">正在加载设置...</div>
      <div v-else-if="error" class="settings-error">{{ error }}</div>
      <div v-if="message" class="settings-message">{{ message }}</div>

      <nav class="settings-tabs" aria-label="设置分类">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" type="button" @click="activeTab = tab.key">
          {{ tab.label }}
        </button>
      </nav>

      <section v-if="!loading && profile && activeTab === 'system'" class="settings-content system-settings">
        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.GL-001</span>
              <h2>基础档案</h2>
            </div>
            <button v-if="!editingIdentity" class="ghost-btn" type="button" @click="startEditingIdentity">编辑</button>
          </header>
          <div class="account-status-row">
            <span class="account-status-dot"></span>
            <span class="account-status-label">账号状态：</span>
            <strong>正常</strong>
          </div>
          <div v-if="!editingIdentity" class="identity-grid">
            <div class="identity-row">
              <span class="identity-label">昵称</span>
              <span class="identity-value">{{ profile.nickname }}</span>
            </div>
            <div class="identity-row">
              <span class="identity-label">绑定手机号</span>
              <span class="identity-value identity-muted">{{ profile.phone || '—' }}</span>
              <button class="ghost-btn ghost-btn-sm" type="button" @click="startEditingIdentity">{{ profile.phone ? '更换' : '绑定' }}</button>
            </div>
            <div class="identity-row">
              <span class="identity-label">绑定邮箱</span>
              <span class="identity-value identity-muted">{{ profile.email || '—' }}</span>
              <button class="ghost-btn ghost-btn-sm" type="button" @click="startEditingIdentity">{{ profile.email ? '更换' : '绑定' }}</button>
            </div>
          </div>
          <div v-else class="identity-grid">
            <label class="identity-edit-row">
              <span class="identity-label">昵称</span>
              <input v-model="identityForm.nickname" class="edit-input" />
            </label>
            <label class="identity-edit-row">
              <span class="identity-label">手机号</span>
              <input v-model="identityForm.phone" class="edit-input" placeholder="13xxxxxxxxx" />
            </label>
            <label class="identity-edit-row">
              <span class="identity-label">邮箱</span>
              <input v-model="identityForm.email" class="edit-input" placeholder="example@domain.com" />
            </label>
            <div class="identity-edit-actions">
              <button class="primary-btn" type="button" :disabled="saving" @click="saveIdentity">保存</button>
              <button class="ghost-btn" type="button" @click="cancelEditingIdentity">取消</button>
            </div>
          </div>
        </article>

        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.GL-002</span>
              <h2>账户安全</h2>
            </div>
          </header>
          <div class="account-status-row">
            <span class="identity-label">登录密码</span>
            <span class="identity-value">••••••••</span>
            <div class="password-action-group">
              <button class="ghost-btn" type="button" @click="openRecoverPasswordDialog">忘记密码</button>
              <button class="ghost-btn" type="button" @click="openChangePasswordDialog">更改密码</button>
            </div>
          </div>
          <p class="security-hint">用于登录验证、敏感操作的二次确认</p>
        </article>

        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.GL-003</span>
              <h2>数据安全锁</h2>
            </div>
            <label class="switch" :class="{ active: burnAfterRead }">
              <input type="checkbox" :checked="burnAfterRead" @change="toggleBurnAfterRead" />
              <span class="switch-track"></span>
              <span class="switch-label">{{ burnAfterRead ? '已激活' : '未激活' }}</span>
            </label>
          </header>
          <p class="security-hint">激活后，所有会话结束立即清除内存残留痕迹，符合最高级保密标准。</p>
        </article>

        <div v-if="showChangePasswordDialog" class="modal-overlay" @click.self="cancelChangePassword">
          <div class="modal-card modal-card-sm">
            <header class="modal-header">
              <h3>更改密码</h3>
              <button class="icon-btn" type="button" @click="cancelChangePassword">
                <span class="material-symbols-outlined">close</span>
              </button>
            </header>
            <div class="modal-body">
              <label class="form-row">
                <span>当前密码</span>
                <div class="password-input-wrap">
                  <input v-model="passwordForm.old_password" :type="showOldPassword ? 'text' : 'password'" class="form-input" placeholder="输入当前密码" />
                  <button type="button" class="password-toggle" @click="showOldPassword = !showOldPassword">
                    <span class="material-symbols-outlined">{{ showOldPassword ? 'visibility_off' : 'visibility' }}</span>
                  </button>
                </div>
              </label>
              <label class="form-row">
                <span>新密码</span>
                <div class="password-input-wrap">
                  <input v-model="passwordForm.new_password" :type="showNewPassword ? 'text' : 'password'" class="form-input" placeholder="设置新密码" minlength="6" />
                  <button type="button" class="password-toggle" @click="showNewPassword = !showNewPassword">
                    <span class="material-symbols-outlined">{{ showNewPassword ? 'visibility_off' : 'visibility' }}</span>
                  </button>
                </div>
                <small class="form-hint">至少 6 位</small>
              </label>
              <label class="form-row">
                <span>确认新密码</span>
                <div class="password-input-wrap">
                  <input v-model="passwordForm.confirm_new_password" :type="showConfirmPassword ? 'text' : 'password'" class="form-input" placeholder="再次输入新密码" />
                  <button type="button" class="password-toggle" @click="showConfirmPassword = !showConfirmPassword">
                    <span class="material-symbols-outlined">{{ showConfirmPassword ? 'visibility_off' : 'visibility' }}</span>
                  </button>
                </div>
              </label>
              <p v-if="passwordError" class="form-error">{{ passwordError }}</p>
            </div>
            <footer class="modal-footer">
              <button class="ghost-btn" type="button" @click="cancelChangePassword">取消</button>
              <button class="primary-btn" type="button" :disabled="saving" @click="submitChangePassword">确认修改</button>
            </footer>
          </div>
        </div>

        <div v-if="showRecoverPasswordDialog" class="modal-overlay" @click.self="cancelRecoverPassword">
          <div class="modal-card modal-card-sm">
            <header class="modal-header">
              <div>
                <h3>短信验证重设密码</h3>
                <p class="modal-subtitle">验证码将发送至已绑定手机号 {{ profile.phone || '—' }}</p>
              </div>
              <button class="icon-btn" type="button" @click="cancelRecoverPassword">
                <span class="material-symbols-outlined">close</span>
              </button>
            </header>
            <div class="modal-body">
              <label class="form-row">
                <span>验证码</span>
                <div class="code-input-row">
                  <input v-model="recoverPasswordForm.phone_code" class="form-input" placeholder="请输入短信验证码" maxlength="6" inputmode="numeric" autocomplete="one-time-code" />
                  <button class="ghost-btn code-btn" type="button" :disabled="saving || recoverCodeCountdown > 0" @click="sendRecoverPasswordCode">
                    {{ recoverCodeCountdown > 0 ? `${recoverCodeCountdown}s` : (saving ? '发送中...' : '获取验证码') }}
                  </button>
                </div>
              </label>
              <label class="form-row">
                <span>新密码</span>
                <div class="password-input-wrap">
                  <input v-model="recoverPasswordForm.new_password" :type="showRecoverNewPassword ? 'text' : 'password'" class="form-input" placeholder="设置新密码" minlength="6" />
                  <button type="button" class="password-toggle" @click="showRecoverNewPassword = !showRecoverNewPassword">
                    <span class="material-symbols-outlined">{{ showRecoverNewPassword ? 'visibility_off' : 'visibility' }}</span>
                  </button>
                </div>
                <small class="form-hint">至少 6 位，需包含大小写字母和数字</small>
              </label>
              <label class="form-row">
                <span>确认新密码</span>
                <div class="password-input-wrap">
                  <input v-model="recoverPasswordForm.confirm_new_password" :type="showRecoverConfirmPassword ? 'text' : 'password'" class="form-input" placeholder="再次输入新密码" />
                  <button type="button" class="password-toggle" @click="showRecoverConfirmPassword = !showRecoverConfirmPassword">
                    <span class="material-symbols-outlined">{{ showRecoverConfirmPassword ? 'visibility_off' : 'visibility' }}</span>
                  </button>
                </div>
              </label>
              <p v-if="recoverPasswordError" class="form-error">{{ recoverPasswordError }}</p>
            </div>
            <footer class="modal-footer">
              <button class="ghost-btn" type="button" @click="cancelRecoverPassword">取消</button>
              <button class="primary-btn" type="button" :disabled="saving" @click="submitRecoverPassword">确认重设</button>
            </footer>
          </div>
        </div>

      </section>

      <section v-else-if="!loading && profile && activeTab === 'billing'" class="settings-content billing-settings">
        <article class="settings-card billing-tier-card">
          <div class="billing-tier-head">
            <div>
              <span class="card-ref">REF.SUB-001</span>
              <h2>{{ profile.subscription_label }}<span class="tier-tag" :class="profile.subscription_plan === 'free' ? 'tier-tag-free' : 'tier-tag-paid'">{{ profile.subscription_plan === 'free' ? '未订阅' : profile.subscription_period }}</span></h2>
              <p class="billing-tier-hint">{{ profile.subscription_plan === 'free' ? '当前为免费体验等级，未购买任何付费方案。' : `当前为${profile.subscription_label}（${profile.subscription_price}${profile.subscription_period}），可通过下方算力包扩展配额。` }}</p>
            </div>
            <div class="billing-tier-actions">
              <button v-if="profile.subscription_plan === 'free'" class="primary-btn" type="button" @click="openUpgradeDialog">立即升级</button>
            </div>
          </div>
          <div class="billing-quota-bar">
            <div class="quota-bar-header">
              <span class="quota-bar-label">已用额度</span>
              <span class="quota-bar-value">{{ profile.quota_used }} / {{ profile.monthly_quota }}</span>
            </div>
            <div class="quota-bar-track">
              <div class="quota-bar-fill" :style="{ width: Math.min(100, (profile.quota_used / Math.max(1, profile.monthly_quota)) * 100) + '%' }"></div>
            </div>
          </div>
        </article>

        <h3 class="section-title"><span class="material-symbols-outlined">receipt_long</span>订单历史</h3>
        <button class="ghost-btn history-trigger" type="button" @click="openHistory">
          <span class="material-symbols-outlined">history</span>
          查看历史订单
        </button>

        <h3 class="section-title"><span class="material-symbols-outlined">bolt</span>算力补充包</h3>
        <div class="power-pack-grid">
          <article v-for="pack in POWER_PACKS" :key="pack.key" class="power-pack-card" :class="{ recommended: pack.recommended }">
            <span class="card-ref">{{ pack.ref }}</span>
            <span v-if="pack.recommended" class="recommend-tag">最受欢迎</span>
            <h3 class="pack-name">{{ pack.name }}</h3>
            <p class="pack-price">{{ pack.price }}<span class="pack-unit">{{ pack.unit }}</span></p>
            <ul class="pack-features">
              <li v-for="f in pack.features" :key="f.text" :class="{ disabled: !f.ok }">
                <span class="material-symbols-outlined">{{ f.ok ? 'check' : 'close' }}</span>{{ f.text }}
              </li>
            </ul>
            <button class="ghost-btn ghost-btn-block" type="button" @click="openPaymentModal(pack)">购买</button>
          </article>
        </div>

        <div v-if="showUpgradeDialog" class="modal-overlay" @click.self="closeUpgradeDialog">
          <div class="modal-card modal-card-lg">
            <header class="modal-header">
              <div>
                <span class="card-ref">REF.SUB-MODAL</span>
                <h3>订阅方案</h3>
                <p class="modal-subtitle">选择适合您的数字笔杆子。告别幻觉，字字有据。</p>
              </div>
              <button class="icon-btn" type="button" @click="closeUpgradeDialog">
                <span class="material-symbols-outlined">close</span>
              </button>
            </header>
            <div class="upgrade-grid">
              <article v-for="sub in SUB_PLANS" :key="sub.key" class="upgrade-card" :class="{ selected: upgradingPlanKey === sub.key, recommended: sub.recommended }">
                <span class="card-ref">{{ sub.ref }}</span>
                <h4 class="upgrade-name">{{ sub.name }}</h4>
                <p class="upgrade-price">{{ sub.price }}<span class="upgrade-period">{{ sub.period }}</span></p>
                <ul class="upgrade-features">
                  <li v-for="f in sub.features" :key="f">
                    <span class="material-symbols-outlined">check</span>{{ f }}
                  </li>
                </ul>
                <button class="primary-btn primary-btn-block" type="button" :disabled="saving" @click="selectUpgradePlan(sub.key); confirmUpgrade()">
                  {{ sub.actionLabel }}
                </button>
              </article>
            </div>
            <footer class="modal-footer">
              <span class="modal-security-hint"><span class="material-symbols-outlined">verified</span>所有方案均含银行级加密与数据隔离保护</span>
              <a href="/pricing" class="modal-link">查看完整方案对比 →</a>
            </footer>
          </div>
        </div>

        <div v-if="showHistoryDialog" class="modal-overlay" @click.self="closeHistory">
          <div class="modal-card modal-card-md history-modal">
            <header class="modal-header">
              <div>
                <span class="card-ref">REF.HIS-001</span>
                <h3>历史订单</h3>
                <p class="modal-subtitle">包含算力包与订阅相关订单</p>
              </div>
              <button class="icon-btn" type="button" @click="closeHistory">
                <span class="material-symbols-outlined">close</span>
              </button>
            </header>
            <div class="modal-body">
              <div v-if="historyLoading" class="modal-empty">正在加载历史订单...</div>
              <div v-else-if="historyError" class="form-error">{{ historyError }}</div>
              <div v-else-if="historyOrders.length === 0" class="modal-empty">暂无历史订单</div>
              <div v-else class="history-list">
                <article v-for="order in historyOrders" :key="order.id" class="history-row">
                  <div class="history-row-main">
                    <div class="history-name">{{ order.product_name || order.product_code || '订单' }} · {{ historyAmount(order) }}</div>
                    <div class="history-meta">
                      <span>{{ historyMethodLabel(order.payment_method) }}</span>
                      <span>·</span>
                      <span>{{ order.token_quota || 0 }} Tokens</span>
                    </div>
                  </div>
                  <div class="history-row-side">
                    <span class="history-status" :class="`is-${order.status}`">{{ historyStatusLabel(order.status) }}</span>
                    <div class="history-time">{{ historyDate(order.created_at) }}</div>
                  </div>
                </article>
              </div>
            </div>
            <footer class="modal-footer">
              <button class="ghost-btn" type="button" @click="closeHistory">关闭</button>
            </footer>
          </div>
        </div>
      </section>

      <section v-else-if="!loading && profile && activeTab === 'model'" class="settings-content model-settings">
        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.MODEL-001</span>
              <h2>AI 模型选择</h2>
            </div>
          </header>
          <p class="security-hint">选择驱动审查引擎的底层模型。不同模型在推理深度与响应速度之间存在权衡。</p>
          <div class="model-card-grid">
            <div v-for="card in MODEL_CATALOG" :key="card.model_name" class="model-card" :class="{ selected: profile.model_name === card.model_name }" @click="selectModel(card.model_name)">
              <span v-if="profile.model_name === card.model_name" class="material-symbols-outlined model-check">check_circle</span>
              <strong class="model-card-title">{{ card.label }}</strong>
              <span class="model-card-tier">{{ card.tier }}</span>
              <span class="model-card-context">上下文：{{ card.context }}</span>
            </div>
          </div>
          <div class="model-info-bar">
            <span>当前服务端：{{ profile.model_base_url }}</span>
            <span>API Key：{{ profile.model_api_key_preview }}</span>
          </div>
          <label class="switch switch-row" :class="{ active: burnAfterRead }">
            <span class="switch-label-text">启用数据脱敏（身份证 / 手机号 / 银行卡 / 金额）</span>
            <span class="switch-track-wrap">
              <input type="checkbox" :checked="burnAfterRead" @change="toggleBurnAfterRead" />
              <span class="switch-track"></span>
            </span>
          </label>
        </article>

        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.API-001</span>
              <h2>开发者 API Key</h2>
            </div>
            <button v-if="!showApiKeyForm && !newlyCreatedKey" class="primary-btn" type="button" @click="openCreateApiKey">创建 API Key</button>
          </header>
          <p class="security-hint">用于 Agent / MCP / CLI 调用。后端记录 last_viewed_at、last_used_at。</p>

          <div v-if="newlyCreatedKey" class="apikey-new-key">
            <p class="apikey-new-hint">请立即复制完整密钥，关闭后将无法再次查看：</p>
            <div class="apikey-new-row">
              <button class="apikey-secret-text" type="button" title="点击复制完整 API Key" @click="copyApiKey(newlyCreatedKey.full_key)">
                <code>{{ newlyCreatedKey.full_key }}</code>
              </button>
              <button class="primary-btn" type="button" @click="copyApiKey(newlyCreatedKey.full_key)">复制</button>
              <button class="ghost-btn" type="button" @click="newlyCreatedKey = null">关闭</button>
            </div>
          </div>

          <div v-if="!apiKeys.length && !showApiKeyForm" class="empty-state">暂无 API Key</div>
          <div v-else class="apikey-list">
            <div v-for="key in apiKeys" :key="key.id" class="apikey-row">
              <div class="apikey-row-prefix">
                <span class="apikey-status" :class="'status-' + key.status">{{ key.status === 'active' ? '活跃' : '已撤销' }}</span>
                <code>{{ secretCache[key.id] || key.key_prefix }}</code>
              </div>
              <div class="apikey-row-meta">
                <strong>{{ key.name }}</strong>
                <span class="apikey-detail">{{ key.client_type }} · {{ key.scope_template }}</span>
              </div>
              <div class="apikey-row-actions">
                <button class="icon-btn" type="button" :title="secretCache[key.id] ? '隐藏' : '显示'" @click="handleEyeClick(key.id)">
                  <span class="material-symbols-outlined">{{ secretCache[key.id] ? 'visibility_off' : 'visibility' }}</span>
                </button>
                <button class="icon-btn" type="button" title="复制" @click="handleCopyClick(key.id)">
                  <span class="material-symbols-outlined">content_copy</span>
                </button>
                <button class="icon-btn icon-btn-danger" type="button" title="撤销" @click="handleRevokeClick(key.id)">
                  <span class="material-symbols-outlined">delete</span>
                </button>
              </div>
            </div>
          </div>
        </article>

        <div v-if="showApiKeyForm" class="modal-overlay" @click.self="cancelCreateApiKey">
          <form class="modal-card modal-card-lg" @submit.prevent="submitCreateApiKey">
            <header class="modal-header">
              <div>
                <span class="card-ref">REF.API-MODAL</span>
                <h3>创建 API Key</h3>
                <p class="modal-subtitle">用于 Agent / MCP / CLI 调用。完整密钥只会在创建后显示一次。</p>
              </div>
              <button class="icon-btn" type="button" @click="cancelCreateApiKey">
                <span class="material-symbols-outlined">close</span>
              </button>
            </header>
            <div class="modal-body apikey-form">
              <label class="form-row">
                <span>密钥名称 <em>*</em></span>
                <input v-model="newKeyForm.name" class="form-input" required maxlength="100" placeholder="如：我的 CLI 工具" />
              </label>
              <div class="form-row">
                <span>权限模板</span>
                <div class="scope-template-grid">
                  <label v-for="tpl in SCOPE_TEMPLATES" :key="tpl.key" class="scope-template-card" :class="{ selected: newKeyForm.scope_template === tpl.key }">
                    <input v-model="newKeyForm.scope_template" type="radio" :value="tpl.key" />
                    <div>
                      <strong>{{ tpl.label }}</strong>
                      <span>{{ tpl.description }}</span>
                    </div>
                  </label>
                </div>
              </div>
              <div v-if="newKeyForm.scope_template === 'advanced_custom'" class="form-row">
                <span>自定义权限 <em>*</em></span>
                <div class="custom-scope-grid">
                  <label v-for="scope in API_KEY_SCOPES" :key="scope.key" class="custom-scope-card" :class="{ selected: newKeyForm.custom_scopes.includes(scope.key) }">
                    <input v-model="newKeyForm.custom_scopes" type="checkbox" :value="scope.key" />
                    <div>
                      <strong>{{ scope.label }}</strong>
                      <code>{{ scope.key }}</code>
                      <span>{{ scope.description }}</span>
                    </div>
                  </label>
                </div>
                <p class="form-hint">不包含删除记录等破坏性权限；创建后的 API Key 可按权限用于 MCP、CLI 或 Agent。</p>
              </div>
              <div class="form-row">
                <span>有效期</span>
                <div class="custom-select" :class="{ open: showExpiryDropdown }" tabindex="0" @focusout="showExpiryDropdown = false">
                  <button type="button" class="custom-select-trigger" @click="showExpiryDropdown = !showExpiryDropdown">
                    <span>{{ expiryOptions.find(o => o.value === newKeyForm.expires_in_days)?.label || '选择有效期' }}</span>
                    <span class="material-symbols-outlined custom-select-arrow">expand_more</span>
                  </button>
                  <ul v-if="showExpiryDropdown" class="custom-select-options">
                    <li v-for="opt in expiryOptions" :key="opt.value" :class="{ active: newKeyForm.expires_in_days === opt.value }" @click="newKeyForm.expires_in_days = opt.value; showExpiryDropdown = false">
                      {{ opt.label }}
                      <span v-if="opt.recommended" class="option-badge">推荐</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
            <footer class="modal-footer">
              <button class="ghost-btn" type="button" @click="cancelCreateApiKey">取消</button>
              <button class="primary-btn" type="submit" :disabled="!canSubmitApiKey">创建</button>
            </footer>
          </form>
        </div>

        <div v-if="confirmingKeyId" class="modal-overlay" @click.self="cancelConfirm">
          <div class="modal-card modal-card-sm">
            <header class="modal-header">
              <h3>{{ confirmAction === 'revoke' ? '撤销 API Key' : '确认显示' }}</h3>
            </header>
            <div class="modal-body">
              <p>{{ confirmMessage }}</p>
            </div>
            <footer class="modal-footer">
              <button class="ghost-btn" type="button" @click="cancelConfirm">取消</button>
              <button class="primary-btn" type="button" @click="confirmAction2">确认</button>
            </footer>
          </div>
        </div>
      </section>

      <section v-else-if="!loading && activeTab === 'knowledge'" class="settings-content knowledge-settings">
        <article v-for="category in knowledge" :key="category.category_key" class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.KB-{{ category.category_key }}</span>
              <h2>{{ category.category_label }}</h2>
            </div>
          </header>
          <div v-if="category.subcategories.length" class="knowledge-grid">
            <div v-for="sub in category.subcategories" :key="sub.id" class="knowledge-sub">
              <strong class="knowledge-sub-name">{{ sub.name }}</strong>
              <span v-if="!sub.documents.length" class="empty-state">暂无文档</span>
              <label v-for="doc in sub.documents" :key="doc.id" class="doc-toggle">
                <input type="checkbox" :checked="doc.enabled" @change="toggleDocument(doc)" />
                <span>{{ doc.title }}</span>
              </label>
            </div>
          </div>
          <p v-else class="empty-state">暂无知识库文档</p>
        </article>
      </section>

      <section v-else-if="!loading && activeTab === 'taboo'" class="settings-content taboo-settings">
        <article class="settings-card">
          <header>
            <div class="card-header-main">
              <span class="card-ref">REF.TB-001</span>
              <h2>违禁词库</h2>
            </div>
          </header>
          <p class="security-hint">设置绝对红线规避标准，引擎在处理文本时将严格隔离以下词条。</p>
          <form class="taboo-input" @submit.prevent="submitTabooWord">
            <input v-model="tabooForm.word" placeholder="输入需规避的敏感词汇..." required maxlength="100" />
            <input v-model="tabooForm.replacement" placeholder="建议替换词（可选）" maxlength="100" />
            <input v-model="tabooForm.note" placeholder="备注（可选）" />
            <button class="primary-btn" type="submit" :disabled="saving">{{ editingTabooId ? '保存修改' : '隔离入库' }}</button>
            <button v-if="editingTabooId" class="ghost-btn" type="button" @click="resetTabooForm">取消</button>
          </form>
          <div v-if="!tabooWords.length" class="empty-state">暂无违禁词</div>
          <div v-else class="taboo-list">
            <span v-for="word in tabooWords" :key="word.id">
              [{{ word.word }}]
              <small v-if="word.replacement">替换为：{{ word.replacement }}</small>
              <button type="button" @click="editTaboo(word)">编辑</button>
              <button type="button" aria-label="移除词条" @click="removeTabooWord(word.id)">×</button>
            </span>
          </div>
        </article>
      </section>
    </main>

    <DashboardFooter />

    <PaymentModal
      v-if="modalProduct"
      :product-code="modalProduct.code"
      :product-name="modalProduct.name"
      :amount-label="modalProduct.price"
      @paid="handlePaymentSuccess"
      @close="closePaymentModal"
    />
  </div>
</template>

<style scoped>
.settings-page { min-height: 100vh; background: #0A0A0A; }
.settings-main { width: min(1440px, calc(100% - 64px)); margin: 0 auto; padding: 48px 0 96px; }
.settings-breadcrumb { display: flex; align-items: center; gap: 8px; color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; }
.settings-breadcrumb a { color: inherit; text-decoration: none; }
.settings-breadcrumb strong { color: #f2ca50; }
.settings-breadcrumb .material-symbols-outlined { font-size: 16px; }
.settings-header { margin: 24px 0 28px; padding-top: 16px; border-top: 1px solid rgba(212, 175, 55, 0.4); }
.settings-header h1 { margin: 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: clamp(32px, 4vw, 48px); font-weight: 700; line-height: 1.2; }
.settings-tabs { display: flex; gap: 32px; border-bottom: 1px solid #353534; margin-bottom: 32px; }
.settings-tabs button { position: relative; border: 0; padding: 0 0 16px; background: transparent; color: #d0c5af; font-size: 18px; cursor: pointer; font-family: "Hanken Grotesk", sans-serif; }
.settings-tabs button.active { border-bottom: 2px solid #d4af37; color: #f2ca50; }
.settings-tabs button.active::after { content: ""; position: absolute; left: 50%; bottom: -5px; width: 8px; height: 8px; transform: translateX(-50%); background: #d4af37; box-shadow: 0 0 12px rgba(212, 175, 55, 0.3); }

.settings-state, .settings-error, .settings-message, .empty-state { border: 1px solid #4d4635; padding: 14px 16px; margin-bottom: 18px; background: #1c1b1b; color: #d0c5af; }
.settings-error { border-color: rgba(255, 180, 171, 0.55); color: #ffb4ab; }
.settings-message { border-color: rgba(74, 222, 128, 0.35); color: #34d399; }

.system-settings, .billing-settings, .model-settings, .knowledge-settings, .taboo-settings { display: flex; flex-direction: column; gap: 24px; }

.settings-card { position: relative; border: 1px solid rgba(212, 175, 55, 0.2); padding: 24px; background: #121212; }
.settings-card::before { content: ""; position: absolute; top: 0; left: 24px; right: 24px; height: 1px; background: linear-gradient(90deg, transparent, #d4af37 50%, transparent); opacity: 0.5; }
.settings-card header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
.card-header-main { display: flex; flex-direction: column; gap: 6px; }
.card-header-main h2 { margin: 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 24px; font-weight: 700; }
.card-ref { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; }

.primary-btn { border: 1px solid #d4af37; padding: 10px 22px; background: #d4af37; color: #1a1410; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; font-weight: 500; cursor: pointer; border-radius: 0.25rem; transition: box-shadow 200ms; }
.primary-btn:hover { box-shadow: 0 0 12px rgba(212, 175, 55, 0.3); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.primary-btn-block { width: 100%; }

.ghost-btn { border: 1px solid rgba(212, 175, 55, 0.4); padding: 8px 18px; background: transparent; color: #f2ca50; font-family: "Hanken Grotesk", sans-serif; font-size: 13px; cursor: pointer; border-radius: 0.25rem; transition: all 200ms; }
.ghost-btn:hover { background: rgba(212, 175, 55, 0.1); }
.ghost-btn-sm { padding: 4px 12px; font-size: 12px; }
.ghost-btn-block { display: block; width: 100%; margin-top: auto; }

.icon-btn { border: 0; background: transparent; color: #99907c; cursor: pointer; padding: 4px; }
.icon-btn:hover { color: #f2ca50; }
.icon-btn-danger:hover { color: #ffb4ab; }
.icon-btn .material-symbols-outlined { font-size: 18px; }

.account-status-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 12px; }
.account-status-dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 8px rgba(52, 211, 153, 0.5); }
.account-status-label { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; }
.password-action-group { display: inline-flex; align-items: center; gap: 10px; margin-left: auto; }

.identity-grid { display: grid; gap: 16px; }
.identity-row { display: grid; grid-template-columns: 140px 1fr auto; align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid rgba(155, 116, 22, 0.15); }
.identity-row:last-child { border-bottom: 0; }
.identity-label { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.08em; }
.identity-value { color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 15px; }
.identity-muted { color: #99907c; }
.identity-edit-row { display: flex; flex-direction: column; gap: 6px; padding: 8px 0; }
.identity-edit-row .identity-label { color: #d0c5af; font-size: 13px; }
.edit-input { width: 100%; border: 0; border-bottom: 1px solid #4d4635; padding: 8px 0; background: transparent; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 15px; outline: none; }
.edit-input:focus { border-bottom-color: #d4af37; box-shadow: 0 4px 12px -4px rgba(212, 175, 55, 0.3); }
.identity-edit-actions { display: flex; gap: 12px; margin-top: 12px; }

.security-hint { color: #99907c; font-size: 12px; font-family: "Hanken Grotesk", sans-serif; margin: 8px 0 0; }

.switch { display: inline-flex; align-items: center; gap: 12px; cursor: pointer; }
.switch input { display: none; }
.switch-track { position: relative; width: 44px; height: 22px; background: #353534; border-radius: 999px; transition: background 200ms; flex-shrink: 0; }
.switch-track::after { content: ""; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; background: #99907c; border-radius: 50%; transition: all 200ms; }
.switch.active .switch-track { background: #34d399; box-shadow: 0 0 12px rgba(52, 211, 153, 0.3); }
.switch.active .switch-track::after { left: 24px; background: #fff; }
.switch-label { color: #f2ca50; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.08em; }
.switch-row { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 14px 16px; border: 1px solid rgba(155, 116, 22, 0.18); background: #1c1b1b; }
.switch-label-text { color: #d0c5af; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; }
.switch-track-wrap { display: inline-flex; align-items: center; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 24px; }
.modal-card { background: #121212; border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 0; max-width: 720px; width: 100%; max-height: 90vh; overflow: auto; }
.modal-card-sm { max-width: 480px; }
.modal-card-lg { max-width: 960px; }
.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 28px; border-bottom: 1px solid rgba(155, 116, 22, 0.2); }
.modal-header h3 { margin: 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 22px; }
.modal-subtitle { color: #99907c; font-size: 13px; margin: 4px 0 0; }
.modal-body { padding: 20px 28px; }
.modal-footer { display: flex; justify-content: flex-end; align-items: center; gap: 12px; padding: 16px 28px; border-top: 1px solid rgba(155, 116, 22, 0.2); }

.history-modal .modal-body { max-height: 480px; overflow-y: auto; }
.modal-empty { color: var(--color-on-surface-variant, #99907c); padding: 32px 0; text-align: center; }
.history-list { display: flex; flex-direction: column; gap: 12px; }
.history-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 14px 16px; border: 1px solid var(--color-outline-variant, #e4beb9); background: var(--color-surface-container-low, #fcf2eb); }
.history-row-main { display: flex; flex-direction: column; gap: 4px; }
.history-name { color: var(--color-on-surface, #1f1b17); font-family: "Source Serif 4", serif; font-size: 16px; font-weight: 600; }
.history-meta { color: var(--color-on-surface-variant, #5b403d); font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.05em; display: flex; gap: 6px; }
.history-row-side { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.history-status { display: inline-block; padding: 2px 10px; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.06em; background: var(--color-surface-container, #f0e6e0); color: var(--color-on-surface-variant, #5b403d); }
.history-status.is-paid { color: #2e7d32; }
.history-status.is-pending { color: #b26a00; }
.history-status.is-failed { color: #c62828; }
.history-status.is-closed { color: var(--color-on-surface-variant, #5b403d); }
.history-time { color: var(--color-on-surface-variant, #5b403d); font-family: "JetBrains Mono", monospace; font-size: 11px; }
.history-trigger { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 16px; }
[data-theme="dark"] .history-row { background: rgba(212, 175, 55, 0.06); border-color: rgba(155, 116, 22, 0.35); }
[data-theme="dark"] .history-name { color: #e5e2e1; }
[data-theme="dark"] .history-meta { color: #99907c; }
[data-theme="dark"] .history-time { color: #99907c; }
[data-theme="dark"] .history-status { background: rgba(0, 0, 0, 0.4); color: #99907c; }
[data-theme="dark"] .history-status.is-paid { color: #66bb6a; }
[data-theme="dark"] .history-status.is-pending { color: #f0b400; }
[data-theme="dark"] .history-status.is-failed { color: #c62828; }
[data-theme="dark"] .history-status.is-closed { color: #99907c; }
.modal-security-hint { display: inline-flex; align-items: center; gap: 6px; color: #99907c; font-size: 12px; margin-right: auto; }
.modal-security-hint .material-symbols-outlined { font-size: 14px; color: #34d399; }
.modal-link { color: #d4af37; text-decoration: none; font-family: "Hanken Grotesk", sans-serif; font-size: 13px; }
.modal-link:hover { text-decoration: underline; }

.form-row { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.form-row > span { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.08em; }
.form-row em { color: #ffb4ab; font-style: normal; margin-left: 2px; }
.form-input { width: 100%; border: 1px solid #4d4635; padding: 10px 14px; background: #0A0A0A; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; outline: none; border-radius: 0.25rem; }
.form-input:focus { border-color: #d4af37; box-shadow: 0 0 12px rgba(212, 175, 55, 0.3); }
.form-hint { color: #99907c; font-size: 11px; margin-top: 2px; }

.custom-select { position: relative; }
.custom-select-trigger { width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border: 0; border-bottom: 2px solid #4d4635; background: transparent; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; cursor: pointer; transition: border-color 0.2s; }
.custom-select-trigger:hover { border-bottom-color: #a67c00; }
.custom-select.open .custom-select-trigger { border-bottom-color: #d4af37; box-shadow: 0 4px 0 -2px rgba(212, 175, 55, 0.3); }
.custom-select-arrow { font-size: 18px; color: #99907c; transition: transform 0.2s; }
.custom-select.open .custom-select-arrow { transform: rotate(180deg); color: #d4af37; }
.custom-select-options { position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 20; margin: 0; padding: 4px 0; list-style: none; border: 1px solid rgba(212, 175, 55, 0.3); background: #141414; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5), 0 0 12px rgba(212, 175, 55, 0.08); }
.custom-select-options li { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; cursor: pointer; transition: background 0.15s, color 0.15s; }
.custom-select-options li:hover { background: rgba(212, 175, 55, 0.08); color: #f2ca50; }
.custom-select-options li.active { color: #d4af37; background: rgba(212, 175, 55, 0.06); }
.option-badge { padding: 1px 8px; border: 1px solid rgba(212, 175, 55, 0.4); color: #d4af37; font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.06em; }
.form-error { color: #ffb4ab; font-size: 13px; margin: 8px 0 0; padding: 8px 12px; border: 1px solid rgba(255, 180, 171, 0.3); background: rgba(255, 180, 171, 0.05); }
.form-actions { display: flex; gap: 12px; margin-top: 12px; }
.code-input-row { display: flex; align-items: center; gap: 10px; }
.code-input-row .form-input { flex: 1; }
.code-btn { min-width: 104px; white-space: nowrap; }
.code-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.password-input-wrap { position: relative; }
.password-input-wrap .form-input { padding-right: 42px; }
.password-toggle { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); border: 0; background: transparent; color: #99907c; cursor: pointer; padding: 6px; }
.password-toggle:hover { color: #f2ca50; }
.password-toggle .material-symbols-outlined { font-size: 18px; }

.billing-tier-card { background: linear-gradient(135deg, #121212, #1c1b1b); }
.billing-tier-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.billing-tier-head h2 { margin: 4px 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 28px; }
.billing-tier-actions { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
.tier-tag { display: inline-block; margin-left: 8px; padding: 2px 10px; border: 1px solid #d4af37; color: #d4af37; font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 0.08em; vertical-align: middle; }
.tier-tag-free { border-color: #99907c; color: #99907c; }
.tier-tag-paid { border-color: #d4af37; color: #d4af37; }
.billing-tier-hint { color: #99907c; font-size: 13px; margin: 8px 0 0; max-width: 480px; }

.billing-quota-bar { margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(212, 175, 55, 0.12); }
.quota-bar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.quota-bar-label { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: 0.06em; }
.quota-bar-value { color: #f2ca50; font-family: "JetBrains Mono", monospace; font-size: 13px; font-weight: 600; }
.quota-bar-track { width: 100%; height: 6px; background: rgba(212, 175, 55, 0.1); overflow: hidden; }
.quota-bar-fill { height: 100%; background: linear-gradient(90deg, #d4af37, #f2ca50); box-shadow: 0 0 8px rgba(212, 175, 55, 0.4); transition: width 0.6s ease; }

.section-title { display: flex; align-items: center; gap: 8px; margin: 24px 0 16px; color: #f2ca50; font-family: "Syne", sans-serif; font-size: 20px; font-weight: 700; }
.section-title .material-symbols-outlined { color: #d4af37; }

.power-pack-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.power-pack-card { position: relative; display: flex; flex-direction: column; gap: 12px; padding: 24px; border: 1px solid rgba(155, 116, 22, 0.2); background: #121212; transition: border-color 200ms; }
.power-pack-card:hover { border-color: rgba(212, 175, 55, 0.5); }
.power-pack-card.recommended { border-color: #d4af37; box-shadow: 0 0 20px rgba(212, 175, 55, 0.15); }
.recommend-tag { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); padding: 2px 12px; background: #d4af37; color: #1a1410; font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 700; letter-spacing: 0.1em; }
.pack-name { margin: 8px 0 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 20px; }
.pack-price { margin: 0; color: #f2ca50; font-family: "Syne", sans-serif; font-size: 32px; font-weight: 700; }
.pack-unit { color: #99907c; font-size: 14px; font-weight: 400; margin-left: 4px; }
.pack-features { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.pack-features li { display: flex; align-items: center; gap: 8px; color: #d0c5af; font-size: 13px; }
.pack-features li.disabled { color: #66563a; }
.pack-features li .material-symbols-outlined { font-size: 16px; color: #34d399; }
.pack-features li.disabled .material-symbols-outlined { color: #66563a; }

.upgrade-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; padding: 24px 28px; }
.upgrade-card { display: flex; flex-direction: column; gap: 12px; padding: 24px; border: 1px solid rgba(155, 116, 22, 0.2); background: #1c1b1b; transition: all 200ms; }
.upgrade-card:hover { border-color: rgba(212, 175, 55, 0.4); }
.upgrade-card.selected { border-color: #d4af37; box-shadow: 0 0 20px rgba(212, 175, 55, 0.2); }
.upgrade-card.recommended { border-color: #d4af37; }
.upgrade-name { margin: 8px 0 0; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 20px; }
.upgrade-price { margin: 0; color: #1a1410; background: #d4af37; padding: 12px 16px; text-align: center; font-family: "Syne", sans-serif; font-size: 24px; font-weight: 700; }
.upgrade-period { color: rgba(26, 20, 16, 0.6); font-size: 12px; font-weight: 400; margin-left: 4px; }
.upgrade-features { list-style: none; margin: 8px 0; padding: 0; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.upgrade-features li { display: flex; align-items: center; gap: 8px; color: #d0c5af; font-size: 12px; }
.upgrade-features li .material-symbols-outlined { font-size: 14px; color: #34d399; }

.model-card-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin: 20px 0; }
.model-card { position: relative; border: 1px solid #353534; padding: 20px; background: #1c1b1b; cursor: pointer; transition: all 200ms; }
.model-card:hover { border-color: rgba(212, 175, 55, 0.4); }
.model-card.selected { border-color: #d4af37; background: linear-gradient(180deg, rgba(212, 175, 55, 0.1), rgba(212, 175, 55, 0.02)); box-shadow: inset 0 0 0 1px rgba(212, 175, 55, 0.3), 0 0 20px rgba(212, 175, 55, 0.1); }
.model-check { position: absolute; top: 12px; right: 12px; color: #d4af37; font-size: 20px; }
.model-card-title { display: block; color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 18px; margin-bottom: 8px; }
.model-card-tier { display: block; color: #f2ca50; font-size: 13px; margin-bottom: 4px; }
.model-card-context { display: block; color: #99907c; font-size: 12px; font-family: "JetBrains Mono", monospace; }
.model-info-bar { display: flex; flex-wrap: wrap; gap: 24px; padding: 14px 16px; border: 1px solid #353534; background: #1c1b1b; color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 12px; margin-bottom: 16px; }

.apikey-form { display: flex; flex-direction: column; gap: 4px; }
.scope-template-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 8px; }
.scope-template-card { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; border: 1px solid #353534; background: #0A0A0A; cursor: pointer; transition: all 200ms; border-radius: 0.25rem; }
.scope-template-card input { margin-top: 4px; }
.scope-template-card strong { display: block; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; }
.scope-template-card span { color: #99907c; font-size: 12px; }
.scope-template-card.selected { border-color: #d4af37; background: rgba(212, 175, 55, 0.05); box-shadow: 0 0 12px rgba(212, 175, 55, 0.15); }
.custom-scope-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 8px; }
.custom-scope-card { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; border: 1px solid #353534; background: #0A0A0A; cursor: pointer; transition: all 200ms; border-radius: 0.25rem; }
.custom-scope-card input { margin-top: 4px; }
.custom-scope-card strong { display: block; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; }
.custom-scope-card code { display: block; margin: 3px 0; color: #f2ca50; font-family: "JetBrains Mono", monospace; font-size: 11px; }
.custom-scope-card span { color: #99907c; font-size: 12px; }
.custom-scope-card.selected { border-color: #d4af37; background: rgba(212, 175, 55, 0.05); box-shadow: 0 0 12px rgba(212, 175, 55, 0.15); }

.apikey-new-key { margin-top: 16px; padding: 16px; border: 1px solid rgba(74, 222, 128, 0.35); background: rgba(52, 211, 153, 0.05); }
.apikey-new-hint { color: #d0c5af; font-size: 13px; margin: 0 0 12px; }
.apikey-new-row { display: flex; align-items: center; gap: 8px; }
.apikey-secret-text { flex: 1; border: 0; padding: 0; background: transparent; cursor: copy; text-align: left; }
.apikey-new-row code { display: block; width: 100%; padding: 10px 14px; background: #0A0A0A; color: #34d399; font-family: "JetBrains Mono", monospace; font-size: 12px; word-break: break-all; border: 1px solid rgba(74, 222, 128, 0.3); }

.apikey-list { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.apikey-row { display: grid; grid-template-columns: 1fr 1fr auto; align-items: center; gap: 16px; padding: 14px 16px; border: 1px solid #353534; background: #1c1b1b; }
.apikey-row-prefix { display: flex; flex-direction: column; gap: 4px; }
.apikey-status { display: inline-block; padding: 2px 8px; border: 1px solid #4d4635; font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; width: fit-content; }
.apikey-status.status-active { border-color: rgba(74, 222, 128, 0.35); color: #34d399; }
.apikey-status.status-revoked { border-color: rgba(255, 180, 171, 0.55); color: #ffb4ab; }
.apikey-row-prefix code { color: #d0c5af; font-family: "JetBrains Mono", monospace; font-size: 12px; word-break: break-all; }
.apikey-row-meta { display: flex; flex-direction: column; gap: 4px; }
.apikey-row-meta strong { color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; }
.apikey-detail { color: #99907c; font-family: "JetBrains Mono", monospace; font-size: 11px; }
.apikey-row-actions { display: flex; gap: 4px; }

.knowledge-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.knowledge-sub { display: flex; flex-direction: column; gap: 8px; padding: 16px; border: 1px solid #353534; background: #1c1b1b; }
.knowledge-sub-name { color: #e5e2e1; font-family: "Syne", sans-serif; font-size: 16px; }
.doc-toggle { display: flex; align-items: center; gap: 8px; color: #d0c5af; font-size: 13px; }
.doc-toggle input { accent-color: #d4af37; }

.taboo-input { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }
.taboo-input input { flex: 1; min-width: 160px; border: 1px solid #4d4635; padding: 10px 14px; background: #0A0A0A; color: #e5e2e1; font-family: "Hanken Grotesk", sans-serif; font-size: 14px; outline: none; border-radius: 0.25rem; }
.taboo-input input:focus { border-color: #d4af37; box-shadow: 0 0 12px rgba(212, 175, 55, 0.3); }
.taboo-list { display: flex; flex-wrap: wrap; gap: 8px; }
.taboo-list span { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border: 1px solid rgba(255, 180, 171, 0.5); background: #1c1b1b; color: #e5e2e1; font-family: "JetBrains Mono", monospace; font-size: 12px; }
.taboo-list small { color: #99907c; }
.taboo-list button { border: 0; background: transparent; color: #99907c; cursor: pointer; }
.taboo-list button:hover { color: #ffb4ab; }

@media (max-width: 900px) {
  .power-pack-grid, .upgrade-grid, .model-card-grid, .scope-template-grid, .custom-scope-grid, .apikey-row, .knowledge-grid { grid-template-columns: 1fr; }
  .billing-tier-head { flex-direction: column; }
  .billing-tier-actions { align-items: flex-start; }
  .identity-row { grid-template-columns: 1fr; gap: 4px; }
  .third-party-row { grid-template-columns: 1fr; }
}
</style>
