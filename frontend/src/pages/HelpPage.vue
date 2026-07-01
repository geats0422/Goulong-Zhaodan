<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const nav = [
  { group: '新手入门', items: [['start', '开始使用'], ['first-inspect', '第一次材料包体检']] },
  { group: '功能指南', items: [['feature-inspect', '材料包体检'], ['feature-knowledge', '知识库'], ['feature-history', '体检台'], ['feature-stats', '数据统计']] },
  { group: '账户与订阅', items: [['faq-account', '账户登录'], ['faq-billing', '订阅与额度'], ['faq-payment', '支付方式'], ['faq-security', '数据安全']] },
  { group: 'Agent 接入', items: [['agent-key', 'API Key'], ['agent-intro', 'MCP / CLI / Skill']] },
  { group: '常见问题', items: [['faq-doc', '文档相关'], ['faq-ai', 'AI 相关'], ['faq-export', '报告导出']] },
]

const steps = [
  { ref: 'REF.GL-H01', step: '第 1 步', title: '注册账号', desc: '支持手机号 + 短信验证码，或邮箱 + 密码（8 位以上，含大小写字母和数字）注册。', href: '/register', cta: '前往注册' },
  { ref: 'REF.GL-H02', step: '第 2 步', title: '上传材料包体检', desc: '进入靶场（Dashboard），拖拽上传合同、报价、申请表、证照等多个文件，系统自动解析并识别文件类型。', href: '/dashboard', cta: '进入靶场' },
  { ref: 'REF.GL-H03', step: '第 3 步', title: '查看体检报告', desc: '审查完成后获得问题清单、修改建议与证据定位（章-节-段-句），支持 Markdown / PDF 导出。', href: '/dashboard', cta: '查看报告' },
]

