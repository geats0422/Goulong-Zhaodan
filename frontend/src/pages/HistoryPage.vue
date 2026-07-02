<script setup>
import { onMounted, ref, watch } from 'vue'
import AppTopNav from '../components/app/AppTopNav.vue'
import DocumentPreviewPane from '../components/inspection/DocumentPreviewPane.vue'
import InspectionReportPane from '../components/inspection/InspectionReportPane.vue'
import {
  burnInspectionRecord,
  deleteInspectionRecord,
  downloadInspectionReportPdf,
  fetchInspectionRecord,
  fetchInspectionRecords,
  inspectInspectionRecord,
} from '../services/inspectionApi.js'

const records = ref([])
const pagination = ref({ page: 1, page_size: 10, total: 0, total_pages: 1 })
const loading = ref(false)
const error = ref('')
const searchKeyword = ref('')
const riskLevel = ref('')
const selectedRecord = ref(null)
const detailLoading = ref(false)
const reviewModalOpen = ref(false)
const reviewRecord = ref(null)
const reviewReport = ref(null)
const reviewError = ref('')
const reviewing = ref(false)

function riskLabel(risk) {
  return ({ pending: '等待审查', low: '纯净通过', medium: '发现疑点', high: '高风险偏离' })[risk] || risk || '未评级'
}

function riskTone(risk) {
  return ({ pending: 'warn', low: 'success', medium: 'warn', high: 'danger' })[risk] || 'muted'
}

function formatTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

async function loadRecords(page = pagination.value.page) {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchInspectionRecords({
      page,
      page_size: pagination.value.page_size,
      risk_level: riskLevel.value,
      keyword: searchKeyword.value.trim(),
    })
    records.value = data.items || []
    pagination.value = data.pagination || pagination.value
  } catch (e) {
    error.value = e.message || '体检记录加载失败'
  } finally {
    loading.value = false
  }
}

function goToPage(page) {
  if (page < 1 || page > pagination.value.total_pages || loading.value) return
  loadRecords(page)
}

async function exportRecord(record) {
  try {
    await downloadInspectionReportPdf(record.id, record.document_name)
  } catch (e) {
    error.value = e.message || '导出审查报告失败'
  }
}

