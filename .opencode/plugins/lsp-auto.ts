/**
 * LSP Auto-Detection Plugin
 *
 * 自动检测项目类型并配置对应的 LSP 服务器。
 * 在 opencode 启动时扫描项目文件，推荐并记录可用的 LSP 配置。
 */

import type { Plugin } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"

// ─── LSP 服务器定义 ──────────────────────────────────────

interface LspDefinition {
  name: string
  languages: string[]
  detectFiles: string[]      // 项目根目录中存在的文件来检测
  detectDirs: string[]       // 项目根目录中存在的目录来检测
  command: string[]           // 要检查的二进制名称（第一个存在就用它）
  installHint: string         // 如果二进制不存在，提示如何安装
}

const LSP_DEFINITIONS: LspDefinition[] = [
  {
    name: "typescript-language-server",
    languages: ["typescript", "javascript", "tsx", "jsx"],
    detectFiles: ["tsconfig.json", "jsconfig.json"],
    detectDirs: ["src"],
    command: ["typescript-language-server", "npx typescript-language-server"],
    installHint: "npm install -g typescript-language-server typescript",
  },
  {
    name: "vscode-eslint-language-server",
    languages: ["typescript", "javascript", "tsx", "jsx"],
    detectFiles: [".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs", "eslint.config.ts"],
    detectDirs: [],
    command: ["vscode-eslint-language-server"],
    installHint: "npm install -g vscode-langservers-extracted",
  },
  {
    name: "pyright",
    languages: ["python"],
    detectFiles: ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
    detectDirs: [],
    command: ["pyright-langserver", "npx pyright"],
    installHint: "pip install pyright",
  },
  {
    name: "ruff-lsp",
    languages: ["python"],
    detectFiles: ["pyproject.toml", "ruff.toml"],
    detectDirs: [],
    command: ["ruff-lsp"],
    installHint: "pip install ruff-lsp",
  },
  {
    name: "gopls",
    languages: ["go"],
    detectFiles: ["go.mod", "go.sum"],
    detectDirs: [],
    command: ["gopls"],
    installHint: "go install golang.org/x/tools/gopls@latest",
  },
  {
    name: "rust-analyzer",
    languages: ["rust"],
    detectFiles: ["Cargo.toml", "Cargo.lock"],
    detectDirs: [],
    command: ["rust-analyzer"],
    installHint: "rustup component add rust-analyzer",
  },
  {
    name: "jdtls",
    languages: ["java"],
    detectFiles: ["pom.xml", "build.gradle", "build.gradle.kts"],
    detectDirs: ["src/main/java"],
    command: ["jdtls"],
    installHint: "从 https://download.eclipse.org/jdtls/ 下载",
  },
  {
    name: "kotlin-language-server",
    languages: ["kotlin"],
    detectFiles: ["build.gradle.kts", "settings.gradle.kts"],
    detectDirs: ["src/main/kotlin"],
    command: ["kotlin-language-server"],
    installHint: "从 https://github.com/fwcd/kotlin-language-server/releases 下载",
  },
  {
    name: "clangd",
    languages: ["c", "cpp", "c++"],
    detectFiles: ["CMakeLists.txt", "Makefile", "compile_commands.json"],
    detectDirs: [],
    command: ["clangd"],
    installHint: "安装 LLVM/clangd: https://clangd.llvm.org/installation",
  },
  {
    name: "tailwindcss-language-server",
    languages: ["typescript", "javascript", "tsx", "jsx", "html", "css"],
    detectFiles: ["tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs"],
    detectDirs: [],
    command: ["tailwindcss-language-server", "npx @tailwindcss/language-server"],
    installHint: "npm install -g @tailwindcss/language-server",
  },
  {
    name: "json-language-server",
    languages: ["json", "jsonc"],
    detectFiles: [],   // 几乎所有项目都有 JSON 文件
    detectDirs: [],
    command: ["vscode-json-language-server"],
    installHint: "npm install -g vscode-langservers-extracted",
  },
  {
    name: "css-language-server",
    languages: ["css", "scss", "less"],
    detectFiles: [],
    detectDirs: ["styles", "css"],
    command: ["vscode-css-language-server"],
    installHint: "npm install -g vscode-langservers-extracted",
  },
  {
    name: "html-language-server",
    languages: ["html"],
    detectFiles: [],
    detectDirs: [],
    command: ["vscode-html-language-server"],
    installHint: "npm install -g vscode-langservers-extracted",
  },
  {
    name: "lua-language-server",
    languages: ["lua"],
    detectFiles: [".luarc.json", ".luacheckrc"],
    detectDirs: ["lua"],
    command: ["lua-language-server"],
    installHint: "从 https://github.com/LuaLS/lua-language-server/releases 下载",
  },
  {
    name: "marksman",
    languages: ["markdown"],
    detectFiles: [],
    detectDirs: ["docs"],
    command: ["marksman"],
    installHint: "从 https://github.com/artempyanykh/marksman/releases 下载",
  },
]

