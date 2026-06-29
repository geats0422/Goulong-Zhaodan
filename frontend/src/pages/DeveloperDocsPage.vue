<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const mcpTools = [
  { name: 'zhaodan_me', desc: '检查 API Key 身份与 scopes', scope: '任意有效 Key', readonly: true },
  { name: 'zhaodan_search_knowledge', desc: '检索法规/知识库片段，返回 snippets 与 sources', scope: 'knowledge:read', readonly: true },
  { name: 'zhaodan_list_records', desc: '列出当前用户体检记录摘要', scope: 'inspection:read', readonly: true },
  { name: 'zhaodan_get_record', desc: '获取指定体检记录详情（风险/问题/法规引用）', scope: 'inspection:read', readonly: true },
  { name: 'zhaodan_inspect_text', desc: '直接审查一段工程文档正文，返回完整体检报告', scope: 'inspection:run', readonly: false },
  { name: 'zhaodan_parse_file', desc: '上传本地文件解析，创建 pending 记录返回 record_id', scope: 'inspection:run', readonly: false },
  { name: 'zhaodan_inspect_record', desc: '基于 record_id 执行体检，复用已解析正文', scope: 'inspection:run', readonly: false },
  { name: 'zhaodan_create_inspect_job', desc: '创建异步体检 job（长文本/批处理）', scope: 'inspection:run', readonly: false },
  { name: 'zhaodan_create_parse_job', desc: '创建异步解析 job（base64 投递 worker）', scope: 'inspection:run', readonly: false },
  { name: 'zhaodan_get_job_status', desc: '查询异步 job 状态与结果', scope: '任意有效 Key', readonly: true },
]

const cliCommands = [
  { cmd: 'zhaodan me', desc: '检查身份与 scopes' },
  { cmd: 'zhaodan knowledge:search --query <关键词>', desc: '检索知识库', extra: '[--application-scenario bidding|contract] [--limit 10]' },
  { cmd: 'zhaodan records:list', desc: '列出体检记录' },
  { cmd: 'zhaodan records:get --record-id <id>', desc: '获取记录详情' },
  { cmd: 'zhaodan inspect:text --document-name <name> --text <正文>', desc: '文本体检', extra: '[--application-scenario bidding|contract] [--taboo-words <词>]' },
  { cmd: 'zhaodan parse:file --file-path <path>', desc: '上传文件解析' },
  { cmd: 'zhaodan inspect:record --record-id <id>', desc: '基于 record_id 体检', extra: '[--application-scenario bidding|contract] [--taboo-words <词>]' },
  { cmd: 'zhaodan jobs:inspect --document-name <name> --text <正文>', desc: '创建异步体检任务' },
  { cmd: 'zhaodan jobs:parse --file-path <path>', desc: '创建异步解析任务' },
  { cmd: 'zhaodan jobs:status --job-id <id>', desc: '查询异步任务状态' },
]

const apiEndpoints = [
  { method: 'GET', path: '/api/v1/agent/me', desc: '身份验证', scope: '任意' },
  { method: 'POST', path: '/api/v1/agent/knowledge/search', desc: '知识库检索', scope: 'knowledge:read' },
  { method: 'GET', path: '/api/v1/agent/records', desc: '体检记录列表', scope: 'inspection:read' },
  { method: 'GET', path: '/api/v1/agent/records/{record_id}', desc: '体检记录详情', scope: 'inspection:read' },
  { method: 'POST', path: '/api/v1/agent/inspect', desc: '同步体检（文本/record_id）', scope: 'inspection:run' },
  { method: 'POST', path: '/api/v1/agent/parse', desc: '文件解析（multipart）', scope: 'inspection:run' },
  { method: 'POST', path: '/api/v1/agent/jobs/inspect', desc: '创建异步体检 job', scope: 'inspection:run' },
  { method: 'POST', path: '/api/v1/agent/jobs/parse', desc: '创建异步解析 job', scope: 'inspection:run' },
  { method: 'GET', path: '/api/v1/agent/jobs/{job_id}', desc: '查询异步 job 状态', scope: '任意' },
]