async function viewRecord(record) {
  detailLoading.value = true
  error.value = ''
  try {
    selectedRecord.value = await fetchInspectionRecord(record.id)
  } catch (e) {
    error.value = e.message || '审查详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

function closeRecordDetail() {
  selectedRecord.value = null
}

async function removeRecord(record) {
  if (!window.confirm(`确认删除「${record.document_name}」这条审查记录吗？删除后不可恢复。`)) return
  error.value = ''
  try {
    await deleteInspectionRecord(record.id)
    const nextPage = records.value.length === 1 && pagination.value.page > 1
      ? pagination.value.page - 1
      : pagination.value.page
    await loadRecords(nextPage)
  } catch (e) {
    error.value = e.message || '删除审查记录失败'
  }
}

async function reviewPendingRecord(record) {
  reviewModalOpen.value = true
  reviewRecord.value = null
  reviewReport.value = null
  reviewError.value = ''
  reviewing.value = true

  try {
    reviewRecord.value = await fetchInspectionRecord(record.id)
    reviewReport.value = await inspectInspectionRecord(record.id, { project_id: 'default' })
    await loadRecords(pagination.value.page)
  } catch (e) {
    reviewError.value = e.message || '智能审查失败'
  } finally {
    reviewing.value = false
  }
}

function closeReviewModal() {
  reviewModalOpen.value = false
  reviewRecord.value = null
  reviewReport.value = null
  reviewError.value = ''
  reviewing.value = false
}

async function exportReviewReport() {
  if (!reviewReport.value) return
  try {
    await downloadInspectionReportPdf(reviewReport.value.id, reviewReport.value.document_name)
  } catch (e) {
    reviewError.value = e.message || '导出审查报告失败'
  }
}

async function burnRecordContent() {
  if (!selectedRecord.value) return
  if (!window.confirm('焚烧后原文不可恢复，确认焚烧？')) return
  error.value = ''
  try {
    await burnInspectionRecord(selectedRecord.value.id)
    selectedRecord.value.parsed_content = ''
  } catch (e) {
    error.value = e.message || '焚烧原文失败'
  }
}

watch([riskLevel, searchKeyword], () => loadRecords(1))
onMounted(() => loadRecords(1))
</script>

<template>
  <div class="inspection-archive-page">
    <AppTopNav active="inspection" />

    <main class="archive-shell">
      <div class="archive-breadcrumb">首页 / 审查档案库</div>
      <header class="archive-header">
        <div>
          <p class="eyebrow">INSPECTION ARCHIVE</p>
          <h1>审查档案库</h1>
        </div>
        <div class="archive-filters" role="search">
          <label class="search-box">
            <span class="material-symbols-outlined">search</span>
            <input v-model="searchKeyword" type="search" placeholder="检索案卷名称..." />
          </label>
          <label class="select-box">
            <span>诊断结果</span>
            <select v-model="riskLevel">
              <option value="">全部</option>
              <option value="low">纯净通过</option>
              <option value="medium">发现疑点</option>
              <option value="high">高风险偏离</option>
            </select>
          </label>
        </div>
      </header>

      <section class="archive-card">
        <div v-if="error" class="archive-error">
          <span class="material-symbols-outlined">error</span>
          {{ error }}
        </div>

        <table class="archive-table">
          <thead>
            <tr>
              <th>案卷名称</th>
              <th>工程类别</th>
              <th>体检时间</th>
              <th>挂载重症</th>
              <th>诊断结果</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="6" class="empty-cell">正在加载审查档案...</td>
            </tr>
            <tr v-else-if="records.length === 0">
              <td colspan="6" class="empty-cell">暂无审查档案，请先在首页上传合同或招投标文件完成审查。</td>
            </tr>
            <tr v-for="record in records" v-else :key="record.id">
              <td class="record-name">
                <span class="material-symbols-outlined">description</span>
                {{ record.document_name }}
              </td>
              <td>{{ record.document_type_label || '-' }}</td>
              <td>{{ formatTime(record.created_at) }}</td>
              <td>
                <span class="issue-pill">{{ record.overall_risk === 'pending' ? '待审查' : `${record.issue_count} 处问题` }}</span>
              </td>
              <td>
                <span class="risk-pill" :class="riskTone(record.overall_risk)">{{ riskLabel(record.overall_risk) }}</span>
              </td>
              <td class="actions-cell">
                <button v-if="record.overall_risk === 'pending'" type="button" @click="reviewPendingRecord(record)">
                  <span class="material-symbols-outlined">policy</span>审查
                </button>
                <button type="button" @click="viewRecord(record)">
                  <span class="material-symbols-outlined">visibility</span>查看报告
                </button>
                <button type="button" @click="exportRecord(record)">
                  <span class="material-symbols-outlined">download</span>下载报告
                </button>
                <button type="button" class="danger-action" @click="removeRecord(record)">
                  <span class="material-symbols-outlined">delete</span>删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <nav class="archive-pagination" aria-label="审查档案分页">
        <button type="button" :disabled="pagination.page <= 1 || loading" @click="goToPage(pagination.page - 1)">上一页</button>
        <button
          v-for="page in pagination.total_pages"
          :key="page"
          type="button"
          :class="{ active: page === pagination.page }"
          :disabled="loading"
          @click="goToPage(page)"
        >
          {{ page }}
        </button>
        <button type="button" :disabled="pagination.page >= pagination.total_pages || loading" @click="goToPage(pagination.page + 1)">下一页</button>
      </nav>
    </main>

    <div v-if="reviewModalOpen" class="review-modal-overlay" @click.self="closeReviewModal">
      <div class="review-modal-container">
        <div class="review-modal-topbar">
          <div>
            <span class="review-modal-eyebrow">INSPECTION REPORT</span>
            <strong>智能审查诊断书</strong>
          </div>
          <button class="modal-close" type="button" @click="closeReviewModal">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <div class="review-modal-body">
          <DocumentPreviewPane :text="reviewRecord?.parsed_content || reviewRecord?.text_preview || ''" />
          <div class="review-report-sidebar">
            <div v-if="reviewing" class="reviewing-panel">
              <div class="spinner" />
              <p>正在执行智能审查...</p>
            </div>
            <InspectionReportPane
              v-else
              :report="reviewReport"
              :error="reviewError"
              :show-back="false"
              @export="exportReviewReport"
              @close="closeReviewModal"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-if="selectedRecord || detailLoading" class="record-modal-backdrop" @click.self="closeRecordDetail">
      <section class="record-modal" role="dialog" aria-modal="true" aria-labelledby="record-detail-title">
        <header class="record-modal-header">
          <div>
            <p class="eyebrow">INSPECTION DETAIL</p>
            <h2 id="record-detail-title">审查详情</h2>
          </div>
          <button type="button" class="modal-close" aria-label="关闭详情" @click="closeRecordDetail">
            <span class="material-symbols-outlined">close</span>
          </button>
        </header>

        <div v-if="detailLoading" class="modal-loading">正在加载审查详情...</div>
        <template v-else-if="selectedRecord">
          <div class="record-meta-grid">
            <div>
              <span>案卷名称</span>
              <strong>{{ selectedRecord.document_name }}</strong>
            </div>
            <div>
              <span>工程类别</span>
              <strong>{{ selectedRecord.document_type_label || '-' }}</strong>
            </div>
            <div>
              <span>体检时间</span>
              <strong>{{ formatTime(selectedRecord.created_at) }}</strong>
            </div>
            <div>
              <span>诊断结果</span>
              <strong>{{ riskLabel(selectedRecord.overall_risk) }}</strong>
            </div>
          </div>

          <section class="detail-section">
            <h3>审查摘要</h3>
            <p>{{ selectedRecord.summary || '暂无摘要' }}</p>
          </section>

          <section class="detail-section">
            <h3>问题清单</h3>
            <div v-if="(selectedRecord.issues || []).length === 0" class="empty-detail">暂无发现问题</div>
            <article v-for="(issue, idx) in selectedRecord.issues" v-else :key="idx" class="issue-card">
              <div class="issue-card-title">
                <strong>{{ issue.title || `问题 ${idx + 1}` }}</strong>
                <span>{{ issue.severity || '未评级' }}</span>
              </div>
              <p v-if="issue.description">{{ issue.description }}</p>
              <p v-if="issue.suggestion">建议：{{ issue.suggestion }}</p>
            </article>
          </section>

          <section class="detail-section">
            <h3>引用依据</h3>
            <div v-if="(selectedRecord.regulation_refs || []).length === 0" class="empty-detail">暂无引用依据</div>
            <ul v-else class="ref-list">
              <li v-for="ref in selectedRecord.regulation_refs" :key="ref">{{ ref }}</li>
            </ul>
          </section>

          <div v-if="selectedRecord.parsed_content" class="detail-section">
            <button type="button" class="burn-action" @click="burnRecordContent">
              <span class="material-symbols-outlined">local_fire_department</span>焚烧原文
            </button>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.inspection-archive-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #faf6ea 0%, #efe5c7 100%);
  color: #2c2416;
}

.archive-shell {
  width: min(1120px, calc(100vw - 40px));
  margin: 0 auto;
  padding: 72px 0 96px;
}

.archive-breadcrumb,
.eyebrow {
  color: #8a6a2f;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.archive-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  margin: 28px 0 36px;
}

.archive-header h1 {
  margin: 6px 0 0;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 500;
  letter-spacing: 0.08em;
}

.archive-filters {
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-box,
.select-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid rgba(138, 106, 47, 0.34);
  padding: 10px 4px;
  color: #8a6a2f;
}

.search-box input,
.select-box select {
  min-width: 210px;
  border: 0;
  background: transparent;
  color: #2c2416;
  font: inherit;
  outline: 0;
}

.select-box span {
  white-space: nowrap;
}

.archive-card {
  border-top: 2px solid #d4af37;
  background: rgba(255, 252, 244, 0.64);
  box-shadow: 0 18px 60px rgba(111, 86, 48, 0.08);
}

.archive-error {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(184, 28, 28, 0.18);
  margin: 16px;
  padding: 12px 14px;
  background: rgba(184, 28, 28, 0.08);
  color: #8f1d1d;
}

.archive-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.archive-table th,
.archive-table td {
  border-bottom: 1px solid rgba(138, 106, 47, 0.16);
  padding: 18px 20px;
  text-align: left;
}

.archive-table th {
  color: #7b633a;
  font-size: 12px;
  font-weight: 600;
}

.archive-table tbody tr:hover {
  background: rgba(212, 175, 55, 0.1);
}

.record-name {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #2c2416;
  font-weight: 600;
}

.record-name .material-symbols-outlined {
  color: #d4af37;
  font-size: 20px;
}

.issue-pill,
.risk-pill {
  display: inline-flex;
  border: 1px solid rgba(138, 106, 47, 0.22);
  padding: 5px 8px;
  font-size: 12px;
}

.risk-pill.success { color: #16a05d; }
.risk-pill.warn { color: #b88700; }
.risk-pill.danger { color: #c24132; }
.risk-pill.muted { color: #7b633a; }

.actions-cell button,
.archive-pagination button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid rgba(138, 106, 47, 0.28);
  background: rgba(255, 252, 244, 0.7);
  color: #8a6a2f;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.actions-cell button {
  padding: 8px 10px;
}

.actions-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actions-cell .danger-action {
  color: #b23a2c;
}

.actions-cell button:hover,
.archive-pagination button:hover:not(:disabled),
.archive-pagination button.active {
  border-color: #d4af37;
  background: rgba(212, 175, 55, 0.12);
  color: #5c4212;
}

.archive-pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.empty-cell {
  padding: 48px 20px !important;
  color: #8a6a2f;
  text-align: center !important;
}

.archive-pagination {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 24px;
}

.archive-pagination button {
  min-width: 38px;
  height: 36px;
  padding: 0 12px;
}

.review-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
}

.review-modal-container {
  width: 92vw;
  max-width: 1200px;
  height: 88vh;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(77, 70, 53, 0.4);
  background: #0a0a0a;
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.6);
}

.review-modal-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.3);
  background: #0e0e0e;
  color: #e5e2e1;
}

