<script setup>
import { computed } from 'vue'
import {
  getRiskChip,
  isArchivedLegacyRecord,
  ARCHIVED_LEGACY_HINT,
  confidenceLabel,
  isLowConfidence,
  rulePackageKeysDisplay,
  knowledgeSourcesDisplay,
} from '../../composables/inspectionDisplay.js'

const props = defineProps({
  report: { type: Object, default: null },
  error: { type: String, default: null },
  showBack: { type: Boolean, default: true },
})

const emit = defineEmits(['export', 'back', 'close'])

// 任务17：风险等级消费服务端最终值，统一中文标签（含 critical），与历史列表/PDF 一致。
const riskChip = computed(() => getRiskChip(props.report?.overall_risk))
const archivedLegacy = computed(() => isArchivedLegacyRecord(props.report))
const lowConfidence = computed(() => isLowConfidence(props.report))
const confidenceText = computed(() => confidenceLabel(props.report?.classification_confidence))
const rulePackages = computed(() => rulePackageKeysDisplay(props.report))
const knowledgeSources = computed(() => knowledgeSourcesDisplay(props.report?.knowledge_sources_snapshot))
</script>

<template>
  <div class="report-pane">
    <div v-if="error" class="report-error">
      <span class="material-symbols-outlined">error</span>
      <p>{{ error }}</p>
    </div>

    <template v-if="report">
      <header class="report-header">
        <h2><span class="material-symbols-outlined">policy</span>智能审查诊断书</h2>
        <span v-if="report.issues?.length" class="diagnostic-alert">
          <i /><span>[发现 {{ report.issues.length }} 处问题]</span>
        </span>
        <span v-else class="diagnostic-alert alert-clean">
          <i /><span>[未发现明显风险]</span>
        </span>
      </header>

      <div class="report-meta">
        <span class="report-doc-name">
          <span class="material-symbols-outlined">description</span>{{ report.document_name }}
        </span>
        <span class="risk-chip" :class="riskChip.cls">
          {{ riskChip.label }}
        </span>
      </div>

      <div v-if="archivedLegacy" class="report-archived-hint">
        <span class="material-symbols-outlined">archive</span>
        <span>{{ ARCHIVED_LEGACY_HINT }}</span>
      </div>

      <div v-if="confidenceText !== '未知' || lowConfidence" class="report-classification">
        <span class="section-label">识别置信度</span>
        <span class="confidence-pill" :class="{ 'confidence-low': lowConfidence }">{{ confidenceText }}</span>
        <span v-if="lowConfidence" class="confidence-notice">置信度较低，请人工复核工程/合同类别</span>
      </div>

      <p v-if="report.summary" class="report-summary">{{ report.summary }}</p>

      <div v-if="report.issues?.length" class="issue-list">
        <article v-for="(issue, idx) in report.issues" :key="idx" class="issue-card circuit-border card-top-highlight">
          <div class="issue-icon" :class="`issue-${issue.severity || 'medium'}`">
            <span class="material-symbols-outlined">{{ issue.severity === 'high' ? 'warning' : 'balance' }}</span>
          </div>
          <div class="issue-body">
            <h3>{{ issue.title }}</h3>
            <p v-if="issue.location" class="issue-location">{{ issue.location }}</p>
            <p><span>诊断对象:</span>{{ issue.object || issue.description }}</p>
            <p v-if="issue.suggestion" class="issue-suggestion"><span>修复建议:</span>{{ issue.suggestion }}</p>
            <div v-if="issue.citation" class="citation-box">
              <div><span class="material-symbols-outlined">menu_book</span>引证标尺</div>
              <p>{{ issue.citation }}</p>
            </div>
            <div v-if="issue.tag" class="issue-tag">{{ issue.tag }}</div>
          </div>
        </article>
      </div>

      <div v-if="report.regulation_refs?.length" class="regulation-section">
        <span class="section-label">引用法规</span>
        <div class="regulation-refs">
          <span v-for="ref in report.regulation_refs" :key="ref" class="ref-tag">{{ ref }}</span>
        </div>
      </div>

      <div v-if="rulePackages.length" class="regulation-section">
        <span class="section-label">规则包快照</span>
        <div class="regulation-refs">
          <span v-for="pkg in rulePackages" :key="pkg" class="ref-tag">{{ pkg }}</span>
        </div>
      </div>

      <div v-if="knowledgeSources.length" class="regulation-section">
        <span class="section-label">知识来源快照</span>
        <div class="regulation-refs">
          <span v-for="src in knowledgeSources" :key="src" class="ref-tag">{{ src }}</span>
        </div>
      </div>

      <div class="report-end"><span /><em>审查结束</em><span /></div>

      <div class="report-actions">
        <button class="action-btn primary" @click="emit('export')">
          <span class="material-symbols-outlined">download</span>导出体检报告
        </button>
        <button v-if="showBack" class="action-btn" @click="emit('back')">
          <span class="material-symbols-outlined">arrow_back</span>返回审查准备
        </button>
        <button class="action-btn" @click="emit('close')">
          <span class="material-symbols-outlined">close</span>关闭弹窗
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.report-pane {
  padding: 32px;
  max-width: 640px;
  margin: 0 auto;
}

