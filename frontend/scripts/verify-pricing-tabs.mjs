import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const html = readFileSync(resolve('pricing.html'), 'utf8')
const js = readFileSync(resolve('src/main.js'), 'utf8')

const requiredTabs = ['个人', '团队', '企业']
for (const tab of requiredTabs) {
  if (!html.includes(`>${tab}<`)) {
    throw new Error(`缺少定价 Tab: ${tab}`)
  }
}

const panels = html.match(/data-pricing-panel=/g) ?? []
if (panels.length !== 3) {
  throw new Error(`需要 3 个定价面板，当前为 ${panels.length}`)
}

for (const id of ['personal', 'team', 'enterprise']) {
  if (!html.includes(`data-pricing-panel="${id}"`)) {
    throw new Error(`缺少定价面板: ${id}`)
  }
}

if (!html.includes('团队协作版开发中') || !html.includes('企业私有化能力后续支持')) {
  throw new Error('团队/企业面板必须说明后续支持状态')
}

if (!js.includes('data-pricing-tab') || !js.includes('data-pricing-panel')) {
  throw new Error('缺少定价 Tab 切换逻辑')
}

console.log('pricing tabs verified')
