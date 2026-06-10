<script setup>
import { computed, onMounted, ref } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'
import {
  createTabooWord,
  deleteTabooWord,
  getSettingsOverview,
  updateKnowledgeDocument,
  updatePassword,
  updateProfile,
  updateTabooWord,
} from '../services/settingsApi.js'

const activeTab = ref('system')
const tabs = [
  { key: 'system', label: '[系统设置]' },
  { key: 'knowledge', label: '[知识库设置]' },
  { key: 'taboo', label: '[违禁词设置]' },
]

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const message = ref('')
const profile = ref(null)
const knowledge = ref([])
const tabooWords = ref([])
const profileForm = ref({ display_name: '', wechat_bound: false, alipay_bound: false, burn_after_read: true })
const passwordForm = ref({ old_password: '', new_password: '' })
const tabooForm = ref({ word: '', replacement: '', note: '' })
const editingTabooId = ref(null)

const quotaPercent = computed(() => {
  if (!profile.value?.monthly_quota) return 0
  return Math.min(100, (profile.value.quota_used / profile.value.monthly_quota) * 100)
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const data = await getSettingsOverview()
    profile.value = data.profile
    knowledge.value = data.knowledge || []
    tabooWords.value = data.taboo_words || []
    profileForm.value = {
      display_name: data.profile.display_name,
      wechat_bound: data.profile.wechat_bound,
      alipay_bound: data.profile.alipay_bound,
      burn_after_read: data.profile.burn_after_read,
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设置加载失败'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  message.value = ''
  try {
    profile.value = await updateProfile(profileForm.value)
    message.value = '系统设置已保存'
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  saving.value = true
  message.value = ''
  try {
    await updatePassword(passwordForm.value)
    passwordForm.value = { old_password: '', new_password: '' }
    message.value = '密码已更新'
  } catch (err) {
    error.value = err instanceof Error ? err.message : '密码更新失败'
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

onMounted(loadSettings)
</script>

<template>
  <div class="dashboard-page settings-page">
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
        <article class="settings-card circuit-card card-primary">
          <header>
            <span class="material-symbols-outlined">account_balance_wallet</span>
            <h2>令鉴与配额</h2>
          </header>
          <div class="quota-grid">
            <div>
              <p class="setting-label">当前订阅等级</p>
              <strong><span class="material-symbols-outlined">workspace_premium</span>{{ profile.subscription_plan }}</strong>
            </div>
            <div>
              <div class="quota-head">
                <p class="setting-label">本月可用体检额度</p>
                <span>{{ profile.quota_used }} / {{ profile.monthly_quota }}</span>
              </div>
              <div class="quota-track"><i :style="{ width: `${quotaPercent}%` }"></i></div>
            </div>
          </div>
        </article>

        <article class="settings-card">
          <header>
            <span class="material-symbols-outlined muted-icon">badge</span>
            <h2>身份与绑定</h2>
          </header>
          <div class="identity-grid">
            <label>
              <span>用户名</span>
              <input readonly :value="profile.username" />
            </label>
            <label>
              <span>显示名称</span>
              <input v-model="profileForm.display_name" maxlength="100" />
            </label>
          </div>
          <div class="binding-section">
            <p class="setting-label">第三方鉴权绑定</p>
            <div class="binding-row">
              <span class="binding-chip" :class="{ active: profileForm.wechat_bound }">
                微信 <small>{{ profileForm.wechat_bound ? '已绑定' : '未绑定' }}</small>
                <button type="button" @click="profileForm.wechat_bound = !profileForm.wechat_bound">切换</button>
              </span>
              <span class="binding-chip" :class="{ active: profileForm.alipay_bound }">
                支付宝 <small>{{ profileForm.alipay_bound ? '已绑定' : '未绑定' }}</small>
                <button type="button" @click="profileForm.alipay_bound = !profileForm.alipay_bound">切换</button>
              </span>
            </div>
          </div>
          <button class="settings-action" type="button" :disabled="saving" @click="saveProfile">保存系统设置</button>
        </article>

        <article class="settings-card">
          <header><span class="material-symbols-outlined muted-icon">lock_reset</span><h2>修改密码</h2></header>
          <div class="identity-grid">
            <label><span>旧密码</span><input v-model="passwordForm.old_password" type="password" /></label>
            <label><span>新密码</span><input v-model="passwordForm.new_password" type="password" minlength="6" /></label>
          </div>
          <button class="settings-action" type="button" :disabled="saving" @click="savePassword">更新密码</button>
        </article>

        <article class="settings-card circuit-card card-primary safety-card">
          <div>
            <header>
              <span class="material-symbols-outlined">enhanced_encryption</span>
              <h2>数据安全锁</h2>
            </header>
            <p>激活后，所有会话结束立即清除内存残留痕迹，符合最高级保密标准。</p>
          </div>
          <div class="burn-toggle">
            <span>阅后即焚模式</span>
            <label aria-label="阅后即焚模式">
              <input v-model="profileForm.burn_after_read" type="checkbox" />
              <i></i>
            </label>
          </div>
        </article>
      </section>

      <section v-else-if="!loading && activeTab === 'knowledge'" class="settings-content knowledge-settings full-width">
        <article v-for="category in knowledge" :key="category.category_key" class="settings-card private-archive circuit-card card-primary">
          <header><span class="material-symbols-outlined">folder_special</span><h2>{{ category.category_label }}</h2></header>
          <div v-if="category.subcategories.length" class="knowledge-grid">
            <div v-for="sub in category.subcategories" :key="sub.id">
              <strong>{{ sub.name }}</strong>
              <span v-if="!sub.documents.length">暂无文档</span>
              <label v-for="doc in sub.documents" :key="doc.id" class="doc-toggle">
                <input type="checkbox" :checked="doc.enabled" @change="toggleDocument(doc)" />
                <span>{{ doc.title }}</span>
              </label>
            </div>
          </div>
          <p v-else class="empty-state">暂无知识库文档</p>
        </article>
      </section>

      <section v-else-if="!loading" class="settings-content taboo-settings">
        <article class="settings-card taboo-card">
          <header><span class="material-symbols-outlined">warning</span><h2>生成与审查规避标准</h2></header>
          <p>设置绝对红线规避标准，引擎在处理文本时将严格隔离以下词条。</p>
          <form class="taboo-input" @submit.prevent="submitTabooWord">
            <input v-model="tabooForm.word" placeholder="输入需规避的敏感词汇..." required maxlength="100" />
            <input v-model="tabooForm.replacement" placeholder="建议替换词（可选）" maxlength="100" />
            <input v-model="tabooForm.note" placeholder="备注（可选）" />
            <button type="submit" :disabled="saving">{{ editingTabooId ? '保存修改' : '隔离入库' }}</button>
            <button v-if="editingTabooId" type="button" @click="resetTabooForm">取消</button>
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
  </div>
</template>

<style scoped>
.settings-page {
  min-height: 100vh;
  background: #0f1115;
}

.settings-main {
  width: min(1440px, calc(100% - 40px));
  margin: 0 auto;
  padding: 48px 0 96px;
}

.settings-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.settings-breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.settings-breadcrumb a:hover,
.settings-breadcrumb strong {
  color: #f2ca50;
  font-weight: 500;
}

.settings-breadcrumb .material-symbols-outlined {
  font-size: 16px;
}

.settings-header {
  margin: 24px 0 28px;
  padding-top: 16px;
  border-top: 2px solid rgba(212, 175, 55, 0.4);
}

.settings-header h1 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.2;
}

.settings-tabs {
  display: flex;
  gap: 32px;
  border-bottom: 1px solid #353534;
  margin-bottom: 32px;
}

.settings-tabs button {
  position: relative;
  border: 0;
  padding: 0 0 16px;
  background: transparent;
  color: #d0c5af;
  font-size: 18px;
  cursor: pointer;
}

.settings-tabs button.active {
  border-bottom: 2px solid #d4af37;
  color: #f2ca50;
  box-shadow: 0 4px 10px -2px rgba(212, 175, 55, 0.3);
}

.settings-tabs button.active::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -5px;
  width: 8px;
  height: 8px;
  transform: translateX(-50%);
  background: #d4af37;
}

.settings-content {
  max-width: 960px;
}

.settings-content.full-width {
  max-width: 1120px;
}

.settings-state,
.settings-error,
.settings-message,
.empty-state {
  border: 1px solid #4d4635;
  padding: 14px 16px;
  margin-bottom: 18px;
  background: #1c1b1b;
  color: #d0c5af;
}

.settings-error {
  border-color: rgba(255, 180, 171, 0.55);
  color: #ffb4ab;
}

.settings-message {
  border-color: rgba(74, 222, 128, 0.35);
  color: #34d399;
}

.system-settings,
.knowledge-settings,
.taboo-settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.knowledge-settings {
  max-width: 1120px;
  display: grid;
  grid-template-columns: 360px 1fr;
}

.settings-card {
  position: relative;
  border: 1px solid rgba(212, 175, 55, 0.2);
  padding: 24px;
  background: rgba(18, 18, 18, 0.72);
  backdrop-filter: blur(20px);
}

.settings-action {
  margin-top: 22px;
  border: 1px solid #d4af37;
  padding: 10px 18px;
  background: rgba(212, 175, 55, 0.1);
  color: #f2ca50;
  cursor: pointer;
}

.settings-action:disabled,
.taboo-input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-primary {
  border-top: 2px solid rgba(212, 175, 55, 0.62);
}

.circuit-card::before,
.circuit-card::after {
  content: "";
  position: absolute;
  width: 7px;
  height: 7px;
  border: 1px solid #d4af37;
}

.circuit-card::before {
  top: 0;
  left: 0;
  border-right: 0;
  border-bottom: 0;
}

.circuit-card::after {
  right: 0;
  bottom: 0;
  border-top: 0;
  border-left: 0;
}

.settings-card header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.settings-card header h2 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 24px;
}

.settings-card header .material-symbols-outlined {
  color: #f2ca50;
}

.muted-icon {
  color: #99907c !important;
}

.quota-grid,
.identity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 32px;
}

.setting-label,
.identity-grid label span {
  display: block;
  margin: 0 0 8px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.quota-grid strong {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #ffe088;
  font-size: 18px;
}

.quota-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.quota-head span {
  color: #f2ca50;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.quota-track {
  position: relative;
  height: 8px;
  overflow: hidden;
  background: #2a2a2a;
}

.quota-track i {
  position: absolute;
  inset: 0 auto 0 0;
  width: 28.4%;
  background: #10b981;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
}

.identity-grid input,
.taboo-input input {
  width: 100%;
  border: 0;
  border-bottom: 1px solid #4d4635;
  padding: 0 0 10px;
  background: transparent;
  color: #d0c5af;
  font-family: "Geist", monospace;
  outline: none;
}

.binding-section {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid #353534;
}

.binding-row,
.taboo-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.binding-chip,
.taboo-list span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #4d4635;
  padding: 8px 12px;
  background: #1c1b1b;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.binding-chip.active {
  border-color: rgba(212, 175, 55, 0.35);
  background: rgba(242, 202, 80, 0.05);
  box-shadow: 0 0 15px rgba(212, 175, 55, 0.15);
}

.binding-chip small {
  color: #99907c;
}

.binding-chip button {
  border: 0;
  background: transparent;
  color: #f2ca50;
  cursor: pointer;
}

.binding-chip.active small {
  color: #f2ca50;
}

.safety-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
}

