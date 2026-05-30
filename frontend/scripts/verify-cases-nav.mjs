import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const pages = ['index.html', 'pricing.html', 'cases.html']

for (const page of pages) {
  const html = readFileSync(resolve(page), 'utf8')
  if (!html.includes('href="/cases.html"')) {
    throw new Error(`${page} 的客户案例导航没有指向 /cases.html`)
  }
}

const casesHtml = readFileSync(resolve('cases.html'), 'utf8')
for (const text of ['行业令鉴与实战战报', '调遣您的初审 Agent', '重大合规错漏前置拦截率']) {
  if (!casesHtml.includes(text)) {
    throw new Error(`cases.html 缺少 Stitch 还原内容: ${text}`)
  }
}

console.log('cases navigation verified')
