import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const html = readFileSync(resolve('index.html'), 'utf8')

for (const text of ['top-nav pricing-nav', 'zhulong-brand', 'brand-mark', 'GOULONG', '立即预约演示']) {
  if (!html.includes(text)) {
    throw new Error(`首页导航缺少统一样式内容: ${text}`)
  }
}

for (const href of ['/solution.html', '/security.html', '/cases.html', '/pricing.html']) {
  if (!html.includes(`href="${href}"`)) {
    throw new Error(`首页导航缺少链接: ${href}`)
  }
}

if (html.includes('>注册<') || html.includes('句龙 · 照胆</a>')) {
  throw new Error('首页导航仍保留旧版文案')
}

console.log('home navigation verified')
