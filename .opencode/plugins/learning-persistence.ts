/**
 * Learning Persistence Plugin — 复利学习的存储引擎
 *
 * 功能:
 * 1. 项目检测 — 通过 git remote 生成唯一项目 ID
 * 2. 条目持久化 — 读写 learning entries
 * 3. 置信度进化 — 匹配已有条目时自动提升 confidence
 * 4. 会话启动加载 — 自动加载高置信度学习提醒
 * 5. 升级检测 — 标记达到升级阈值的条目
 */

import type { Plugin } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"
import * as os from "os"
import { randomBytes, createHash } from "crypto"

// ─── 类型定义 ────────────────────────────────────────────

type Domain = "code-style" | "testing" | "debugging" | "security" | "workflow" | "performance" | "project"
type EntryType = "pattern" | "fix" | "convention" | "tool" | "architecture"
type Scope = "project" | "global"

interface LearningEntry {
  id: string
  type: EntryType
  domain: Domain
  scope: Scope
  project_id: string
  project_name: string
  confidence: number
  confirmed_in: number
  sessions: string[]
  created: string
  updated: string
  what: string
  trigger: string
  why: string
  evidence: string[]
  suggested_promotion?: { target: "rule" | "skill" | "agent" | "command"; path: string; reason: string }
}

// ─── 路径定义 ────────────────────────────────────────────

const HOME = os.homedir()
const LEARNINGS_ROOT = path.join(HOME, ".opencode", "learnings")
const REGISTRY_FILE = path.join(LEARNINGS_ROOT, "projects.json")

// ─── 项目检测 ────────────────────────────────────────────

const detectProject = (directory: string): { id: string; name: string } | null => {
  try {
    const gitDir = path.join(directory, ".git")
    if (!fs.existsSync(gitDir)) return null

    // 尝试获取 remote URL 生成稳定 ID
    const configPath = path.join(gitDir, "config")
    if (fs.existsSync(configPath)) {
      const config = fs.readFileSync(configPath, "utf8")
      const match = config.match(/url\s*=\s*(?:git@|https:\/\/)(?:github\.com\/|gitlab\.com\/)?(.+?)(?:\.git)?\s*$/)
      if (match) {
        const repoPath = match[1].replace(/[:\/]/g, "-")
        return { id: repoPath, name: repoPath.split("/").pop() || repoPath }
      }
    }

    // Fallback: 使用目录名
    const dirName = path.basename(directory)
    return { id: createHash("sha256").update(directory).digest("hex").slice(0, 12), name: dirName }
  } catch {
    return null
  }
}

// ─── 注册表管理 ──────────────────────────────────────────

interface ProjectRegistry {
  [projectId: string]: { name: string; path: string; created: string; entryCount: number }
}

const loadRegistry = (): ProjectRegistry => {
  try {
    if (fs.existsSync(REGISTRY_FILE)) {
      return JSON.parse(fs.readFileSync(REGISTRY_FILE, "utf8"))
    }
  } catch {}
  return {}
}

const saveRegistry = (registry: ProjectRegistry) => {
  const dir = path.dirname(REGISTRY_FILE)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(REGISTRY_FILE, JSON.stringify(registry, null, 2), "utf8")
}

// ─── 条目读写 ────────────────────────────────────────────

const entriesDir = (projectId: string): string =>
  path.join(LEARNINGS_ROOT, projectId, "entries")

const loadEntries = (projectId: string): LearningEntry[] => {
  const dir = entriesDir(projectId)
  if (!fs.existsSync(dir)) return []

  const entries: LearningEntry[] = []
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".md")) continue
    try {
      const content = fs.readFileSync(path.join(dir, file), "utf8")
      const entry = parseEntryFile(content)
      if (entry) entries.push(entry)
    } catch {}
  }
  return entries.sort((a, b) => b.confidence - a.confidence)
}

const saveEntry = (projectId: string, entry: LearningEntry) => {
  const dir = entriesDir(projectId)
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })

  const yamlBlock = `---
id: "${entry.id}"
type: ${entry.type}
domain: ${entry.domain}
scope: ${entry.scope}
project_id: "${entry.project_id}"
confidence: ${entry.confidence}
confirmed_in: ${entry.confirmed_in}
created: "${entry.created}"
updated: "${entry.updated}"
sessions:
${entry.sessions.map(s => `  - "${s}"`).join("\n")}
---
`

  const body = `# What
${entry.what}

# Trigger
${entry.trigger}

# Why It Matters
${entry.why}

# Evidence
${entry.evidence.map(e => `- ${e}`).join("\n")}
`

  const filename = `${entry.id}.md`
  fs.writeFileSync(path.join(dir, filename), yamlBlock + body, "utf8")
}

