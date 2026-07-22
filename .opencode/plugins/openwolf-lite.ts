import type { Plugin } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"

type AnatomyEntry = {
  desc: string
  tokenEstimate: number
  lastSeenAt: string
}

type AnatomyState = {
  version: number
  updatedAt: string
  files: Record<string, AnatomyEntry>
}

type SessionSnapshot = {
  id: string
  startedAt: string
  endedAt: string
  reads: number
  writes: number
  repeatedReadWarnings: number
  doNotRepeatWarnings: number
  anatomyHits: number
  estimatedTokensRead: number
  estimatedTokensWritten: number
}

type LedgerState = {
  version: number
  lifetime: {
    sessions: number
    reads: number
    writes: number
    repeatReadWarnings: number
    doNotRepeatWarnings: number
    anatomyHits: number
    estimatedTokensRead: number
    estimatedTokensWritten: number
  }
  sessions: SessionSnapshot[]
}

type DoNotRepeatRule = {
  id: string
  pattern: string
  hint: string
  enabled: boolean
}

type DoNotRepeatState = {
  version: number
  rules: DoNotRepeatRule[]
}

type BugItem = {
  id: string
  errorPattern: string
  rootCause: string
  fix: string
  tags: string[]
  createdAt: string
  lastUsedAt?: string
}

type BuglogState = {
  version: number
  items: BugItem[]
}

const toIso = () => new Date().toISOString()

const estimateTokens = (text: string, filePath: string): number => {
  const ext = path.extname(filePath).toLowerCase()
  const proseExt = new Set([".md", ".txt", ".rst"])
  const ratio = proseExt.has(ext) ? 4.0 : 3.5
  return Math.max(1, Math.round(text.length / ratio))
}

const normalizeRelativePath = (projectDir: string, filePath: string): string => {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(projectDir, filePath)
  return path.relative(projectDir, abs).replace(/\\/g, "/")
}

const resolveAbsolutePath = (projectDir: string, filePath: string): string => {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(projectDir, filePath)
  return path.resolve(abs)
}

const isInsideProject = (projectDir: string, absPath: string): boolean => {
  const projectRoot = path.resolve(projectDir)
  const rel = path.relative(projectRoot, absPath)
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel)
}

const summarizeFile = (relPath: string, content: string): string => {
  const firstLine = content
    .split(/\r?\n/)
    .map((x) => x.trim())
    .find((x) => x.length > 0)
  if (firstLine) {
    return `${path.basename(relPath)}: ${firstLine.slice(0, 80)}`
  }
  return `${path.basename(relPath)}: empty or binary content`
}

const ensureDir = (dir: string) => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

