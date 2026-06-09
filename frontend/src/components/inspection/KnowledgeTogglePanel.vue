<script setup>
import { computed, ref, onMounted } from 'vue'
import { getSettingsOverview, updateKnowledgeDocument } from '../../services/settingsApi.js'

const props = defineProps({
  documentType: { type: String, default: 'bidding' },
  documentTypeLabel: { type: String, default: '招投标文件' },
})

const emit = defineEmits(['start-inspection'])

const DOCUMENT_TYPE_LABELS = { bidding: '招投标文件', contract: '合同' }

const loading = ref(false)
const error = ref(null)
const systemDocs = ref([])
const userDocs = ref([])

const availableSystemDocs = computed(() => systemDocs.value.filter(doc => doc.application_scenario === props.documentType))
const availableUserDocs = computed(() => userDocs.value.filter(doc => doc.application_scenario === props.documentType))
const hasAvailableDocs = computed(() => availableSystemDocs.value.length > 0 || availableUserDocs.value.length > 0)

function flattenKnowledgeDocuments(knowledge = []) {
  return knowledge.flatMap(category => (category.subcategories || []).flatMap(subcategory => (
    subcategory.documents || []
  ).map(doc => ({
    ...doc,
    name: doc.title,
    subcategory_name: subcategory.name,
    category_key: category.category_key,
  }))))
}

onMounted(async () => {
  loading.value = true
  error.value = null
  try {
    const overview = await getSettingsOverview()
    const documents = flattenKnowledgeDocuments(overview.knowledge || [])
    systemDocs.value = documents.filter(d => d.owner_type === 'system')
    userDocs.value = documents.filter(d => d.owner_type !== 'system')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function toggleDocument(doc) {
  const list = doc.owner_type === 'system' ? systemDocs : userDocs
  const index = list.value.findIndex(item => item.id === doc.id)
  if (index === -1) return
  const previous = doc.enabled
  try {
    list.value[index].enabled = !doc.enabled
    await updateKnowledgeDocument(doc.id, !previous)
  } catch {
    list.value[index].enabled = previous
  }
}
</script>

<template>
  <div class="knowledge-panel">
    <header class="panel-header">
      <h3><span class="material-symbols-outlined">checklist</span>审查准备</h3>
    </header>

    <div class="panel-section">
      <span class="section-label">识别文档类型</span>
      <span class="type-badge">{{ DOCUMENT_TYPE_LABELS[documentType] || documentTypeLabel }}</span>
    </div>

    <div v-if="loading" class="panel-loading">加载中...</div>
    <div v-else-if="error" class="panel-error">{{ error }}</div>
    <template v-else>
      <div v-if="availableSystemDocs.length" class="panel-section">
        <span class="section-label">系统默认知识库</span>
        <div v-for="doc in availableSystemDocs" :key="doc.id" class="doc-row">
          <span class="doc-name">{{ doc.name || doc.filename }}</span>
          <span class="doc-status doc-status-on">已启用</span>
        </div>
      </div>

      <div v-if="availableUserDocs.length" class="panel-section">
        <span class="section-label">用户知识库</span>
        <div v-for="doc in availableUserDocs" :key="doc.id" class="doc-row">
          <label class="doc-toggle">
            <input type="checkbox" :checked="doc.enabled" @change="toggleDocument(doc)" />
            <span class="toggle-slider" />
          </label>
          <span class="doc-name">{{ doc.name || doc.filename }}</span>
        </div>
      </div>

      <div v-if="!hasAvailableDocs" class="panel-section">
        <span class="section-label">暂无{{ DOCUMENT_TYPE_LABELS[documentType] || documentTypeLabel }}类知识库文档</span>
      </div>
    </template>

    <div class="panel-action">
      <button class="start-btn" :disabled="loading" @click="emit('start-inspection')">
        <span class="material-symbols-outlined">play_arrow</span>
        开始审查
      </button>
    </div>
  </div>
</template>

<style scoped>
.knowledge-panel {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.panel-header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #f2ca50;
  font-family: "Noto Serif", "Noto Serif SC", serif;
  font-size: 20px;
}

.panel-header h3 .material-symbols-outlined {
  font-size: 22px;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.type-badge {
  display: inline-flex;
  border: 1px solid rgba(212, 175, 55, 0.25);
  padding: 6px 12px;
  background: rgba(212, 175, 55, 0.08);
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.doc-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(77, 70, 53, 0.15);
  font-family: "Geist", monospace;
  font-size: 12px;
}

.doc-name {
  color: #d0c5af;
}

.doc-status {
  margin-left: auto;
  padding: 3px 8px;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.doc-status-on {
  border: 1px solid rgba(100, 200, 120, 0.25);
  background: rgba(100, 200, 120, 0.08);
  color: #7dd88a;
}

.doc-toggle {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  cursor: pointer;
}

.doc-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  border-radius: 10px;
  background: rgba(77, 70, 53, 0.35);
  transition: background 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #99907c;
  transition: transform 0.2s;
}

.doc-toggle input:checked + .toggle-slider {
  background: rgba(212, 175, 55, 0.3);
}

.doc-toggle input:checked + .toggle-slider::before {
  transform: translateX(16px);
  background: #d4af37;
}

.panel-loading,
.panel-error {
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.panel-error {
  color: #ffb4ab;
}

.panel-action {
  margin-top: auto;
  padding-top: 16px;
}

.start-btn {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  border: 1px solid #d4af37;
  background: rgba(212, 175, 55, 0.1);
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.start-btn:hover:not(:disabled) {
  background: rgba(212, 175, 55, 0.18);
}

.start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

[data-theme="light"] .panel-header h3 {
  color: #8a6a10;
}

[data-theme="light"] .section-label {
  color: #8a7a66;
}

[data-theme="light"] .type-badge {
  border-color: rgba(197, 150, 26, 0.3);
  background: rgba(197, 150, 26, 0.06);
  color: #c5961a;
}

[data-theme="light"] .doc-name {
  color: #6f5630;
}

[data-theme="light"] .doc-row {
  border-bottom-color: rgba(111, 86, 48, 0.1);
}

[data-theme="light"] .doc-status-on {
  border-color: rgba(40, 140, 60, 0.25);
  background: rgba(40, 140, 60, 0.06);
  color: #2d8a3e;
}

[data-theme="light"] .toggle-slider {
  background: rgba(111, 86, 48, 0.2);
}

[data-theme="light"] .toggle-slider::before {
  background: #8a7a66;
}

[data-theme="light"] .doc-toggle input:checked + .toggle-slider {
  background: rgba(197, 150, 26, 0.2);
}

[data-theme="light"] .doc-toggle input:checked + .toggle-slider::before {
  background: #c5961a;
}

[data-theme="light"] .start-btn {
  border-color: #c5961a;
  background: rgba(197, 150, 26, 0.06);
  color: #c5961a;
}

[data-theme="light"] .start-btn:hover:not(:disabled) {
  background: rgba(197, 150, 26, 0.12);
}
</style>