const faqGroups = [
  {
    id: 'feature-inspect',
    tag: '§ 功能 · 体检',
    title: '材料包体检',
    items: [
      ['支持哪些文件格式？', '支持 PDF、DOCX、DOC、TXT 等常见文档格式。可一次上传多个文件（合同、报价、申请表、证照、说明文件），系统会做跨文件的一致性与完整性审查。'],
      ['体检会检查哪些问题？', '主体一致性（公司名称、统一社会信用代码、联系人、地址）、金额/日期/编号冲突、附件完整性（正文引用但缺失的附件），并标注问题所在文件与段落。'],
      ['审查场景怎么识别？', '在文件解析阶段自动识别为「合同」或「招投标文件」等类型，驱动后续知识库召回与审查，无需手动选择。'],
    ],
  },
  {
    id: 'feature-knowledge',
    tag: '§ 功能 · 知识库',
    title: '知识库',
    items: [
      ['知识库是什么？', '企业专属参考卷宗库。可上传历史合同、行业范本、企业规范，体检时按相似度召回相关条款作为审查依据。'],
      ['知识库支持哪些操作？', '在知识库页面可上传新卷宗、重命名、删除，并按分类管理。'],
    ],
  },
  {
    id: 'feature-history',
    tag: '§ 功能 · 体检台',
    title: '体检台（历史记录）',
    items: [
      ['体检台能做什么？', '查看所有历史体检记录的档案库，可按状态筛选、查看报告详情、物理销毁案卷（阅后即焚）。'],
      ['已销毁的记录还能找回吗？', '物理销毁（焚毁）后文档原文不可恢复，仅保留审查结论元数据。请确认后再操作。'],
    ],
  },
  {
    id: 'feature-stats',
    tag: '§ 功能 · 统计',
    title: '数据统计',
    items: [
      ['统计页看什么？', '上传文档数、违禁词出现率、额度消耗、体检趋势等 MVP 指标，帮助复盘审查效果。'],
    ],
  },
  {
    id: 'faq-account',
    tag: '§ 账户',
    title: '账户登录',
    items: [
      ['忘记密码怎么办？', '登录页点击「账号密码登录」，使用「忘记密码」通过手机号验证码重置；后端也提供 /auth/reset-password 端点。'],
      ['可以用邮箱登录吗？', '可以。注册时填写邮箱并完成邮箱验证后，即可用邮箱 + 密码登录；也支持手机号 + 短信验证码快捷登录。'],
      ['注册为什么要人机验证？', '注册和验证码端点启用 Cloudflare Turnstile 人机验证，防止自动化注册攻击和短信轰炸。'],
    ],
  },
  {
    id: 'faq-billing',
    tag: '§ 订阅',
    title: '订阅与额度',
    items: [
      ['订阅套餐有哪些？', 'Pro 月度 ¥49、Pro 季度 ¥139、Pro 年度 ¥499（最高性价比）。订阅周期内无限次体检。'],
      ['额度包会过期吗？', '不会。额度包（轻量 ¥5 / 标准 ¥18 / 大额 ¥58）永久有效、不过期，可随时补充。'],
      ['额度是怎么消耗的？', '按 AI 模型真实 Token 消耗计量，100% 按用量计费，不额外加价。可在统计页查看额度消耗趋势。'],
    ],
  },
  {
    id: 'faq-payment',
    tag: '§ 支付',
    title: '支付方式',
    items: [
      ['支持哪些支付方式？', '目前支持微信扫码支付。下单后扫码完成支付，额度立即到账。'],
      ['可以开发票吗？', '企业客户可联系商务（business@goulong-ai.cn）按合同约定开具发票。'],
    ],
  },
  {
    id: 'faq-security',
    tag: '§ 安全',
    title: '数据安全',
    items: [
      ['上传的文档安全吗？', '数据流转于 TEE 加密内存，支持阅后即焚。文档处理方式由您自主选择：审查后即焚（物理删除原文）或保留备查。'],
      ['什么是数据安全锁？', '设置中的数据安全锁可对敏感操作二次确认。结合本地脱敏与审计留痕，建立安全边界。'],
      ['文档会被用于训练模型吗？', '不会。照胆采用原生结构解析与确定性树状寻址，拒绝把敏感数据沉淀进公有云向量数据库。'],
    ],
  },
  {
    id: 'agent-key',
    tag: '§ Agent · Key',
    title: 'API Key',
    items: [
      ['如何创建 API Key？', '设置 → 开发者 API Key → 创建，选择权限模板（mcp_readonly / cli_review / agent_full_access），系统生成完整密钥（仅显示一次）。'],
      ['API Key 有哪些权限模板？', 'mcp_readonly（只读）、cli_review（查询+体检）、agent_full_access（完整协作，含读写）。均不含删除等破坏性权限。'],
    ],
  },
  {
    id: 'agent-intro',
    tag: '§ Agent · 接入',
    title: 'MCP / CLI / Skill',
    items: [
      ['Agent 怎么接入照胆？', '支持三种方式：MCP Server（Claude Code / Cursor / Codex 等）、CLI（zhaodan 命令）、Skill（opencode / Claude Code 加载技能文件）。详见技术文档。', '/docs'],
      ['REST API 怎么调？', '所有端点以 /api/v1/agent 为前缀，使用 Authorization: Bearer <API_KEY> 认证。完整端点列表见技术文档。', '/docs'],
    ],
  },
  {
    id: 'faq-doc',
    tag: '§ FAQ · 文档',
    title: '文档相关',
    items: [
      ['单个文件最大多大？', '单文件建议不超过 50MB。超大文件建议拆分或使用异步 job 处理。'],
      ['可以上传扫描件 / 图片吗？', '目前以文本型文档为主（PDF/DOCX/TXT）。纯图片扫描件的识别效果取决于其中是否包含可提取文本。'],
    ],
  },
  {
    id: 'faq-ai',
    tag: '§ FAQ · AI',
    title: 'AI 相关',
    items: [
      ['体检结果准吗？需要人工复核吗？', '体检属于 AI 辅助输出，可能存在偏差或遗漏。正式提交前应由具备资质的人员人工复核，AI 结果仅供参考、不构成正式合规意见。'],
      ['用的是哪家大模型？', 'DeepSeek。照胆用确定性逻辑与原生结构解析替代纯向量检索，降低幻觉。'],
    ],
  },
  {
    id: 'faq-export',
    tag: '§ FAQ · 导出',
    title: '报告导出',
    items: [
      ['可以导出报告吗？', '可以。支持 Markdown 与 PDF 诊断报告导出，便于提交业务、法务或合规复核。'],
      ['报告里有证据定位吗？', '有。每个问题都标注来源文件与「章-节-段-句」层级位置，可追溯。'],
    ],
  },
]
</script>

