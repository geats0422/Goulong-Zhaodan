// 任务 14 回归校验：Step 2「合同初审准备」面板不再包含招投标/合同场景切换，
// 并按设计契约提交 {engineering_type_key, contract_type_key, knowledge_document_ids}。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 14
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(file) {
  return readFileSync(resolve(root, file), 'utf8')
}

const panel = read('src/components/inspection/KnowledgeTogglePanel.vue')
const header = read('src/components/inspection/InspectionStepHeader.vue')
const modal = read('src/components/inspection/InspectionReviewModal.vue')
const api = read('src/services/inspectionApi.js')

// ---------------------------------------------------------------------------
// 1. KnowledgeTogglePanel: 场景切换 UI 必须彻底移除
// ---------------------------------------------------------------------------
const scenarioSwitchArtifacts = [
  'SCENARIO_OPTIONS',
  'scenario-switch',
  'scenario-btn',
  'switchScenario',
  'effectiveScenario',
  'selectedScenario',
  "update:selectedScenario",
  'DOCUMENT_TYPE_LABELS',
  '切换场景',
  '识别文档类型',
]
for (const token of scenarioSwitchArtifacts) {
  if (panel.includes(token)) {
    throw new Error(`KnowledgeTogglePanel 不得再保留招投标/合同场景切换残留：${token}`)
  }
}

// 2. 场景切换不得作为可选项重新出现（bidding 不能作为可选场景）
if (panel.includes("{ value: 'bidding'") || panel.includes("value: \"bidding\"")) {
  throw new Error('KnowledgeTogglePanel 不得再提供 bidding 作为可选场景')
}

// ---------------------------------------------------------------------------
// 3. KnowledgeTogglePanel: 必须呈现「合同初审准备」与两个独立类别维度
// ---------------------------------------------------------------------------
if (!panel.includes('合同初审准备')) {
  throw new Error('KnowledgeTogglePanel 标题必须为「合同初审准备」')
}
if (!panel.includes('AI 推荐工程类别') || !panel.includes('AI 推荐合同类别')) {
  throw new Error('KnowledgeTogglePanel 必须分别展示工程类别与合同类别两个独立维度的 AI 推荐')
}
if (!panel.includes('BaseSelect')) {
  throw new Error('KnowledgeTogglePanel 必须使用类别选择器让用户独立修改工程/合同类别')
}
if (!panel.includes('BaseCheckbox')) {
  throw new Error('KnowledgeTogglePanel 必须支持用户知识库多选')
}

// 4. 置信度提醒存在但不阻止继续（开始审查按钮始终可用）
if (!panel.includes('confidence-hint') || !panel.includes('showConfidenceHint')) {
  throw new Error('KnowledgeTogglePanel 必须在低置信度时展示提醒')
}
if (!panel.includes('开始审查')) {
  throw new Error('KnowledgeTogglePanel 必须保留「开始审查」入口（提醒不阻止继续）')
}

// 5. 用户/系统知识库互斥展示
if (!panel.includes('selectKnowledgeBasis') || !panel.includes('showSystemFallback')) {
  throw new Error('KnowledgeTogglePanel 必须基于 selectKnowledgeBasis 实现用户/系统知识库互斥展示')
}

// 6. 提交 payload 走设计契约三字段
if (!panel.includes('buildInspectionPayload')) {
  throw new Error('KnowledgeTogglePanel 必须通过 buildInspectionPayload 构造提交 payload')
}

// ---------------------------------------------------------------------------
// 7. InspectionStepHeader: 第二步标题为「合同初审准备」
// ---------------------------------------------------------------------------
if (!header.includes("label: '合同初审准备'")) {
  throw new Error('InspectionStepHeader 第二步标题必须为「合同初审准备」')
}

// ---------------------------------------------------------------------------
// 8. InspectionReviewModal: 不再回退到 bidding，按新契约提交 payload
// ---------------------------------------------------------------------------
const modalBiddingDefaults = [
  "|| 'bidding'",
  "selectedScenario",
  "document_type || 'bidding'",
]
for (const token of modalBiddingDefaults) {
  if (modal.includes(token)) {
    throw new Error(`InspectionReviewModal 不得再保留 bidding 回退或场景切换：${token}`)
  }
}
if (!modal.includes(':classification="parseData.file"')) {
  throw new Error('InspectionReviewModal 必须将解析结果作为 classification 传入准备面板')
}
if (!modal.includes('inspectInspectionRecord') || !modal.includes('lastPreparePayload')) {
  throw new Error('InspectionReviewModal 必须通过 inspectInspectionRecord 提交 Step 2 payload')
}

// ---------------------------------------------------------------------------
// 9. inspectionApi: 提供类别预设查询
// ---------------------------------------------------------------------------
if (!api.includes('fetchEngineeringTypes') || !api.includes('fetchContractTypes')) {
  throw new Error('inspectionApi 必须提供工程类别与合同类别预设查询函数')
}

console.log('Step 2 合同初审准备面板契约校验通过（无招投标/合同场景切换）')
