/**
 * 合同初审历史详情与报告展示工具（任务17）。
 *
 * 统一前端风险等级、最终工程/合同类别、置信度、规则包与知识来源快照的展示，
 * 保证历史列表、详情弹窗、报告面板与 PDF 下载使用服务端最终值与统一中文标签，
 * 旧记录无新字段时回退到历史兼容文本，历史招投标记录展示归档提示。
 *
 * 本模块为纯函数集合，不依赖 Vue，便于用 node:test 覆盖新旧记录、低置信度、
 * 归档提示与风险等级展示一致性。
 */

// 后端 risk_policy.RISK_LEVELS = (low, medium, high, critical)
// 标签文案与后端 report_pdf._RISK_STYLE 保持一致，UI / 历史列表 / PDF 三处统一。
export const RISK_LABELS = {
  low: '低风险',
  medium: '中等风险',
  high: '较高风险',
  critical: '严重风险',
  pending: '等待审查',
}

const RISK_TONES = {
  low: 'success',
  medium: 'warn',
  high: 'danger',
  critical: 'critical',
  pending: 'muted',
}

const RISK_CHIPS = {
  low: { label: '低风险', cls: 'risk-low' },
  medium: { label: '中等风险', cls: 'risk-medium' },
  high: { label: '较高风险', cls: 'risk-high' },
  critical: { label: '严重风险', cls: 'risk-critical' },
}

const UNKNOWN_RISK_CHIP = { label: '未评级', cls: 'risk-muted' }

const CONFIDENCE_LABELS = {
  high: '高',
  medium: '中',
  low: '低',
}

// 旧 severity 词（error/warning/info）的中文映射，避免对历史问题透出英文。
const LEGACY_SEVERITY_LABELS = {
  error: '严重',
  warning: '警示',
  info: '提示',
}

/** 历史招投标资料归档提示，用于只读展示，不可按旧场景重审。 */
export const ARCHIVED_LEGACY_HINT = '招投标资料已归档，无法按旧场景重审'

/**
 * 风险等级统一中文标签。
 * 未知值一律回退到「未评级」，绝不把英文 key 或模型原始标签（error/warning/info）透出给用户。
 */
export function riskLabel(risk) {
  return RISK_LABELS[risk] || '未评级'
}

/** 风险等级样式 tone，用于历史列表 / Dashboard 状态 pill。 */
export function riskTone(risk) {
  return RISK_TONES[risk] || 'muted'
}

/**
 * 问题 severity 中文标签：复用风险术语（low/medium/high/critical），
 * 兼容旧 error/warning/info，未知值回退到「未评级」，绝不透出英文。
 */
export function severityLabel(severity) {
  if (severity && Object.prototype.hasOwnProperty.call(RISK_LABELS, severity) && severity !== 'pending') {
    return RISK_LABELS[severity]
  }
  return LEGACY_SEVERITY_LABELS[severity] || '未评级'
}

/** 报告面板风险 chip（label + cls），覆盖 critical。 */
export function getRiskChip(risk) {
  return RISK_CHIPS[risk] || UNKNOWN_RISK_CHIP
}

/**
 * Dashboard 近期记录状态摘要：保留问题数语义，但基础词与统一标签协调，并支持 critical。
 * - pending → 等待审查
 * - low → 纯净通过
 * - medium/high/critical → 有问题数则展示「N 处…」，否则展示等级本身
 */
export function riskStatusText(risk, issueCount = 0) {
  if (risk === 'pending') return '等待审查'
  if (risk === 'low') return '纯净通过'
  if (risk === 'medium') return issueCount > 0 ? `${issueCount} 处疑点` : '中等风险'
  if (risk === 'high') return issueCount > 0 ? `${issueCount} 处较高风险` : '较高风险'
  if (risk === 'critical') return issueCount > 0 ? `${issueCount} 处严重风险` : '严重风险'
  return '未评级'
}

/**
 * 判断是否为历史招投标归档记录（只读，不重分类）。
 * 与后端 inspection_history.is_archived_legacy_record 判定条件保持一致。
 */
export function isArchivedLegacyRecord(record) {
  if (!record) return false
  return (
    record.application_scenario === 'bidding'
    || record.document_type === 'bidding'
    || record.classification_source === 'archived_legacy'
  )
}

/**
 * 分类展示文案（只读快照），与后端 inspection_history.classification_display 协调：
 * - 归档招投标记录 → 历史记录 + 归档提示
 * - legacy 旧合同记录 → 历史记录 / 通用工程合同
 * - 新记录有完整快照 → 「工程类别 / 合同类别」
 * - 无任何分类字段 → 历史记录 / 通用工程合同
 */
export function classificationDisplayText(record) {
  if (!record) return '历史记录 / 通用工程合同'
  if (isArchivedLegacyRecord(record)) {
    return `历史记录 / ${ARCHIVED_LEGACY_HINT}`
  }
  if (record.classification_source === 'legacy') {
    return '历史记录 / 通用工程合同'
  }
  const engineering = record.engineering_type_snapshot
  const contract = record.contract_type_snapshot
  if (engineering && contract) {
    return `${engineering} / ${contract}`
  }
  return '历史记录 / 通用工程合同'
}

/**
 * 最终工程类别展示：优先快照中文名，无则 final key，无则历史兼容默认「通用工程」。
 */
export function engineeringTypeLabel(record) {
  if (!record) return '通用工程'
  if (record.engineering_type_snapshot) return record.engineering_type_snapshot
  if (record.final_engineering_type) return record.final_engineering_type
  return '通用工程'
}

/**
 * 最终合同类别展示：优先快照中文名，无则 final key，无则历史兼容默认「其他类」。
 */
export function contractTypeLabel(record) {
  if (!record) return '其他类'
  if (record.contract_type_snapshot) return record.contract_type_snapshot
  if (record.final_contract_type) return record.final_contract_type
  return '其他类'
}

/** 置信度中文标签（高/中/低），未知值回退到「未知」。 */
export function confidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] || '未知'
}

/**
 * 低置信度标识：low 或 medium 需要展示提醒（高置信度不提醒）。
 * 旧记录无置信度字段不提醒，避免对历史数据产生噪声。
 */
export function isLowConfidence(record) {
  const confidence = record?.classification_confidence
  return confidence === 'low' || confidence === 'medium'
}

/**
 * 规则包展示：兼容新数组 rule_package_keys 与旧单值 rule_package_key。
 * 新数组优先；空字符串/空白被过滤。
 */
export function rulePackageKeysDisplay(record) {
  if (!record) return []
  if (Array.isArray(record.rule_package_keys)) {
    return record.rule_package_keys
      .map((key) => String(key))
      .filter((key) => key.trim())
  }
  if (record.rule_package_key) return [String(record.rule_package_key)]
  return []
}

/**
 * 知识来源快照展示：从快照对象中提取可读标题（title 优先，其次 name，纯字符串直接保留）。
 * 空标题被过滤；非数组输入返回空数组。
 */
export function knowledgeSourcesDisplay(snapshot) {
  if (!Array.isArray(snapshot)) return []
  return snapshot
    .map((src) => {
      if (src === null || typeof src !== 'object') return src
      return src.title || src.name || null
    })
    .filter((value) => value !== null && value !== undefined && String(value).trim())
}
