// 任务 18 回归校验：帮助中心、开发者文档与 README 不再把「招投标」作为新业务入口，
// 示例 payload / curl 不再使用 bidding；历史兼容字段的弃用说明必须保留。
//
// 设计依据：docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
// 任务依据：docs/plans/2026-08-01-contract-inspection-type-and-quota-plan.md 任务 18
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(file) {
  return readFileSync(resolve(root, file), 'utf8')
}

const help = read('src/pages/HelpPage.vue')
const docs = read('src/pages/DeveloperDocsPage.vue')
const readme = read('../README.md')

// ---------------------------------------------------------------------------
// 1. HelpPage: 体检场景识别文案不得再把招投标作为新业务入口
// ---------------------------------------------------------------------------
if (help.includes('招投标文件')) {
  throw new Error('HelpPage 不得再把招投标文件作为新业务入口展示')
}
// 必须引导到合同初审 + 工程/合同类别
if (!help.includes('合同初审') && !help.includes('合同类别') && !help.includes('工程类别')) {
  throw new Error('HelpPage 场景识别文案必须改为合同初审与工程/合同类别描述')
}

// ---------------------------------------------------------------------------
// 2. DeveloperDocsPage: 示例 payload / curl 不得使用 bidding 或招投标作为新业务入口
// ---------------------------------------------------------------------------
const docsBiddingSamples = [
  '"application_scenario": "bidding"',
  "'application_scenario': 'bidding'",
  '--application-scenario bidding',
  '招投标资格条件',
  '上传招标文件',
]
for (const token of docsBiddingSamples) {
  if (docs.includes(token)) {
    throw new Error(`DeveloperDocsPage 示例不得再使用招投标/bidding 入口：${token}`)
  }
}
// 示例必须改为合同场景
if (!docs.includes('"application_scenario": "contract"')) {
  throw new Error('DeveloperDocsPage HTTP 体检示例必须使用 contract 场景')
}
// 文档体检核心能力描述必须改为合同初审
if (!docs.includes('合同初审') && !docs.includes('上传合同')) {
  throw new Error('DeveloperDocsPage 文档体检能力描述必须改为合同初审/合同上传')
}

// ---------------------------------------------------------------------------
// 3. README: 项目定位不得再把招投标代理作为目标用户/核心场景
// ---------------------------------------------------------------------------
const readmeBiddingBusiness = [
  '招投标代理、合同审查人员',
  '招投标代理、造价',
  '招标/投标文件合规审查',
  '面向工程咨询、招投标代理',
]
for (const token of readmeBiddingBusiness) {
  if (readme.includes(token)) {
    throw new Error(`README 不得再把招投标作为新业务定位：${token}`)
  }
}
// README 必须体现合同初审新定位
if (!readme.includes('合同初审')) {
  throw new Error('README 必须把项目定位更新为合同初审')
}

// ---------------------------------------------------------------------------
// 4. 历史兼容字段的弃用说明必须保留（application_scenario 读取能力）
// ---------------------------------------------------------------------------
const compatPreserved =
  readme.includes('application_scenario') || docs.includes('application_scenario')
if (!compatPreserved) {
  throw new Error('application_scenario 历史兼容字段说明必须在文档中保留')
}

console.log('文档与开发者入口招投标新业务描述清理校验通过（合同初审入口 + 历史兼容保留）')
