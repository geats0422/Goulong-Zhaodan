// 任务19：合同初审跨 composable 集成流程测试。
//
// 与单 composable 单元测试不同，本文件串联 inspectionPrepare / quotaError /
// inspectionDisplay / knowledgeArchive，模拟真实用户完整旅程，验证多个 composable
// 协作时的契约一致性（任务19 要求的"集成测试"层面）。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务19
import { test } from 'node:test'
import assert from 'node:assert/strict'

const {
  resolveRecommendation,
  isLowConfidence,
  buildConfidenceHint,
  selectKnowledgeBasis,
  buildInspectionPayload,
} = await import('../inspectionPrepare.js')

const {
  isInsufficientQuotaError,
  getQuotaAction,
  extractApiError,
  QUOTA_INSUFFICIENT_CODE,
} = await import('../quotaError.js')

const {
  isArchivedLegacyRecord,
  classificationDisplayText,
  rulePackageKeysDisplay,
  knowledgeSourcesDisplay,
  riskLabel,
} = await import('../inspectionDisplay.js')

const {
  canDeleteArchived,
  applyArchiveDeletion,
} = await import('../knowledgeArchive.js')

// 构造后端 402 额度不足响应抛出的 Error（与后端 INSUFFICIENT_QUOTA_DETAIL 对齐）
function makeBackendQuotaError() {
  const err = new Error('当前账户额度不足，本次审查需要更多算力额度。')
  err.code = 'insufficient_quota'
  err.action = {
    type: 'billing',
    path: '/settings?tab=billing',
    label: '前往账单与订阅',
  }
  return err
}

// ---------------------------------------------------------------------------
// 主流程：解析响应(低置信度) → 推荐 → 回退系统 → 构建 payload → 额度错误 → 跳转 billing
// ---------------------------------------------------------------------------

test('主流程：低置信度新合同，无用户知识库回退系统默认，额度不足跳转账单', () => {
  // 1. 解析/分类阶段：后端返回低置信度推荐
  const parseResponse = {
    detected_engineering_type: 'municipal-road',
    detected_contract_type: 'professional-subcontract',
    classification_confidence: 'medium',
    classification_source: 'model',
  }
  const rec = resolveRecommendation(parseResponse)
  assert.equal(rec.engineeringTypeKey, 'municipal-road')
  assert.equal(rec.contractTypeKey, 'professional-subcontract')
  assert.equal(rec.confidence, 'medium')

  // 2. 低置信度提醒显示，但不阻止继续（isLowConfidence 接收 confidence 字符串）
  assert.equal(isLowConfidence(rec.confidence), true)
  const hint = buildConfidenceHint(rec.confidence)
  assert.ok(hint.length > 0, '中置信度应有提醒文案')
  assert.equal(/禁止|不能继续|阻止/.test(hint), false, '提醒不得阻断用户继续')

  // 3. 知识库选择：用户无启用文档 → 回退系统默认
  const basis = selectKnowledgeBasis(
    [],
    [{ id: 1, owner_type: 'system', enabled: true, name: '民法典合同编' }],
  )
  assert.equal(basis.mode, 'system')
  assert.equal(basis.fallback, true)
  assert.ok(basis.note.length > 0, '回退时应展示系统默认提示')

  // 4. 构建 Step 2 三字段 payload（即使低置信度仍可提交）
  const payload = buildInspectionPayload({
    engineeringTypeKey: rec.engineeringTypeKey,
    contractTypeKey: rec.contractTypeKey,
    knowledgeDocumentIds: [],
  })
  assert.deepEqual(payload, {
    engineering_type_key: 'municipal-road',
    contract_type_key: 'professional-subcontract',
    knowledge_document_ids: [],
  })
  assert.equal('application_scenario' in payload, false, 'payload 不含 bidding 遗留字段')

  // 5. 提交触发额度不足：错误识别 + 账单跳转
  const apiError = makeBackendQuotaError()
  assert.equal(isInsufficientQuotaError(apiError), true)
  const action = getQuotaAction(apiError)
  assert.equal(action.path, '/settings?tab=billing')
  assert.notEqual(action.path, '/pricing')
})

// ---------------------------------------------------------------------------
// 主流程：高置信度新合同，用户知识库优先（不混入系统文档）
// ---------------------------------------------------------------------------