<template>
  <MarketingShell>
    <main>
      <header class="pricing-hero-section help-hero-section">
        <div class="container pricing-hero-inner">
          <nav class="case-breadcrumb" aria-label="面包屑">
            <a href="/">首页</a>
            <span>/</span>
            <span>帮助中心</span>
          </nav>
          <div class="gold-rule"></div>
          <p class="eyebrow">HELP CENTER</p>
          <h1>帮助中心</h1>
          <p class="lead">在这里找到使用照胆所需的一切答案。浏览下方分类，或跳转到对应功能区。</p>
          <div class="help-hero-tags">
            <a href="#start" class="help-hero-tag">新手入门</a>
            <a href="#faq-billing" class="help-hero-tag">订阅与额度</a>
            <a href="#faq-security" class="help-hero-tag">数据安全</a>
            <a href="#agent-intro" class="help-hero-tag">Agent 接入</a>
          </div>
        </div>
      </header>

      <div class="help-layout container">
        <aside class="help-sidebar">
          <nav class="help-nav">
            <div v-for="sec in nav" :key="sec.group" class="help-nav-section">
              <h4>{{ sec.group }}</h4>
              <a v-for="it in sec.items" :key="it[0]" :href="'#' + it[0]" class="help-nav-link">{{ it[1] }}</a>
            </div>
          </nav>
        </aside>

        <article class="help-content">
          <section id="start" class="help-section">
            <div class="help-section-tag">§ 01 · 入门</div>
            <h2>欢迎使用句龙 · 照胆</h2>
            <p class="help-lead">照胆是业务提交前审查 Agent，在 OA、合同审批、采购申请正式流转前，对材料包做一致性与完整性审查。三步即可上手。</p>
            <div class="help-step-grid">
              <div v-for="s in steps" :key="s.ref" class="circuit-card help-step-card">
                <span class="corner corner-tl"></span>
                <span class="corner corner-br"></span>
                <span class="help-card-ref">{{ s.ref }}</span>
                <div class="help-step-num">{{ s.step }}</div>
                <h3>{{ s.title }}</h3>
                <p>{{ s.desc }}</p>
                <a :href="s.href" class="help-step-link">
                  {{ s.cta }}
                  <span class="material-symbols-outlined">arrow_forward</span>
                </a>
              </div>
            </div>
          </section>

          <hr class="help-divider" />

          <section id="first-inspect" class="help-section">
            <div class="help-section-tag">§ 02 · 教程</div>
            <h2>5 分钟完成第一次材料包体检</h2>
            <ol class="help-tutorial">
              <li><span class="help-tutorial-num">01</span><div><h3>登录进入靶场</h3><p>登录后在 Dashboard（靶场）点击上传，或直接拖拽文件到上传区。</p></div></li>
              <li><span class="help-tutorial-num">02</span><div><h3>上传材料包</h3><p>一次选择多个文件（合同、报价、申请表、证照），系统自动解析并识别文件类型。</p></div></li>
              <li><span class="help-tutorial-num">03</span><div><h3>确认解析与知识库</h3><p>在审查弹窗中确认解析结果，按需勾选启用的知识库与审查场景。</p></div></li>
              <li><span class="help-tutorial-num">04</span><div><h3>执行审查</h3><p>点击执行，AI 按一致性、完整性、法规依据输出问题清单与证据定位。</p></div></li>
              <li><span class="help-tutorial-num">05</span><div><h3>查看与导出报告</h3><p>在体检台查看报告详情，导出 Markdown / PDF，或对案卷执行阅后即焚。</p></div></li>
            </ol>
          </section>

          <hr class="help-divider" />

          <section v-for="g in faqGroups" :key="g.id" :id="g.id" class="help-section">
            <div class="help-section-tag">{{ g.tag }}</div>
            <h2>{{ g.title }}</h2>
            <div class="help-faq-list">
              <details v-for="(it, i) in g.items" :key="i" class="help-faq-item">
                <summary>{{ it[0] }}<span class="material-symbols-outlined help-faq-icon">expand_more</span></summary>
                <p>{{ it[1] }}<a v-if="it[2]" :href="it[2]" class="help-faq-link">前往 →</a></p>
              </details>
            </div>
          </section>

          <div class="help-contact">
            <span class="corner corner-tl"></span>
            <span class="corner corner-br"></span>
            <p class="eyebrow">STILL NEED HELP</p>
            <h2>没找到答案？</h2>
            <p>如果是商务合作、私有化部署或其他问题，随时联系我们。</p>
            <a href="mailto:business@goulong-ai.cn" class="btn btn-primary">联系商务合作</a>
          </div>
        </article>
      </div>
    </main>
  </MarketingShell>
</template>

<style scoped>
.help-hero-section {
  padding-bottom: 48px;
}

