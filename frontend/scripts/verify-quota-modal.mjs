// 任务 16 回归校验：统一额度弹窗与账单 Tab 跳转。
//
// 校验内容：
// 1. inspectionApi.js 不再把对象型 detail 压扁成字符串（必须挂载 code/action 属性）
// 2. InspectionReviewModal.vue 不再用 includes('额度') 文本匹配，不硬编码 /pricing
// 3. SettingsPage.vue 读取 query 参数 tab=billing 自动激活账单 Tab
// 4. 全局搜索不再把额度不足入口指向 /pricing（除订阅升级比较链接外）
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 16
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(file) {
  return readFileSync(resolve(root, file), 'utf8')
}

const inspectionApi = read('src/services/inspectionApi.js')
const reviewModal = read('src/components/inspection/InspectionReviewModal.vue')
const settingsPage = read('src/pages/SettingsPage.vue')
const quotaError = read('src/composables/quotaError.js')
const quotaModal = read('src/components/QuotaErrorModal.vue')

// ---------------------------------------------------------------------------
// 1. inspectionApi: 透传完整 detail 结构到 Error 属性
// ---------------------------------------------------------------------------
// 旧实现只有：const detail = typeof data.detail === 'object' ? data.detail.message || ...
// 新实现必须把 detail.code / detail.action 挂到 Error 上
if (!inspectionApi.includes('err.code') && !inspectionApi.includes('error.code')) {
  throw new Error('inspectionApi 必须把 detail.code 挂到 Error.code 属性（透传稳定错误码）')
}
if (!inspectionApi.includes('err.action') && !inspectionApi.includes('error.action')) {
  throw new Error('inspectionApi 必须把 detail.action 挂到 Error.action 属性（透传账单跳转结构）')
}

// ---------------------------------------------------------------------------
// 2. InspectionReviewModal: 用 code 判定，不再文本匹配，不硬编码 /pricing
// ---------------------------------------------------------------------------
if (reviewModal.includes("includes('额度')")) {
  throw new Error("InspectionReviewModal 不得再用 includes('额度') 文本匹配判定额度不足")
}
if (reviewModal.includes('isInsufficientQuotaError') === false && reviewModal.includes('insufficient_quota') === false) {
  throw new Error('InspectionReviewModal 必须使用 isInsufficientQuotaError 或 code===insufficient_quota 判定额度不足')
}
// 额度跳转链接不得硬编码为 /pricing
const quotaCtaLines = reviewModal.split('\n').filter((l) => l.includes('step-error-cta') || l.includes('前往补充额度') || l.includes('前往账单与订阅'))
for (const line of quotaCtaLines) {
  if (line.includes('href="/pricing"')) {
    throw new Error(`InspectionReviewModal 额度跳转不得硬编码 /pricing：${line.trim()}`)
  }
}
// 必须消费 action.path（来自后端契约）
if (!reviewModal.includes('action') && !reviewModal.includes('quotaAction') && !reviewModal.includes('getQuotaAction')) {
  throw new Error('InspectionReviewModal 必须消费后端 action.path / getQuotaAction')
}

// ---------------------------------------------------------------------------
// 3. SettingsPage: 读取 query 参数 tab=billing 自动激活账单 Tab
// ---------------------------------------------------------------------------
if (!settingsPage.includes('useRoute') && !settingsPage.includes('route.query')) {
  throw new Error('SettingsPage 必须通过 useRoute 读取 query 参数')
}
if (!settingsPage.includes("tab=billing") && !settingsPage.includes("tab === 'billing'") && !settingsPage.includes('query.tab')) {
  throw new Error('SettingsPage 必须读取 ?tab=billing 参数自动激活账单 Tab')
}

// ---------------------------------------------------------------------------
// 4. 共享组件 QuotaErrorModal: 提供统一弹窗与按钮跳转
// ---------------------------------------------------------------------------
if (!quotaModal.includes('当前账户额度不足')) {
  throw new Error('QuotaErrorModal 必须展示统一文案「当前账户额度不足」')
}
if (!quotaModal.includes('本次审查需要更多算力额度')) {
  throw new Error('QuotaErrorModal 必须展示副标题「本次审查需要更多算力额度」')
}
// 按钮跳转目标必须由 action.path 驱动或 fallback 到默认值
if (quotaModal.includes('href="/pricing"')) {
  throw new Error('QuotaErrorModal 按钮不得硬编码 /pricing')
}
// 必须提供 close 事件，关闭按钮不改变路由
if (!quotaModal.includes("emit('close')") && !quotaModal.includes('emit("close")')) {
  throw new Error('QuotaErrorModal 必须提供 close 事件（关闭按钮不改变路由）')
}

// ---------------------------------------------------------------------------
// 5. quotaError composable: 纯函数契约
// ---------------------------------------------------------------------------
for (const fn of ['isInsufficientQuotaError', 'getQuotaAction', 'extractApiError']) {
  if (!quotaError.includes(`export function ${fn}`)) {
    throw new Error(`quotaError 必须导出纯函数：${fn}`)
  }
}
if (!quotaError.includes("QUOTA_INSUFFICIENT_CODE = 'insufficient_quota'")) {
  throw new Error('quotaError 必须导出稳定错误码常量 QUOTA_INSUFFICIENT_CODE')
}
if (!quotaError.includes("DEFAULT_QUOTA_ACTION_PATH = '/settings?tab=billing'")) {
  throw new Error('quotaError 必须固定默认跳转目标为 /settings?tab=billing')
}

console.log('统一额度弹窗与账单 Tab 跳转契约校验通过（错误透传 + code 判定 + tab 自动激活）')
