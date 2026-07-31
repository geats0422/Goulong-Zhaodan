<script setup>
import { ref, onMounted, computed } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'
import DashboardFooter from '../components/app/DashboardFooter.vue'
import BaseSelect from '../components/ui/BaseSelect.vue'
import { useAuth } from '../composables/useAuth.js'

const { fetchWithAuth } = useAuth()

const CATEGORIES = [
  { key: 'new_infrastructure', label: '新基建' },
  { key: 'traditional', label: '传统基建' },
  { key: 'urban_renewal', label: '城市更新' },
]
const CATEGORY_OPTIONS = CATEGORIES.map((c) => ({ value: c.key, label: c.label }))
const SCENARIO_OPTIONS = [
  { value: 'bidding', label: '招投标' },
  { value: 'contract', label: '合同' },
]

const loading = ref(false)
const error = ref(null)
const categoryGroups = ref([])
const showUploadModal = ref(false)
const uploading = ref(false)
const uploadForm = ref({
  file: null,
  category: 'traditional',
  subcategory_id: '',
  subcategory_name: '',
  application_scenario: 'bidding',
})

function mapDocumentStatus(status) {
  if (status === 'completed') return { state: 'ready', label: '索引树已构建' }
  if (status === 'converting' || status === 'indexing') return { state: 'processing', label: '解析中...' }
  if (status === 'pending') return { state: 'pending', label: '处理中...' }
  if (status === 'failed' || status === 'convert_failed' || status === 'index_failed') return { state: 'failed', label: '处理失败' }
  return { state: 'pending', label: '处理中...' }
}

function getIcon(name) {
  if (!name) return 'description'
  return name.endsWith('.pdf') ? 'picture_as_pdf' : 'description'
}

function mapApplicationScenario(scenario) {
  if (scenario === 'contract') return '合同'
  return '招投标'
}