.report-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  background: rgba(147, 0, 10, 0.15);
  color: #ffb4ab;
  font-family: "Geist", monospace;
  font-size: 13px;
  margin-bottom: 24px;
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.55);
}

.report-header h2 {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: #f2ca50;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 22px;
}

.diagnostic-alert {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  padding: 6px 10px;
  background: rgba(147, 0, 10, 0.2);
  color: #ffb4ab;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.alert-clean {
  border-color: rgba(100, 200, 120, 0.3);
  background: rgba(100, 200, 120, 0.1);
  color: #7dd88a;
}

.diagnostic-alert i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ffb4ab;
}

.alert-clean i {
  background: #7dd88a;
}

.report-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.report-doc-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 13px;
}

.report-doc-name .material-symbols-outlined {
  font-size: 16px;
  color: #d4af37;
}

.risk-chip {
  padding: 5px 12px;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.06em;
}

.risk-high {
  border: 1px solid rgba(255, 180, 171, 0.35);
  background: rgba(147, 0, 10, 0.15);
  color: #ffb4ab;
}

.risk-medium {
  border: 1px solid rgba(255, 219, 60, 0.3);
  background: rgba(255, 219, 60, 0.08);
  color: #ffe16d;
}

.risk-low {
  border: 1px solid rgba(100, 200, 120, 0.3);
  background: rgba(100, 200, 120, 0.08);
  color: #7dd88a;
}

.risk-critical {
  border: 1px solid rgba(255, 99, 99, 0.45);
  background: rgba(123, 31, 31, 0.28);
  color: rgba(255, 107, 107, 0.96);
}

.report-archived-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 180, 171, 0.3);
  background: rgba(123, 31, 31, 0.15);
  color: rgba(255, 180, 171, 0.92);
  font-family: var(--font-mono, "Geist", monospace);
  font-size: 12px;
}

.report-archived-hint .material-symbols-outlined {
  font-size: 16px;
}

