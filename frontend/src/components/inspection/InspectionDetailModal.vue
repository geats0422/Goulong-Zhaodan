<script setup>
import { computed, ref, watch } from 'vue'
import InspectionStepHeader from './InspectionStepHeader.vue'
import InspectionFileSummary from './InspectionFileSummary.vue'
import DocumentPreviewPane from './DocumentPreviewPane.vue'
import KnowledgeTogglePanel from './KnowledgeTogglePanel.vue'
import InspectionReportPane from './InspectionReportPane.vue'
import { downloadInspectionReportPdf, fetchInspectionRecord } from '../../services/inspectionApi.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  recordId: { type: [Number, String], default: null },
})

const emit = defineEmits(['close'])

const STEP = { PARSE: 1, PREPARE: 2, REPORT: 3 }
const currentStep = ref(STEP.PARSE)
const loading = ref(false)
const error = ref('')
const record = ref(null)

const previewText = computed(() => record.value?.parsed_content || record.value?.text_preview || '')
const fileSummary = computed(() => {
  if (!record.value) return null
  const name = record.value.document_name || '未命名文档'
  const ext = name.includes('.') ? name.split('.').pop() : ''
  return {
    name,
    size: 0,
    format: ext || 'txt',
    document_type: record.value.document_type || 'unknown',
    document_type_label: record.value.document_type_label || '未知类型',
  }
})
const reportData = computed(() => {
  if (!record.value) return null
  return {
    id: record.value.id,
    document_name: record.value.document_name,
    overall_risk: record.value.overall_risk,
    summary: record.value.summary,
    issues: record.value.issues || [],
    regulation_refs: record.value.regulation_refs || [],
  }
})

