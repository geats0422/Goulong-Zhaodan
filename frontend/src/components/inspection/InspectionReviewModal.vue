<script setup>
import { ref, computed, watch } from 'vue'
import InspectionStepHeader from './InspectionStepHeader.vue'
import InspectionFileSummary from './InspectionFileSummary.vue'
import DocumentPreviewPane from './DocumentPreviewPane.vue'
import KnowledgeTogglePanel from './KnowledgeTogglePanel.vue'
import InspectionReportPane from './InspectionReportPane.vue'
import { parseInspectionFile, inspectParsedSession, downloadInspectionReportPdf } from '../../services/inspectionApi.js'

const props = defineProps({
  file: { type: File, default: null },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const STEP = { PARSING: 1, PREPARE: 2, REPORT: 3 }

const currentStep = ref(STEP.PARSING)
const stepErrors = ref([null, null, null])
const parseData = ref(null)
const reportData = ref(null)
const inspecting = ref(false)
const sessionExpired = ref(false)

const previewText = computed(() => parseData.value?.file?.parsed_content || parseData.value?.file?.text_preview || '')

watch(() => props.open, async (isOpen) => {
  if (!isOpen || !props.file) return

  currentStep.value = STEP.PARSING
  stepErrors.value = [null, null, null]
  parseData.value = null
  reportData.value = null
  inspecting.value = false
  sessionExpired.value = false

  try {
    parseData.value = await parseInspectionFile(props.file)
    stepErrors.value[0] = null
  } catch (e) {
    stepErrors.value[0] = e.message
  }
})

function goToStep(step) {
  currentStep.value = step
}

async function startInspection() {
  if (!parseData.value || inspecting.value) return
  inspecting.value = true
  stepErrors.value[1] = null
  stepErrors.value[2] = null

  try {
    reportData.value = await inspectParsedSession(parseData.value.session_id, {
      project_id: 'default',
    })
    currentStep.value = STEP.REPORT
  } catch (e) {
    stepErrors.value[2] = e.message
    if (e.message.includes('解析会话已失效')) {
      sessionExpired.value = true
    }
  } finally {
    inspecting.value = false
  }
}

async function handleExport() {
  if (!reportData.value) return
  try {
    await downloadInspectionReportPdf(reportData.value.id, reportData.value.document_name || '审查报告')
  } catch (e) {
    stepErrors.value[2] = e.message
  }
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-topbar">
          <InspectionStepHeader :current-step="currentStep" />
          <button class="modal-close" @click="handleClose">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <div class="modal-body">
          <!-- Step 1: 解析文件 -->
          <template v-if="currentStep === STEP.PARSING">
            <div v-if="stepErrors[0]" class="step-error">
              <span class="material-symbols-outlined">error</span>
              <p>{{ stepErrors[0] }}</p>
              <button class="action-btn" @click="handleClose">关闭</button>
            </div>
            <template v-else-if="parseData">
              <div class="step-content step-parse-layout">
                <DocumentPreviewPane :text="previewText" />
                <aside class="parse-sidebar">
                  <div class="parse-info">
                    <InspectionFileSummary :file="parseData.file" />
                  </div>
                  <div class="step-actions parse-actions">
                    <button class="action-btn secondary" type="button" @click="handleClose">
                      取消
                    </button>
                    <button class="action-btn primary" type="button" @click="goToStep(STEP.PREPARE)">
                      下一步
                    </button>
                  </div>
                </aside>
              </div>
            </template>
            <div v-else class="step-loading">
              <div class="spinner" />
              <p>正在解析文件...</p>
            </div>
          </template>

          <!-- Step 2: 审查准备 -->
          <template v-if="currentStep === STEP.PREPARE">
            <div class="step-content step-two-col">
              <DocumentPreviewPane :text="previewText" />
              <div class="prepare-sidebar">
                <KnowledgeTogglePanel
                  v-if="parseData"
                  :document-type="parseData.file.document_type"
                  :document-type-label="parseData.file.document_type_label"
                  @start-inspection="startInspection"
                />
                <div v-if="inspecting" class="inspecting-overlay">
                  <div class="spinner" />
                  <p>正在执行智能审查...</p>
                </div>
                <div v-if="stepErrors[2] && !inspecting" class="step-error-inline">
                  <span class="material-symbols-outlined">error</span>
                  <p>{{ stepErrors[2] }}</p>
                  <button class="action-btn" @click="startInspection">
                    <span class="material-symbols-outlined">refresh</span>重试
                  </button>
                </div>
              </div>
            </div>
          </template>

          <!-- Step 3: 审查报告 -->
          <template v-if="currentStep === STEP.REPORT">
            <div class="step-content step-report">
              <DocumentPreviewPane :text="previewText" />
              <div class="report-sidebar">
                <InspectionReportPane
                  :report="reportData"
                  :error="stepErrors[2]"
                  @export="handleExport"
                  @back="goToStep(STEP.PREPARE)"
                  @close="handleClose"
                />
              </div>
            </div>
          </template>
        </div>

        <div v-if="sessionExpired" class="session-expired-mask" role="alertdialog" aria-modal="true" aria-labelledby="session-expired-title">
          <div class="session-expired-dialog">
            <span class="material-symbols-outlined">error</span>
            <h3 id="session-expired-title">解析会话已失效</h3>
            <p>解析会话已失效，请关闭弹窗后重新上传文件。</p>
            <button class="action-btn primary" type="button" @click="handleClose">关闭弹窗</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
}

.modal-container {
  width: 92vw;
  max-width: 1200px;
  height: 88vh;
  display: flex;
  flex-direction: column;
  background: #0a0a0a;
  border: 1px solid rgba(77, 70, 53, 0.4);
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.6);
}

.modal-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.3);
  background: #0e0e0e;
}

.modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(77, 70, 53, 0.3);
  background: transparent;
  color: #99907c;
  cursor: pointer;
  transition: color 0.2s;
}

.modal-close:hover {
  color: #e5e2e1;
}

.modal-body {
  flex: 1;
  overflow: hidden;
}

.step-content {
  padding: 24px;
}

.step-parse-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  height: 100%;
  padding: 0;
}

.step-two-col {
  display: grid;
  grid-template-columns: 1fr 380px;
  height: 100%;
  padding: 0;
}

.step-report {
  display: grid;
  grid-template-columns: 1fr 1fr;
  height: 100%;
  padding: 0;
}

.parse-sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  background: #0a0a0a;
  border-left: 1px solid rgba(77, 70, 53, 0.25);
  min-height: 0;
}

.parse-info {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 24px 104px;
}

.step-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.parse-actions {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 5;
  padding: 18px 24px;
  border-top: 1px solid rgba(77, 70, 53, 0.25);
  background: #0f0f0f;
  box-shadow: 0 -16px 24px rgba(0, 0, 0, 0.34);
}

.prepare-sidebar {
  position: relative;
  background: #0a0a0a;
  overflow-y: auto;
}

.report-sidebar {
  background: #0a0a0a;
  overflow-y: auto;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 104px;
  height: 40px;
  padding: 0 20px;
  border: 1px solid rgba(77, 70, 53, 0.3);
  background: #353534;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
}

.action-btn.secondary {
  border-color: rgba(153, 144, 124, 0.35);
  background: rgba(53, 53, 52, 0.35);
  color: #d0c5af;
}

.action-btn.primary {
  border-color: #d4af37;
  background: #d4af37;
  color: #111;
}

.step-error-inline {
  margin-top: 20px;
  padding: 16px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  background: rgba(147, 0, 10, 0.15);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #ffb4ab;
  text-align: center;
}

.step-error-inline .material-symbols-outlined {
  font-size: 28px;
}

.step-error-inline p {
  font-family: "Geist", monospace;
  font-size: 13px;
  margin: 0;
  word-break: break-word;
}

.step-error-inline .action-btn {
  border-color: rgba(255, 180, 171, 0.3);
  background: rgba(147, 0, 10, 0.2);
  color: #ffb4ab;
}

.step-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px 24px;
  color: #ffb4ab;
  text-align: center;
}

.step-error .material-symbols-outlined {
  font-size: 48px;
}

.step-error p {
  font-family: "Geist", monospace;
  font-size: 14px;
}

.step-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 64px 24px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 13px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(77, 70, 53, 0.3);
  border-top-color: #d4af37;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.inspecting-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(10, 10, 10, 0.85);
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 13px;
  z-index: 1;
}

.session-expired-mask {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.72);
}

.session-expired-dialog {
  width: min(420px, calc(100vw - 48px));
  border: 1px solid rgba(255, 180, 171, 0.36);
  padding: 28px;
  background: #121212;
  color: #e5e2e1;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55);
  text-align: center;
}

.session-expired-dialog > .material-symbols-outlined {
  color: #ffb4ab;
  font-size: 40px;
}

.session-expired-dialog h3 {
  margin: 12px 0 8px;
  color: #ffdad6;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 22px;
}

.session-expired-dialog p {
  margin: 0 0 20px;
  color: #d0c5af;
  line-height: 1.7;
}

[data-theme="light"] .modal-overlay {
  background: rgba(0, 0, 0, 0.4);
}

[data-theme="light"] .modal-container {
  background: #faf8f4;
  border-color: rgba(111, 86, 48, 0.2);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.1);
}

[data-theme="light"] .modal-topbar {
  background: #fff;
  border-bottom-color: rgba(111, 86, 48, 0.15);
}

[data-theme="light"] .modal-close {
  border-color: rgba(111, 86, 48, 0.15);
  color: #8a7a66;
}

[data-theme="light"] .modal-close:hover {
  color: #2c2416;
}

[data-theme="light"] .prepare-sidebar,
[data-theme="light"] .parse-sidebar,
[data-theme="light"] .report-sidebar {
  background: #fff;
}

[data-theme="light"] .parse-sidebar {
  border-left-color: rgba(111, 86, 48, 0.15);
}

[data-theme="light"] .parse-actions {
  border-top-color: rgba(111, 86, 48, 0.15);
  background: #fff;
  box-shadow: 0 -16px 24px rgba(111, 86, 48, 0.12);
}

[data-theme="light"] .action-btn {
  border-color: rgba(111, 86, 48, 0.2);
  background: #f0ebe0;
  color: #2c2416;
}

[data-theme="light"] .action-btn.secondary {
  border-color: rgba(111, 86, 48, 0.28);
  background: #fff;
  color: #6f5630;
}

[data-theme="light"] .action-btn.primary {
  border-color: #d49f00;
  background: #d49f00;
  color: #fff;
}

[data-theme="light"] .session-expired-mask {
  background: rgba(44, 36, 22, 0.35);
}

[data-theme="light"] .session-expired-dialog {
  border-color: rgba(184, 28, 28, 0.24);
  background: #fff;
  color: #2c2416;
}

[data-theme="light"] .session-expired-dialog h3 {
  color: #8f1d1d;
}

[data-theme="light"] .session-expired-dialog p {
  color: #6f5630;
}

@media (max-width: 980px) {
  .modal-container {
    width: 100vw;
    height: 100vh;
  }

  .step-two-col,
  .step-parse-layout,
  .step-report {
    grid-template-columns: 1fr;
    height: auto;
  }
}
</style>
