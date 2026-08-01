import { test } from 'node:test'
import assert from 'node:assert/strict'

const {
  RISK_LABELS,
  riskLabel,
  riskTone,
  getRiskChip,
  riskStatusText,
  isArchivedLegacyRecord,
  ARCHIVED_LEGACY_HINT,
  classificationDisplayText,
  engineeringTypeLabel,
  contractTypeLabel,
  confidenceLabel,
  isLowConfidence,
  rulePackageKeysDisplay,
  knowledgeSourcesDisplay,
} = await import('../inspectionDisplay.js')

// ---------------------------------------------------------------------------
// 风险等级统一中文标签：与后端 PDF 一致，必须覆盖 critical
// 契约：low/medium/high/critical 中文标签，不显示英文/模型原始标签
// ---------------------------------------------------------------------------
test('RISK_LABELS 覆盖 low/medium/high/critical 四级 + pending', () => {
  assert.equal(RISK_LABELS.low, '低风险')
  assert.equal(RISK_LABELS.medium, '中等风险')
  assert.equal(RISK_LABELS.high, '较高风险')
  assert.equal(RISK_LABELS.critical, '严重风险')
  assert.equal(RISK_LABELS.pending, '等待审查')
})

test('riskLabel: 已知等级返回统一中文标签', () => {
  assert.equal(riskLabel('low'), '低风险')
  assert.equal(riskLabel('medium'), '中等风险')
  assert.equal(riskLabel('high'), '较高风险')
  assert.equal(riskLabel('critical'), '严重风险')
  assert.equal(riskLabel('pending'), '等待审查')
})

test('riskLabel: 未知/null/undefined 不显示英文，回退到「未评级」', () => {
  assert.equal(riskLabel('unknown'), '未评级')
  assert.equal(riskLabel(null), '未评级')
  assert.equal(riskLabel(undefined), '未评级')
  assert.equal(riskLabel(''), '未评级')
  assert.doesNotMatch(riskLabel('weird'), /^(low|medium|high|critical)$/i)
})

test('riskLabel: 不出现模型原始标签（error/warning/info）', () => {
  assert.equal(riskLabel('error'), '未评级')
  assert.equal(riskLabel('warning'), '未评级')
  assert.equal(riskLabel('info'), '未评级')
})

test('riskTone: 各风险等级有对应样式 tone', () => {
  assert.equal(riskTone('low'), 'success')
  assert.equal(riskTone('medium'), 'warn')
  assert.equal(riskTone('high'), 'danger')
  assert.equal(riskTone('critical'), 'critical')
  assert.equal(riskTone('pending'), 'muted')
  assert.equal(riskTone('unknown'), 'muted')
})

// ---------------------------------------------------------------------------
// issue severity 标签：复用风险术语，兼容旧 error/warning/info，统一中文
// ---------------------------------------------------------------------------
test('severityLabel 覆盖新风险术语 low/medium/high/critical', async () => {
  const mod = await import('../inspectionDisplay.js')
  assert.equal(mod.severityLabel('low'), '低风险')
  assert.equal(mod.severityLabel('medium'), '中等风险')
  assert.equal(mod.severityLabel('high'), '较高风险')
  assert.equal(mod.severityLabel('critical'), '严重风险')
})

test('severityLabel 兼容旧 error/warning/info 不显示英文', async () => {
  const mod = await import('../inspectionDisplay.js')
  assert.equal(mod.severityLabel('error'), '严重')
  assert.equal(mod.severityLabel('warning'), '警示')
  assert.equal(mod.severityLabel('info'), '提示')
})

test('severityLabel 未知值/null 不显示英文，回退未评级', async () => {
  const mod = await import('../inspectionDisplay.js')
  assert.equal(mod.severityLabel('weird'), '未评级')
  assert.equal(mod.severityLabel(null), '未评级')
})

test('getRiskChip: 返回 label+cls，覆盖 critical', () => {
  assert.deepEqual(getRiskChip('low'), { label: '低风险', cls: 'risk-low' })
  assert.deepEqual(getRiskChip('medium'), { label: '中等风险', cls: 'risk-medium' })
  assert.deepEqual(getRiskChip('high'), { label: '较高风险', cls: 'risk-high' })
  assert.deepEqual(getRiskChip('critical'), { label: '严重风险', cls: 'risk-critical' })
  const unknown = getRiskChip('foo')
  assert.equal(unknown.label, '未评级')
  assert.doesNotMatch(unknown.label, /^foo$/i)
})

