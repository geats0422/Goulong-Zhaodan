import { test } from 'node:test'
import assert from 'node:assert/strict'

const {
  ENGINEERING_TYPES,
  CONTRACT_TYPES,
  DEFAULT_ENGINEERING_KEY,
  DEFAULT_CONTRACT_KEY,
  LOW_CONFIDENCE_LEVELS,
  mergeTypeOptions,
  resolveRecommendation,
  isLowConfidence,
  buildConfidenceHint,
  selectKnowledgeBasis,
  buildInspectionPayload,
} = await import('../inspectionPrepare.js')

// ---------------------------------------------------------------------------
// 预设类别契约：覆盖设计文档定义的全部预设，且工程/合同两个维度独立
// ---------------------------------------------------------------------------
test('ENGINEERING_TYPES: 覆盖六个工程类别预设', () => {
  const keys = ENGINEERING_TYPES.map((t) => t.key)
  assert.deepEqual(keys, [
    'building-construction',
    'municipal-road',
    'decoration',
    'mep-installation',
    'steel-structure',
    'general-engineering',
  ])
  assert.ok(ENGINEERING_TYPES.every((t) => t.name && typeof t.name === 'string'))
})

test('CONTRACT_TYPES: 覆盖三个合同类别预设', () => {
  const keys = CONTRACT_TYPES.map((t) => t.key)
  assert.deepEqual(keys, ['labor-subcontract', 'professional-subcontract', 'other'])
  assert.ok(CONTRACT_TYPES.every((t) => t.name && typeof t.name === 'string'))
})

test('工程类别与合同类别的 key 互不重叠（独立维度）', () => {
  const engineeringKeys = new Set(ENGINEERING_TYPES.map((t) => t.key))
  const contractKeys = new Set(CONTRACT_TYPES.map((t) => t.key))
  for (const k of contractKeys) {
    assert.equal(engineeringKeys.has(k), false, `合同类别 key "${k}" 不应出现在工程类别中`)
  }
})

test('默认回退类别：通用工程 + 其他类', () => {
  assert.equal(DEFAULT_ENGINEERING_KEY, 'general-engineering')
  assert.equal(DEFAULT_CONTRACT_KEY, 'other')
  assert.ok(ENGINEERING_TYPES.some((t) => t.key === DEFAULT_ENGINEERING_KEY))
  assert.ok(CONTRACT_TYPES.some((t) => t.key === DEFAULT_CONTRACT_KEY))
})

// ---------------------------------------------------------------------------
// mergeTypeOptions: 合并服务端类别与默认预设，按 key 去重，服务端覆盖同名
// ---------------------------------------------------------------------------
test('mergeTypeOptions: 服务端为空时返回默认预设的副本', () => {
  const merged = mergeTypeOptions(ENGINEERING_TYPES, null)
  assert.equal(merged.length, ENGINEERING_TYPES.length)
  assert.deepEqual(merged.map((t) => t.key), ENGINEERING_TYPES.map((t) => t.key))
})

test('mergeTypeOptions: 服务端新增用户私有类别追加到末尾', () => {
  const userPrivate = [{ key: 'custom-mine', name: '我的专项', owner_type: 'user' }]
  const merged = mergeTypeOptions(ENGINEERING_TYPES, userPrivate)
  const keys = merged.map((t) => t.key)
  assert.ok(keys.includes('custom-mine'))
  assert.ok(keys.length === ENGINEERING_TYPES.length + 1)
})

test('mergeTypeOptions: 同 key 时服务端定义覆盖默认（例如用户改名）', () => {
  const overridden = [{ key: 'municipal-road', name: '市政道路（自定义）' }]
  const merged = mergeTypeOptions(ENGINEERING_TYPES, overridden)
  const hit = merged.find((t) => t.key === 'municipal-road')
  assert.equal(hit.name, '市政道路（自定义）')
})

test('mergeTypeOptions: 不修改原始默认数组（不可变）', () => {
  const snapshot = ENGINEERING_TYPES.map((t) => ({ ...t }))
  mergeTypeOptions(ENGINEERING_TYPES, [{ key: 'brand-new', name: '新类别' }])
  assert.deepEqual(ENGINEERING_TYPES, snapshot)
})

