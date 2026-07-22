/**
 * My OpenCode Plugin — 融合三套配置的钩子自动化
 *
 * 来源:
 *   - session.created → ECC SessionStart (加载上下文)
 *   - session.idle    → ECC Stop (保存经验 + 通知)
 *   - tool.execute.before → ECC PreToolUse (保护配置)
 *   - experimental.session.compacting → ECC PreCompact (保存关键状态)
 */

import type { Plugin } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"
import * as os from "os"

// ─── 路径定义 ──────────────────────────────────────────

const HOME = os.homedir()
const LEARNINGS_DIR = path.join(HOME, ".opencode", "learnings")
const LEARNINGS_FILE = path.join(LEARNINGS_DIR, "latest-session.md")

// ─── 共享状态 ──────────────────────────────────────────

let sessionStartTime = Date.now()
let editedFiles = new Set<string>()

// ─── 工具函数 ──────────────────────────────────────────

const ensureDir = (dir: string) => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

const getProjectSlug = (directory: string): string => {
  try {
    const gitDir = path.join(directory, ".git")
    if (fs.existsSync(gitDir)) {
      const configPath = path.join(gitDir, "config")
      if (fs.existsSync(configPath)) {
        const config = fs.readFileSync(configPath, "utf8")
        const match = config.match(/url\s*=\s*(?:git@|https:\/\/)[^/]+\/(.+?)\.git/)
        if (match) return match[1].replace(/\//g, "-")
      }
    }
  } catch {}
  return path.basename(directory).replace(/\s+/g, "-").toLowerCase()
}

const isDestructiveCommand = (command: string): boolean => {
  const dangerous = [
    /\brm\s+-rf\b/, /\bDROP\s+TABLE\b/, /\bDELETE\s+FROM\b/,
    /\bgit\s+push\s+--force\b/, /\bgit\s+reset\s+--hard\b/,
    /\bformat\s+(c:|d:)\\/i, /\bdel\s+\/f\s+\/s\b/i,
    /\bDROP\s+DATABASE\b/, /\bTRUNCATE\b/,
  ]
  return dangerous.some(p => p.test(command))
}

const isConfigFile = (filePath: string): boolean => {
  const configs = [
    ".prettierrc", ".eslintrc", "eslint.config", "tsconfig.json",
    ".editorconfig", "biome.json", "prettier.config",
  ]
  const basename = path.basename(filePath)
  return configs.some(c => basename.includes(c))
}

// ─── 主插件 ────────────────────────────────────────────

export const MyPlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx

  // 启动记录
  sessionStartTime = Date.now()
  editedFiles = new Set<string>()
  ensureDir(LEARNINGS_DIR)

  await client.app.log({
    body: {
      service: "my-opencode-plugin",
      level: "info",
      message: `Plugin initialized in ${directory}`,
    },
  })

  return {
    // ═══ SessionStart → 加载上次会话上下文 ═══
    "session.created": async () => {
      sessionStartTime = Date.now()
      editedFiles = new Set<string>()

      const recentFiles = fs.readdirSync(LEARNINGS_DIR)
        .filter(f => f.endsWith(".md"))
        .sort()
        .slice(-5)

      if (recentFiles.length > 0) {
        await client.app.log({
          body: {
            service: "my-opencode-plugin",
            level: "info",
            message: `Recent learnings: ${recentFiles.join(", ")}`,
          },
        })
      }
    },

    // ═══ Stop → 保存学习记录 + 通知 ═══
    "session.idle": async () => {
      const duration = Math.round((Date.now() - sessionStartTime) / 60000)

      // 保存摘要到 learnings 目录
      const projectSlug = getProjectSlug(directory)
      const projectDir = path.join(LEARNINGS_DIR, projectSlug)
      ensureDir(projectDir)

      const today = new Date().toISOString().slice(0, 10)
      const sessionFile = path.join(projectDir, `${today}-session.md`)

      const summary = `# 会话记录 - ${today}

## 项目
- 目录: ${directory}
- 持续时间: ~${duration} 分钟
- 编辑文件数: ${editedFiles.size}

## 编辑的文件
${[...editedFiles].map(f => `- ${f}`).join("\n")}

## 关键决策
_[运行 /learn 来记录关键决策]_

## 经验教训
_[运行 /learn 来记录经验教训]_
`

      fs.writeFileSync(sessionFile, summary, "utf8")

      // 更新 latest 链接
      const latestLink = path.join(LEARNINGS_DIR, "latest-session.md")
      try { fs.unlinkSync(latestLink) } catch {}
      try { fs.symlinkSync(sessionFile, latestLink) } catch {
        fs.writeFileSync(latestLink, summary, "utf8")
      }

      await client.app.log({
        body: {
          service: "my-opencode-plugin",
          level: "info",
          message: `Session ended (${duration}min, ${editedFiles.size} files). Use /learn to record insights.`,
        },
      })
    },

    // ═══ SessionEnd → 清理 ═══
    "session.deleted": async () => {
      editedFiles = new Set<string>()
    },

    // ═══ PreToolUse → 守护检查 ═══
    "tool.execute.before": async (input, output) => {
      // 保护 .env 文件不被读取
      if (input.tool === "read") {
        const fp = (output.args as any)?.filePath || ""
        if (typeof fp === "string" && fp.includes(".env")) {
          throw new Error(
            "禁止读取 .env 文件。这些文件可能包含敏感信息（密钥、token）。"
          )
        }
      }

      // 守护敏感配置文件不被写入（.env 文件允许创建/编辑）
      if ((input.tool === "write" || input.tool === "edit") && (output.args as any)?.filePath) {
        const fp = (output.args as any).filePath
        if (typeof fp === "string" && isConfigFile(fp)) {
          throw new Error(
            `禁止修改 linter/formatter 配置文件 "${fp}"。修复代码使其符合现有规范，不要削弱配置。`
          )
        }
      }

      // 危险命令警告（非阻塞)
      if (input.tool === "bash") {
        const cmd = (output.args as any)?.command || ""
        if (typeof cmd === "string" && isDestructiveCommand(cmd)) {
          await client.app.log({
            body: {
              service: "my-opencode-plugin",
              level: "warn",
              message: `Destructive command detected: ${cmd.slice(0, 100)}`,
              extra: { command: cmd },
            },
          })
        }
      }
    },

    // ═══ PostToolUse → 记录编辑文件 ═══
    "tool.execute.after": async (input) => {
      if (input.tool === "write" || input.tool === "edit") {
        const fp = (input.args as any)?.filePath
        if (typeof fp === "string") {
          editedFiles.add(fp)
        }
      }
    },

    // ═══ 文件编辑事件 → 额外追踪 ═══
    "file.edited": async (input) => {
      if (input.file) {
        editedFiles.add(input.file)
      }
    },

    // ═══ PreCompact → 压缩前保存关键状态 ═══
    "experimental.session.compacting": async (_input, output) => {
      output.context.push(`## 当前工作状态

在压缩前的上下文中：
- 如果正在进行关键任务，明确记录当前进度
- 如果做出了重要决策，简要记录
- 如果正在编辑特定文件，列出文件路径
- 记录任何尚未解决的阻塞问题

这些信息应该包含在压缩后的摘要中，以便恢复工作。`)
    },
  }
}

export default MyPlugin
