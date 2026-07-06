<script setup>
import MarketingShell from '../components/marketing/MarketingShell.vue'

const toc = [
  ['scope', '适用范围与法律依据'],
  ['collect', '数据收集清单'],
  ['third-party', '第三方服务商'],
  ['usage', '数据使用目的与法律依据'],
  ['doc', '上传文档处理方式'],
  ['retention', '数据保留期限'],
  ['rights', '您的权利'],
  ['security', '安全措施'],
  ['minor', '儿童保护'],
  ['update', '政策更新'],
  ['contact', '联系方式'],
]

const laws = [
  { icon: 'gavel', name: '《个人信息保护法》PIPL', desc: '规范个人信息收集、使用、存储、删除全生命周期' },
  { icon: 'database', name: '《数据安全法》DSL', desc: '数据分类分级管理，跨境传输安全评估' },
  { icon: 'shield', name: '《网络安全法》CSL', desc: '等级保护制度，关键信息基础设施保护' },
  { icon: 'verified', name: 'GB/T 35273', desc: '《信息安全技术 个人信息安全规范》' },
]

const collectData = [
  ['账号信息', '邮箱、手机号、昵称、密码哈希（bcrypt）', '身份认证'],
  ['上传材料', '合同、报价、申请表、证照等文档原文', '一致性与完整性审查'],
  ['AI 调用记录', 'Token 消耗、耗时、文档名称', '用量计费与追溯'],
  ['订阅与支付', '方案名称、状态、额度、订单号', '订阅管理'],
  ['操作日志', '审查操作、账户变更记录', '操作追溯'],
]

const localStore = [
  { name: 'localStorage', items: ['access_token — JWT 登录令牌', 'theme — 主题偏好（dark/light）'] },
  { name: '不使用', items: ['本服务不使用 Cookie', '不集成任何第三方追踪或分析工具（如 Google Analytics、百度统计）'] },
]

const vendors = [
  { ref: 'REF.GL-V01', name: '阿里云 ECS', tags: ['应用服务器', '中国大陆'], desc: '后端应用部署，处理运行时数据与系统日志。', outbound: false },
  { ref: 'REF.GL-V02', name: '阿里云 RDS PostgreSQL', tags: ['数据库', '中国大陆'], desc: '业务核心数据存储，包括账号、订阅、审查记录。', outbound: false },
  { ref: 'REF.GL-V03', name: '阿里云 OSS', tags: ['对象存储', '中国大陆'], desc: '用户上传的材料包文档与附件存储。', outbound: false },
  { ref: 'REF.GL-V04', name: '阿里云短信', tags: ['验证码', '中国大陆'], desc: '发送手机验证码，仅包含手机号与验证码内容。', outbound: false },
  { ref: 'REF.GL-V05', name: '阿里云邮件', tags: ['邮件发送', '中国大陆'], desc: '邮箱验证码邮件发送。', outbound: false },
  { ref: 'REF.GL-V06', name: 'DeepSeek', tags: ['AI 模型', '中国大陆'], desc: '材料包一致性、完整性审查等 AI 能力。', outbound: false },
]

const usageRows = [
  ['用户注册与认证', '邮箱、手机号、密码', '合同履行（PIPL §13(2)）'],
  ['材料包 AI 审查', '用户上传的文档内容', '合同履行'],
  ['短信/邮件验证码', '手机号、邮箱', '合同履行'],
  ['用量计费', 'Token 消耗记录', '合同履行'],
  ['安全防护（限频、人机验证）', 'IP、请求频率', '合法利益（PIPL §13(6)）'],
  ['操作审计与追溯', '操作日志', '合法利益'],
]

const retention = [
  { period: '90 天', title: '账号与业务数据', desc: '账号存续期间 + 注销后 90 天内自动删除，包括上传文件、审查记录、API Key。' },
  { period: '1 年', title: 'AI 调用与算力记录', desc: '用于用量追溯与系统优化，到期自动清理。' },
  { period: '3 年', title: '订阅与支付记录', desc: '依据税务合规要求保留；个人信息到期匿名化处理。' },
  { period: '1 年', title: '操作日志', desc: '用于安全审计与纠纷追溯，到期自动清理。' },
]