// ---------------------------------------------------------------------------
// resolveRecommendation: 解析 AI 分类推荐，两个维度独立，兼容旧记录
// ---------------------------------------------------------------------------
test('resolveRecommendation: 完整 AI 推荐时返回两个维度独立推荐值', () => {
  const rec = resolveRecommendation({
    detected_engineering_type: 'municipal-road',
    detected_contract_type: 'professional-subcontract',
    classification_confidence: 'high',
    classification_source: 'ai',
  })
  assert.equal(rec.engineeringTypeKey, 'municipal-road')
  assert.equal(rec.contractTypeKey, 'professional-subcontract')
  assert.equal(rec.confidence, 'high')
  assert.equal(rec.source, 'ai')
  assert.equal(rec.needsConfirm, false, '高置信度无需特别确认')
})

test('resolveRecommendation: 两个类别可被独立识别（不会互相污染）', () => {
  // 工程类别识别明确、合同类别低置信度的常见场景
  const rec = resolveRecommendation({
    detected_engineering_type: 'building-construction',
    detected_contract_type: 'other',
    classification_confidence: 'medium',
  })
  assert.equal(rec.engineeringTypeKey, 'building-construction')
  assert.equal(rec.contractTypeKey, 'other')
  assert.notEqual(rec.engineeringTypeKey, rec.contractTypeKey)
})

test('resolveRecommendation: 无任何分类信息时回退到通用工程/其他类', () => {
  const rec = resolveRecommendation({})
  assert.equal(rec.engineeringTypeKey, DEFAULT_ENGINEERING_KEY)
  assert.equal(rec.contractTypeKey, DEFAULT_CONTRACT_KEY)
  assert.equal(rec.confidence, 'unknown')
  assert.equal(rec.needsConfirm, true, '未知分类需用户确认')
})

test('resolveRecommendation: 兼容旧记录 document_type=contract', () => {
  const rec = resolveRecommendation({ document_type: 'contract' })
  assert.equal(rec.engineeringTypeKey, DEFAULT_ENGINEERING_KEY)
  assert.equal(rec.contractTypeKey, DEFAULT_CONTRACT_KEY)
  assert.equal(rec.source, 'legacy')
  assert.equal(rec.needsConfirm, true)
})

test('resolveRecommendation: 旧招投标记录标记为已归档不参与初审', () => {
  const rec = resolveRecommendation({ document_type: 'bidding' })
  assert.equal(rec.archived, true, '招投标记录应标记为归档')
  assert.equal(rec.needsConfirm, true)
})

// ---------------------------------------------------------------------------
// isLowConfidence / buildConfidenceHint: 低置信度提醒但允许继续
// ---------------------------------------------------------------------------
test('LOW_CONFIDENCE_LEVELS: 包含 low/medium/unknown，不含 high', () => {
  assert.deepEqual(LOW_CONFIDENCE_LEVELS, ['low', 'medium', 'unknown'])
})

test('isLowConfidence: high 返回 false', () => {
  assert.equal(isLowConfidence('high'), false)
})

test('isLowConfidence: low/medium/unknown 返回 true', () => {
  assert.equal(isLowConfidence('low'), true)
  assert.equal(isLowConfidence('medium'), true)
  assert.equal(isLowConfidence('unknown'), true)
})

test('isLowConfidence: 缺失/异常值视为需要提醒', () => {
  assert.equal(isLowConfidence(null), true)
  assert.equal(isLowConfidence(undefined), true)
  assert.equal(isLowConfidence('weird'), true)
})

test('buildConfidenceHint: high 不产生提醒文案', () => {
  assert.equal(buildConfidenceHint('high'), '')
})

test('buildConfidenceHint: low/medium/unknown 产生提醒文案，且提醒不阻止继续', () => {
  for (const level of ['low', 'medium', 'unknown']) {
    const hint = buildConfidenceHint(level)
    assert.ok(typeof hint === 'string' && hint.length > 0, `${level} 应有提醒文案`)
    // 提醒是引导性文案，不应包含"禁止/不能/阻止"等阻断措辞
    assert.equal(/禁止|不能继续|阻止/.test(hint), false, `${level} 提醒不应阻断用户继续`)
  }
})

// ---------------------------------------------------------------------------
// selectKnowledgeBasis: 用户文档与系统默认文档互斥展示（不混合）
// ---------------------------------------------------------------------------
test('selectKnowledgeBasis: 有用户已启用文档时只返回用户文档（mode=user）', () => {
  const userDocs = [
    { id: 12, owner_type: 'user', enabled: true, name: '我的分包合同规则' },
    { id: 18, owner_type: 'user', enabled: true, name: '公司历史判例' },
  ]
  const systemDocs = [
    { id: 1, owner_type: 'system', enabled: true, name: '民法典合同编' },
  ]
  const basis = selectKnowledgeBasis(userDocs, systemDocs)
  assert.equal(basis.mode, 'user')
  assert.equal(basis.docs.length, 2)
  assert.ok(basis.docs.every((d) => d.owner_type === 'user'))
  assert.equal(basis.fallback, false)
  assert.equal(basis.note, '', '用户文档模式下不应出现回退提示')
})