.review-modal-topbar div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.review-modal-eyebrow {
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
}

.review-modal-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
}

.review-report-sidebar {
  min-height: 0;
  overflow-y: auto;
  border-left: 1px solid rgba(77, 70, 53, 0.35);
  background: #101114;
}

.reviewing-panel {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #d0c5af;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(212, 175, 55, 0.18);
  border-top-color: #d4af37;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.record-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: rgba(44, 36, 22, 0.34);
  backdrop-filter: blur(8px);
}

.record-modal {
  width: min(760px, 100%);
  max-height: min(820px, calc(100vh - 64px));
  overflow-y: auto;
  border: 1px solid rgba(138, 106, 47, 0.28);
  background: #fffaf0;
  box-shadow: 0 28px 80px rgba(61, 43, 13, 0.24);
}

.record-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px 20px;
  border-bottom: 1px solid rgba(138, 106, 47, 0.18);
}

.record-modal-header h2 {
  margin: 4px 0 0;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 30px;
  font-weight: 500;
  letter-spacing: 0.08em;
}

.modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(138, 106, 47, 0.24);
  background: rgba(255, 252, 244, 0.86);
  color: #8a6a2f;
  cursor: pointer;
}

.modal-loading,
.record-meta-grid,
.detail-section {
  margin: 24px 32px;
}