const parseEntryFile = (content: string): LearningEntry | null => {
  try {
    const yamlMatch = content.match(/^---\n([\s\S]*?)\n---/)
    if (!yamlMatch) return null

    const yaml: Record<string, any> = {}
    for (const line of yamlMatch[1].split("\n")) {
      const colonIdx = line.indexOf(":")
      if (colonIdx > 0) {
        const key = line.slice(0, colonIdx).trim()
        let value: any = line.slice(colonIdx + 1).trim()
        value = value.replace(/^["']|["']$/g, "") // strip quotes
        if (!isNaN(Number(value))) value = Number(value)
        yaml[key] = value
      }
    }

    const body = content.slice(yamlMatch[0].length)

    const whatMatch = body.match(/# What\n([\s\S]*?)(?=\n# |$)/)
    const triggerMatch = body.match(/# Trigger\n([\s\S]*?)(?=\n# |$)/)
    const whyMatch = body.match(/# Why It Matters\n([\s\S]*?)(?=\n# |$)/)
    const evidenceMatch = body.match(/# Evidence\n([\s\S]*?)$/)

    return {
      id: yaml.id || "",
      type: yaml.type || "pattern",
      domain: yaml.domain || "workflow",
      scope: yaml.scope || "project",
      project_id: yaml.project_id || "",
      project_name: yaml.project_name || "",
      confidence: yaml.confidence || 0.3,
      confirmed_in: yaml.confirmed_in || 1,
      sessions: yaml.sessions || [],
      created: yaml.created || new Date().toISOString(),
      updated: yaml.updated || new Date().toISOString(),
      what: whatMatch ? whatMatch[1].trim() : "",
      trigger: triggerMatch ? triggerMatch[1].trim() : "",
      why: whyMatch ? whyMatch[1].trim() : "",
      evidence: evidenceMatch ? evidenceMatch[1].trim().split("\n").filter(l => l.startsWith("- ")).map(l => l.slice(2)) : [],
      suggested_promotion: confidenceCheck(yaml.confidence || 0.3, yaml.type || "pattern", yaml.domain || "workflow"),
    }
  } catch {
    return null
  }
}

// ─── 置信度检测 ──────────────────────────────────────────

const confidenceCheck = (confidence: number, type: string, domain: string): LearningEntry["suggested_promotion"] | undefined => {
  if (confidence < 0.7) return undefined

  // 映射 type+domain 到升级目标
  if (["convention", "pattern"].includes(type) && domain === "code-style") {
    return { target: "rule", path: "rules/common.md", reason: "编码约定 → 通用规则" }
  }
  if (["fix", "tool"].includes(type)) {
    return { target: "skill", path: `skills/${type}-${domain}/SKILL.md`, reason: "操作经验 → 可复用技能" }
  }
  if (type === "workflow") {
    return { target: "command", path: "opencode.json → command", reason: "工作流模式 → 斜杠命令" }
  }
  if (type === "architecture") {
    return { target: "agent", path: "prompts/*.txt", reason: "架构知识 → Agent 提示词" }
  }
  return { target: "rule", path: "rules/common.md", reason: "通用模式 → 自动规则" }
}

// ─── 匹配算法 ────────────────────────────────────────────

interface MatchedEntry {
  entry: LearningEntry
  similarity: number  // 0-1
}

const findSimilarEntries = (newWhat: string, existing: LearningEntry[]): MatchedEntry[] => {
  const keywords = newWhat.toLowerCase().split(/\s+/).filter(w => w.length > 3)
  return existing
    .map(e => {
      const target = (e.what + " " + e.trigger).toLowerCase()
      const matches = keywords.filter(k => target.includes(k)).length
      const similarity = keywords.length > 0 ? matches / keywords.length : 0
      return { entry: e, similarity }
    })
    .filter(m => m.similarity > 0.4)
    .sort((a, b) => b.similarity - a.similarity)
}

// ─── 统计 ────────────────────────────────────────────────

interface LearningStats {
  total: number
  confirmed: number
  readyToPromote: number
  promoted: number
  byDomain: Record<string, number>
  latestEntries: { what: string; confidence: number }[]
}

const getStats = (projectId: string): LearningStats => {
  const entries = loadEntries(projectId)
  const byDomain: Record<string, number> = {}
  for (const e of entries) {
    byDomain[e.domain] = (byDomain[e.domain] || 0) + 1
  }

  return {
    total: entries.length,
    confirmed: entries.filter(e => e.confidence >= 0.4).length,
    readyToPromote: entries.filter(e => e.confidence >= 0.7 && e.suggested_promotion).length,
    promoted: entries.filter(e => e.confidence >= 0.9).length,
    byDomain,
    latestEntries: entries.slice(0, 5).map(e => ({ what: e.what.slice(0, 80), confidence: e.confidence })),
  }
}

// ─── 插件主体 ────────────────────────────────────────────

export const LearningPersistencePlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx

  const project = detectProject(directory)

  if (!project) {
    await client.app.log({ body: { service: "learning-persistence", level: "debug", message: "No git project detected, skipping learning persistence" } })
    return {}
  }

  // 注册项目
  const registry = loadRegistry()
  if (!registry[project.id]) {
    registry[project.id] = { name: project.name, path: directory, created: new Date().toISOString(), entryCount: 0 }
    saveRegistry(registry)
  }

  const stats = getStats(project.id)

  await client.app.log({
    body: {
      service: "learning-persistence",
      level: "info",
      message: `Project "${project.name}" — ${stats.total} learnings (${stats.readyToPromote} ready to promote)`,
      extra: { projectId: project.id, stats },
    },
  })

  return {
    // ═══ 会话启动 — 加载高置信度提醒 ═══
    "session.created": async () => {
      const entries = loadEntries(project!.id)
      const highConfidence = entries.filter(e => e.confidence >= 0.4)

      if (highConfidence.length > 0) {
        const reminders = highConfidence
          .slice(0, 8)
          .map(e => `  • [${e.domain}] ${e.what.slice(0, 100)} (confidence ${e.confidence.toFixed(1)})`)
          .join("\n")

        await client.app.log({
          body: {
            service: "learning-persistence",
            level: "info",
            message: `Active learnings for this project:\n${reminders}`,
            extra: { count: highConfidence.length },
          },
        })
      }

      // 更新注册表中的计数
      const reg = loadRegistry()
      if (reg[project!.id]) {
        reg[project!.id].entryCount = entries.length
        saveRegistry(reg)
      }
    },
  }
}

export default LearningPersistencePlugin