// ---------------------------------------------------------------------------
// Dashboard 状态摘要：保留问题数语义，但基础词与统一标签协调，且支持 critical
// ---------------------------------------------------------------------------
test('riskStatusText: pending 等待审查', () => {
  assert.equal(riskStatusText('pending'), '等待审查')
})

test('riskStatusText: low 显示纯净通过', () => {
  assert.equal(riskStatusText('low', 0), '纯净通过')
})

test('riskStatusText: medium 带问题数', () => {
  assert.equal(riskStatusText('medium', 3), '3 处疑点')
  assert.equal(riskStatusText('medium', 0), '中等风险')
})

test('riskStatusText: high 带问题数', () => {
  assert.equal(riskStatusText('high', 2), '2 处较高风险')
})

test('riskStatusText: critical 带问题数（任务17新增）', () => {
  assert.equal(riskStatusText('critical', 5), '5 处严重风险')
  assert.equal(riskStatusText('critical', 0), '严重风险')
})

// ---------------------------------------------------------------------------
// 历史 bidding 归档：只读快照，不重分类，提示归档
// ---------------------------------------------------------------------------
test('ARCHIVED_LEGACY_HINT 提示文案', () => {
  assert.equal(ARCHIVED_LEGACY_HINT, '招投标资料已归档，无法按旧场景重审')
})

test('isArchivedLegacyRecord: application_scenario=bidding 为归档', () => {
  assert.equal(isArchivedLegacyRecord({ application_scenario: 'bidding' }), true)
})

test('isArchivedLegacyRecord: document_type=bidding 为归档', () => {
  assert.equal(isArchivedLegacyRecord({ document_type: 'bidding' }), true)
})

test('isArchivedLegacyRecord: classification_source=archived_legacy 为归档', () => {
  assert.equal(isArchivedLegacyRecord({ classification_source: 'archived_legacy' }), true)
})

test('isArchivedLegacyRecord: 合同记录不为归档', () => {
  assert.equal(isArchivedLegacyRecord({ document_type: 'contract' }), false)
  assert.equal(isArchivedLegacyRecord({ classification_source: 'legacy' }), false)
})

test('isArchivedLegacyRecord: null/空对象安全', () => {
  assert.equal(isArchivedLegacyRecord(null), false)
  assert.equal(isArchivedLegacyRecord({}), false)
})

// ---------------------------------------------------------------------------
// 分类展示文案：与后端 inspection_history.classification_display 协调
// ---------------------------------------------------------------------------
test('classificationDisplayText: 归档招投标记录显示归档提示', () => {
  const text = classificationDisplayText({ document_type: 'bidding' })
  assert.match(text, /招投标资料已归档/)
  assert.match(text, /历史记录/)
})

test('classificationDisplayText: legacy 旧合同记录显示通用工程合同', () => {
  assert.equal(
    classificationDisplayText({ classification_source: 'legacy' }),
    '历史记录 / 通用工程合同',
  )
})

test('classificationDisplayText: 新记录有快照显示「工程类别 / 合同类别」', () => {
  assert.equal(
    classificationDisplayText({
      engineering_type_snapshot: '市政道路',
      contract_type_snapshot: '专业工程分包',
    }),
    '市政道路 / 专业工程分包',
  )
})

test('classificationDisplayText: 无任何分类字段显示历史兼容文本', () => {
  assert.equal(classificationDisplayText({}), '历史记录 / 通用工程合同')
  assert.equal(classificationDisplayText(null), '历史记录 / 通用工程合同')
})

test('classificationDisplayText: 只有一个快照也回退到通用工程合同', () => {
  assert.equal(
    classificationDisplayText({ engineering_type_snapshot: '市政道路' }),
    '历史记录 / 通用工程合同',
  )
})

// ---------------------------------------------------------------------------
// 最终工程/合同类别：优先快照中文名，无则 key，无则历史兼容默认
// ---------------------------------------------------------------------------
test('engineeringTypeLabel: snapshot 中文名优先', () => {
  assert.equal(
    engineeringTypeLabel({ engineering_type_snapshot: '钢结构', final_engineering_type: 'steel' }),
    '钢结构',
  )
})

test('engineeringTypeLabel: 无 snapshot 时回退到 final key', () => {
  assert.equal(
    engineeringTypeLabel({ final_engineering_type: 'municipal-road' }),
    'municipal-road',
  )
})

test('engineeringTypeLabel: 全无字段显示「通用工程」', () => {
  assert.equal(engineeringTypeLabel({}), '通用工程')
  assert.equal(engineeringTypeLabel(null), '通用工程')
})

