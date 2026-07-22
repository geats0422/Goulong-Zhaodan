/**
 * Quality Metrics Plugin
 *
 * 提供项目类型检测 + 代码质量度量工具。
 * 自动检测可用工具并分类（前端/后端/数据库/通用）。
 * 启动时检测项目类型并报告可用的质量工具。
 */

import type { Plugin } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"

// ─── 类型定义 ────────────────────────────────────────────

type ProjectKind = "frontend" | "backend" | "database" | "fullstack" | "general"

interface QualityTool {
  name: string
  available: boolean
  command: string
  configFile: string
  category: "frontend" | "backend" | "database" | "general"
}

interface LintResult {
  errors: number
  warnings: number
  files: number
  details: { file: string; line: number; rule: string; message: string }[]
}

// ─── 工具检测 ────────────────────────────────────────────

const detectQualityTools = (projectDir: string): QualityTool[] => {
  const hasFile = (f: string) => fs.existsSync(path.join(projectDir, f))
  const hasPackage = (pkg: string) => {
    const pkgPath = path.join(projectDir, "package.json")
    if (!fs.existsSync(pkgPath)) return false
    try {
      const json = JSON.parse(fs.readFileSync(pkgPath, "utf8"))
      const deps = { ...json.dependencies, ...json.devDependencies }
      return pkg in deps
    } catch { return false }
  }
  const hasPythonPackage = (pkg: string) => {
    for (const f of ["requirements.txt", "pyproject.toml", "setup.cfg", "Pipfile"]) {
      if (hasFile(f)) {
        try {
          const content = fs.readFileSync(path.join(projectDir, f), "utf8")
          if (content.includes(pkg)) return true
        } catch {}
      }
    }
    return false
  }

  return [
    // ─── 前端工具 ───
    { name: "ESLint",         category: "frontend", configFile: ".eslintrc.*|eslint.config.*", command: "npx eslint . --format json 2>&1 || true", available: hasFile(".eslintrc.js") || hasFile(".eslintrc.json") || hasFile(".eslintrc.yaml") || hasFile(".eslintrc.yml") || hasFile("eslint.config.js") || hasFile("eslint.config.mjs") || hasFile("eslint.config.ts") || hasPackage("eslint") },
    { name: "TypeScript",     category: "frontend", configFile: "tsconfig.json", command: "npx tsc --noEmit --pretty false 2>&1 || true", available: hasFile("tsconfig.json") && hasPackage("typescript") },
    { name: "Prettier",       category: "frontend", configFile: ".prettierrc*|prettier.config.*", command: "npx prettier --check \"src/**/*.{ts,tsx,js,jsx,css,json}\" 2>&1 || true", available: hasFile(".prettierrc") || hasFile(".prettierrc.js") || hasFile(".prettierrc.json") || hasFile("prettier.config.js") || hasPackage("prettier") },
    { name: "Biome",          category: "frontend", configFile: "biome.json", command: "npx biome check --max-diagnostics 1000 2>&1 || true", available: hasFile("biome.json") && hasPackage("@biomejs/biome") },
    { name: "Lighthouse",     category: "frontend", configFile: "lighthouserc.*", command: "npx lighthouse --output json --quiet 2>&1 || true", available: hasPackage("lighthouse") || hasFile("lighthouserc.js") || hasFile("lighthouserc.json") },

    // ─── 后端工具 ───
    { name: "Pylint",         category: "backend", configFile: "pyproject.toml|.pylintrc", command: "python -m pylint src/ 2>&1 || true", available: hasPythonPackage("pylint") },
    { name: "MyPy",           category: "backend", configFile: "mypy.ini|pyproject.toml", command: "python -m mypy src/ 2>&1 || true", available: hasPythonPackage("mypy") || hasFile("mypy.ini") },
    { name: "Bandit (安全)",  category: "backend", configFile: "bandit.yaml", command: "python -m bandit -r src/ 2>&1 || true", available: hasPythonPackage("bandit") },
    { name: "Go Vet",         category: "backend", configFile: "go.mod", command: "go vet ./... 2>&1 || true", available: hasFile("go.mod") },
    { name: "Cargo Clippy",   category: "backend", configFile: "Cargo.toml", command: "cargo clippy -- -D warnings 2>&1 || true", available: hasFile("Cargo.toml") },

    // ─── 数据库工具 ───
    { name: "Prisma Validate", category: "database", configFile: "schema.prisma", command: "npx prisma validate 2>&1 || true", available: hasFile("schema.prisma") || hasPackage("prisma") },
    { name: "SQLFluff",       category: "database", configFile: ".sqlfluff", command: "sqlfluff lint . 2>&1 || true", available: hasPythonPackage("sqlfluff") || hasFile(".sqlfluff") },
    { name: "Migrations",     category: "database", configFile: "migrations/", command: "ls migrations/ 2>&1 || Get-ChildItem migrations/ 2>&1", available: (() => { for (const d of ["migrations","prisma/migrations","db/migrations","alembic"]){ if (fs.existsSync(path.join(projectDir, d))) return true; } return false })() },

    // ─── 通用工具 ───
    { name: "Test (Node)",    category: "general", configFile: "package.json", command: "npm test -- --coverage 2>&1 || true", available: hasFile("package.json") },
    { name: "Test (Python)",  category: "general", configFile: "pytest.ini|pyproject.toml", command: "python -m pytest --cov 2>&1 || true", available: hasPythonPackage("pytest") },
    { name: "Test (Go)",      category: "general", configFile: "go.mod", command: "go test -cover ./... 2>&1 || true", available: hasFile("go.mod") },
  ]
}

