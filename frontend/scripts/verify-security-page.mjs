import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const securityPath = resolve('security.html')
if (!existsSync(securityPath)) {
  throw new Error('缺少 security.html')
}

const pages = ['index.html', 'pricing.html', 'cases.html', 'security.html']
for (const page of pages) {
  const html = readFileSync(resolve(page), 'utf8')
  if (!html.includes('href="/security.html"')) {
    throw new Error(`${page} 的数据安全导航没有指向 /security.html`)
  }
}

const securityHtml = readFileSync(securityPath, 'utf8')
for (const text of ['绝对静默与密档壁垒', '内存级阅后即焚', '层级索引树不留痕', '业务服务层天然隔离']) {
  if (!securityHtml.includes(text)) {
    throw new Error(`security.html 缺少 Stitch 还原内容: ${text}`)
  }
}

console.log('security page verified')
