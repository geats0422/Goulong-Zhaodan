// 合同初审准备（Step 2）核心决策逻辑。
//
// 本模块刻意保持为纯函数集合，便于在 node:test 下独立测试。
// 组件层（KnowledgeTogglePanel.vue）只负责 IO 与渲染，所有
// 「类别推荐 / 置信度提醒 / 知识库互斥 / 提交 payload」的判断都收口在这里。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md

// ---------------------------------------------------------------------------
// 预设类别：工程类别与合同类别是两个独立维度，key 互不重叠。
// ---------------------------------------------------------------------------

export const ENGINEERING_TYPES = [
  { key: 'building-construction', name: '房建施工' },
  { key: 'municipal-road', name: '市政道路' },
  { key: 'decoration', name: '装饰装修' },
  { key: 'mep-installation', name: '机电安装' },
  { key: 'steel-structure', name: '钢结构' },
  { key: 'general-engineering', name: '通用工程' },
]

export const CONTRACT_TYPES = [
  { key: 'labor-subcontract', name: '劳务分包' },
  { key: 'professional-subcontract', name: '专业工程分包' },
  { key: 'other', name: '其他类' },
]

// 无法识别时的回退推荐值：通用工程 + 其他类。
export const DEFAULT_ENGINEERING_KEY = 'general-engineering'
export const DEFAULT_CONTRACT_KEY = 'other'

// 需要向用户展示提醒（但仍允许继续）的置信度等级。
// high 视为足够明确，不提醒。
export const LOW_CONFIDENCE_LEVELS = ['low', 'medium', 'unknown']

const CONFIDENCE_HINTS = {
  low: 'AI 对该类别判断把握较低，请重点确认后再开始审查。',
  medium: 'AI 对该类别判断为中等置信度，建议核对后再继续。',
  unknown: '未能自动识别类别，已填入通用推荐值，请确认后再开始审查。',
}

/**
 * 合并服务端返回的类别与默认预设。
 *
 * - 同 key 时服务端定义覆盖默认（用户可自定义名称）。
 * - 服务端独有的 key 追加到末尾（用户私有类别）。
 * - 不修改原始默认数组（不可变）。
 */
export function mergeTypeOptions(defaults, serverTypes) {
  const list = defaults.map((t) => ({ ...t }))
  if (!Array.isArray(serverTypes) || serverTypes.length === 0) return list
  const byKey = new Map(list.map((t) => [t.key, t]))
  for (const opt of serverTypes) {
    if (!opt || !opt.key) continue
    const hit = byKey.get(opt.key)
    if (hit) {
      Object.assign(hit, opt)
    } else {
      list.push({ ...opt })
      byKey.set(opt.key, opt)
    }
  }
  return list
}

/**
 * 从解析结果 / 历史记录中解析 AI 分类推荐，兼容旧 document_type。
 *
 * 返回：
 *   {
 *     engineeringTypeKey, contractTypeKey,
 *     confidence, source, needsConfirm, archived
 *   }
 *
 * - 新字段优先：detected_engineering_type / detected_contract_type /
 *   classification_confidence / classification_source。
 * - 缺失时回退到「通用工程 + 其他类」，confidence=unknown，needsConfirm=true。
 * - 旧 document_type=contract 视为 legacy（仍可初审，需确认）。
 * - 旧 document_type=bidding 标记 archived=true（照胆不再做招投标初审）。
 */
export function resolveRecommendation(source = {}) {
  const src = source || {}

  if (src.document_type === 'bidding') {
    return {
      engineeringTypeKey: DEFAULT_ENGINEERING_KEY,
      contractTypeKey: DEFAULT_CONTRACT_KEY,
      confidence: 'unknown',
      source: 'archived_legacy',
      needsConfirm: true,
      archived: true,
    }
  }

  const fromLegacy = src.document_type === 'contract'

  const engineeringTypeKey = src.detected_engineering_type || DEFAULT_ENGINEERING_KEY
  const contractTypeKey = src.detected_contract_type || DEFAULT_CONTRACT_KEY
  const confidence = src.classification_confidence || 'unknown'
  const sourceTag = src.classification_source || (fromLegacy ? 'legacy' : 'fallback')

  // 未知/低置信度，或缺失分类信息（仍走默认值）时需要用户确认。
  const needsConfirm = isLowConfidence(confidence) || !src.detected_engineering_type || !src.detected_contract_type

  return {
    engineeringTypeKey,
    contractTypeKey,
    confidence,
    source: sourceTag,
    needsConfirm,
    archived: false,
  }
}

/**
 * 判断置信度是否需要展示提醒。
 * high 视为足够明确；其余（含缺失/异常值）都需要提醒。
 */
export function isLowConfidence(confidence) {
  return confidence !== 'high'
}

/**
 * 构造置信度提醒文案。
 * high 返回空字符串（不提醒）；其余等级返回引导性文案，且不阻止用户继续。
 */
export function buildConfidenceHint(confidence) {
  if (confidence === 'high') return ''
  return CONFIDENCE_HINTS[confidence] || CONFIDENCE_HINTS.unknown
}

/**
 * 根据用户已启用文档与系统默认文档，决定 Step 2 审查依据。
 *
 * 规则（互斥，绝不混合）：
 *   1. 存在用户「已启用」文档 → 只展示用户文档（mode=user），默认全选。
 *   2. 没有用户启用文档 → 回退系统默认文档（mode=system），并给出回退提示。
 *   3. 两者都没有 → mode=empty。
 *
 * 返回：
 *   {
 *     mode: 'user' | 'system' | 'empty',
 *     docs: Array,            // 本次展示的文档列表
 *     defaultSelectedIds,     // 多选初始化默认选中 id（仅 user 模式非空）
 *     fallback: boolean,      // 是否回退到系统默认
 *     note: string,           // 回退提示（仅 system 模式非空）
 *   }
 */
export function selectKnowledgeBasis(userDocs = [], systemDocs = []) {
  const enabledUserDocs = (userDocs || []).filter((d) => d && d.enabled)

  if (enabledUserDocs.length > 0) {
    return {
      mode: 'user',
      docs: enabledUserDocs,
      defaultSelectedIds: enabledUserDocs.map((d) => d.id),
      fallback: false,
      note: '',
    }
  }

  const enabledSystemDocs = (systemDocs || []).filter((d) => d && d.enabled)

  if (enabledSystemDocs.length > 0) {
    return {
      mode: 'system',
      docs: enabledSystemDocs,
      defaultSelectedIds: [],
      fallback: true,
      note: '未启用用户知识库，本次审查将使用系统默认合同规则包。',
    }
  }

  return {
    mode: 'empty',
    docs: [],
    defaultSelectedIds: [],
    fallback: false,
    note: '',
  }
}

/**
 * 构造 Step 2 提交 payload（设计文档定义的三字段 JSON）。
 * 不再包含 application_scenario 等 bidding 遗留字段。
 */
export function buildInspectionPayload({
  engineeringTypeKey,
  contractTypeKey,
  knowledgeDocumentIds,
} = {}) {
  return {
    engineering_type_key: engineeringTypeKey,
    contract_type_key: contractTypeKey,
    knowledge_document_ids: Array.isArray(knowledgeDocumentIds) ? knowledgeDocumentIds : [],
  }
}