const scopeTemplates = [
  { name: 'mcp_readonly', desc: '只读 Agent', scopes: 'knowledge:read + inspection:read' },
  { name: 'cli_review', desc: 'CLI 体检', scopes: 'inspection:run + knowledge:read' },
  { name: 'mcp_inspect', desc: 'MCP 体检（推荐）', scopes: 'inspection:run + knowledge:read' },
  { name: 'agent_automation', desc: 'Agent 自动化', scopes: '全权限（不含删除）' },
]
</script>

<template>
  <MarketingShell>
    <main>
      <!-- Hero -->
      <header class="pricing-hero-section">
        <div class="container pricing-hero-inner">
          <nav class="case-breadcrumb" aria-label="面包屑">
            <a href="/">首页</a>
            <span>/</span>
            <span>开发文档</span>
          </nav>
          <div class="gold-rule"></div>
          <p class="eyebrow">DEVELOPER DOCUMENTATION</p>
          <h1>2A 接入指南</h1>
          <p class="lead">照胆已具备 ToB + ToA 双轨能力：RESTful API 面向后端集成，MCP Server 面向 AI Agent，CLI 面向开发者自动化。</p>
        </div>
      </header>

      <!-- 三栏布局 -->
      <div class="docs-layout">
        <!-- 左侧导航 -->
        <aside class="docs-sidebar">
          <nav class="docs-nav">
            <div class="docs-nav-section">
              <h4 class="docs-nav-title">开始</h4>
              <a href="#intro" class="docs-nav-link">简介</a>
              <a href="#quickstart" class="docs-nav-link">快速开始</a>
              <a href="#api-key" class="docs-nav-link">API Key</a>
            </div>
            <div class="docs-nav-section">
              <h4 class="docs-nav-title">接入方式</h4>
              <a href="#mcp" class="docs-nav-link">MCP Server</a>
              <a href="#cli" class="docs-nav-link">CLI 工具</a>
              <a href="#api" class="docs-nav-link">HTTP API</a>
            </div>
            <div class="docs-nav-section">
              <h4 class="docs-nav-title">参考</h4>
              <a href="#scopes" class="docs-nav-link">权限模板</a>
              <a href="#security" class="docs-nav-link">安全实践</a>
            </div>
          </nav>
        </aside>

        <!-- 内容区 -->
        <main class="docs-content">
          <!-- 简介 -->
          <article id="intro" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-001</span>
              <span class="docs-meta-tag">2A CAPABILITY</span>
            </div>
            <h2>照胆开发者文档</h2>
            <p class="docs-lead">照胆是国家合规审查 AI 代理服务器，支持工程文档智能体检、法规知识检索和异步批处理。本文档面向通过 API、MCP 或 CLI 接入照胆的开发者和 AI Agent。</p>

            <div class="docs-callout">
              <span class="material-symbols-outlined">rocket_launch</span>
              <div>
                <h3>三种接入方式</h3>
                <p>Agent 支持 MCP 时用 MCP Server；可运行命令行时用 CLI；只能发 HTTP 请求时直接调 REST API。三种方式共享同一套 API Key 和权限体系。</p>
              </div>
            </div>

            <h3>核心能力</h3>
            <div class="docs-feature-grid">
              <div class="docs-feature">
                <span class="material-symbols-outlined">fact_check</span>
                <h4>文档体检</h4>
                <p>上传招标文件/合同，AI 自动识别风险点并引用法规依据。</p>
              </div>
              <div class="docs-feature">
                <span class="material-symbols-outlined">menu_book</span>
                <h4>知识检索</h4>
                <p>检索法规库与工程标准，返回精确 snippets 与 sources。</p>
              </div>
              <div class="docs-feature">
                <span class="material-symbols-outlined">sync</span>
                <h4>异步任务</h4>
                <p>长文本和批处理走异步 job，不阻塞当前会话。</p>
              </div>
              <div class="docs-feature">
                <span class="material-symbols-outlined">token</span>
                <h4>Token 计费</h4>
                <p>按真实模型消耗计量，支持额度包与微信支付。</p>
              </div>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- 快速开始 -->
          <article id="quickstart" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-002</span>
            </div>
            <h2>快速开始</h2>
            <ol class="docs-step-list">
              <li><span class="docs-step-num">01</span>注册账号并登录</li>
              <li><span class="docs-step-num">02</span>在 设置 → 开发者 API Key 创建 Key（选择权限模板）</li>
              <li><span class="docs-step-num">03</span>设置环境变量 <code>ZHAODAN_API_KEY</code></li>
              <li><span class="docs-step-num">04</span>执行第一次调用</li>
            </ol>

            <h3>环境变量</h3>
            <div class="docs-code-block">
              <div class="docs-code-header">
                <span class="docs-code-tag">Shell</span>
              </div>
              <pre><code>export ZHAODAN_API_KEY="您的 API Key"