// ─── 检测逻辑 ────────────────────────────────────────────

const isExecutable = (cmd: string): boolean => {
  try {
    // Windows
    if (process.platform === "win32") {
      const result = require("child_process").spawnSync("where", [cmd], {
        stdio: "pipe",
        shell: true,
        timeout: 3000,
      })
      return result.status === 0 && result.stdout.length > 0
    }
    // Unix
    const result = require("child_process").spawnSync("which", [cmd], {
      stdio: "pipe",
      timeout: 3000,
    })
    return result.status === 0 && result.stdout.length > 0
  } catch {
    return false
  }
}

const findCommand = (commands: string[]): string | null => {
  for (const cmd of commands) {
    if (isExecutable(cmd)) return cmd
  }
  return null
}

const detectLspForProject = (projectDir: string): {
  available: { name: string; command: string; languages: string[] }[]
  unavailable: { name: string; languages: string[]; installHint: string }[]
} => {
  const available: { name: string; command: string; languages: string[] }[] = []
  const unavailable: { name: string; languages: string[]; installHint: string }[] = []

  for (const def of LSP_DEFINITIONS) {
    // 检测项目是否匹配
    let detected = false

    if (def.detectFiles.length > 0) {
      for (const file of def.detectFiles) {
        if (fs.existsSync(path.join(projectDir, file))) {
          detected = true
          break
        }
      }
    }

    if (!detected && def.detectDirs.length > 0) {
      for (const dir of def.detectDirs) {
        if (fs.existsSync(path.join(projectDir, dir))) {
          detected = true
          break
        }
      }
    }

    if (!detected) continue

    // 检查二进制是否可用
    const cmd = findCommand(def.command)
    if (cmd) {
      available.push({ name: def.name, command: cmd, languages: def.languages })
    } else {
      unavailable.push({
        name: def.name,
        languages: def.languages,
        installHint: def.installHint,
      })
    }
  }

  return { available, unavailable }
}

// ─── 根据已安装的 LSP 推断主要语言 ─────────────────────────

const inferLanguages = (
  available: { name: string; languages: string[] }[]
): string[] => {
  const langSet = new Set<string>()
  for (const item of available) {
    for (const lang of item.languages) {
      langSet.add(lang)
    }
  }
  return [...langSet]
}

// ─── 插件主体 ────────────────────────────────────────────

export const LspAutoPlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx

  // 只在首次启动时检测（检测耗时 1-3 秒）
  const result = detectLspForProject(directory)
  const languages = inferLanguages(result.available)

  // 结构化日志
  await client.app.log({
    body: {
      service: "lsp-auto",
      level: "info",
      message: "LSP auto-detection complete",
      extra: {
        project: directory,
        detectedLanguages: languages,
        availableLspCount: result.available.length,
        availableLsps: result.available.map(l => l.name),
        unavailableLsps: result.unavailable.map(l => ({
          name: l.name,
          install: l.installHint,
        })),
      },
    },
  })

  // 如果有未安装的 LSP，记录推荐安装命令
  if (result.unavailable.length > 0) {
    const hints = result.unavailable
      .map(u => `  - ${u.name}: ${u.installHint}`)
      .join("\n")

    await client.app.log({
      body: {
        service: "lsp-auto",
        level: "warn",
        message: `Some LSP servers not installed:\n${hints}`,
        extra: { unavailable: result.unavailable.map(u => u.name) },
      },
    })
  }

  // 检测到 TypeScript 但没有 ESLint LSP → 推荐配置
  const hasTsAvailable = result.available.some(l => l.name === "typescript-language-server")
  const hasEslintAvailable = result.available.some(l => l.name === "vscode-eslint-language-server")
  if (hasTsAvailable && !hasEslintAvailable) {
    await client.app.log({
      body: {
        service: "lsp-auto",
        level: "info",
        message: "Tip: Install ESLint LSP for real-time lint feedback: npm install -g vscode-langservers-extracted",
      },
    })
  }

  return {}
}

export default LspAutoPlugin