watch(
  () => [props.open, props.recordId],
  async ([isOpen, id]) => {
    if (!isOpen || !id) return
    currentStep.value = STEP.PARSE
    error.value = ''
    record.value = null
    loading.value = true
    try {
      record.value = await fetchInspectionRecord(id)
    } catch (e) {
      error.value = e.message || '审查详情加载失败'
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

function goToStep(step) {
  if (!record.value || loading.value) return
  currentStep.value = step
}

function handleClose() {
  emit('close')
}

async function handleExport() {
  if (!record.value) return
  try {
    await downloadInspectionReportPdf(record.value.id, record.value.document_name)
  } catch (e) {
    error.value = e.message || '导出审查报告失败'
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="detail-overlay" @click.self="handleClose">
      <div class="detail-container" role="dialog" aria-modal="true" aria-label="审查详情">
        <div class="detail-topbar">
          <InspectionStepHeader :current-step="currentStep" />
          <div class="step-jump">
            <button type="button" :class="{ active: currentStep === STEP.PARSE }" :disabled="loading || !record" @click="goToStep(STEP.PARSE)">解析</button>
            <button type="button" :class="{ active: currentStep === STEP.PREPARE }" :disabled="loading || !record" @click="goToStep(STEP.PREPARE)">准备</button>
            <button type="button" :class="{ active: currentStep === STEP.REPORT }" :disabled="loading || !record" @click="goToStep(STEP.REPORT)">报告</button>
          </div>
          <button class="modal-close" type="button" aria-label="关闭详情" @click="handleClose">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <div class="detail-body">
          <div v-if="loading" class="detail-loading">
            <div class="spinner" />
            <p>正在加载审查详情...</p>
          </div>
          <div v-else-if="error" class="detail-error">
            <span class="material-symbols-outlined">error</span>
            <p>{{ error }}</p>
            <button class="action-btn secondary" type="button" @click="handleClose">关闭</button>
          </div>
          <template v-else-if="record">
            <div v-if="currentStep === STEP.PARSE" class="step-content step-parse-layout">
              <DocumentPreviewPane :text="previewText" />
              <aside class="parse-sidebar">
                <InspectionFileSummary :file="fileSummary" />
                <div class="step-actions">
                  <button class="action-btn secondary" type="button" @click="handleClose">关闭</button>
                  <button class="action-btn primary" type="button" @click="goToStep(STEP.PREPARE)">下一步</button>
                </div>
              </aside>
            </div>

            <div v-else-if="currentStep === STEP.PREPARE" class="step-content step-two-col">
              <DocumentPreviewPane :text="previewText" />
              <div class="prepare-sidebar">
                <KnowledgeTogglePanel
                  readonly
                  :document-type="record.document_type || 'unknown'"
                  :document-type-label="record.document_type_label || '未知类型'"
                />
                <div class="step-actions">
                  <button class="action-btn secondary" type="button" @click="goToStep(STEP.PARSE)">上一步</button>
                  <button class="action-btn primary" type="button" @click="goToStep(STEP.REPORT)">查看报告</button>
                </div>
              </div>
            </div>

            <div v-else class="step-content step-report">
              <DocumentPreviewPane :text="previewText" />
              <div class="report-sidebar">
                <InspectionReportPane
                  :report="reportData"
                  :show-back="true"
                  @export="handleExport"
                  @back="goToStep(STEP.PREPARE)"
                  @close="handleClose"
                />
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
}

.detail-container {
  width: 92vw;
  max-width: 1200px;
  height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg, #0a0a0a);
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 70%, transparent);
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.6);
}

.detail-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  border-bottom: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 60%, transparent);
  background: var(--color-surface, #0e0e0e);
}

.step-jump {
  display: inline-flex;
  gap: 6px;
  margin-left: auto;
  margin-right: 8px;
}

.step-jump button {
  min-width: 52px;
  height: 28px;
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 70%, transparent);
  background: transparent;
  color: var(--color-muted, #99907c);
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  letter-spacing: 0.06em;
  cursor: pointer;
}

.step-jump button.active,
.step-jump button:hover:not(:disabled) {
  border-color: var(--color-primary, #d4af37);
  color: var(--color-primary, #d4af37);
  background: color-mix(in srgb, var(--color-primary, #d4af37) 10%, transparent);
}

.step-jump button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 70%, transparent);
  background: transparent;
  color: var(--color-muted, #99907c);
  cursor: pointer;
}

.modal-close:hover {
  color: var(--color-text, #e5e2e1);
}

.detail-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.detail-loading,
.detail-error {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: var(--color-muted, #d0c5af);
}

.detail-error {
  color: #ffb4ab;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid color-mix(in srgb, var(--color-primary, #d4af37) 18%, transparent);
  border-top-color: var(--color-primary, #d4af37);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.step-content {
  height: 100%;
}

.step-parse-layout,
.step-two-col,
.step-report {
  display: grid;
  height: 100%;
  padding: 0;
}

.step-parse-layout {
  grid-template-columns: minmax(0, 1fr) 360px;
}

.step-two-col {
  grid-template-columns: minmax(0, 1fr) 380px;
}

.step-report {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.parse-sidebar,
.prepare-sidebar,
.report-sidebar {
  position: relative;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 55%, transparent);
  background: var(--color-bg, #0a0a0a);
  overflow: hidden;
}

.prepare-sidebar,
.report-sidebar {
  overflow-y: auto;
}

.parse-sidebar {
  padding: 24px 24px 0;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: auto;
  padding: 16px 0 20px;
}

.prepare-sidebar .step-actions {
  padding: 16px 24px 20px;
  border-top: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 40%, transparent);
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 70%, transparent);
  background: transparent;
  color: var(--color-muted, #d0c5af);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13px;
}

.action-btn.primary {
  border-color: var(--color-primary, #d4af37);
  background: var(--color-primary, #d4af37);
  color: #1f1a12;
}

.action-btn.secondary:hover {
  border-color: var(--color-primary, #d4af37);
  color: var(--color-primary, #d4af37);
}

@media (max-width: 900px) {
  .step-parse-layout,
  .step-two-col,
  .step-report {
    grid-template-columns: 1fr;
  }

  .parse-sidebar,
  .prepare-sidebar,
  .report-sidebar {
    border-left: none;
    border-top: 1px solid color-mix(in srgb, var(--color-border, #4d4635) 55%, transparent);
  }
}
</style>