// ─── 项目类型检测 ────────────────────────────────────────

const detectProjectKind = (projectDir: string): ProjectKind => {
  const hasFile = (f: string) => fs.existsSync(path.join(projectDir, f))

  const isFrontend = hasFile("tsconfig.json") || hasFile("jsconfig.json") ||
    (() => {
      try {
        const pkgPath = path.join(projectDir, "package.json")
        if (!fs.existsSync(pkgPath)) return false
        const json = JSON.parse(fs.readFileSync(pkgPath, "utf8"))
        const deps = { ...json.dependencies, ...json.devDependencies }
        return ["react","vue","angular","svelte","next","nuxt","solid-js","preact"].some(d => d in deps)
      } catch { return false }
    })()

  const isBackend = (() => {
    try {
      const pkgPath = path.join(projectDir, "package.json")
      if (fs.existsSync(pkgPath)) {
        const json = JSON.parse(fs.readFileSync(pkgPath, "utf8"))
        const deps = { ...json.dependencies, ...json.devDependencies }
        if (["express","fastify","koa","hono","nest","@nestjs/core","next","nuxt","sveltekit","remix","astro"].some(d => d in deps)) return true
      }
      return false
    } catch { return false }
  })() || hasFile("go.mod") || hasFile("requirements.txt") || hasFile("Cargo.toml") || hasFile("Gemfile")

  const hasDatabase = (() => {
    for (const d of ["migrations","prisma","db/migrations","alembic"]) {
      if (fs.existsSync(path.join(projectDir, d))) return true
    }
    return ["schema.prisma","knexfile.js","knexfile.ts","drizzle.config.ts"].some(f => hasFile(f))
  })()

  if (isFrontend && isBackend) return "fullstack"
  if (isFrontend) return "frontend"
  if (isBackend) return "backend"
  if (hasDatabase) return "database"
  return "general"
}

// ─── 结果解析 ────────────────────────────────────────────