export ZHAODAN_API_BASE_URL="http://localhost:8000"  # 可选，默认即此值</code></pre>
            </div>

            <h3>第一次调用（curl）</h3>
            <div class="docs-code-block">
              <div class="docs-code-header">
                <span class="docs-code-tag">cURL</span>
              </div>
              <pre><code>curl -X POST http://localhost:8000/api/v1/agent/knowledge/search \
  -H "Authorization: Bearer $ZHAODAN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "招投标资格条件", "application_scenario": "bidding", "limit": 5}'</code></pre>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- API Key -->
          <article id="api-key" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-003</span>
            </div>
            <h2>API Key 管理</h2>
            <p>API Key 在 <a href="/settings">设置 → 开发者 API Key</a> 页面创建。创建时选择权限模板，系统会生成完整密钥（仅显示一次）。Key 用于 Agent / MCP / CLI 调用，后端记录 <code>last_viewed_at</code> 和 <code>last_used_at</code>。</p>
            <div class="docs-callout docs-callout-warn">
              <span class="material-symbols-outlined">warning</span>
              <div>
                <h3>安全提示</h3>
                <p>API Key 等同于账户凭证。请妥善保管，不要提交到代码仓库或暴露在前端代码中。不包含删除记录等破坏性权限。</p>
              </div>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- MCP Server -->
          <article id="mcp" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-004</span>
              <span class="docs-meta-tag">MCP</span>
            </div>
            <h2>MCP Server</h2>
            <p>照胆 MCP Server 基于 Model Context Protocol，供支持 MCP 的 AI Agent（如 Claude、Cursor 等）直接调用照胆的体检、检索和异步任务能力。</p>

            <h3>安装与配置</h3>
            <div class="docs-code-block">
              <div class="docs-code-header">
                <span class="docs-code-tag">MCP Config (JSON)</span>
              </div>
              <pre><code>{
  "mcpServers": {
    "goulong-zhaodan": {
      "command": "node",
      "args": ["MCP/dist/index.js"],
      "env": {
        "ZHAODAN_API_KEY": "您的 API Key",
        "ZHAODAN_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}</code></pre>
            </div>

            <h3>工具列表（10 个）</h3>
            <div class="docs-table-wrap">
              <table class="docs-table">
                <thead>
                  <tr>
                    <th>工具</th>
                    <th>描述</th>
                    <th>Scope</th>
                    <th>读写</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="t in mcpTools" :key="t.name">
                    <td><code>{{ t.name }}</code></td>
                    <td>{{ t.desc }}</td>
                    <td><span class="scope-chip">{{ t.scope }}</span></td>
                    <td>{{ t.readonly ? '只读' : '读+写' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- CLI -->
          <article id="cli" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-005</span>
              <span class="docs-meta-tag">CLI</span>
            </div>
            <h2>CLI 工具</h2>
            <p>照胆 CLI 供可运行命令行但没有 MCP 支持的 Agent 使用。通过 <code>zhaodan</code> 命令调用。</p>

            <h3>安装</h3>
            <div class="docs-code-block">
              <div class="docs-code-header">
                <span class="docs-code-tag">Shell</span>
              </div>
              <pre><code>cd CLI && npm install && npm run build
# 或全局链接
npm link</code></pre>
            </div>

            <h3>命令列表</h3>
            <div class="docs-table-wrap">
              <table class="docs-table">
                <thead>
                  <tr>
                    <th>命令</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="c in cliCommands" :key="c.cmd">
                    <td><code>{{ c.cmd }}</code></td>
                    <td>{{ c.desc }}<span v-if="c.extra" class="cmd-extra">{{ c.extra }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- HTTP API -->
          <article id="api" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-006</span>
              <span class="docs-meta-tag">REST API</span>
            </div>
            <h2>HTTP API</h2>
            <p>所有端点以 <code>/api/v1/agent</code> 为前缀，使用 <code>Authorization: Bearer &lt;API_KEY&gt;</code> 认证。</p>

            <h3>端点列表</h3>
            <div class="docs-table-wrap">
              <table class="docs-table">
                <thead>
                  <tr>
                    <th>方法</th>
                    <th>路径</th>
                    <th>说明</th>
                    <th>Scope</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="e in apiEndpoints" :key="e.path">
                    <td><span class="method-chip" :class="e.method">{{ e.method }}</span></td>
                    <td><code>{{ e.path }}</code></td>
                    <td>{{ e.desc }}</td>
                    <td><span class="scope-chip">{{ e.scope }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h3>体检请求示例</h3>
            <div class="docs-code-block">
              <div class="docs-code-header">
                <span class="docs-code-tag">JSON</span>
              </div>
              <pre><code>{
  "document_name": "招标文件.txt",
  "text": "第一章 投标须知...",
  "application_scenario": "bidding",
  "taboo_words": "",
  "project_id": "default"
}</code></pre>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- 权限模板 -->
          <article id="scopes" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-007</span>
            </div>
            <h2>权限模板</h2>
            <p>创建 API Key 时选择模板，系统自动配置对应 scopes。也可选择"高级自定义"按需勾选。</p>
            <div class="docs-feature-grid">
              <div v-for="s in scopeTemplates" :key="s.name" class="scope-card">
                <h4>{{ s.name }}</h4>
                <p class="scope-card-desc">{{ s.desc }}</p>
                <p class="scope-card-scopes">{{ s.scopes }}</p>
              </div>
            </div>
          </article>

          <hr class="docs-divider" />

          <!-- 安全实践 -->
          <article id="security" class="docs-article">
            <div class="docs-article-meta">
              <span class="ref-label">REF.GL-DOCS-008</span>
            </div>
            <h2>安全实践</h2>
            <div class="docs-security-list">
              <div class="docs-security-item">
                <span class="material-symbols-outlined">key</span>
                <div>
                  <h4>最小权限原则</h4>
                  <p>只读场景使用 <code>mcp_readonly</code>，体检场景使用 <code>mcp_inspect</code>，避免不必要的 <code>agent_automation</code>。</p>
                </div>
              </div>
              <div class="docs-security-item">
                <span class="material-symbols-outlined">visibility_off</span>
                <div>
                  <h4>阅后即焚</h4>
                  <p>照胆默认开启阅后即焚，体检报告在查看后自动清理中间态，不持久化原始文档正文。</p>
                </div>
              </div>
              <div class="docs-security-item">
                <span class="material-symbols-outlined">block</span>
                <div>
                  <h4>无破坏性操作</h4>
                  <p>Skills / MCP / CLI 均不提供删除记录能力。默认不请求或假设 <code>records:delete</code> 权限。</p>
                </div>
              </div>
              <div class="docs-security-item">
                <span class="material-symbols-outlined">verified_user</span>
                <div>
                  <h4>Cloudflare Turnstile</h4>
                  <p>注册和验证码端点启用人机验证，防止自动化注册攻击和短信轰炸。</p>
                </div>
              </div>
            </div>
          </article>
        </main>
      </div>
    </main>
  </MarketingShell>
</template>

<style scoped>
.docs-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 0;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px 80px;
}

/* 左侧导航 */
.docs-sidebar {
  position: sticky;
  top: 80px;
  align-self: start;
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  padding: 32px 0;
  border-right: 1px solid color-mix(in srgb, var(--gold) 12%, transparent);
}

.docs-nav {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-right: 20px;
}

.docs-nav-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.docs-nav-title {
  margin: 0 0 8px;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: var(--muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.docs-nav-link {
  display: block;
  padding: 6px 12px;
  color: var(--muted);
  text-decoration: none;
  font-size: 13px;
  border-left: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}

.docs-nav-link:hover {
  color: var(--gold);
  border-left-color: var(--gold);
  background: color-mix(in srgb, var(--gold) 6%, transparent);
}

/* 内容区 */
.docs-content {
  padding: 32px 0 32px 48px;
  min-width: 0;
}

.docs-article {
  margin-bottom: 16px;
}

.docs-article-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.ref-label {
  font: 500 10px/1 "JetBrains Mono", monospace;
  color: var(--gold);
  letter-spacing: 0.14em;
}

.docs-meta-tag {
  font: 500 10px/1 "JetBrains Mono", monospace;
  color: var(--muted);
  letter-spacing: 0.14em;
  padding: 4px 8px;
  border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
}

.docs-article h2 {
  margin: 0 0 16px;
  font-family: "Syne", sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}

.docs-article h3 {
  margin: 32px 0 12px;
  font-family: "Syne", sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--gold);
}

.docs-article h4 {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.docs-lead {
  font-size: 15px;
  line-height: 1.7;
  color: var(--muted);
  margin: 0 0 16px;
  max-width: 680px;
}

.docs-article p {
  font-size: 14px;
  line-height: 1.7;
  color: var(--muted);
  margin: 0 0 12px;
}

.docs-article p code {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: var(--gold);
  background: color-mix(in srgb, var(--gold) 8%, transparent);
  padding: 2px 6px;
}

.docs-article a {
  color: var(--gold);
  text-decoration: none;
}

.docs-article a:hover {
  text-decoration: underline;
}

/* 分隔线 (Golden Thread) */
.docs-divider {
  border: 0;
  height: 1px;
  margin: 40px 0;
  background: linear-gradient(90deg,
    color-mix(in srgb, var(--gold) 30%, transparent),
    color-mix(in srgb, var(--gold) 8%, transparent) 50%,
    transparent);
}

/* Callout */
.docs-callout {
  display: flex;
  gap: 16px;
  padding: 20px;
  margin: 20px 0;
  border: 1px solid color-mix(in srgb, var(--gold) 20%, transparent);
  background: color-mix(in srgb, var(--surface-2, #1c1b1b) 60%, transparent);
}

.docs-callout .material-symbols-outlined {
  font-size: 24px;
  color: var(--gold);
  flex-shrink: 0;
}

.docs-callout h3 {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.docs-callout p {
  margin: 0;
  font-size: 13px;
}

.docs-callout-warn {
  border-color: color-mix(in srgb, var(--error, #ffb4ab) 25%, transparent);
}

.docs-callout-warn .material-symbols-outlined {
  color: var(--error, #ffb4ab);
}

/* 步骤列表 */
.docs-step-list {
  list-style: none;
  padding: 0;
  margin: 16px 0;
  counter-reset: step;
}

.docs-step-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  font-size: 14px;
  color: var(--muted);
  border-bottom: 1px solid color-mix(in srgb, var(--line) 30%, transparent);
}

.docs-step-num {
  font: 700 12px/1 "JetBrains Mono", monospace;
  color: var(--gold);
  letter-spacing: 0.1em;
}

/* 特性网格 */
.docs-feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin: 16px 0;
}

.docs-feature {
  padding: 20px;
  border: 1px solid color-mix(in srgb, var(--line) 40%, transparent);
  background: color-mix(in srgb, var(--surface-2, #1c1b1b) 50%, transparent);
}

.docs-feature .material-symbols-outlined {
  font-size: 28px;
  color: var(--gold);
  margin-bottom: 8px;
}

.docs-feature h4 {
  margin: 0 0 4px;
  font-size: 14px;
}

.docs-feature p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
}

/* 代码块 */
.docs-code-block {
  margin: 16px 0;
  border: 1px solid color-mix(in srgb, var(--gold) 15%, transparent);
  overflow: hidden;
}

.docs-code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: color-mix(in srgb, var(--bg) 80%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--gold) 12%, transparent);
}

.docs-code-tag {
  font: 500 10px/1 "JetBrains Mono", monospace;
  color: var(--muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.docs-code-block pre {
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  background: color-mix(in srgb, var(--bg) 95%, transparent);
}

.docs-code-block code {
  font-family: "JetBrains Mono", monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text);
  white-space: pre;
}

/* 表格 */
.docs-table-wrap {
  margin: 16px 0;
  overflow-x: auto;
  border: 1px solid color-mix(in srgb, var(--line) 40%, transparent);
}

.docs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.docs-table th {
  padding: 10px 14px;
  text-align: left;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: var(--gold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  border-bottom: 1px solid color-mix(in srgb, var(--gold) 20%, transparent);
  background: color-mix(in srgb, var(--bg) 60%, transparent);
}

.docs-table td {
  padding: 10px 14px;
  color: var(--muted);
  border-bottom: 1px solid color-mix(in srgb, var(--line) 20%, transparent);
}

.docs-table tr:last-child td {
  border-bottom: 0;
}

.docs-table td code {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: var(--gold);
}

.docs-table td code {
  background: none;
  padding: 0;
}

.cmd-extra {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: color-mix(in srgb, var(--muted) 70%, transparent);
}

/* Chips */
.scope-chip {
  display: inline-block;
  padding: 2px 8px;
  font: 500 10px/1.4 "JetBrains Mono", monospace;
  color: var(--muted);
  border: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
  white-space: nowrap;
}

.method-chip {
  display: inline-block;
  padding: 2px 8px;
  font: 700 10px/1.4 "JetBrains Mono", monospace;
  letter-spacing: 0.05em;
}

.method-chip.GET {
  color: #66bb6a;
}

.method-chip.POST {
  color: var(--gold);
}

/* 权限卡片 */
.scope-card {
  padding: 20px;
  border: 1px solid color-mix(in srgb, var(--gold) 15%, transparent);
  background: color-mix(in srgb, var(--surface-2, #1c1b1b) 50%, transparent);
}

.scope-card h4 {
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
  color: var(--gold);
  margin: 0 0 6px;
}

.scope-card-desc {
  margin: 0 0 4px;
  font-size: 13px;
}

.scope-card-scopes {
  margin: 0;
  font: 500 11px/1.4 "JetBrains Mono", monospace;
  color: var(--muted);
}

/* 安全列表 */
.docs-security-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 16px 0;
}

.docs-security-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  border: 1px solid color-mix(in srgb, var(--line) 35%, transparent);
}

.docs-security-item .material-symbols-outlined {
  font-size: 22px;
  color: var(--gold);
  flex-shrink: 0;
}

.docs-security-item h4 {
  margin: 0 0 4px;
  font-size: 14px;
}

.docs-security-item p {
  margin: 0;
  font-size: 13px;
}

/* 响应式 */
@media (max-width: 900px) {
  .docs-layout {
    grid-template-columns: 1fr;
  }

  .docs-sidebar {
    display: none;
  }

  .docs-content {
    padding-left: 0;
  }
}
</style>