const rights = [
  ['visibility', '知情权', '本政策 + 注册时确认'],
  ['toggle_on', '决定权', '非必要数据可拒绝'],
  ['search', '查询权', '设置页面查看全部'],
  ['edit', '更正权', '昵称、邮箱、手机号、密码'],
  ['delete', '删除权', '注销 → 90 天内删除'],
  ['download', '可携带权', '规划中，即将提供'],
  ['link_off', '撤回同意权', '解绑第三方账号'],
  ['gavel', '自动化决策拒绝权', 'AI 审查仅供参考'],
]

const security = [
  ['lock', '传输', 'HTTPS（TLS 1.2+）、HSTS'],
  ['key', '存储', '密码 bcrypt 加密'],
  ['vpn_key', '访问', 'JWT Bearer + 资源级越权检查'],
  ['shield', '请求防护', 'IP/账户限频、人机验证'],
  ['memory', '内存', 'TEE 加密内存 · 阅后即焚'],
  ['history_edu', '审计', '操作变更日志全程留痕'],
]
</script>

<template>
  <MarketingShell>
    <main class="legal-page">
      <header class="legal-hero">
        <div class="container pricing-hero-inner">
          <div class="legal-hero-meta">
            <span class="legal-ref">REF.GL-LEGAL-PRIVACY</span>
            <span class="legal-update">最后更新 · 2026-07-01</span>
          </div>
          <div class="gold-rule"></div>
          <p class="eyebrow">PRIVACY POLICY</p>
          <h1>隐私政策</h1>
          <p class="lead">本政策说明句龙·照胆如何收集、使用、存储和保护您的个人信息。请您在使用前仔细阅读，并随时回顾本页面以获知最新版本。</p>
          <div class="legal-stamps">
            <span class="legal-stamp">PIPL 合规</span>
            <span class="legal-stamp">数据安全法</span>
            <span class="legal-stamp">网络安全法</span>
            <span class="legal-stamp">GB/T 35273</span>
          </div>
        </div>
      </header>

      <nav class="legal-toc container" aria-label="目录">
        <div class="legal-toc-title">目录 / CONTENTS</div>
        <ol>
          <li v-for="(t, i) in toc" :key="t[0]">
            <a :href="`#${t[0]}`"><span class="legal-toc-num">{{ String(i + 1).padStart(2, '0') }}</span>{{ t[1] }}</a>
          </li>
        </ol>
      </nav>

      <article class="legal-article container">
        <section id="scope" class="legal-section">
          <div class="legal-section-tag">§ 01</div>
          <h2>适用范围与法律依据</h2>
          <p>本政策适用于句龙·照胆（域名 goulong-ai.cn 及子域名，下称"本服务"）向您提供的全部产品功能。我们严格遵守中华人民共和国相关法律法规，包括但不限于：</p>
          <div class="legal-law-grid">
            <div v-for="l in laws" :key="l.name" class="legal-law-card">
              <span class="material-symbols-outlined legal-law-icon">{{ l.icon }}</span>
              <h3>{{ l.name }}</h3>
              <p>{{ l.desc }}</p>
            </div>
          </div>
        </section>

        <section id="collect" class="legal-section">
          <div class="legal-section-tag">§ 02</div>
          <h2>数据收集清单</h2>
          <h3 class="legal-sub">2.1 您主动提供与自动收集的数据</h3>
          <div class="legal-table-wrap">
            <table class="legal-table">
              <thead>
                <tr><th>数据类别</th><th>具体字段</th><th>用途</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in collectData" :key="r[0]">
                  <td>{{ r[0] }}</td><td>{{ r[1] }}</td><td>{{ r[2] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <h3 class="legal-sub">2.2 前端本地存储</h3>
          <div class="legal-storage-grid">
            <div v-for="s in localStore" :key="s.name" class="legal-storage-card">
              <h4>{{ s.name }}</h4>
              <ul>
                <li v-for="it in s.items" :key="it">{{ it }}</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="third-party" class="legal-section">
          <div class="legal-section-tag">§ 03</div>
          <h2>第三方服务商</h2>
          <p>为提供完整服务，我们委托以下第三方处理您的数据。委托处理严格限定在提供服务所必需的最小范围内。</p>
          <div class="legal-vendor-grid">
            <article v-for="v in vendors" :key="v.ref" class="legal-vendor-card" :class="{ outbound: v.outbound }">
              <span class="corner corner-tl"></span>
              <span class="corner corner-br"></span>
              <span class="legal-vendor-ref">{{ v.ref }}</span>
              <h3>{{ v.name }}</h3>
              <div class="legal-vendor-tags">
                <span v-for="t in v.tags" :key="t" class="legal-vendor-tag" :class="{ 'tag-outbound': v.outbound }">{{ t }}</span>
              </div>
              <p>{{ v.desc }}</p>
            </article>
          </div>
        </section>

        <section id="usage" class="legal-section">
          <div class="legal-section-tag">§ 04</div>
          <h2>数据使用目的与法律依据</h2>
          <div class="legal-table-wrap">
            <table class="legal-table">
              <thead>
                <tr><th>使用目的</th><th>涉及数据</th><th>法律依据</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in usageRows" :key="r[0]">
                  <td>{{ r[0] }}</td><td>{{ r[1] }}</td><td>{{ r[2] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="doc" class="legal-section">
          <div class="legal-section-tag">§ 05</div>
          <h2>上传文档处理方式</h2>
          <p>您上传的材料包（合同、报价、申请等文档）是审查的核心对象。处理方式由您自主选择：</p>
          <div class="legal-doc-grid">
            <div class="legal-doc-card">
              <span class="material-symbols-outlined">local_fire_department</span>
              <h4>审查后即焚</h4>
              <p>任务完成后物理删除文档原文，仅保留审查结论与证据定位，绝不落盘留痕。</p>
            </div>
            <div class="legal-doc-card">
              <span class="material-symbols-outlined">save</span>
              <h4>保留备查</h4>
              <p>文档保留在阿里云 OSS，您可随时查看、下载，或手动执行「物理销毁案卷」。</p>
            </div>
          </div>
        </section>

        <section id="retention" class="legal-section">
          <div class="legal-section-tag">§ 06</div>
          <h2>数据保留期限</h2>
          <div class="legal-retention-grid">
            <div v-for="r in retention" :key="r.title" class="legal-retention-card">
              <div class="legal-retention-period">{{ r.period }}</div>
              <h4>{{ r.title }}</h4>
              <p>{{ r.desc }}</p>
            </div>
          </div>
          <p class="legal-note">账号注销流程：设置 → 账户 → 提交注销申请 → 30 天冷静期（可恢复）→ 注销后 90 天内完成全部数据物理删除。支付记录按税务要求保留 3 年（不含个人信息明文）。</p>
        </section>

        <section id="rights" class="legal-section">
          <div class="legal-section-tag">§ 07</div>
          <h2>您的权利</h2>
          <p>依据 PIPL 第四章，您对个人信息享有以下权利：</p>
          <div class="legal-rights-grid">
            <div v-for="r in rights" :key="r[1]" class="legal-right">
              <span class="material-symbols-outlined">{{ r[0] }}</span>
              <h4>{{ r[1] }}</h4>
              <p>{{ r[2] }}</p>
            </div>
          </div>
        </section>

        <section id="security" class="legal-section">
          <div class="legal-section-tag">§ 08</div>
          <h2>安全措施</h2>
          <div class="legal-security-grid">
            <div v-for="s in security" :key="s[1]" class="legal-security-cell">
              <span class="material-symbols-outlined">{{ s[0] }}</span>
              <h4>{{ s[1] }}</h4>
              <p>{{ s[2] }}</p>
            </div>
          </div>
        </section>

        <section id="minor" class="legal-section">
          <div class="legal-section-tag">§ 09</div>
          <h2>儿童保护</h2>
          <p>句龙·照胆面向企业业务经办人员，<strong>不面向 14 周岁以下儿童</strong>。注册时需确认年满 18 周岁。如发现儿童误注册，监护人可联系我们申请删除账户。</p>
        </section>

        <section id="update" class="legal-section">
          <div class="legal-section-tag">§ 10</div>
          <h2>政策更新</h2>
          <ul class="legal-list">
            <li>重大变更（新增数据收集、新增第三方、改变数据用途）：提前 <strong>30 天</strong>通过站内通知与邮件告知您。</li>
            <li>若您不同意变更内容，可选择注销账号并要求删除全部数据。</li>
            <li>每次更新均会更新页面顶部的"最后更新"日期。</li>
          </ul>
        </section>

        <section id="contact" class="legal-section legal-section-cta">
          <div class="legal-section-tag">§ 11</div>
          <h2>联系方式</h2>
          <p>如您对本政策或个人信息处理有任何疑问、投诉或请求，请通过以下方式联系我们：</p>
          <a href="mailto:business@goulong-ai.cn" class="legal-contact-card">
            <span class="material-symbols-outlined">mail</span>
            <span>business@goulong-ai.cn</span>
          </a>
        </section>
      </article>

      <div class="legal-back container">
        <a href="/about" class="legal-back-link">
          <span class="material-symbols-outlined">arrow_back</span>
          返回关于我们
        </a>
      </div>
    </main>
  </MarketingShell>
</template>

<style scoped>
.legal-page {
  padding-bottom: 72px;
}

.legal-hero {
  padding: 96px 0 48px;
  text-align: center;
}

.legal-hero-meta {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.legal-ref,
.legal-update {
  color: var(--gold);
  font: 500 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-update {
  color: var(--muted);
}

.legal-hero h1 {
  margin: 12px 0;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(2.4rem, 5vw, 3.6rem);
}

.legal-stamps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.legal-stamp {
  padding: 6px 12px;
  border: 1px solid color-mix(in srgb, var(--gold) 30%, transparent);
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
}

.legal-toc {
  max-width: 880px;
  margin: 0 auto 48px;
  padding: 28px 32px;
  border: 1px solid color-mix(in srgb, var(--gold) 22%, transparent);
  background: linear-gradient(180deg, color-mix(in srgb, var(--surface) 92%, transparent), color-mix(in srgb, var(--bg) 92%, transparent));
}

.legal-toc-title {
  margin-bottom: 16px;
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-toc ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 24px;
}

.legal-toc a {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.legal-toc a:hover {
  color: var(--gold);
}

.legal-toc-num {
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
}

.legal-article {
  max-width: 880px;
  margin: 0 auto;
}

.legal-section {
  position: relative;
  padding: 36px 0;
  border-top: 1px solid color-mix(in srgb, var(--gold) 16%, transparent);
}

.legal-section-tag {
  position: absolute;
  top: 36px;
  left: 0;
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.16em;
}

.legal-section h2 {
  margin: 0 0 18px;
  padding-left: 56px;
  color: var(--text);
  font-family: "Syne", "Noto Serif SC", serif;
  font-size: clamp(1.4rem, 2.4vw, 1.8rem);
}

.legal-section p {
  color: var(--muted);
  line-height: 1.85;
}

.legal-section p + p {
  margin-top: 12px;
}

.legal-sub {
  margin: 24px 0 14px;
  color: var(--text);
  font-family: "Hanken Grotesk", "Noto Sans SC", sans-serif;
  font-size: 18px;
  font-weight: 600;
}

.legal-section strong {
  color: var(--text);
}

.legal-law-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 20px;
}

.legal-law-card {
  position: relative;
  padding: 20px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-law-icon {
  color: var(--gold);
  font-size: 24px;
}

.legal-law-card h3 {
  margin: 10px 0 6px;
  color: var(--text);
  font-size: 16px;
}

.legal-law-card p {
  font-size: 13px;
  line-height: 1.6;
}

.legal-table-wrap {
  overflow-x: auto;
  margin: 16px 0;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
}

.legal-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
}

.legal-table th,
.legal-table td {
  padding: 14px 16px;
  border-bottom: 1px solid color-mix(in srgb, var(--gold) 14%, transparent);
  text-align: left;
  font-size: 14px;
}

.legal-table th {
  color: var(--gold);
  font: 600 12px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
  background: color-mix(in srgb, var(--surface) 90%, transparent);
}

.legal-table td {
  color: var(--muted);
}

.legal-table tbody tr:last-child td {
  border-bottom: 0;
}

.legal-storage-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.legal-storage-card {
  padding: 20px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-storage-card h4 {
  margin: 0 0 10px;
  color: var(--gold);
  font: 600 13px/1 "JetBrains Mono", monospace;
}

.legal-storage-card ul {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}

.legal-vendor-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin: 20px 0;
}

.legal-vendor-card {
  position: relative;
  padding: 24px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-vendor-card.outbound {
  border-color: color-mix(in srgb, var(--gold) 40%, transparent);
}

.legal-vendor-ref {
  display: block;
  margin-bottom: 10px;
  color: var(--gold);
  font: 600 11px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.14em;
}

.legal-vendor-card h3 {
  margin-bottom: 10px;
  color: var(--text);
  font-size: 17px;
}

.legal-vendor-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.legal-vendor-tag {
  padding: 4px 8px;
  border: 1px solid color-mix(in srgb, var(--gold) 24%, transparent);
  color: var(--muted);
  font: 500 10px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.06em;
}

.legal-vendor-tag.tag-outbound {
  color: var(--error, #ffb4ab);
  border-color: color-mix(in srgb, var(--error, #ffb4ab) 40%, transparent);
}

.legal-vendor-card p {
  font-size: 13px;
  line-height: 1.7;
}

.legal-callout {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid color-mix(in srgb, var(--gold) 24%, transparent);
  background: color-mix(in srgb, var(--gold-soft) 40%, transparent);
}

.legal-callout .material-symbols-outlined {
  color: var(--gold);
  font-size: 22px;
}

.legal-callout h4 {
  margin: 0 0 6px;
  color: var(--text);
  font-size: 14px;
}

.legal-callout p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.legal-doc-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 18px;
}

.legal-doc-card {
  padding: 22px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-doc-card .material-symbols-outlined {
  color: var(--gold);
  font-size: 28px;
  font-variation-settings: 'FILL' 1;
}

.legal-doc-card h4 {
  margin: 10px 0 8px;
  color: var(--text);
  font-size: 16px;
}

.legal-doc-card p {
  font-size: 13px;
  line-height: 1.7;
}

.legal-retention-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin: 18px 0;
}

.legal-retention-card {
  padding: 20px 16px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-retention-period {
  margin-bottom: 8px;
  color: var(--gold);
  font: 700 22px/1 "JetBrains Mono", monospace;
}

.legal-retention-card h4 {
  margin-bottom: 6px;
  color: var(--text);
  font-size: 14px;
}

.legal-retention-card p {
  font-size: 12px;
  line-height: 1.6;
}

.legal-note {
  margin-top: 16px;
  padding: 14px 16px;
  border-left: 2px solid var(--gold);
  background: color-mix(in srgb, var(--gold-soft) 30%, transparent);
  font-size: 13px;
  line-height: 1.7;
}

.legal-rights-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 18px;
}

.legal-right {
  padding: 18px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-right .material-symbols-outlined {
  color: var(--gold);
  font-size: 22px;
}

.legal-right h4 {
  margin: 8px 0 4px;
  color: var(--text);
  font-size: 14px;
}

.legal-right p {
  font-size: 12px;
  line-height: 1.5;
}

.legal-security-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-top: 18px;
}

.legal-security-cell {
  padding: 18px;
  border: 1px solid color-mix(in srgb, var(--gold) 18%, transparent);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
}

.legal-security-cell .material-symbols-outlined {
  color: var(--gold);
  font-size: 22px;
}

.legal-security-cell h4 {
  margin: 8px 0 4px;
  color: var(--text);
  font-size: 14px;
}

.legal-security-cell p {
  font-size: 12px;
  line-height: 1.6;
}

.legal-list {
  margin: 12px 0;
  padding-left: 20px;
  color: var(--muted);
  line-height: 2;
}

.legal-section-cta {
  text-align: center;
}

.legal-contact-card {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 24px;
  border: 1px solid var(--gold);
  color: var(--gold);
  text-decoration: none;
  font: 600 14px/1 "JetBrains Mono", monospace;
  letter-spacing: 0.08em;
  transition: background 0.2s;
}

.legal-contact-card:hover {
  background: color-mix(in srgb, var(--gold) 14%, transparent);
}

.legal-back {
  max-width: 880px;
  margin: 24px auto 0;
}

.legal-back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.legal-back-link:hover {
  color: var(--gold);
}

@media (max-width: 820px) {
  .legal-section-tag {
    position: static;
    margin-bottom: 8px;
  }

  .legal-section h2 {
    padding-left: 0;
  }

  .legal-toc ol,
  .legal-law-grid,
  .legal-storage-grid,
  .legal-vendor-grid,
  .legal-doc-grid {
    grid-template-columns: 1fr;
  }

  .legal-retention-grid,
  .legal-rights-grid,
  .legal-security-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .legal-retention-grid,
  .legal-rights-grid,
  .legal-security-grid {
    grid-template-columns: 1fr;
  }
}
</style>
