import { test } from 'node:test'
import assert from 'node:assert/strict'

// 任务 15：知识库管理页与设置页归档区域核心契约测试。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 15
const {
  FIXED_UPLOAD_CATEGORY,
  FIXED_UPLOAD_SCENARIO,
  buildUploadFields,
  isDocumentVisible,
  canDeleteArchived,
  applyArchiveDeletion,
} = await import('../knowledgeArchive.js')

// ---------------------------------------------------------------------------
// 上传契约：固定合同场景，工程/合同类别取代旧大类，永不提交 bidding
// ---------------------------------------------------------------------------
test('FIXED_UPLOAD_SCENARIO: 固定为 contract（照胆只做合同初审）', () => {
  assert.equal(FIXED_UPLOAD_SCENARIO, 'contract')
})

test('FIXED_UPLOAD_CATEGORY: 固定 general，不再使用新基建/传统基建/城市更新旧分类', () => {
  assert.equal(FIXED_UPLOAD_CATEGORY, 'general')
  assert.notEqual(FIXED_UPLOAD_CATEGORY, 'new_infrastructure')
  assert.notEqual(FIXED_UPLOAD_CATEGORY, 'traditional')
  assert.notEqual(FIXED_UPLOAD_CATEGORY, 'urban_renewal')
})

test('buildUploadFields: 默认返回合同场景 + 通用工程/其他类', () => {
  const fields = buildUploadFields()
  assert.equal(fields.application_scenario, 'contract')
  assert.equal(fields.category, 'general')
  assert.equal(fields.engineering_type_key, 'general-engineering')
  assert.equal(fields.contract_type_key, 'other')
})

test('buildUploadFields: 用户选择的工程/合同类别被正确传递', () => {
  const fields = buildUploadFields({
    engineering_type_key: 'municipal-road',
    contract_type_key: 'professional-subcontract',
  })
  assert.equal(fields.engineering_type_key, 'municipal-road')
  assert.equal(fields.contract_type_key, 'professional-subcontract')
})

test('buildUploadFields: 永不返回 bidding 场景', () => {
  // 即便传入 bidding 也被强制覆盖为 contract
  const fields = buildUploadFields({ application_scenario: 'bidding' })
  assert.equal(fields.application_scenario, 'contract')
})

test('buildUploadFields: 返回字段不含旧分类键（new_infrastructure/traditional/urban_renewal）', () => {
  const fields = buildUploadFields({
    engineering_type_key: 'building-construction',
    contract_type_key: 'labor-subcontract',
  })
  assert.equal('new_infrastructure' in fields, false)
  assert.equal('traditional' in fields, false)
  assert.equal('urban_renewal' in fields, false)
})

test('buildUploadFields: 子类字段透传（保留组织能力，但 category 固定）', () => {
  const fields = buildUploadFields({
    engineering_type_key: 'decoration',
    contract_type_key: 'other',
    subcategory_id: 42,
    subcategory_name: '装饰合同集',
  })
  assert.equal(fields.subcategory_id, 42)
  assert.equal(fields.subcategory_name, '装饰合同集')
  assert.equal(fields.category, 'general')
})

test('buildUploadFields: 不传子类时不包含子类字段（保持 payload 精简）', () => {
  const fields = buildUploadFields()
  assert.equal('subcategory_id' in fields, false)
  assert.equal('subcategory_name' in fields, false)
})

// ---------------------------------------------------------------------------
// 可见性过滤：停用的招投标文档归档隐藏，不展示在概览/管理页
// ---------------------------------------------------------------------------
test('isDocumentVisible: 停用的招投标文档不可见（已归档隐藏）', () => {
  assert.equal(
    isDocumentVisible({ application_scenario: 'bidding', is_active: false }),
    false,
  )
})

test('isDocumentVisible: 启用的合同文档可见', () => {
  assert.equal(
    isDocumentVisible({ application_scenario: 'contract', is_active: true }),
    true,
  )
})

test('isDocumentVisible: 启用的招投标文档仍可见（边缘，设计仅要求停用者隐藏）', () => {
  assert.equal(
    isDocumentVisible({ application_scenario: 'bidding', is_active: true }),
    true,
  )
})

test('isDocumentVisible: 缺失字段时默认可见（防御性，不误伤正常文档）', () => {
  assert.equal(isDocumentVisible({}), true)
  assert.equal(isDocumentVisible(null), true)
  assert.equal(isDocumentVisible(undefined), true)
})

test('isDocumentVisible: is_active 未提供时视为启用（兼容旧接口字段缺失）', () => {
  assert.equal(
    isDocumentVisible({ application_scenario: 'bidding' }),
    true,
    '只有显式 is_active=false 的招投标文档才隐藏',
  )
})

// ---------------------------------------------------------------------------
// 归档资料删除权限：用户仅能删除本人归档资料，系统归档资料不可删除
// ---------------------------------------------------------------------------
test('canDeleteArchived: 用户归档资料可删除', () => {
  assert.equal(
    canDeleteArchived({ id: 10, owner_type: 'user', application_scenario: 'bidding' }),
    true,
  )
})

test('canDeleteArchived: 系统归档资料不可删除（仅管理员/迁移脚本可清理）', () => {
  assert.equal(
    canDeleteArchived({ id: 1, owner_type: 'system', application_scenario: 'bidding' }),
    false,
  )
})

test('canDeleteArchived: 缺少 id 视为不可删除', () => {
  assert.equal(canDeleteArchived({ owner_type: 'user' }), false)
  assert.equal(canDeleteArchived({}), false)
  assert.equal(canDeleteArchived(null), false)
  assert.equal(canDeleteArchived(undefined), false)
})

// ---------------------------------------------------------------------------
// 删除成功后列表刷新：不可变更新
// ---------------------------------------------------------------------------
test('applyArchiveDeletion: 返回不包含已删除 id 的新列表', () => {
  const list = [
    { id: 10, title: '归档资料 A' },
    { id: 11, title: '归档资料 B' },
    { id: 12, title: '归档资料 C' },
  ]
  const next = applyArchiveDeletion(list, 11)
  assert.deepEqual(
    next.map((d) => d.id),
    [10, 12],
  )
})

test('applyArchiveDeletion: 不修改原列表（不可变）', () => {
  const list = [
    { id: 10, title: 'A' },
    { id: 11, title: 'B' },
  ]
  const snapshot = list.map((d) => ({ ...d }))
  applyArchiveDeletion(list, 10)
  assert.deepEqual(list, snapshot, '原列表不应被修改')
})

test('applyArchiveDeletion: 删除不存在的 id 时返回等价列表', () => {
  const list = [{ id: 10, title: 'A' }]
  const next = applyArchiveDeletion(list, 999)
  assert.equal(next.length, 1)
  assert.equal(next[0].id, 10)
})

test('applyArchiveDeletion: 无效 id 时返回等价列表（防御性）', () => {
  const list = [{ id: 10, title: 'A' }]
  assert.deepEqual(applyArchiveDeletion(list, null), list)
  assert.deepEqual(applyArchiveDeletion(list, undefined), list)
})

test('applyArchiveDeletion: 空列表返回空列表', () => {
  assert.deepEqual(applyArchiveDeletion([], 10), [])
})