test('selectKnowledgeBasis: 无用户启用文档时回退系统默认（mode=system）并提示', () => {
  const basis = selectKnowledgeBasis([], [
    { id: 1, owner_type: 'system', enabled: true, name: '民法典合同编' },
    { id: 2, owner_type: 'system', enabled: true, name: '建筑法' },
  ])
  assert.equal(basis.mode, 'system')
  assert.equal(basis.fallback, true)
  assert.equal(basis.docs.length, 2)
  assert.ok(basis.note.length > 0, '回退时应展示系统默认知识库回退提示')
})

test('selectKnowledgeBasis: 用户已上传但停用的文档不参与（视为无用户文档）', () => {
  const basis = selectKnowledgeBasis(
    [{ id: 99, owner_type: 'user', enabled: false, name: '已停用文档' }],
    [{ id: 1, owner_type: 'system', enabled: true, name: '民法典合同编' }],
  )
  assert.equal(basis.mode, 'system', '停用的用户文档不应触发用户优先')
  assert.equal(basis.fallback, true)
  assert.ok(basis.docs.every((d) => d.owner_type !== 'user'))
})

test('selectKnowledgeBasis: 用户与系统都没有文档时返回 empty 模式', () => {
  const basis = selectKnowledgeBasis([], [])
  assert.equal(basis.mode, 'empty')
  assert.equal(basis.docs.length, 0)
  assert.equal(basis.fallback, false)
})

test('selectKnowledgeBasis: 用户文档存在时不混入系统文档（严格互斥）', () => {
  const basis = selectKnowledgeBasis(
    [{ id: 12, owner_type: 'user', enabled: true, name: '我的规则' }],
    [{ id: 1, owner_type: 'system', enabled: true, name: '民法典' }],
  )
  assert.equal(basis.mode, 'user')
  const hasSystem = basis.docs.some((d) => d.owner_type === 'system')
  assert.equal(hasSystem, false, '用户文档存在时绝不能混入系统默认文档')
})

test('selectKnowledgeBasis: 默认全选用户启用文档的 id（供多选初始化）', () => {
  const userDocs = [
    { id: 12, owner_type: 'user', enabled: true },
    { id: 18, owner_type: 'user', enabled: true },
  ]
  const basis = selectKnowledgeBasis(userDocs, [])
  assert.deepEqual(basis.defaultSelectedIds, [12, 18])
})

// ---------------------------------------------------------------------------
// buildInspectionPayload: Step 2 提交 payload 契约（三字段 JSON）
// ---------------------------------------------------------------------------
test('buildInspectionPayload: 产出设计文档定义的三字段 JSON', () => {
  const payload = buildInspectionPayload({
    engineeringTypeKey: 'municipal-road',
    contractTypeKey: 'professional-subcontract',
    knowledgeDocumentIds: [12, 18],
  })
  assert.deepEqual(payload, {
    engineering_type_key: 'municipal-road',
    contract_type_key: 'professional-subcontract',
    knowledge_document_ids: [12, 18],
  })
})

test('buildInspectionPayload: 不包含 application_scenario 等 bidding 遗留字段', () => {
  const payload = buildInspectionPayload({
    engineeringTypeKey: 'general-engineering',
    contractTypeKey: 'other',
    knowledgeDocumentIds: [],
  })
  assert.equal('application_scenario' in payload, false)
  assert.equal('scenario' in payload, false)
  assert.equal('document_type' in payload, false)
})

test('buildInspectionPayload: 知识库文档 ID 为空数组时仍合法（回退系统默认由后端处理）', () => {
  const payload = buildInspectionPayload({
    engineeringTypeKey: 'building-construction',
    contractTypeKey: 'labor-subcontract',
    knowledgeDocumentIds: [],
  })
  assert.ok(Array.isArray(payload.knowledge_document_ids))
  assert.equal(payload.knowledge_document_ids.length, 0)
})

test('buildInspectionPayload: 工程与合同类别 key 可独立任意组合', () => {
  const combos = [
    ['building-construction', 'labor-subcontract'],
    ['municipal-road', 'professional-subcontract'],
    ['steel-structure', 'other'],
  ]
  for (const [eng, con] of combos) {
    const payload = buildInspectionPayload({
      engineeringTypeKey: eng,
      contractTypeKey: con,
      knowledgeDocumentIds: [1],
    })
    assert.equal(payload.engineering_type_key, eng)
    assert.equal(payload.contract_type_key, con)
  }
})