test('主流程：高置信度且用户有启用文档时，仅使用用户文档（不混入系统）', () => {
  const rec = resolveRecommendation({
    detected_engineering_type: 'building-construction',
    detected_contract_type: 'labor-subcontract',
    classification_confidence: 'high',
  })
  assert.equal(rec.needsConfirm, false, '高置信度无需特别确认')
  assert.equal(isLowConfidence('high'), false)

  const userDocs = [
    { id: 12, owner_type: 'user', enabled: true, name: '公司分包合同规则' },
  ]
  const systemDocs = [
    { id: 1, owner_type: 'system', enabled: true, name: '民法典合同编' },
  ]
  const basis = selectKnowledgeBasis(userDocs, systemDocs)
  assert.equal(basis.mode, 'user')
  assert.equal(basis.fallback, false)
  // 用户文档存在时绝不能混入系统默认文档
  assert.equal(basis.docs.some((d) => d.owner_type === 'system'), false)
  assert.deepEqual(basis.defaultSelectedIds, [12])

  const payload = buildInspectionPayload({
    engineeringTypeKey: rec.engineeringTypeKey,
    contractTypeKey: rec.contractTypeKey,
    knowledgeDocumentIds: basis.defaultSelectedIds,
  })
  assert.equal(payload.engineering_type_key, 'building-construction')
  assert.equal(payload.contract_type_key, 'labor-subcontract')
  assert.deepEqual(payload.knowledge_document_ids, [12])
})

// ---------------------------------------------------------------------------
// 旧 bidding 记录历史兼容：归档标记 + 展示文案 + 规则包快照
// ---------------------------------------------------------------------------

test('旧记录兼容：bidding 记录标记归档，展示归档文案，规则包快照可读', () => {
  const legacyRecord = {
    document_type: 'bidding',
    classification_source: 'archived_legacy',
    rule_package_key: 'old-bidding-rules:v1',
    overall_risk: 'low',
    knowledge_sources_snapshot: [{ title: '招标投标法' }],
  }
  // 归档标记
  assert.equal(isArchivedLegacyRecord(legacyRecord), true)
  // 展示文案：含归档/历史提示
  const display = classificationDisplayText(legacyRecord)
  assert.ok(/招投标资料已归档|历史记录/.test(display), '归档记录应展示归档或历史文案')
  // 旧单值规则包兼容为单元素数组
  assert.deepEqual(rulePackageKeysDisplay(legacyRecord), ['old-bidding-rules:v1'])
  // 知识来源快照可读
  assert.deepEqual(knowledgeSourcesDisplay(legacyRecord.knowledge_sources_snapshot), ['招标投标法'])
  // 风险标签仍正常展示（不被归档影响）
  assert.equal(riskLabel(legacyRecord.overall_risk), '低风险')
})

test('旧记录兼容：无任何分类字段的 legacy 合同记录回退通用工程合同', () => {
  const legacyContract = { classification_source: 'legacy', overall_risk: 'medium' }
  assert.equal(isArchivedLegacyRecord(legacyContract), false, 'legacy 合同非归档')
  assert.equal(
    classificationDisplayText(legacyContract),
    '历史记录 / 通用工程合同',
  )
})

// ---------------------------------------------------------------------------
// 归档删除流程：权限判断 → 删除 → 列表刷新
// ---------------------------------------------------------------------------

test('归档删除流程：用户资料可删，系统资料不可删，删除后列表刷新', () => {
  const archiveList = [
    { id: 10, title: '我的招标资料', owner_type: 'user', application_scenario: 'bidding' },
    { id: 11, title: '系统招标资料', owner_type: 'system', application_scenario: 'bidding' },
  ]
  // 权限判断：用户资料可删，系统资料不可删
  assert.equal(canDeleteArchived(archiveList[0]), true)
  assert.equal(canDeleteArchived(archiveList[1]), false)

  // 删除用户资料后，列表不含该 id，且原列表不被修改
  const next = applyArchiveDeletion(archiveList, 10)
  assert.equal(next.some((d) => d.id === 10), false)
  assert.equal(next.some((d) => d.id === 11), true, '系统资料保留')
  assert.equal(archiveList.length, 2, '原列表不可变')
})

// ---------------------------------------------------------------------------
// 额度错误识别健壮性：非额度错误不误判为额度不足
// ---------------------------------------------------------------------------

test('额度错误识别：解析失败等普通错误不误判为额度不足', () => {
  const parseErr = new Error('文档解析失败')
  parseErr.code = 'parse_failed'
  assert.equal(isInsufficientQuotaError(parseErr), false)
  // 普通错误仍能提取 message，但 action 用默认值（不跳 pricing）
  const extracted = extractApiError(parseErr)
  assert.equal(extracted.message, '文档解析失败')
  assert.equal(extracted.code, 'parse_failed')
  assert.equal(extracted.action, null)

  // 即便如此，getQuotaAction 对非额度错误也只返回 billing 默认（防御性，不跳 pricing）
  const action = getQuotaAction(parseErr)
  assert.notEqual(action.path, '/pricing')
})
