import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const read = (file) => readFileSync(resolve(root, file), 'utf8')

// BaseSelect 的键盘导航规则必须可脱离 DOM 验证，且跳过禁用项。
const { getEnabledOptionIndex, getNextEnabledOptionIndex } = await import('../src/components/ui/selectNavigation.js')
const options = [
  { value: 'a', label: 'A' },
  { value: 'b', label: 'B', disabled: true },
  { value: 'c', label: 'C' },
]
assert.equal(getEnabledOptionIndex(options, 'b'), 0)
assert.equal(getEnabledOptionIndex(options, 'c'), 2)
assert.equal(getNextEnabledOptionIndex(options, 0, 1), 2)
assert.equal(getNextEnabledOptionIndex(options, 2, -1), 0)
assert.equal(getNextEnabledOptionIndex(options, 0, 'end'), 2)

// listOrders 的失败必须对调用方可见，不能伪装成空订单。
globalThis.sessionStorage = { getItem: () => null, setItem() {}, removeItem() {} }
globalThis.window = { location: { pathname: '/' } }
globalThis.fetch = async () => ({
  ok: false,
  status: 503,
  json: async () => ({ detail: '订单服务暂不可用' }),
})
const { listOrders } = await import(`../src/services/paymentApi.js?test=${Date.now()}`)
await assert.rejects(listOrders(), /订单服务暂不可用/)

globalThis.fetch = async () => ({
  ok: false,
  status: 500,
  json: async () => ({ detail: { internal: '不应暴露' } }),
})
const { listOrders: listOrdersWithMalformedError } = await import(`../src/services/paymentApi.js?test=${Date.now() + 1}`)
await assert.rejects(listOrdersWithMalformedError(), /历史订单加载失败/)

const settings = read('src/pages/SettingsPage.vue')
assert.match(settings, /historyError\.value\s*=\s*err instanceof Error/)
assert.doesNotMatch(settings, /catch \(err\) \{\s*historyError\.value[\s\S]{0,160}historyOrders\.value\s*=\s*\[\]/)

const select = read('src/components/ui/BaseSelect.vue')
for (const token of ['aria-activedescendant', 'aria-controls', ':id="listboxId"', '@keydown="onKeydown"', 'activeIndex']) {
  assert.ok(select.includes(token), `BaseSelect 必须包含 ${token}`)
}
for (const token of ['const labelId =', ':id="labelId"', ':aria-labelledby="label ? labelId : undefined"']) {
  assert.ok(select.includes(token), `BaseSelect 的可见标签必须与触发按钮关联：缺少 ${token}`)
}

const modal = read('src/components/PaymentModal.vue')
for (const token of ['role="dialog"', 'aria-modal="true"', 'aria-labelledby="payment-modal-title"', 'id="payment-modal-title"', '@keydown.esc="close"', 'closeButtonRef', 'previouslyFocusedElement']) {
  assert.ok(modal.includes(token), `PaymentModal 必须包含 ${token}`)
}
for (const token of ['modalRef', 'function trapFocus(event)', 'FOCUSABLE_SELECTOR', '@keydown.tab="trapFocus"', 'role="alert"']) {
  assert.ok(modal.includes(token), `PaymentModal 必须提供焦点陷阱和错误播报：缺少 ${token}`)
}

console.log('支付错误与可访问性行为校验通过')
