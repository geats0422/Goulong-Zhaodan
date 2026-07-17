<script setup>
const props = defineProps({
  file: { type: Object, default: null },
  parserEngine: { type: String, default: null },
})

const PARSER_ENGINE_LABELS = {
  mineru: '备份文件增强识别',
  markitdown: '本地解析',
  plain: '纯文本读取',
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function engineLabel() {
  if (!props.parserEngine) return ''
  return PARSER_ENGINE_LABELS[props.parserEngine] || props.parserEngine
}
</script>

<template>
  <div v-if="file" class="file-summary">
    <div class="file-summary-row">
      <span class="material-symbols-outlined file-icon">description</span>
      <div class="file-meta">
        <h3>{{ file.name }}</h3>
        <div class="file-details">
          <span class="detail-item"><span class="detail-label">大小</span>{{ formatFileSize(file.size) }}</span>
          <span class="detail-sep">/</span>
          <span class="detail-item"><span class="detail-label">格式</span>{{ file.format }}</span>
          <span class="detail-sep">/</span>
          <span class="detail-item"><span class="detail-label">类型</span>{{ file.document_type_label }}</span>
        </div>
      </div>
    </div>
    <div class="parse-status">
      <span class="material-symbols-outlined">task_alt</span>
      <div>
        <strong>解析完成</strong>
        <p v-if="engineLabel()" class="parse-engine-hint">
          <span class="material-symbols-outlined engine-icon">memory</span>{{ engineLabel() }}
        </p>
        <p v-else>左侧已生成只读文档预览，可确认后进入审查准备。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-summary {
  padding: 20px;
  border: 1px solid rgba(77, 70, 53, 0.3);
  background: #121212;
}

.file-summary-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.file-icon {
  font-size: 28px;
  color: #d4af37;
}

.file-meta h3 {
  margin: 0 0 8px;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 14px;
  word-break: break-all;
}

.file-details {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-family: "Geist", monospace;
  font-size: 12px;
  color: #d0c5af;
}

.detail-label {
  color: #99907c;
  margin-right: 4px;
}

.detail-sep {
  color: rgba(77, 70, 53, 0.5);
}

.parse-status {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(77, 70, 53, 0.2);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: #d0c5af;
}

.parse-status .material-symbols-outlined {
  color: #d4af37;
  font-size: 20px;
}

.parse-status strong {
  display: block;
  margin-bottom: 4px;
  color: #e5e2e1;
  font-family: "Geist", monospace;
  font-size: 13px;
}

.parse-status p {
  margin: 0;
  color: #99907c;
  font-size: 12px;
  line-height: 1.6;
}

.parse-engine-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid rgba(212, 175, 55, 0.25);
  background: rgba(212, 175, 55, 0.06);
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.parse-engine-hint .engine-icon {
  font-size: 13px;
}

[data-theme="light"] .file-summary {
  border-color: rgba(111, 86, 48, 0.2);
  background: #faf8f4;
}

[data-theme="light"] .file-icon {
  color: #c5961a;
}

[data-theme="light"] .file-meta h3 {
  color: #2c2416;
}

[data-theme="light"] .file-details {
  color: #6f5630;
}

[data-theme="light"] .detail-label {
  color: #8a7a66;
}

[data-theme="light"] .parse-status .material-symbols-outlined {
  color: #c5961a;
}

[data-theme="light"] .parse-status strong {
  color: #2c2416;
}

[data-theme="light"] .parse-status p {
  color: #8a7a66;
}

[data-theme="light"] .parse-engine-hint {
  border-color: rgba(197, 150, 26, 0.3);
  background: rgba(197, 150, 26, 0.06);
  color: #c5961a;
}
</style>
