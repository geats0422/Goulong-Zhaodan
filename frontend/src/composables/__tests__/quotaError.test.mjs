// 任务 16：统一额度弹窗与账单 Tab 跳转核心契约测试。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 16
//
// 后端统一额度不足契约（来自 backend/app/core/quota.py INSUFFICIENT_QUOTA_DETAIL）：
// {
//   "code": "insufficient_quota",
//   "message": "当前账户额度不足，本次审查需要更多算力额度。",
//   "action": {
//     "type": "billing",
//     "path": "/settings?tab=billing",
//     "label": "前往账单与订阅"
//   }
// }
import { test } from 'node:test'
import assert from 'node:assert/strict'

const {
  isInsufficientQuotaError,
  getQuotaAction,
  extractApiError,
  QUOTA_INSUFFICIENT_CODE,
  DEFAULT_QUOTA_ACTION_PATH,
} = await import('../quotaError.js')

// 后端契约快照：用于构造真实 402 错误对象
function makeQuotaError(overrides = {}) {
  const err = new Error('当前账户额度不足，本次审查需要更多算力额度。')
  err.code = 'insufficient_quota'
  err.action = {
    type: 'billing',
    path: '/settings?tab=billing',
    label: '前往账单与订阅',
  }
  Object.assign(err, overrides)
  return err
}

// ---------------------------------------------------------------------------
// 稳定错误码常量
// ---------------------------------------------------------------------------
test('QUOTA_INSUFFICIENT_CODE: 稳定错误码 insufficient_quota', () => {
  assert.equal(QUOTA_INSUFFICIENT_CODE, 'insufficient_quota')
})

test('DEFAULT_QUOTA_ACTION_PATH: 默认跳转目标为 /settings?tab=billing，不再指向 /pricing', () => {
  assert.equal(DEFAULT_QUOTA_ACTION_PATH, '/settings?tab=billing')
  assert.notEqual(DEFAULT_QUOTA_ACTION_PATH, '/pricing')
})

// ---------------------------------------------------------------------------
// isInsufficientQuotaError: 用 code 判定，不再用文本匹配
// ---------------------------------------------------------------------------
test('isInsufficientQuotaError: code===insufficient_quota 时返回 true', () => {
  assert.equal(isInsufficientQuotaError(makeQuotaError()), true)
})

test('isInsufficientQuotaError: code 不匹配时返回 false（不靠文本猜测）', () => {
  const err = new Error('当前账户额度不足，本次审查需要更多算力额度。')
  err.code = 'other_error'
  assert.equal(isInsufficientQuotaError(err), false)
})

test('isInsufficientQuotaError: 普通错误（无 code 属性）返回 false', () => {
  assert.equal(isInsufficientQuotaError(new Error('解析失败')), false)
})

test('isInsufficientQuotaError: null/undefined 安全返回 false', () => {
  assert.equal(isInsufficientQuotaError(null), false)
  assert.equal(isInsufficientQuotaError(undefined), false)
})

// ---------------------------------------------------------------------------
// getQuotaAction: 提取 action.path 与 action.label，提供安全 fallback
// ---------------------------------------------------------------------------
test('getQuotaAction: 返回后端 action 结构（path + label）', () => {
  const action = getQuotaAction(makeQuotaError())
  assert.equal(action.path, '/settings?tab=billing')
  assert.equal(action.label, '前往账单与订阅')
})

test('getQuotaAction: action.path 缺失时 fallback 到 /settings?tab=billing', () => {
  const err = makeQuotaError()
  err.action = { type: 'billing', label: '前往账单与订阅' }
  const action = getQuotaAction(err)
  assert.equal(action.path, '/settings?tab=billing')
})

test('getQuotaAction: action 整体缺失时返回默认结构', () => {
  const err = makeQuotaError()
  delete err.action
  const action = getQuotaAction(err)
  assert.equal(action.path, '/settings?tab=billing')
  assert.ok(action.label.length > 0, '必须提供可读 label')
})

test('getQuotaAction: 非 insufficient_quota 错误仍返回默认结构（防御性）', () => {
  const action = getQuotaAction(new Error('普通错误'))
  assert.equal(action.path, '/settings?tab=billing')
})

test('getQuotaAction: action.path 永不为 /pricing（即使后端误传）', () => {
  const err = makeQuotaError()
  err.action = { type: 'billing', path: '/pricing', label: '查看定价' }
  const action = getQuotaAction(err)
  assert.notEqual(action.path, '/pricing')
  assert.equal(action.path, '/settings?tab=billing')
})

// ---------------------------------------------------------------------------
// extractApiError: 从 fetch 抛出的 Error 中提取完整结构（透传不压扁）
// ---------------------------------------------------------------------------
test('extractApiError: 普通字符串 message 仍能正常工作（向后兼容）', () => {
  const result = extractApiError(new Error('解析失败'))
  assert.equal(result.message, '解析失败')
  assert.equal(result.code, null)
  assert.equal(result.action, null)
})

test('extractApiError: 透传挂载在 Error 上的 code/action（关键修复）', () => {
  const err = makeQuotaError()
  const result = extractApiError(err)
  assert.equal(result.message, '当前账户额度不足，本次审查需要更多算力额度。')
  assert.equal(result.code, 'insufficient_quota')
  assert.deepEqual(result.action, {
    type: 'billing',
    path: '/settings?tab=billing',
    label: '前往账单与订阅',
  })
})

test('extractApiError: null/undefined 安全返回空结构', () => {
  assert.deepEqual(extractApiError(null), { message: '', code: null, action: null })
  assert.deepEqual(extractApiError(undefined), { message: '', code: null, action: null })
})

test('extractApiError: 非 Error 对象（如字符串）包装为 message', () => {
  const result = extractApiError('网络错误')
  assert.equal(result.message, '网络错误')
  assert.equal(result.code, null)
})
