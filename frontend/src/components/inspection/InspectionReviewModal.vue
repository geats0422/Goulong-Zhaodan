<script setup>
import { ref, computed, watch } from 'vue'
import InspectionStepHeader from './InspectionStepHeader.vue'
import InspectionFileSummary from './InspectionFileSummary.vue'
import DocumentPreviewPane from './DocumentPreviewPane.vue'
import KnowledgeTogglePanel from './KnowledgeTogglePanel.vue'
import InspectionReportPane from './InspectionReportPane.vue'
import QuotaErrorModal from '../QuotaErrorModal.vue'
import { parseInspectionFile, fetchInspectionRecord, inspectInspectionRecord, downloadInspectionReportPdf } from '../../services/inspectionApi.js'
import { retryDocumentJob } from '../../services/documentJobApi.js'
import { useDocumentJobPolling } from '../../composables/useDocumentJobPolling.js'
import {
  describeInspectionJobStage,
  describeInspectionJobError,
  isConvertToPdfRequired,
} from '../../composables/inspectionJobStages.js'
import {
  isInsufficientQuotaError,
  extractApiError,
} from '../../composables/quotaError.js'

const props = defineProps({
  file: { type: File, default: null },
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const STEP = { PARSING: 1, PREPARE: 2, REPORT: 3 }

const { startPolling, cancelPolling } = useDocumentJobPolling()

const currentStep = ref(STEP.PARSING)
const stepErrors = ref([null, null, null])
const parseData = ref(null)
const reportData = ref(null)
const inspecting = ref(false)
const sessionExpired = ref(false)
// 最近一次 Step 2 提交的 payload（工程/合同类别 + 知识库），用于失败后重试。
const lastPreparePayload = ref(null)

// 任务 16：额度不足统一弹窗状态。
// 仅在后端返回稳定错误码 insufficient_quota 时打开；其他错误走既有内嵌展示。
const quotaError = ref(null)

// 异步解析任务状态
const parseJob = ref(null)            // useDocumentJobPolling 最新 job 快照
const parseError = ref(null)          // 任务级错误消息（网络错误/轮询超时）
const parseRetrying = ref(false)      // 用户点击重试时
const parseHydrating = ref(false)     // succeeded 后预加载文档预览期间
const inspectionRecordId = ref(null)  // succeeded 后的体检记录 ID

const previewText = computed(() => parseData.value?.file?.parsed_content || parseData.value?.file?.text_preview || '')

const parseStageInfo = computed(() => describeInspectionJobStage(parseJob.value))

const parseFailedMessage = computed(() => {
  if (parseError.value) return parseError.value
  const status = parseJob.value?.status
  if (status === 'failed' || status === 'cancelled') {
    return describeInspectionJobError(parseJob.value)
  }
  return null
})

const parseNeedsPdf = computed(() => isConvertToPdfRequired(parseJob.value))

// succeeded 后仍在预加载文档预览时，继续展示 100% 进度，避免左侧出现空白文档预览。
const parseComplete = computed(
  () => parseData.value && parseJob.value?.status === 'succeeded' && !parseHydrating.value,
)

watch(() => props.open, async (isOpen) => {
  if (!isOpen || !props.file) return

  currentStep.value = STEP.PARSING
  stepErrors.value = [null, null, null]
  parseData.value = null
  reportData.value = null
  inspecting.value = false
  sessionExpired.value = false
  parseJob.value = null
  parseError.value = null
  parseRetrying.value = false
  parseHydrating.value = false
  inspectionRecordId.value = null
  quotaError.value = null
  cancelPolling()

  await startParse(props.file)
})

function startJobPolling(jobId) {
  startPolling(jobId, {
    onUpdate: (job) => { parseJob.value = job },
    onComplete: handleParseComplete,
    onError: (err) => { parseError.value = err.message },
  })
}

async function handleParseComplete(job) {
  parseJob.value = job
  if (job.inspection_record_id) {
    inspectionRecordId.value = job.inspection_record_id
    // 解析成功后预加载 record，使左侧文档预览与文件元信息（document_type 等）就绪。
    parseHydrating.value = true
    try {
      const record = await fetchInspectionRecord(job.inspection_record_id)
      hydrateParseDataFromRecord(record)
    } catch {
      // 预览加载失败不阻塞流程；用户点击「开始审查」时若仍失败会展示具体错误。
    } finally {
      parseHydrating.value = false
    }
  }
  currentStep.value = STEP.PREPARE
}

function hydrateParseDataFromRecord(record) {
  if (!parseData.value?.file || !record) return
  const file = parseData.value.file
  file.parsed_content = record.parsed_content || file.parsed_content || ''
  file.text_preview = record.text_preview || file.text_preview || ''
  if (record.document_type) file.document_type = record.document_type
  if (record.document_type_label) file.document_type_label = record.document_type_label
}

async function startParse(file) {
  parseError.value = null
  parseJob.value = null
  try {
    const data = await parseInspectionFile(file)
    parseData.value = data
    startJobPolling(data.job_id)
  } catch (e) {
    // 任务 16：识别额度不足错误，弹出统一弹窗（不再靠文案匹配）。
    if (isInsufficientQuotaError(e)) {
      quotaError.value = extractApiError(e)
    }
    parseError.value = e.message
  }
}

async function retryParse() {
  const jobId = parseData.value?.job_id
  if (!jobId || parseRetrying.value) return
  parseRetrying.value = true
  parseError.value = null
  parseJob.value = null
  try {
    const job = await retryDocumentJob(jobId)
    parseJob.value = job
    startJobPolling(jobId)
  } catch (e) {
    parseError.value = e.message
  } finally {
    parseRetrying.value = false
  }
}

function goToStep(step) {
  currentStep.value = step
}

async function startInspection(payload) {
  if (!inspectionRecordId.value || inspecting.value) return
  inspecting.value = true
  stepErrors.value[1] = null
  stepErrors.value[2] = null
  // Step 2 提交契约：{ engineering_type_key, contract_type_key, knowledge_document_ids }。
  // 重试（无显式 payload）时复用上一次提交，保证类别选择不丢失。
  const preparePayload = payload || lastPreparePayload.value || {}
  if (payload) lastPreparePayload.value = payload

  try {
    // 提交用户确认的工程/合同类别与知识库选择。
    // 后端审查入口尚未消费新字段时降级为直接拉取已生成的报告，保证流程不中断。
    try {
      await inspectInspectionRecord(inspectionRecordId.value, preparePayload)
    } catch (inspectErr) {
      // 任务 16：额度不足统一弹窗优先于降级逻辑（避免弹窗被吞掉）。
      if (isInsufficientQuotaError(inspectErr)) {
        quotaError.value = extractApiError(inspectErr)
        throw inspectErr
      }
      // 旧后端或不支持新 payload 时忽略，继续拉取报告。
    }
    // worker 完成时已生成完整审查报告，直接通过 record_id 拉取。
    reportData.value = await fetchInspectionRecord(inspectionRecordId.value)
    currentStep.value = STEP.REPORT
  } catch (e) {
    // 任务 16：拉取报告阶段也可能遇到额度不足，同样识别为统一弹窗。
    if (isInsufficientQuotaError(e) && !quotaError.value) {
      quotaError.value = extractApiError(e)
    }
    stepErrors.value[2] = e.message
    if (e.message.includes('记录不存在')) {
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

// 任务 16：额度弹窗交互处理。
// 关闭按钮：仅清理弹窗状态，不改变路由（用户可继续选择重试或关闭主弹窗）。
function handleQuotaClose() {
  quotaError.value = null
}

// 主按钮（前往账单与订阅）：交由 QuotaErrorModal 内的 <a> 触发浏览器跳转，
// 这里仅清理弹窗状态，跳转目标由 getQuotaAction 决定（默认 /settings?tab=billing）。
function handleQuotaNavigate() {
  quotaError.value = null
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
            <div v-if="parseFailedMessage" class="step-error">
              <span class="material-symbols-outlined">error</span>
              <p>{{ parseFailedMessage }}</p>
              <p v-if="parseNeedsPdf" class="step-error-hint">请将文档转为 PDF 后重新上传。</p>
              <div class="step-error-actions">
                <button class="action-btn secondary" type="button" @click="handleClose">关闭</button>
                <button
                  v-if="!parseNeedsPdf && parseData?.job_id"
                  class="action-btn primary"
                  type="button"
                  :disabled="parseRetrying"
                  @click="retryParse"
                >
                  <span class="material-symbols-outlined">refresh</span>
                  {{ parseRetrying ? '正在重试...' : '重试' }}
                </button>
              </div>
            </div>
            <template v-else-if="parseComplete">
              <div class="step-content step-parse-layout">
                <DocumentPreviewPane :text="previewText" />
                <aside class="parse-sidebar">
                  <div class="parse-info">
                    <InspectionFileSummary
                      :file="parseData.file"
                      :parser-engine="parseStageInfo.parserEngine"
                    />
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
            <div v-else class="step-loading step-loading-progress">
              <div class="spinner" />
              <p class="progress-message">{{ parseStageInfo.message }}</p>
              <div v-if="parseStageInfo.progress > 0" class="progress-bar" role="progressbar" :aria-valuenow="parseStageInfo.progress" aria-valuemin="0" aria-valuemax="100">
                <div class="progress-bar-fill" :style="{ width: parseStageInfo.progress + '%' }" />
              </div>
              <p v-if="parseStageInfo.progress > 0" class="progress-percent">{{ parseStageInfo.progress }}%</p>
              <p v-if="parseStageInfo.isMineru" class="progress-engine">
                <span class="material-symbols-outlined">memory</span>MinerU 高质量解析
              </p>
            </div>
          </template>

          <!-- Step 2: 审查准备 -->
          <template v-if="currentStep === STEP.PREPARE">
            <div class="step-content step-two-col">
              <DocumentPreviewPane :text="previewText" />
              <div class="prepare-sidebar">
                <KnowledgeTogglePanel
                  v-if="parseData"
                  :classification="parseData.file"
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

    <!-- 任务 16：统一额度不足弹窗。仅在后端返回 insufficient_quota 时打开。
         按钮跳转目标由后端 action.path 决定，默认 /settings?tab=billing；关闭按钮不改变路由。 -->
    <QuotaErrorModal
      :open="!!quotaError"
      :error="quotaError"
      @close="handleQuotaClose"
      @navigate="handleQuotaNavigate"
    />
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

.step-loading-progress {
  gap: 14px;
  max-width: 480px;
  margin: 0 auto;
}

.progress-message {
  margin: 0;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 14px;
  text-align: center;
}

.progress-bar {
  width: 100%;
  max-width: 360px;
  height: 4px;
  border: 1px solid rgba(77, 70, 53, 0.35);
  background: rgba(77, 70, 53, 0.2);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #d4af37, #f2ca50);
  transition: width 0.4s ease;
}

.progress-percent {
  margin: 0;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  letter-spacing: 0.06em;
}

.progress-engine {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 4px 10px;
  border: 1px solid rgba(212, 175, 55, 0.3);
  background: rgba(212, 175, 55, 0.08);
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.progress-engine .material-symbols-outlined {
  font-size: 14px;
}

.step-error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.step-error-hint {
  margin: -4px 0 0;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
  line-height: 1.6;
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

[data-theme="light"] .progress-message {
  color: #2c2416;
}

[data-theme="light"] .progress-bar {
  border-color: rgba(111, 86, 48, 0.2);
  background: rgba(111, 86, 48, 0.08);
}

[data-theme="light"] .progress-bar-fill {
  background: linear-gradient(90deg, #c5961a, #d4af37);
}

[data-theme="light"] .progress-percent {
  color: #8a7a66;
}

[data-theme="light"] .progress-engine {
  border-color: rgba(197, 150, 26, 0.3);
  background: rgba(197, 150, 26, 0.08);
  color: #c5961a;
}

[data-theme="light"] .step-error-hint {
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
