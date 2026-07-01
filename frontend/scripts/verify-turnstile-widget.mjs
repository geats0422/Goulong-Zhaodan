import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const widget = readFileSync(resolve(root, 'src/components/auth/TurnstileWidget.vue'), 'utf8')

if (!widget.includes('正在载入人机验证')) {
  throw new Error('TurnstileWidget must show a visible loading state before the external script renders')
}

if (!widget.includes('role="status"')) {
  throw new Error('TurnstileWidget loading/error state must be announced as status text')
}

if (!widget.includes('人机验证无法加载') || !widget.includes('Turnstile script load failed')) {
  throw new Error('TurnstileWidget must surface script load failures instead of remaining blank')
}

if (!widget.includes("'error-callback'")) {
  throw new Error('TurnstileWidget must handle Turnstile runtime errors')
}

if (!widget.includes('[data-theme="light"] .turnstile-status')) {
  throw new Error('TurnstileWidget status text must remain readable in light theme')
}
