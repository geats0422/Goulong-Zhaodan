// 知识库归档与上传契约（任务 15）。
//
// 本模块刻意保持为纯函数集合，便于在 node:test 下独立测试。
// 页面层（KnowledgeBasePage.vue / SettingsPage.vue）只负责 IO 与渲染，
// 所有「上传场景收敛 / 归档资料可见性 / 删除权限 / 列表刷新」的判断都收口在这里。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 15

import {
  DEFAULT_ENGINEERING_KEY,
  DEFAULT_CONTRACT_KEY,
} from './inspectionPrepare.js'

// ---------------------------------------------------------------------------
// 上传场景收敛：照胆只做合同初审。
// 新上传固定 contract 场景；旧「新基建/传统基建/城市更新」大类不再向用户暴露，
// category 固定为 general（保持后端存储路径兼容），工程/合同类别走独立字段。
// ---------------------------------------------------------------------------
export const FIXED_UPLOAD_CATEGORY = 'general'
export const FIXED_UPLOAD_SCENARIO = 'contract'

/**
 * 构造知识库上传表单字段（不含 file，由页面层组装 FormData）。
 *
 * - 固定合同场景，永远不返回 bidding（即便调用方误传也强制覆盖）。
 * - 固定 category=general，不再使用新基建/传统基建/城市更新旧分类。
 * - 工程/合同类别缺失时回退到通用工程 + 其他类。
 * - 子类字段仅在调用方提供时透传（保留知识库组织能力）。
 */
export function buildUploadFields(form = {}) {
  const source = form || {}
  const fields = {
    category: FIXED_UPLOAD_CATEGORY,
    application_scenario: FIXED_UPLOAD_SCENARIO,
    engineering_type_key: source.engineering_type_key || DEFAULT_ENGINEERING_KEY,
    contract_type_key: source.contract_type_key || DEFAULT_CONTRACT_KEY,
  }
  if (source.subcategory_id !== undefined && source.subcategory_id !== null && source.subcategory_id !== '') {
    fields.subcategory_id = source.subcategory_id
  }
  if (source.subcategory_name) {
    fields.subcategory_name = source.subcategory_name
  }
  return fields
}

// ---------------------------------------------------------------------------
// 可见性过滤：停用的招投标文档归档隐藏，不展示在概览/管理页。
// 设计要求：默认知识库概览、知识库管理页、Step 2 审查依据面板均不展示
// 停用的招投标文档。后端已过滤，前端做防御性二次过滤。
// ---------------------------------------------------------------------------

/**
 * 判断概览文档是否应对当前用户可见。
 *
 * 规则：仅「application_scenario=bidding 且 is_active=false」的文档归档隐藏。
 * 其余文档（含启用的招投标文档、停用的合同文档）默认可见，避免误伤。
 */
export function isDocumentVisible(doc) {
  if (!doc) return true
  if (doc.application_scenario === 'bidding' && doc.is_active === false) {
    return false
  }
  return true
}

// ---------------------------------------------------------------------------
// 归档资料删除权限：用户仅能删除本人归档资料。
// 系统归档资料仅管理员或迁移脚本可清理（不在归档列表接口返回，前端做防御）。
// ---------------------------------------------------------------------------

/**
 * 判断归档资料是否可由当前用户删除。
 *
 * 后端归档列表仅返回当前用户的资料；系统归档资料由管理员能力单独处理。
 * 这里做防御性校验：系统归档资料不可删除，缺少 id 视为不可删除。
 */
export function canDeleteArchived(doc) {
  if (!doc || doc.id === undefined || doc.id === null) return false
  return doc.owner_type !== 'system'
}

// ---------------------------------------------------------------------------
// 列表刷新：删除成功后不可变地更新归档列表。
// ---------------------------------------------------------------------------

/**
 * 返回不包含已删除 id 的新列表（不可变）。
 * 无效 id 时返回等价的新列表（保持引用语义一致：始终返回新数组）。
 */
export function applyArchiveDeletion(list = [], deletedId = null) {
  if (deletedId === null || deletedId === undefined) return [...list]
  return list.filter((d) => d && d.id !== deletedId)
}