const parseEslintOutput = (stdout: string): LintResult => {
  try {
    const results = JSON.parse(stdout) as any[]
    if (!Array.isArray(results)) return { errors: 0, warnings: 0, files: 0, details: [] }
    let errors = 0, warnings = 0, files = 0
    const details: LintResult["details"] = []
    for (const r of results) {
      files++
      for (const m of r.messages || []) {
        if (m.severity === 2) { errors++; details.push({ file: r.filePath, line: m.line, rule: m.ruleId || "unknown", message: m.message }) }
        else { warnings++ }
      }
    }
    return { errors, warnings, files, details: details.slice(0, 50) }
  } catch {
    return { errors: 0, warnings: 0, files: 0, details: [] }
  }
}

const parseTscOutput = (stdout: string): { errors: number; files: number; details: string[] } => {
  const lines = stdout.split("\n").filter(l => l.includes("error TS"))
  return { errors: lines.length, files: new Set(lines.map(l => l.split("(")[0])).size, details: lines.slice(0, 30) }
}

const parseTestOutput = (stdout: string): { passed: number; failed: number; coverage?: string } => {
  const passed = (stdout.match(/(\d+)\s+passing/) || [])[1]
  const failed = (stdout.match(/(\d+)\s+failing/) || [])[1]
  const coverageMatch = stdout.match(/All files\s+\|\s+([\d.]+)/) || stdout.match(/Coverage.*?([\d.]+)%/)
  return { passed: passed ? parseInt(passed) : 0, failed: failed ? parseInt(failed) : 0, coverage: coverageMatch ? `${coverageMatch[1]}%` : undefined }
}

// ─── 插件主体 ────────────────────────────────────────────

export const QualityMetricsPlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx

  let _cachedTools: QualityTool[] | null = null
  let _cachedKind: ProjectKind | null = null

  const getTools = (): QualityTool[] => { if (!_cachedTools) _cachedTools = detectQualityTools(directory); return _cachedTools }
  const getKind = (): ProjectKind => { if (!_cachedKind) _cachedKind = detectProjectKind(directory); return _cachedKind }

  const tools = getTools()
  const kind = getKind()
  const availableTools = tools.filter(t => t.available)

  await client.app.log({
    body: {
      service: "quality-metrics",
      level: "info",
      message: `Project type: ${kind}. Tools: ${availableTools.map(t => t.name).join(", ") || "none"}`,
      extra: { projectKind: kind, available: availableTools.map(t => t.name), categories: {
        frontend: availableTools.filter(t => t.category === "frontend").map(t => t.name),
        backend: availableTools.filter(t => t.category === "backend").map(t => t.name),
        database: availableTools.filter(t => t.category === "database").map(t => t.name),
        general: availableTools.filter(t => t.category === "general").map(t => t.name),
      }},
    },
  })

  return {
    "tool.execute.before": async (input) => {
      if (input.tool === "bash") {
        const cmd = (input.args as any)?.command || ""
        if (/\b(eslint|tsc|prettier|biome|pylint|mypy|bandit|lint|typecheck|test|clippy|go vet)\b/.test(cmd)) {
          await client.app.log({ body: { service: "quality-metrics", level: "debug", message: `Quality tool invoked: ${cmd.slice(0, 80)}` } })
        }
      }
    },

    "session.created": async () => {
      _cachedTools = null; _cachedKind = null
      const tools = getTools()
      const missing = tools.filter(t => !t.available)
      if (missing.length > 0) {
        const hints: Record<string, string> = {
          "ESLint": "npm install -D eslint @eslint/js",
          "TypeScript": "npm install -D typescript",
          "Prettier": "npm install -D prettier",
          "Biome": "npm install -D @biomejs/biome",
          "Pylint": "pip install pylint",
          "MyPy": "pip install mypy",
          "Bandit (安全)": "pip install bandit",
          "SQLFluff": "pip install sqlfluff",
        }
        const suggestions = missing.map(t => `  - ${t.name}: ${hints[t.name] || "not configured"}`).join("\n")
        await client.app.log({ body: { service: "quality-metrics", level: "warn", message: `Missing quality tools:\n${suggestions}` } })
      }
    },
  }
}

export default QualityMetricsPlugin