test('contractTypeLabel: snapshot 中文名优先', () => {
  assert.equal(
    contractTypeLabel({ contract_type_snapshot: '劳务分包', final_contract_type: 'labor' }),
    '劳务分包',
  )
})

test('contractTypeLabel: 无 snapshot 时回退到 final key', () => {
  assert.equal(contractTypeLabel({ final_contract_type: 'other' }), 'other')
})

test('contractTypeLabel: 全无字段显示「其他类」', () => {
  assert.equal(contractTypeLabel({}), '其他类')
  assert.equal(contractTypeLabel(null), '其他类')
})

// ---------------------------------------------------------------------------
// 置信度：中文标签 + 低置信度标识
// ---------------------------------------------------------------------------
test('confidenceLabel: high/medium/low 中文', () => {
  assert.equal(confidenceLabel('high'), '高')
  assert.equal(confidenceLabel('medium'), '中')
  assert.equal(confidenceLabel('low'), '低')
  assert.equal(confidenceLabel('unknown'), '未知')
  assert.equal(confidenceLabel(null), '未知')
})

test('isLowConfidence: low/medium 为低置信度（需提醒）', () => {
  assert.equal(isLowConfidence({ classification_confidence: 'low' }), true)
  assert.equal(isLowConfidence({ classification_confidence: 'medium' }), true)
})

test('isLowConfidence: high 不提醒', () => {
  assert.equal(isLowConfidence({ classification_confidence: 'high' }), false)
})

test('isLowConfidence: 无置信度字段（旧记录）不提醒', () => {
  assert.equal(isLowConfidence({}), false)
  assert.equal(isLowConfidence(null), false)
})

// ---------------------------------------------------------------------------
// 规则包展示：兼容新数组 rule_package_keys 与旧单值 rule_package_key
// ---------------------------------------------------------------------------
test('rulePackageKeysDisplay: 新数组字段直接返回过滤空值', () => {
  assert.deepEqual(
    rulePackageKeysDisplay({ rule_package_keys: ['general-contract', 'house-building'] }),
    ['general-contract', 'house-building'],
  )
})

test('rulePackageKeysDisplay: 数组含空字符串被过滤', () => {
  assert.deepEqual(
    rulePackageKeysDisplay({ rule_package_keys: ['general-contract', '', '  '] }),
    ['general-contract'],
  )
})

test('rulePackageKeysDisplay: 旧单值 rule_package_key 兼容为单元素数组', () => {
  assert.deepEqual(
    rulePackageKeysDisplay({ rule_package_key: 'general-contract' }),
    ['general-contract'],
  )
})

test('rulePackageKeysDisplay: 新数组优先于旧单值', () => {
  assert.deepEqual(
    rulePackageKeysDisplay({ rule_package_keys: ['new'], rule_package_key: 'old' }),
    ['new'],
  )
})

test('rulePackageKeysDisplay: 无任何规则包字段返回空数组', () => {
  assert.deepEqual(rulePackageKeysDisplay({}), [])
  assert.deepEqual(rulePackageKeysDisplay(null), [])
})

// ---------------------------------------------------------------------------
// 知识来源快照展示：提取可读标题
// ---------------------------------------------------------------------------
test('knowledgeSourcesDisplay: 提取 title 字段', () => {
  assert.deepEqual(
    knowledgeSourcesDisplay([
      { title: '民法典合同编', type: 'law' },
      { title: '建筑法', type: 'law' },
    ]),
    ['民法典合同编', '建筑法'],
  )
})

test('knowledgeSourcesDisplay: 无 title 时回退到 name', () => {
  assert.deepEqual(
    knowledgeSourcesDisplay([{ name: '保障农民工工资支付条例' }]),
    ['保障农民工工资支付条例'],
  )
})

test('knowledgeSourcesDisplay: 纯字符串快照直接保留', () => {
  assert.deepEqual(
    knowledgeSourcesDisplay(['建设工程质量管理条例']),
    ['建设工程质量管理条例'],
  )
})

test('knowledgeSourcesDisplay: 过滤空标题', () => {
  assert.deepEqual(
    knowledgeSourcesDisplay([{ title: '' }, { title: '建筑法' }, { foo: 'bar' }]),
    ['建筑法'],
  )
})

test('knowledgeSourcesDisplay: 非数组返回空数组', () => {
  assert.deepEqual(knowledgeSourcesDisplay(null), [])
  assert.deepEqual(knowledgeSourcesDisplay(undefined), [])
  assert.deepEqual(knowledgeSourcesDisplay({}), [])
})
