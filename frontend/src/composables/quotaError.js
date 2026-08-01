// 任务 16：统一额度不足错误识别与跳转工具（纯函数）。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 16
//
// 后端契约（backend/app/core/quota.py INSUFFICIENT_QUOTA_DETAIL）：
//   {
//     "code": "insufficient_quota",
//     "message": "当前账户额度不足，本次审查需要更多算力额度。",
//     "action": {
//       "type": "billing",
//       "path": "/settings?tab=billing",
//       "label": "前往账单与订阅"
//     }
//   }
//
// 关键修复（任务 13 质量审查发现的问题）：
//   - 旧前端用 includes('额度') 文本匹配 + 硬编码 /pricing，文案漂移即失效；
//   - 新前端用稳定错误码判定，跳转目标由后端 action 驱动，永不指向 /pricing。

// 稳定错误码：所有解析/审查入口共享同一 402 契约。
export const QUOTA_INSUFFICIENT_CODE = 'insufficient_quota'

// 默认跳转目标：设置页账单与订阅管理 Tab。
// 即使后端误传 /pricing 或缺失 action.path，前端也强制回退到此路径。
export const DEFAULT_QUOTA_ACTION_PATH = '/settings?tab=billing'

const DEFAULT_QUOTA_ACTION_LABEL = '前往账单与订阅'

// 默认 action 结构：用于后端契约缺失或异常时的安全回退。
function buildDefaultAction() {
  return {
    type: 'billing',
    path: DEFAULT_QUOTA_ACTION_PATH,
    label: DEFAULT_QUOTA_ACTION_LABEL,
  }
}

// 判定错误是否为额度不足错误。
// 不靠文案匹配，只信任稳定错误码，避免文案漂移导致误判。
export function isInsufficientQuotaError(err) {
  if (!err) return false
  return err.code === QUOTA_INSUFFICIENT_CODE
}

// 从错误中提取 action 结构（path + label），用于驱动弹窗按钮。
// 安全策略：
//   - action.path 缺失或为 /pricing（防回滚）时，强制回退到 /settings?tab=billing；
//   - label 缺失时回退到默认「前往账单与订阅」。
export function getQuotaAction(err) {
  const fallback = buildDefaultAction()
  if (!err || typeof err !== 'object') return fallback
  const rawAction = err.action
  if (!rawAction || typeof rawAction !== 'object') return fallback
  const path = typeof rawAction.path === 'string' && rawAction.path.length > 0 && rawAction.path !== '/pricing'
    ? rawAction.path
    : fallback.path
  const label = typeof rawAction.label === 'string' && rawAction.label.length > 0
    ? rawAction.label
    : fallback.label
  return { type: rawAction.type || fallback.type, path, label }
}

// 从 Error 对象提取完整结构（message + code + action）。
// 用于在 Vue 组件 / API 边界解构错误，避免散落的 e.message / e.code 访问。
// 不修改原 Error，返回纯数据对象。
export function extractApiError(err) {
  if (!err) return { message: '', code: null, action: null }
  if (typeof err === 'string') return { message: err, code: null, action: null }
  const message = typeof err.message === 'string' ? err.message : ''
  const code = typeof err.code === 'string' ? err.code : null
  const action = err.action && typeof err.action === 'object' ? err.action : null
  return { message, code, action }
}