async function fetchAllData() {
  loading.value = true
  error.value = null
  try {
    const res = await fetchWithAuth('/api/v1/knowledge/overview')
    if (!res.ok) throw new Error('获取知识库数据失败')
    const contentType = res.headers.get('content-type')
    if (!contentType || !contentType.includes('application/json')) {
      throw new Error('服务器返回非预期响应')
    }
    const data = await res.json()

    categoryGroups.value = (data.categories || []).map((cat) => ({
      key: cat.key,
      name: cat.label,
      subcategories: (cat.subcategories || []).map((sub) => ({
        id: sub.id,
        name: sub.name,
        assets: (sub.documents || []).map((doc) => {
          const mapped = mapDocumentStatus(doc.current_version?.status)
          return {
            id: doc.id,
            icon: getIcon(doc.current_version?.display_name),
            name: doc.current_version?.display_name || doc.title,
            status: mapped.label,
            state: mapped.state,
            size: '',
            owner_type: doc.owner_type,
            application_scenario: doc.application_scenario,
          }
        }),
      })),
    }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function openUploadModal() {
  uploadForm.value = { file: null, category: 'traditional', subcategory_id: '', subcategory_name: '', application_scenario: 'bidding' }
  showUploadModal.value = true
}

function closeUploadModal() {
  showUploadModal.value = false
}

function handleFileChange(e) {
  uploadForm.value.file = e.target.files[0] || null
}

async function submitUpload() {
  if (!uploadForm.value.file) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', uploadForm.value.file)
    form.append('category', uploadForm.value.category)
    if (uploadForm.value.subcategory_id) {
      form.append('subcategory_id', uploadForm.value.subcategory_id)
    }
    if (uploadForm.value.subcategory_name) {
      form.append('subcategory_name', uploadForm.value.subcategory_name)
    }
    form.append('application_scenario', uploadForm.value.application_scenario)
    const res = await fetchWithAuth('/api/v1/knowledge/upload', { method: 'POST', body: form })
    if (!res.ok) throw new Error('上传失败')
    const uploadContentType = res.headers.get('content-type')
    if (!uploadContentType || !uploadContentType.includes('application/json')) {
      throw new Error('服务器返回非预期响应')
    }
    showUploadModal.value = false
    await fetchAllData()
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

const currentCategorySubcategories = computed(() => {
  const group = categoryGroups.value.find((g) => g.key === uploadForm.value.category)
  if (!group) return []
  return group.subcategories || []
})

const subcategoryOptions = computed(() => [
  { value: '', label: '-- 选择已有子类 --' },
  ...currentCategorySubcategories.value.map((sub) => ({ value: String(sub.id), label: sub.name })),
])

const uploadFileName = computed(() => uploadForm.value.file?.name || '未选择文件')

function triggerUploadFile(inputEl) {
  inputEl?.click()
}

onMounted(fetchAllData)
</script>

<template>
  <div class="dashboard-page knowledge-page">
    <AppTopNav active="knowledge" />

    <main class="knowledge-main">
      <div class="ambient-glow"></div>

      <div class="knowledge-breadcrumb">
        <a href="/dashboard">首页</a>
        <span>/</span>
        <strong>知识库资产管理</strong>
      </div>

      <header class="knowledge-header">
        <div>
          <h1>企业专属参考卷宗库</h1>
          <p>分布式架构下的安全资产管理与索引树维护中心。所有入库文档将自动进行合规性脱敏与语义级拆解。</p>
        </div>
        <button class="upload-button circuit-border" type="button" @click="openUploadModal">
          <span class="material-symbols-outlined">add</span>
          上传新卷宗
        </button>
        <div class="cyber-line"></div>
      </header>

      <div v-if="loading" class="knowledge-loading">
        <span class="material-symbols-outlined loading-spin">progress_activity</span>
        <p>正在加载知识库...</p>
      </div>

      <div v-else-if="error" class="knowledge-error">
        <span class="material-symbols-outlined">error</span>
        <p>{{ error }}</p>
        <button type="button" @click="fetchAllData">重试</button>
      </div>

      <div v-else class="category-stack">
        <section v-for="group in categoryGroups" :key="group.key" class="asset-category">
          <template v-for="sub in group.subcategories" :key="sub.id">
            <div v-if="sub.assets.length > 0" class="subcategory-section">
              <div class="category-title">
                <i></i>
                <h2>{{ sub.name }}</h2>
                <span></span>
              </div>

              <div class="asset-grid">
                <article v-for="asset in sub.assets" :key="asset.id" class="asset-card glass-card">
                  <div class="asset-card-head">
                    <span class="material-symbols-outlined file-icon">{{ asset.icon }}</span>
                    <div class="asset-actions">
                      <button v-if="asset.owner_type !== 'system'" type="button" title="重命名" aria-label="重命名">
                        <span class="material-symbols-outlined">edit</span>
                      </button>
                      <button v-if="asset.owner_type !== 'system'" type="button" title="删除" aria-label="删除">
                        <span class="material-symbols-outlined">delete</span>
                      </button>
                    </div>
                  </div>

                  <div class="asset-body">
                    <h3>{{ asset.name }}</h3>
                    <p class="asset-scenario">任务场景：{{ mapApplicationScenario(asset.application_scenario) }}</p>
                    <div class="asset-meta">
                      <span v-if="asset.owner_type === 'system'" class="status-chip status-system">
                        <i></i>
                        [系统默认]
                      </span>
                      <span class="status-chip" :class="`status-${asset.state}`">
                        <i></i>
                        [{{ asset.status }}]
                      </span>
                      <span v-if="asset.size">{{ asset.size }}</span>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </template>

          <div v-if="group.subcategories.length === 0" class="empty-category">
            <p>暂无文档</p>
          </div>
        </section>

        <section v-if="categoryGroups.length === 0" class="asset-category">
          <div class="empty-category">
            <p>暂无文档</p>
          </div>
        </section>
      </div>
    </main>

    <div v-if="showUploadModal" class="upload-modal" @click.self="closeUploadModal">
      <div class="upload-dialog">
        <h3>上传新卷宗</h3>
        <div class="upload-field">
          <label>选择文件</label>
          <div class="file-picker">
            <input ref="uploadFileInput" class="visually-hidden-file" type="file" @change="handleFileChange" />
            <button type="button" class="file-picker-btn" @click="triggerUploadFile($refs.uploadFileInput)">
              <span class="material-symbols-outlined">upload_file</span>
              选择文件
            </button>
            <span class="file-picker-name">{{ uploadFileName }}</span>
          </div>
        </div>
        <div class="upload-field">
          <BaseSelect v-model="uploadForm.category" label="大类" :options="CATEGORY_OPTIONS" />
        </div>
        <div class="upload-field">
          <BaseSelect
            v-if="currentCategorySubcategories.length > 0"
            v-model="uploadForm.subcategory_id"
            label="子类（可选）"
            :options="subcategoryOptions"
          />
          <label v-else>子类（可选）</label>
          <input v-model="uploadForm.subcategory_name" placeholder="或输入新子类名称" />
        </div>
        <div class="upload-field">
          <BaseSelect v-model="uploadForm.application_scenario" label="应用场景" :options="SCENARIO_OPTIONS" />
        </div>
        <div class="upload-actions">
          <button type="button" class="btn-cancel" @click="closeUploadModal" :disabled="uploading">取消</button>
          <button type="button" class="btn-submit" @click="submitUpload" :disabled="uploading || !uploadForm.file">
            {{ uploading ? '上传中...' : '确认上传' }}
          </button>
        </div>
      </div>
    </div>

    <DashboardFooter />
  </div>
</template>

<style scoped>
.knowledge-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #0a0a0a;
  background-image:
    linear-gradient(rgba(212, 175, 55, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(212, 175, 55, 0.03) 1px, transparent 1px);
  background-size: 64px 64px;
  background-position: center top;
}

.knowledge-main {
  position: relative;
  z-index: 1;
  flex: 1;
  width: min(1440px, calc(100% - 40px));
  margin: 0 auto;
  padding: 48px 0 72px;
}

.ambient-glow {
  position: absolute;
  top: 0;
  left: 25%;
  width: 50%;
  height: 500px;
  z-index: -1;
  border-radius: 999px;
  background: rgba(242, 202, 80, 0.05);
  filter: blur(120px);
  pointer-events: none;
}

.knowledge-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(208, 197, 175, 0.7);
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.knowledge-breadcrumb a {
  color: inherit;
  text-decoration: none;
}

.knowledge-breadcrumb a:hover,
.knowledge-breadcrumb strong {
  color: #f2ca50;
  font-weight: 500;
}

.knowledge-header {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 32px;
  margin-top: 40px;
  padding-bottom: 36px;
}

.knowledge-header h1 {
  position: relative;
  display: inline-block;
  margin: 0 0 16px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.2;
}

.knowledge-header h1::after {
  content: "";
  position: absolute;
  top: 8px;
  right: -18px;
  width: 8px;
  height: 8px;
  background: #d4af37;
  transform: rotate(45deg);
  box-shadow: 0 0 10px rgba(212, 175, 55, 0.5);
}

.knowledge-header p {
  max-width: 720px;
  margin: 0;
  color: #d0c5af;
  line-height: 1.7;
}

.upload-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  padding: 16px 24px;
  background: #f2ca50;
  color: #3c2f00;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  cursor: pointer;
  box-shadow: 0 0 20px rgba(212, 175, 55, 0.2);
}

.upload-button:hover {
  background: #d4af37;
}

.cyber-line {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: rgba(212, 175, 55, 0.2);
}

.cyber-line::after {
  content: "";
  position: absolute;
  right: 0;
  top: -2px;
  width: 4px;
  height: 4px;
  background: #d4af37;
}

.knowledge-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  margin-top: 80px;
  color: #d0c5af;
  font-family: "Geist", monospace;
}

.loading-spin {
  font-size: 40px;
  color: #f2ca50;
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.knowledge-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  margin-top: 80px;
  color: #ffb4ab;
  font-family: "Geist", monospace;
}

.knowledge-error button {
  border: 1px solid rgba(212, 175, 55, 0.3);
  padding: 10px 24px;
  background: transparent;
  color: #f2ca50;
  cursor: pointer;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.knowledge-error button:hover {
  background: rgba(212, 175, 55, 0.1);
}

.category-stack {
  display: flex;
  flex-direction: column;
  gap: 64px;
  margin-top: 56px;
}

.asset-category {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.subcategory-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-category {
  padding: 40px;
  text-align: center;
  color: rgba(208, 197, 175, 0.4);
  font-family: "Geist", monospace;
}

.category-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.category-title i {
  width: 4px;
  height: 24px;
  background: #d4af37;
}

.category-title h2 {
  margin: 0;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 32px;
}

.category-title span {
  position: relative;
  flex: 1;
  height: 1px;
  background: rgba(77, 70, 53, 0.75);
}

.category-title span::after {
  content: "";
  position: absolute;
  right: 0;
  top: -2px;
  width: 4px;
  height: 4px;
  background: rgba(212, 175, 55, 0.5);
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.glass-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(212, 175, 55, 0.2);
  padding: 24px;
  background: rgba(18, 18, 18, 0.7);
  backdrop-filter: blur(12px);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.glass-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.6), transparent);
  opacity: 0;
  transition: opacity 0.2s;
}

.glass-card:hover {
  border-color: rgba(212, 175, 55, 0.5);
  box-shadow: inset 0 0 15px rgba(212, 175, 55, 0.15);
}

.glass-card:hover::before {
  opacity: 1;
}

.asset-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.file-icon {
  color: #f2ca50;
  font-size: 32px;
  opacity: 0.84;
}

.asset-actions {
  display: flex;
  gap: 8px;
}

.asset-actions button {
  border: 0;
  padding: 0;
  background: transparent;
  color: #d0c5af;
  cursor: pointer;
}

.asset-actions button:hover:first-child {
  color: #f2ca50;
}

.asset-actions button:hover:last-child {
  color: #ffb4ab;
}

.asset-actions .material-symbols-outlined {
  font-size: 18px;
}

.asset-body {
  margin-top: 20px;
}

.asset-body h3 {
  margin: 0;
  overflow: hidden;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 22px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.asset-card:hover h3 {
  color: #f2ca50;
}

.asset-scenario {
  margin: 10px 0 0;
  color: #d0c5af;
  font-family: "Geist", "Noto Sans SC", sans-serif;
  font-size: 13px;
  line-height: 1.5;
}

.asset-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.asset-meta > span:last-child {
  color: rgba(208, 197, 175, 0.5);
  font-family: "Geist", monospace;
  font-size: 12px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(153, 144, 124, 0.35);
  padding: 6px 8px;
  background: rgba(53, 53, 52, 0.65);
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.status-chip i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #99907c;
}

.status-ready {
  border-color: rgba(242, 202, 80, 0.25);
  background: rgba(242, 202, 80, 0.1);
  color: #f2ca50;
}

.status-ready i {
  background: #f2ca50;
}

.status-processing i {
  background: #99907c;
}

.status-pending {
  color: #d0c5af;
}

.status-failed {
  border-color: rgba(255, 100, 100, 0.35);
  background: rgba(255, 80, 80, 0.1);
  color: #ffb4ab;
}

.status-failed i {
  background: #ff6464;
}

.upload-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
}

.upload-dialog {
  width: min(480px, calc(100% - 40px));
  border: 1px solid rgba(212, 175, 55, 0.3);
  padding: 32px;
  background: #141414;
}

.upload-dialog h3 {
  margin: 0 0 24px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 24px;
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.upload-field label {
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.upload-field input[type="file"],
.upload-field input,
.upload-field select {
  border: 1px solid rgba(212, 175, 55, 0.2);
  padding: 10px 12px;
  background: rgba(18, 18, 18, 0.9);
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 13px;
}

.visually-hidden-file {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.file-picker {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.file-picker-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid rgba(212, 175, 55, 0.35);
  background: transparent;
  color: #f2ca50;
  font-family: "Geist", monospace;
  font-size: 13px;
  cursor: pointer;
}

.file-picker-btn:hover {
  background: rgba(212, 175, 55, 0.12);
}

.file-picker-name {
  color: #99907c;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-field select {
  cursor: pointer;
}

.upload-field input[type="file"]::file-selector-button {
  border: 1px solid rgba(212, 175, 55, 0.3);
  padding: 6px 16px;
  background: transparent;
  color: #f2ca50;
  cursor: pointer;
  font-family: "Geist", monospace;
  font-size: 12px;
  margin-right: 12px;
}

.upload-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}

.upload-actions button {
  border: 0;
  padding: 10px 20px;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  cursor: pointer;
}

.btn-cancel {
  background: transparent;
  border: 1px solid rgba(153, 144, 124, 0.35) !important;
  color: #d0c5af;
}

.btn-submit {
  background: #f2ca50;
  color: #3c2f00;
}

.btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 980px) {
  .knowledge-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .asset-grid {
    grid-template-columns: 1fr;
  }
}
.status-system {
  border-color: rgba(212, 175, 55, 0.5);
  background: rgba(212, 175, 55, 0.12);
  color: #d4af37;
}

.status-system i {
  background: #d4af37;
}

[data-theme="light"] .upload-dialog {
  background: #ffffff;
  border-color: rgba(180, 160, 100, 0.4);
}

[data-theme="light"] .asset-scenario {
  color: #6f5630;
  font-weight: 600;
}

[data-theme="light"] .upload-dialog h3 {
  color: #1a1a1a;
}

[data-theme="light"] .upload-field input,
[data-theme="light"] .upload-field select {
  background: #f8f7f4;
  color: #1a1a1a;
  border-color: rgba(180, 160, 100, 0.35);
}

[data-theme="light"] .upload-field input[type="file"]::file-selector-button {
  color: #8b7a00;
}

[data-theme="light"] .btn-cancel {
  color: #555;
}

[data-theme="light"] .btn-submit {
  background: #d4af37;
  color: #fff;
}
</style>