.report-classification {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.confidence-pill {
  padding: 4px 10px;
  border: 1px solid rgba(77, 70, 53, 0.3);
  background: rgba(53, 53, 52, 0.4);
  color: rgba(208, 197, 175, 0.92);
  font-family: var(--font-mono, "Geist", monospace);
  font-size: 12px;
}

.confidence-pill.confidence-low {
  border-color: rgba(255, 219, 60, 0.4);
  background: rgba(255, 219, 60, 0.1);
  color: rgba(255, 225, 109, 0.95);
}

.confidence-notice {
  color: rgba(255, 225, 109, 0.95);
  font-family: var(--font-mono, "Geist", monospace);
  font-size: 11px;
}

.report-summary {
  color: #d0c5af;
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 24px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
}

.issue-card {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 16px;
  padding: 20px;
  background: #121212;
}

.circuit-border {
  border: 1px solid rgba(77, 70, 53, 0.3);
}

.card-top-highlight {
  border-top: 2px solid #d4af37;
}

.issue-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.issue-high {
  border: 1px solid rgba(255, 180, 171, 0.2);
  background: rgba(147, 0, 10, 0.1);
  color: #ffb4ab;
}

.issue-medium,
.issue-gold {
  border: 1px solid rgba(255, 249, 239, 0.2);
  background: rgba(255, 219, 60, 0.1);
  color: #ffe16d;
}

.issue-low {
  border: 1px solid rgba(100, 200, 120, 0.2);
  background: rgba(100, 200, 120, 0.1);
  color: #7dd88a;
}

.issue-body h3 {
  margin: 0 0 12px;
  color: #e5e2e1;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 18px;
}

.issue-location {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.issue-body p {
  margin: 8px 0;
  color: #d0c5af;
  font-size: 13px;
}

.issue-body p span {
  margin-right: 8px;
  color: #99907c;
}

.issue-suggestion,
.issue-suggestion span {
  color: #f2ca50 !important;
}

.citation-box {
  margin-top: 12px;
  border-left: 2px solid #d4af37;
  padding: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: rgba(227, 226, 226, 0.8);
  font-family: "Geist", monospace;
  font-size: 12px;
}

.citation-box div {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(77, 70, 53, 0.35);
  color: #e9c349;
}

.issue-tag {
  display: inline-flex;
  margin-top: 8px;
  border: 1px solid rgba(77, 70, 53, 0.35);
  padding: 6px 10px;
  background: rgba(53, 53, 52, 0.5);
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
}

.regulation-section {
  margin-bottom: 24px;
}

.section-label {
  display: block;
  margin-bottom: 8px;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
}

.regulation-refs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ref-tag {
  border: 1px solid rgba(77, 70, 53, 0.3);
  padding: 4px 10px;
  background: rgba(53, 53, 52, 0.4);
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 11px;
}

.report-end {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 14px;
  margin: 32px 0 24px;
  opacity: 0.42;
}

.report-end span {
  width: 48px;
  height: 1px;
  background: #4d4635;
}

.report-end em {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
  font-style: normal;
}

.report-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid rgba(77, 70, 53, 0.3);
  background: #353534;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.action-btn:hover {
  background: #454544;
}

.action-btn.primary {
  border-color: rgba(212, 175, 55, 0.3);
  background: rgba(212, 175, 55, 0.1);
  color: #d4af37;
}

.action-btn.primary:hover {
  background: rgba(212, 175, 55, 0.18);
}

.action-btn .material-symbols-outlined {
  font-size: 16px;
}

[data-theme="light"] .report-pane {
  background: transparent;
}

[data-theme="light"] .report-header h2 {
  color: #8a6a10;
}

[data-theme="light"] .report-header {
  border-bottom-color: rgba(111, 86, 48, 0.2);
}

[data-theme="light"] .report-doc-name {
  color: #6f5630;
}

[data-theme="light"] .report-summary {
  color: #4a3d2e;
}

[data-theme="light"] .issue-card {
  background: #faf8f4;
  border-color: rgba(111, 86, 48, 0.15);
}

[data-theme="light"] .card-top-highlight {
  border-top-color: #c5961a;
}

[data-theme="light"] .issue-body h3 {
  color: #2c2416;
}

[data-theme="light"] .issue-body p {
  color: #4a3d2e;
}

[data-theme="light"] .issue-body p span {
  color: #8a7a66;
}

[data-theme="light"] .action-btn {
  border-color: rgba(111, 86, 48, 0.2);
  background: #f0ebe0;
  color: #2c2416;
}

[data-theme="light"] .action-btn.primary {
  border-color: rgba(197, 150, 26, 0.3);
  background: rgba(197, 150, 26, 0.06);
  color: #c5961a;
}

[data-theme="light"] .ref-tag {
  background: rgba(197, 150, 26, 0.06);
  border-color: rgba(111, 86, 48, 0.15);
  color: #6f5630;
}

[data-theme="light"] .report-archived-hint {
  border-color: rgba(178, 58, 44, 0.3);
  background: rgba(178, 58, 44, 0.08);
  color: rgba(143, 29, 29, 0.95);
}

[data-theme="light"] .confidence-pill {
  background: rgba(197, 150, 26, 0.06);
  border-color: rgba(111, 86, 48, 0.2);
  color: rgba(111, 86, 48, 0.95);
}

[data-theme="light"] .confidence-pill.confidence-low,
[data-theme="light"] .confidence-notice {
  color: rgba(184, 135, 0, 0.95);
}
</style>
