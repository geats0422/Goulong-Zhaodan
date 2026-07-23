<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppTopNav from '../components/app/AppTopNav.vue'
import DashboardFooter from '../components/app/DashboardFooter.vue'
import InspectionReviewModal from '../components/inspection/InspectionReviewModal.vue'
import { useAuth } from '../composables/useAuth.js'
import { fetchInspectionRecords } from '../services/inspectionApi.js'
import { getSettingsOverview } from '../services/settingsApi.js'

const { currentUser } = useAuth()
const router = useRouter()
const username = computed(() => currentUser.value?.nickname || '用户')
const fileInput = ref(null)
const selectedFile = ref(null)
const modalOpen = ref(false)
const recentRecords = ref([])
const activeKnowledgeTags = ref([])

const defaultKnowledgeTags = ['招投标法', '房建施工规范']
const mountedKnowledgeTags = computed(() => activeKnowledgeTags.value.length ? activeKnowledgeTags.value : defaultKnowledgeTags)
function riskText(risk, issueCount = 0) {
  if (risk === 'pending') return '等待审查'
  if (risk === 'low') return '纯净通过'
  if (risk === 'medium') return `${issueCount} 处疑点`
  if (risk === 'high') return `${issueCount} 处高风险`
  return '未评级'
}

function riskTone(risk) {
  return ({ pending: 'amber', low: 'green', medium: 'amber', high: 'red' })[risk] || 'amber'
}

async function loadRecentRecords() {
  const data = await fetchInspectionRecords({ page: 1, page_size: 3 })
  recentRecords.value = (data.items || []).map((record) => ({
    icon: record.document_name.toLowerCase().endsWith('.pdf') ? 'picture_as_pdf' : 'description',
    name: record.document_name,
    status: riskText(record.overall_risk, record.issue_count),
    tone: riskTone(record.overall_risk),
  }))
}

async function loadKnowledgeMounts() {
  try {
    const data = await getSettingsOverview()
    activeKnowledgeTags.value = (data.knowledge || [])
      .flatMap(category => category.subcategories || [])
      .flatMap(sub => sub.documents || [])
      .filter(doc => doc.enabled)
      .map(doc => doc.title)
      .slice(0, 4)
  } catch {
    activeKnowledgeTags.value = []
  }
}

function goToKnowledgeBase() {
  router.push('/knowledge-base')
}

function goToHistory() {
  router.push('/history')
}

function goToStatistics() {
  router.push('/statistics')
}

function openFilePicker() {
  fileInput.value?.click()
}

function handleFileSelected(event) {
  const [file] = event.target.files || []
  if (!file) return
  selectedFile.value = file
  modalOpen.value = true
}

function handleModalClose() {
  modalOpen.value = false
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
  loadRecentRecords()
}

onMounted(() => {
  loadRecentRecords()
  loadKnowledgeMounts()
})
</script>

<template>
  <div class="dashboard-page">
    <AppTopNav active="dashboard" />

    <main class="dashboard-main">
      <header class="dashboard-header">
        <div class="breadcrumb">
          <span>句龙</span>
          <span>/</span>
          <strong>靶场大盘</strong>
        </div>
        <div class="dashboard-title-row">
          <h1>欢迎调遣，<span>经办人{{ username }}</span></h1>
          <div class="secure-status"><i></i>TEE 本地静默保护中</div>
        </div>
      </header>

      <section class="dropzone-card" @click="openFilePicker">
        <div class="grid-pattern"></div>
        <div class="dropzone-inner">
          <div class="upload-orb">
            <span class="material-symbols-outlined">file_upload</span>
          </div>
          <div>
            <h2>极速载入案卷</h2>
            <p>拖拽企业材料包至此，或点击调用系统窗口</p>
          </div>
          <button class="primary-action" type="button" @click.stop="openFilePicker">
            <span class="material-symbols-outlined">add_circle</span>
            发起智能初审
          </button>
          <input ref="fileInput" class="visually-hidden-file" type="file" accept=".pdf,.docx,.txt" @change="handleFileSelected" />
        </div>
      </section>

      <section class="dashboard-grid">
        <article class="dashboard-panel">
          <div class="panel-accent"></div>
          <header class="panel-header">
            <span class="material-symbols-outlined">rule</span>
            <h3>当前启用知识库</h3>
          </header>
          <div class="panel-section">
            <h4>审查依据</h4>
            <div class="tag-row">
              <span v-for="rule in mountedKnowledgeTags" :key="rule" class="tag">{{ rule }}</span>
              <button class="tag tag-add" type="button" @click="goToKnowledgeBase"><span class="material-symbols-outlined">add</span>管理</button>
            </div>
          </div>
          <div class="panel-section">
            <h4>挂载策略</h4>
            <p class="panel-note">优先使用用户已启用知识库；未配置时采用系统默认审查依据。</p>
          </div>
        </article>

        <article class="dashboard-panel">
          <div class="panel-accent"></div>
          <header class="panel-header panel-header-between">
            <div>
              <span class="material-symbols-outlined">history</span>
              <h3>近期体检记录</h3>
            </div>
            <button class="panel-link" type="button" aria-label="查看全部" @click="goToHistory">
              <span class="material-symbols-outlined">arrow_forward</span>
            </button>
          </header>
          <div class="record-list">
            <div v-if="recentRecords.length === 0" class="record-empty">暂无体检记录</div>
            <div v-for="record in recentRecords" :key="record.name" class="record-item">
              <div class="record-title">
                <span class="material-symbols-outlined">{{ record.icon }}</span>
                <span>{{ record.name }}</span>
              </div>
              <span class="status-pill" :class="`status-${record.tone}`">{{ record.status }}</span>
            </div>
          </div>
        </article>

        <article class="dashboard-panel lab-panel">
          <div class="lab-accent"></div>
          <header class="panel-header lab-header">
            <span class="material-symbols-outlined">science</span>
            <h3>数据统计</h3>
          </header>
          <div class="lab-content">
            <div>
              <p class="lab-label">DATA INSIGHT</p>
              <h4>审查记录与额度消耗看板</h4>
              <div class="engine-preview">
                <div class="engine-glow"></div>
                <span class="material-symbols-outlined">monitoring</span>
                <span>基于真实体检记录生成趋势</span>
              </div>
            </div>
            <button class="lab-button" type="button" @click="goToStatistics">
              <span class="material-symbols-outlined">input</span>
              查看统计
            </button>
          </div>
        </article>
      </section>
    </main>

    <DashboardFooter />

    <InspectionReviewModal
      :file="selectedFile"
      :open="modalOpen"
      @close="handleModalClose"
    />
  </div>
</template>