.modal-loading,
.empty-detail {
  color: #8a6a2f;
}

.record-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.record-meta-grid div {
  border: 1px solid rgba(138, 106, 47, 0.18);
  background: rgba(255, 252, 244, 0.68);
  padding: 12px 14px;
}

.record-meta-grid span {
  display: block;
  margin-bottom: 6px;
  color: #8a6a2f;
  font-size: 12px;
}

.record-meta-grid strong {
  font-weight: 500;
}

.detail-section h3 {
  margin: 0 0 12px;
  color: #6f5630;
  font-size: 15px;
  letter-spacing: 0.08em;
}

.detail-section p {
  margin: 0;
  color: rgba(44, 36, 22, 0.78);
  line-height: 1.8;
}

.issue-card {
  border: 1px solid rgba(138, 106, 47, 0.18);
  background: rgba(255, 252, 244, 0.68);
  padding: 14px 16px;
}

.issue-card + .issue-card {
  margin-top: 10px;
}

.issue-card-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.issue-card-title span {
  color: #b88700;
  font-size: 12px;
}

.ref-list {
  margin: 0;
  padding-left: 18px;
  color: rgba(44, 36, 22, 0.78);
  line-height: 1.8;
}

.burn-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(178, 58, 44, 0.36);
  background: rgba(178, 58, 44, 0.08);
  color: #b23a2c;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.burn-action:hover {
  border-color: #b23a2c;
  background: rgba(178, 58, 44, 0.16);
}

@media (max-width: 900px) {
  .archive-header,
  .archive-filters {
    align-items: stretch;
    flex-direction: column;
  }

  .archive-card {
    overflow-x: auto;
  }

  .archive-table {
    min-width: 860px;
  }

  .review-modal-body {
    grid-template-columns: 1fr;
  }

  .review-report-sidebar {
    border-left: none;
    border-top: 1px solid rgba(77, 70, 53, 0.35);
  }

  .record-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
