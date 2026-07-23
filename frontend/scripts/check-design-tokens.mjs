import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const baseline = JSON.parse(readFileSync(resolve('scripts/design-token-baseline.json'), 'utf8'))
const diff = execFileSync('git', ['diff', '--unified=0', '--', 'frontend/src'], {
  cwd: resolve('..'),
  encoding: 'utf8',
})
const violations = []

for (const line of diff.split('\n')) {
  if (!line.startsWith('+') || line.startsWith('+++')) continue
  const source = line.slice(1)
  if (/#(?:[0-9a-fA-F]{3}){1,2}\b/.test(source) && !source.includes('var(--') && !/--color-[\w-]+\s*:/.test(source)) {
    violations.push(`新增硬编码色值: ${source.trim()}`)
  }
  if (/font-family\s*:/.test(source) && !source.includes('var(--font-')) {
    violations.push(`新增非 token 字体: ${source.trim()}`)
  }
}

const activeViolations = violations.filter((violation) => !baseline.accepted.includes(violation))
if (activeViolations.length) {
  console.error(activeViolations.join('\n'))
  process.exit(1)
}

console.log('design:check passed')
