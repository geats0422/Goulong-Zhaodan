import { reactive, readonly } from 'vue'

const state = reactive({
  open: false,
  title: '确认操作',
  message: '',
  confirmText: '确认',
  cancelText: '取消',
  danger: false,
})

let resolver = null

export function useConfirmState() {
  return readonly(state)
}

/** @param {string | { title?: string, message: string, confirmText?: string, cancelText?: string, danger?: boolean }} options */
export function confirmDialog(options) {
  const opts = typeof options === 'string' ? { message: options } : (options || {})
  return new Promise((resolve) => {
    state.open = true
    state.title = opts.title || '确认操作'
    state.message = opts.message || ''
    state.confirmText = opts.confirmText || '确认'
    state.cancelText = opts.cancelText || '取消'
    state.danger = !!opts.danger
    resolver = resolve
  })
}

export function resolveConfirm(result) {
  state.open = false
  const done = resolver
  resolver = null
  done?.(!!result)
}
