import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const solutionPath = resolve('solution.html')
if (!existsSync(solutionPath)) {
  throw new Error('缺少 solution.html')
}

const pages = ['index.html', 'pricing.html', 'cases.html', 'security.html', 'solution.html']
for (const page of pages) {
  const html = readFileSync(resolve(page), 'utf8')
  if (!html.includes('href="/solution.html"')) {
    throw new Error(`${page} 的解决方案导航没有指向 /solution.html`)
  }
}

const solutionHtml = readFileSync(solutionPath, 'utf8')
for (const text of ['重塑规矩，确立初审法度', '第零步防线：免责护城河', '原生解构：绝对空间坐标', '私域红线：智能规避航标']) {
  if (!solutionHtml.includes(text)) {
    throw new Error(`solution.html 缺少 Stitch 还原内容: ${text}`)
  }
}

if (/Solutions|Data Security|Customer Cases|Pricing|Login/.test(solutionHtml)) {
  throw new Error('solution.html 不应保留英文导航文案')
}

console.log('solution page verified')