.help-hero-tags {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.help-hero-tag {
  padding: 7px 14px;
  border: 1px solid color-mix(in srgb, var(--gold) 30%, transparent);
  color: var(--gold);
  text-decoration: none;
  font: 500 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
  transition: background 0.2s, border-color 0.2s;
}

.help-hero-tag:hover {
  background: color-mix(in srgb, var(--gold) 12%, transparent);
  border-color: var(--gold);
}

.help-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 0;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px 80px;
}

.help-sidebar {
  position: sticky;
  top: 80px;
  align-self: start;
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  padding: 32px 0;
  border-right: 1px solid color-mix(in srgb, var(--gold) 12%, transparent);
}

.help-nav {
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding-right: 20px;
}

.help-nav-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.help-nav-section h4 {
  margin: 0 0 8px;
  font: 500 11px/1 "JetBrains Mono", monospace;
  color: var(--muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.help-nav-link {
  display: block;
  padding: 6px 12px;
  color: var(--muted);
  text-decoration: none;
  font-size: 13px;
  border-left: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}

.help-nav-link:hover {
  color: var(--gold);
  border-left-color: var(--gold);
  background: color-mix(in srgb, var(--gold) 6%, transparent);
}

.help-content {
  padding: 32px 0 32px 48px;
  min-width: 0;
}

.help-section {
  padding: 32px 0;
  border-top: 1px solid color-mix(in srgb, var(--gold) 14%, transparent);
}

.help-section:first-child {
  border-top: 0;
  padding-top: 0;
}

.help-section-tag {
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.14em;
  margin-bottom: 10px;
}

.help-section h2 {
  margin: 0 0 16px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.4rem, 2.4vw, 1.9rem);
}

.help-lead {
  color: var(--muted);
  line-height: 1.8;
  max-width: 640px;
  margin-bottom: 24px;
}

.help-step-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

.help-step-card {
  padding: 26px 22px;
}

.help-card-ref {
  display: block;
  margin-bottom: 12px;
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.14em;
}

.help-step-num {
  margin-bottom: 8px;
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.1em;
}

.help-step-card h3 {
  margin-bottom: 8px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: 18px;
}

.help-step-card p {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 14px;
}

.help-step-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--gold);
  text-decoration: none;
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.06em;
}

.help-step-link .material-symbols-outlined {
  font-size: 16px;
}

.help-divider {
  border: 0;
  height: 1px;
  margin: 8px 0;
  background: linear-gradient(90deg,
    color-mix(in srgb, var(--gold) 28%, transparent),
    color-mix(in srgb, var(--gold) 8%, transparent) 50%,
    transparent);
}

.help-tutorial {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.help-tutorial li {
  display: flex;
  gap: 16px;
  padding: 16px;
  border: 1px solid color-mix(in srgb, var(--gold) 16%, transparent);
  background: color-mix(in srgb, var(--surface) 70%, transparent);
}

.help-tutorial-num {
  flex-shrink: 0;
  color: var(--gold);
  font: 700 14px/1 "JetBrains Mono", monospace;
}

.help-tutorial h3 {
  margin: 0 0 4px;
  color: var(--text);
  font-size: 15px;
}

.help-tutorial p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.help-faq-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.help-faq-item {
  padding: 16px 20px;
  border: 1px solid color-mix(in srgb, var(--gold) 16%, transparent);
  background: color-mix(in srgb, var(--surface) 70%, transparent);
}

.help-faq-item summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text);
  font-size: 14px;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.help-faq-item summary::-webkit-details-marker {
  display: none;
}

.help-faq-icon {
  color: var(--gold);
  font-size: 20px;
  transition: transform 0.2s;
}

.help-faq-item[open] .help-faq-icon {
  transform: rotate(180deg);
}

.help-faq-item p {
  margin: 12px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}

.help-faq-link {
  display: inline-block;
  margin-left: 8px;
  color: var(--gold);
  text-decoration: none;
  font-weight: 600;
}

.help-contact {
  position: relative;
  margin-top: 32px;
  padding: 36px 32px;
  text-align: center;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background:
    radial-gradient(420px 180px at 50% 0%, color-mix(in srgb, var(--gold) 12%, transparent), transparent 64%),
    color-mix(in srgb, var(--surface) 80%, transparent);
}

.help-contact h2 {
  margin: 8px 0 10px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.4rem, 2.4vw, 1.9rem);
}

.help-contact p {
  color: var(--muted);
  margin-bottom: 18px;
}

@media (max-width: 900px) {
  .help-layout {
    grid-template-columns: 1fr;
  }

  .help-sidebar {
    display: none;
  }

  .help-content {
    padding-left: 0;
  }

  .help-step-grid {
    grid-template-columns: 1fr;
  }
}
</style>