const safeReadJson = <T>(filePath: string, fallback: T): T => {
  try {
    if (!fs.existsSync(filePath)) return fallback
    const raw = fs.readFileSync(filePath, "utf8")
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

const safeWriteJson = (filePath: string, value: unknown) => {
  const tmp = `${filePath}.tmp`
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8")
  fs.renameSync(tmp, filePath)
}

const extractToolArgs = (argsA: unknown, argsB: unknown): Record<string, unknown> => {
  const a = (argsA && typeof argsA === "object" ? (argsA as Record<string, unknown>) : {})
  const b = (argsB && typeof argsB === "object" ? (argsB as Record<string, unknown>) : {})
  return { ...a, ...b }
}

const extractFilePath = (args: Record<string, unknown>): string | null => {
  const p = args.filePath ?? args.file_path ?? args.path
  return typeof p === "string" && p.length > 0 ? p : null
}

const extractWriteContent = (args: Record<string, unknown>): string => {
  const v = args.content
  return typeof v === "string" ? v : ""
}

const extractReadContent = (args: Record<string, unknown>, output: unknown): string => {
  const out = output && typeof output === "object" ? (output as Record<string, unknown>) : {}
  const candidates: unknown[] = [
    out.content,
    (out as any)?.result?.content,
    args.content,
  ]
  for (const c of candidates) {
    if (typeof c === "string") return c
  }
  return ""
}

export const OpenWolfLitePlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx

  const stateDir = path.join(directory, ".opencode", "state", "openwolf-lite")
  const anatomyFile = path.join(stateDir, "anatomy-lite.json")
  const ledgerFile = path.join(stateDir, "session-ledger.json")
  const buglogFile = path.join(stateDir, "buglog.json")
  const dnrFile = path.join(stateDir, "do-not-repeat.json")

  ensureDir(stateDir)

  let sessionReads = new Map<string, number>()
  let sessionSnapshot: SessionSnapshot = {
    id: `session-${Date.now()}`,
    startedAt: toIso(),
    endedAt: toIso(),
    reads: 0,
    writes: 0,
    repeatedReadWarnings: 0,
    doNotRepeatWarnings: 0,
    anatomyHits: 0,
    estimatedTokensRead: 0,
    estimatedTokensWritten: 0,
  }

  const ensureDefaultStateFiles = () => {
    const anatomyDefault: AnatomyState = { version: 1, updatedAt: toIso(), files: {} }
    const ledgerDefault: LedgerState = {
      version: 1,
      lifetime: {
        sessions: 0,
        reads: 0,
        writes: 0,
        repeatReadWarnings: 0,
        doNotRepeatWarnings: 0,
        anatomyHits: 0,
        estimatedTokensRead: 0,
        estimatedTokensWritten: 0,
      },
      sessions: [],
    }
    const buglogDefault: BuglogState = { version: 1, items: [] }
    const dnrDefault: DoNotRepeatState = {
      version: 1,
      rules: [{ id: "dnr-001", pattern: "never use var", hint: "use const/let", enabled: true }],
    }

    if (!fs.existsSync(anatomyFile)) safeWriteJson(anatomyFile, anatomyDefault)
    if (!fs.existsSync(ledgerFile)) safeWriteJson(ledgerFile, ledgerDefault)
    if (!fs.existsSync(buglogFile)) safeWriteJson(buglogFile, buglogDefault)
    if (!fs.existsSync(dnrFile)) safeWriteJson(dnrFile, dnrDefault)
  }

  const resetSession = () => {
    sessionReads = new Map<string, number>()
    sessionSnapshot = {
      id: `session-${Date.now()}`,
      startedAt: toIso(),
      endedAt: toIso(),
      reads: 0,
      writes: 0,
      repeatedReadWarnings: 0,
      doNotRepeatWarnings: 0,
      anatomyHits: 0,
      estimatedTokensRead: 0,
      estimatedTokensWritten: 0,
    }
  }

  ensureDefaultStateFiles()

  await client.app.log({
    body: {
      service: "openwolf-lite",
      level: "info",
      message: `openwolf-lite initialized in ${directory}`,
    },
  })

  return {
    "session.created": async () => {
      ensureDefaultStateFiles()
      resetSession()
    },

    "tool.execute.before": async (input, output) => {
      const args = extractToolArgs((input as any)?.args, (output as any)?.args)

      if ((input as any)?.tool === "read") {
        const fp = extractFilePath(args)
        if (!fp) return
        const abs = resolveAbsolutePath(directory, fp)
        if (!isInsideProject(directory, abs)) {
          await client.app.log({
            body: {
              service: "openwolf-lite",
              level: "warn",
              message: `Skipped read tracking for out-of-project path: ${fp}`,
            },
          })
          return
        }
        const rel = normalizeRelativePath(directory, abs)

        const readCount = sessionReads.get(rel) || 0
        if (readCount >= 1) {
          sessionSnapshot.repeatedReadWarnings += 1
          await client.app.log({
            body: {
              service: "openwolf-lite",
              level: "warn",
              message: `Repeated read in same session: ${rel}`,
            },
          })
        }

        const anatomy = safeReadJson<AnatomyState>(anatomyFile, { version: 1, updatedAt: toIso(), files: {} })
        const entry = anatomy.files[rel]
        if (entry) {
          sessionSnapshot.anatomyHits += 1
          await client.app.log({
            body: {
              service: "openwolf-lite",
              level: "info",
              message: `anatomy hit: ${rel} (~${entry.tokenEstimate} tok) - ${entry.desc}`,
            },
          })
        }
      }

      if ((input as any)?.tool === "write" || (input as any)?.tool === "edit") {
        const content = extractWriteContent(args)
        if (!content) return
        const dnr = safeReadJson<DoNotRepeatState>(dnrFile, { version: 1, rules: [] })
        for (const rule of dnr.rules) {
          if (!rule.enabled) continue
          const match = content.toLowerCase().includes(rule.pattern.toLowerCase())
          if (match) {
            sessionSnapshot.doNotRepeatWarnings += 1
            await client.app.log({
              body: {
                service: "openwolf-lite",
                level: "warn",
                message: `DNR warning (${rule.id}): ${rule.pattern}. Hint: ${rule.hint}`,
              },
            })
          }
        }
      }
    },

    "tool.execute.after": async (input, output) => {
      const args = extractToolArgs((input as any)?.args, (output as any)?.args)
      const tool = (input as any)?.tool

      if (tool === "read") {
        const fp = extractFilePath(args)
        if (!fp) return
        const abs = resolveAbsolutePath(directory, fp)
        if (!isInsideProject(directory, abs)) return
        const rel = normalizeRelativePath(directory, abs)
        sessionReads.set(rel, (sessionReads.get(rel) || 0) + 1)
        sessionSnapshot.reads += 1

        let content = extractReadContent(args, output)
        if (!content) {
          try {
            content = fs.existsSync(abs) ? fs.readFileSync(abs, "utf8") : ""
          } catch {
            content = ""
          }
        }
        sessionSnapshot.estimatedTokensRead += estimateTokens(content, rel)
      }

      if (tool === "write" || tool === "edit") {
        const fp = extractFilePath(args)
        if (!fp) return
        const abs = resolveAbsolutePath(directory, fp)
        if (!isInsideProject(directory, abs)) return
        const rel = normalizeRelativePath(directory, abs)
        sessionSnapshot.writes += 1

        let content = extractWriteContent(args)
        if (!content) {
          try {
            content = fs.existsSync(abs) ? fs.readFileSync(abs, "utf8") : ""
          } catch {
            content = ""
          }
        }

        const tokenEstimate = estimateTokens(content, rel)
        sessionSnapshot.estimatedTokensWritten += tokenEstimate

        const anatomy = safeReadJson<AnatomyState>(anatomyFile, { version: 1, updatedAt: toIso(), files: {} })
        anatomy.files[rel] = {
          desc: summarizeFile(rel, content),
          tokenEstimate,
          lastSeenAt: toIso(),
        }
        anatomy.updatedAt = toIso()
        safeWriteJson(anatomyFile, anatomy)
      }
    },

    "session.idle": async () => {
      if (sessionSnapshot.reads === 0 && sessionSnapshot.writes === 0) return

      sessionSnapshot.endedAt = toIso()
      const ledger = safeReadJson<LedgerState>(ledgerFile, {
        version: 1,
        lifetime: {
          sessions: 0,
          reads: 0,
          writes: 0,
          repeatReadWarnings: 0,
          doNotRepeatWarnings: 0,
          anatomyHits: 0,
          estimatedTokensRead: 0,
          estimatedTokensWritten: 0,
        },
        sessions: [],
      })

      ledger.lifetime.sessions += 1
      ledger.lifetime.reads += sessionSnapshot.reads
      ledger.lifetime.writes += sessionSnapshot.writes
      ledger.lifetime.repeatReadWarnings += sessionSnapshot.repeatedReadWarnings
      ledger.lifetime.doNotRepeatWarnings += sessionSnapshot.doNotRepeatWarnings
      ledger.lifetime.anatomyHits += sessionSnapshot.anatomyHits
      ledger.lifetime.estimatedTokensRead += sessionSnapshot.estimatedTokensRead
      ledger.lifetime.estimatedTokensWritten += sessionSnapshot.estimatedTokensWritten
      ledger.sessions.push(sessionSnapshot)
      if (ledger.sessions.length > 200) {
        ledger.sessions = ledger.sessions.slice(-200)
      }
      safeWriteJson(ledgerFile, ledger)

      await client.app.log({
        body: {
          service: "openwolf-lite",
          level: "info",
          message: `session saved: reads=${sessionSnapshot.reads}, writes=${sessionSnapshot.writes}`,
        },
      })

      resetSession()
    },
  }
}

export default OpenWolfLitePlugin
