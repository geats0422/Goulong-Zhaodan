<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { getSettingsOverview } from '../../services/settingsApi.js'
import { fetchEngineeringTypes, fetchContractTypes } from '../../services/inspectionApi.js'
import BaseSelect from '../ui/BaseSelect.vue'
import BaseCheckbox from '../ui/BaseCheckbox.vue'
import {
  ENGINEERING_TYPES,
  CONTRACT_TYPES,
  mergeTypeOptions,
  resolveRecommendation,
  isLowConfidence,
  buildConfidenceHint,
  selectKnowledgeBasis,
  buildInspectionPayload,
} from '../../composables/inspectionPrepare.js'

const props = defineProps({
  // 分类推荐来源：解析结果 (parseData.file) 或历史记录 (record)。
  // 兼容字段：detected_engineering_type / detected_contract_type /
  // classification_confidence / classification_source / document_type。
  classification: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['start-inspection'])

// ---------------------------------------------------------------------------
// 类别选项：优先取服务端预设，失败回退到内置预设。
// ---------------------------------------------------------------------------
const engineeringOptions = ref(ENGINEERING_TYPES)
const contractOptions = ref(CONTRACT_TYPES)

const engineeringSelectOptions = computed(() =>
  engineeringOptions.value.map((t) => ({ value: t.key, label: t.name })),
)
const contractSelectOptions = computed(() =>
  contractOptions.value.map((t) => ({ value: t.key, label: t.name })),
)

// ---------------------------------------------------------------------------
// AI 分类推荐 + 当前用户选择（两个维度独立）。
// ---------------------------------------------------------------------------
const recommendation = computed(() => resolveRecommendation(props.classification || {}))

const engineeringTypeKey = ref(recommendation.value.engineeringTypeKey)
const contractTypeKey = ref(recommendation.value.contractTypeKey)

// 推荐来源变化时同步默认选择（例如解析完成后 classification 才填充）。
watch(recommendation, (rec) => {
  engineeringTypeKey.value = rec.engineeringTypeKey
  contractTypeKey.value = rec.contractTypeKey
})

const confidenceLevel = computed(() => recommendation.value.confidence)
const showConfidenceHint = computed(() => isLowConfidence(confidenceLevel.value))
const confidenceHint = computed(() => buildConfidenceHint(confidenceLevel.value))
const recommendEngineeringName = computed(() =>
  engineeringOptions.value.find((t) => t.key === recommendation.value.engineeringTypeKey)?.name
    || recommendation.value.engineeringTypeKey,
)
const recommendContractName = computed(() =>
  contractOptions.value.find((t) => t.key === recommendation.value.contractTypeKey)?.name
    || recommendation.value.contractTypeKey,
)

const CONFIDENCE_LABELS = { high: '高', medium: '中', low: '低', unknown: '未知' }

// ---------------------------------------------------------------------------
// 知识库文档：加载 → 按类别过滤 → 用户/系统互斥展示。
// ---------------------------------------------------------------------------
const loading = ref(false)
const error = ref(null)
const allDocs = ref([])
const selectedDocIds = ref([])

function flattenKnowledgeDocuments(knowledge = []) {
  return knowledge.flatMap(category => (category.subcategories || []).flatMap(subcategory => (
    subcategory.documents || []
  ).map(doc => ({
    ...doc,
    name: doc.title || doc.name,
    subcategory_name: subcategory.name,
    category_key: category.category_key,
  }))))
}

// 文档是否匹配当前选择的工程/合同类别。
// 无类别绑定的文档视为通用规则，始终匹配（设计：通用合同规则包参与回退检索）。
function matchesType(doc, engKey, conKey) {
  const engOk = !doc.engineering_type_key
    || doc.engineering_type_key === engKey
    || doc.engineering_type_key === 'general-engineering'
  const conOk = !doc.contract_type_key
    || doc.contract_type_key === conKey
    || doc.contract_type_key === 'other'
  return engOk && conOk
}

// 排除已归档的招投标文档，按当前类别过滤。
const filteredDocs = computed(() => {
  const eng = engineeringTypeKey.value
  const con = contractTypeKey.value
  return allDocs.value
    .filter(doc => doc.application_scenario !== 'bidding')
    .filter(doc => matchesType(doc, eng, con))
})

const availableUserDocs = computed(() => filteredDocs.value.filter(d => d.owner_type !== 'system'))
const availableSystemDocs = computed(() => filteredDocs.value.filter(d => d.owner_type === 'system'))

const knowledgeBasis = computed(() => selectKnowledgeBasis(availableUserDocs.value, availableSystemDocs.value))

// 展示用文档：用户文档存在时只展示用户文档，否则回退系统默认（互斥）。
const basisDocs = computed(() => knowledgeBasis.value.docs)
const showUserBasis = computed(() => knowledgeBasis.value.mode === 'user')
const showSystemFallback = computed(() => knowledgeBasis.value.mode === 'system')

// 类别或文档变化时重置多选为默认全选（仅用户模式可选；系统回退为只读展示）。
watch(knowledgeBasis, (basis) => {
  selectedDocIds.value = [...basis.defaultSelectedIds]
}, { immediate: true })

async function loadOptionsAndDocs() {
  loading.value = true
  error.value = null
  try {
    // 类别预设：服务端未就绪时回退到内置预设。
    const [engRes, conRes, overview] = await Promise.allSettled([
      fetchEngineeringTypes(),
      fetchContractTypes(),
      getSettingsOverview(),
    ])

    if (engRes.status === 'fulfilled' && Array.isArray(engRes.value)) {
      engineeringOptions.value = mergeTypeOptions(ENGINEERING_TYPES, engRes.value)
    }
    if (conRes.status === 'fulfilled' && Array.isArray(conRes.value)) {
      contractOptions.value = mergeTypeOptions(CONTRACT_TYPES, conRes.value)
    }

    if (overview.status === 'fulfilled') {
      allDocs.value = flattenKnowledgeDocuments(overview.value.knowledge || [])
    } else {
      throw overview.reason || new Error('知识库加载失败')
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadOptionsAndDocs)

function handleStartInspection() {
  if (props.readonly) return
  emit('start-inspection', buildInspectionPayload({
    engineeringTypeKey: engineeringTypeKey.value,
    contractTypeKey: contractTypeKey.value,
    knowledgeDocumentIds: selectedDocIds.value,
  }))
}
</script>

<template>
  <div class="knowledge-panel">
    <header class="panel-header">
      <h3><span class="material-symbols-outlined">checklist</span>合同初审准备</h3>
    </header>

    <!-- 旧招投标记录提示：照胆只做合同初审，招投标记录已归档 -->
    <div v-if="recommendation.archived" class="panel-section archived-hint">
      <span class="material-symbols-outlined">archive</span>
      <p>该记录为招投标资料，已归档且不再参与合同初审。</p>
    </div>

    <div class="panel-section">
      <div class="recommend-row">
        <span class="section-label">AI 推荐工程类别</span>
        <span class="recommend-value">{{ recommendEngineeringName }}</span>
        <span class="confidence-badge" :class="`confidence-${confidenceLevel}`">
          置信度：{{ CONFIDENCE_LABELS[confidenceLevel] || '未知' }}
        </span>
      </div>
      <BaseSelect
        v-model="engineeringTypeKey"
        :options="engineeringSelectOptions"
        :disabled="readonly"
        label="工程类别"
      />
    </div>

    <div class="panel-section">
      <div class="recommend-row">
        <span class="section-label">AI 推荐合同类别</span>
        <span class="recommend-value">{{ recommendContractName }}</span>
        <span class="confidence-badge" :class="`confidence-${confidenceLevel}`">
          置信度：{{ CONFIDENCE_LABELS[confidenceLevel] || '未知' }}
        </span>
      </div>
      <BaseSelect
        v-model="contractTypeKey"
        :options="contractSelectOptions"
        :disabled="readonly"
        label="合同类别"
      />
    </div>

    <!-- 低置信度/未知类别提醒：展示但不阻止继续 -->
    <div v-if="showConfidenceHint" class="panel-section confidence-hint">
      <span class="material-symbols-outlined">info</span>
      <p>{{ confidenceHint }}</p>
    </div>

    <div v-if="loading" class="panel-loading">加载中...</div>
    <div v-else-if="error" class="panel-error">{{ error }}</div>
    <template v-else>
      <!-- 用户知识库：默认全选可多选 -->
      <div v-if="showUserBasis" class="panel-section">
        <span class="section-label">用户知识库（审查依据）</span>
        <div v-for="doc in basisDocs" :key="doc.id" class="doc-row">
          <BaseCheckbox
            :model-value="selectedDocIds"
            :value="doc.id"
            :disabled="readonly"
            :label="doc.name || doc.filename"
          />
        </div>
        <p class="basis-note">已默认选中全部匹配的用户知识库，可按需取消。</p>
      </div>

      <!-- 系统默认回退：无用户启用文档时展示（只读） -->
      <div v-else-if="showSystemFallback" class="panel-section">
        <span class="section-label">系统默认知识库（回退）</span>
        <div v-for="doc in basisDocs" :key="doc.id" class="doc-row">
          <span class="doc-name">{{ doc.name || doc.filename }}</span>
          <span class="doc-status doc-status-on">已启用</span>
        </div>
        <p class="basis-note fallback-note">{{ knowledgeBasis.note }}</p>
      </div>

      <div v-else class="panel-section">
        <span class="section-label">暂无匹配的合同知识库文档</span>
      </div>
    </template>

    <div v-if="!readonly" class="panel-action">
      <button class="start-btn" :disabled="loading" @click="handleStartInspection">
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

.recommend-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.recommend-value {
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 12px;
}

.confidence-badge {
  display: inline-flex;
  border: 1px solid rgba(212, 175, 55, 0.25);
  padding: 3px 8px;
  background: rgba(212, 175, 55, 0.08);
  color: #d4af37;
  font-family: "Geist", monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.confidence-badge.confidence-high {
  border-color: rgba(100, 200, 120, 0.3);
  background: rgba(100, 200, 120, 0.08);
  color: #7dd88a;
}

.confidence-badge.confidence-medium,
.confidence-badge.confidence-low,
.confidence-badge.confidence-unknown {
  border-color: rgba(212, 175, 55, 0.4);
  color: #f2ca50;
}

.confidence-hint {
  flex-direction: row;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(212, 175, 55, 0.25);
  background: rgba(212, 175, 55, 0.06);
}

.confidence-hint .material-symbols-outlined {
  font-size: 16px;
  color: #f2ca50;
}

.confidence-hint p {
  margin: 0;
  color: #d0c5af;
  font-family: "Geist", monospace;
  font-size: 11px;
  line-height: 1.6;
}

.archived-hint {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 180, 171, 0.25);
  background: rgba(147, 0, 10, 0.12);
}

.archived-hint .material-symbols-outlined {
  font-size: 16px;
  color: #ffb4ab;
}

.archived-hint p {
  margin: 0;
  color: #ffb4ab;
  font-family: "Geist", monospace;
  font-size: 11px;
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

.basis-note {
  margin: 4px 0 0;
  color: #99907c;
  font-family: "Geist", monospace;
  font-size: 11px;
  line-height: 1.6;
}

.fallback-note {
  color: #7a9e7e;
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

[data-theme="light"] .recommend-value,
[data-theme="light"] .doc-name {
  color: #6f5630;
}

[data-theme="light"] .doc-row {
  border-bottom-color: rgba(111, 86, 48, 0.1);
}

[data-theme="light"] .confidence-badge {
  border-color: rgba(197, 150, 26, 0.3);
  background: rgba(197, 150, 26, 0.06);
  color: #c5961a;
}

[data-theme="light"] .confidence-badge.confidence-high {
  border-color: rgba(40, 140, 60, 0.25);
  background: rgba(40, 140, 60, 0.06);
  color: #2d8a3e;
}

[data-theme="light"] .confidence-hint {
  border-color: rgba(197, 150, 26, 0.25);
  background: rgba(197, 150, 26, 0.05);
}

[data-theme="light"] .confidence-hint .material-symbols-outlined,
[data-theme="light"] .confidence-hint p {
  color: #8a6a10;
}

[data-theme="light"] .doc-status-on {
  border-color: rgba(40, 140, 60, 0.25);
  background: rgba(40, 140, 60, 0.06);
  color: #2d8a3e;
}

[data-theme="light"] .basis-note {
  color: #8a7a66;
}

[data-theme="light"] .fallback-note {
  color: #2d8a3e;
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