.safety-card p {
  margin: 0;
  color: #99907c;
}

.burn-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #34d399;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.burn-toggle label {
  position: relative;
  width: 44px;
  height: 24px;
  cursor: pointer;
}

.burn-toggle input {
  opacity: 0;
}

.burn-toggle i {
  position: absolute;
  inset: 0;
  border: 1px solid #4d4635;
  border-radius: 999px;
  background: #353534;
}

.burn-toggle i::after {
  content: "";
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
}

.burn-toggle input:checked + i {
  background: #10b981;
  box-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
}

.public-tree ul {
  list-style: none;
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
}

.public-tree li,
.knowledge-grid div {
  border: 1px solid #4d4635;
  padding: 14px;
  background: #1c1b1b;
  color: #d0c5af;
}

.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.knowledge-grid strong {
  display: block;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 22px;
}

.knowledge-grid span {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.doc-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  color: #d0c5af;
  font-size: 13px;
}

.doc-toggle input {
  accent-color: #d4af37;
}

.taboo-card {
  border-top: 2px solid #ffb4ab;
  overflow: hidden;
}

.taboo-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 120px;
  background: linear-gradient(180deg, rgba(255, 180, 171, 0.1), transparent);
  pointer-events: none;
}

.taboo-card header,
.taboo-card p,
.taboo-input,
.taboo-list {
  position: relative;
  z-index: 1;
}

.taboo-card header h2,
.taboo-card header .material-symbols-outlined {
  color: #ffb4ab;
}

.taboo-card p {
  color: #99907c;
}

.taboo-input {
  display: flex;
  gap: 10px;
  margin: 28px 0;
}

.taboo-input input:focus {
  border-bottom-color: #ffb4ab;
}

.taboo-input button {
  border: 1px solid #ffb4ab;
  padding: 10px 22px;
  background: rgba(255, 180, 171, 0.2);
  color: #ffb4ab;
  cursor: pointer;
}

.taboo-list span {
  border-color: rgba(255, 180, 171, 0.5);
}

.taboo-list small {
  color: #99907c;
}

.taboo-list button {
  border: 0;
  background: transparent;
  color: #99907c;
  cursor: pointer;
}

.taboo-list button:hover {
  color: #ffb4ab;
}

@media (max-width: 900px) {
  .settings-tabs,
  .safety-card,
  .taboo-input {
    align-items: flex-start;
    flex-direction: column;
  }

  .quota-grid,
  .identity-grid,
  .knowledge-settings,
  .knowledge-grid {
    grid-template-columns: 1fr;
  }
}
</style>
