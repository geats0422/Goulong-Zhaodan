// 任务 15 回归校验：知识库管理页上传表单收敛为合同场景，设置页增加
// 已归档招投标资料只读区域，用户可永久删除本人归档资料。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 15
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(file) {
  return readFileSync(resolve(root, file), 'utf8')
}

const knowledgePage = read('src/pages/KnowledgeBasePage.vue')
const settingsPage = read('src/pages/SettingsPage.vue')
const settingsApi = read('src/services/settingsApi.js')
const archive = read('src/composables/knowledgeArchive.js')

// ---------------------------------------------------------------------------
// 1. KnowledgeBasePage: 上传表单不再保留招投标场景选择或旧大类分类
// ---------------------------------------------------------------------------
const uploadBiddingArtifacts = [
  'SCENARIO_OPTIONS',
  'CATEGORY_OPTIONS',
  "value: 'bidding'",
  "value: \"bidding\"",
  'application_scenario: "bidding"',
  "application_scenario: 'bidding'",
  "label: '应用场景'",
  "label: '大类'",
  'new_infrastructure',
  'urban_renewal',
]
for (const token of uploadBiddingArtifacts) {
  if (knowledgePage.includes(token)) {
    throw new Error(`KnowledgeBasePage 不得再保留招投标场景选择或旧大类分类残留：${token}`)
  }
}

// 2. KnowledgeBasePage: 必须呈现工程类别与合同类别选择（取代旧大类）
if (!knowledgePage.includes('ENGINEERING_OPTIONS') || !knowledgePage.includes('CONTRACT_OPTIONS')) {
  throw new Error('KnowledgeBasePage 必须提供工程类别与合同类别选项')
}
if (!knowledgePage.includes("label=\"工程类别\"") || !knowledgePage.includes("label=\"合同类别\"")) {
  throw new Error('KnowledgeBasePage 上传表单必须包含工程类别与合同类别选择器')
}

// 3. KnowledgeBasePage: 上传 payload 走 buildUploadFields（固定合同场景）
if (!knowledgePage.includes('buildUploadFields')) {
  throw new Error('KnowledgeBasePage 必须通过 buildUploadFields 构造上传字段（固定合同场景）')
}

// 4. KnowledgeBasePage: 防御性过滤停用的招投标文档
if (!knowledgePage.includes('isDocumentVisible')) {
  throw new Error('KnowledgeBasePage 必须使用 isDocumentVisible 防御性过滤停用招投标文档')
}

// 5. KnowledgeBasePage: 不再展示「任务场景」行（所有可见文档均为合同场景）
if (knowledgePage.includes('任务场景') || knowledgePage.includes('mapApplicationScenario')) {
  throw new Error('KnowledgeBasePage 不应再展示任务场景行（招投标已归档隐藏）')
}

// ---------------------------------------------------------------------------
// 6. SettingsPage: 已归档招投标资料只读区域
// ---------------------------------------------------------------------------
if (!settingsPage.includes('已归档招投标资料')) {
  throw new Error('SettingsPage 知识库设置必须包含「已归档招投标资料」只读区域')
}
if (!settingsPage.includes('archived-knowledge-card') || !settingsPage.includes('archive-list')) {
  throw new Error('SettingsPage 必须包含归档资料列表结构')
}

// 7. SettingsPage: 归档资料不可重新启用（不渲染 BaseToggle）
//    归档卡片内不得出现启用开关
const archiveCardStart = settingsPage.indexOf('archived-knowledge-card')
const archiveCardEnd = settingsPage.indexOf('</article>', archiveCardStart)
if (archiveCardStart === -1 || archiveCardEnd === -1) {
  throw new Error('SettingsPage 无法定位归档资料卡片')
}
const archiveCardHtml = settingsPage.slice(archiveCardStart, archiveCardEnd)
if (archiveCardHtml.includes('BaseToggle') || archiveCardHtml.includes('toggleDocument')) {
  throw new Error('归档资料卡片不得提供重新启用入口（只读 + 删除）')
}
if (!archiveCardHtml.includes('永久删除')) {
  throw new Error('归档资料卡片必须提供永久删除入口')
}

// 8. SettingsPage: 删除确认对话框
if (!settingsPage.includes('confirmDeleteArchivedId') || !settingsPage.includes('doDeleteArchived')) {
  throw new Error('SettingsPage 必须实现归档资料删除确认与执行流程')
}
if (!settingsPage.includes('永久删除归档资料') || !settingsPage.includes('无法恢复')) {
  throw new Error('SettingsPage 必须在删除确认对话框中提示不可恢复后果')
}

// 9. SettingsPage: 删除成功刷新（不可变更新），失败恢复（列表保持不变）
if (!settingsPage.includes('applyArchiveDeletion')) {
  throw new Error('SettingsPage 删除成功后必须通过 applyArchiveDeletion 不可变刷新列表')
}
if (!settingsPage.includes('cancelDeleteArchived')) {
  throw new Error('SettingsPage 必须支持取消删除（失败/取消时列表保持不变）')
}

// 10. SettingsPage: 用户仅能删除本人归档资料（canDeleteArchived 防御性校验）
if (!settingsPage.includes('canDeleteArchived')) {
  throw new Error('SettingsPage 必须通过 canDeleteArchived 判断归档资料删除权限')
}

// ---------------------------------------------------------------------------
// 11. settingsApi: 归档资料 API 契约
// ---------------------------------------------------------------------------
if (!settingsApi.includes('listArchivedKnowledge') || !settingsApi.includes('/inspection/archived-knowledge')) {
  throw new Error('settingsApi 必须提供 listArchivedKnowledge (GET /inspection/archived-knowledge)')
}
if (!settingsApi.includes('deleteArchivedKnowledge')) {
  throw new Error('settingsApi 必须提供 deleteArchivedKnowledge (DELETE /inspection/archived-knowledge/{id})')
}

// ---------------------------------------------------------------------------
// 12. knowledgeArchive composable: 核心契约函数齐备
// ---------------------------------------------------------------------------
for (const fn of ['buildUploadFields', 'isDocumentVisible', 'canDeleteArchived', 'applyArchiveDeletion']) {
  if (!archive.includes(`export function ${fn}`)) {
    throw new Error(`knowledgeArchive 必须导出纯函数：${fn}`)
  }
}
if (!archive.includes("FIXED_UPLOAD_SCENARIO = 'contract'")) {
  throw new Error('knowledgeArchive 必须固定上传场景为 contract')
}

console.log('知识库管理页与设置页归档区域契约校验通过（合同场景收敛 + 归档只读 + 删除流程）')
