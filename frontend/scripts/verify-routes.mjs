import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const checks = [
  ['src/router.js', 'router file'],
  ['src/pages/MarketingHomePage.vue', 'marketing home page'],
  ['src/pages/DashboardPage.vue', 'dashboard page'],
  ['src/pages/InspectionDeskPage.vue', 'inspection desk page'],
  ['src/pages/KnowledgeBasePage.vue', 'knowledge base page'],
  ['src/pages/HistoryPage.vue', 'history page'],
  ['src/pages/StatisticsPage.vue', 'statistics page'],
  ['src/pages/SettingsPage.vue', 'settings page'],
  ['src/components/app/AppTopNav.vue', 'app top navigation'],
  ['src/theme.js', 'theme utilities'],
  ['src/components/marketing/MarketingNavbar.vue', 'marketing navbar'],
  ['src/components/marketing/MarketingFooter.vue', 'marketing footer'],
]

const missing = checks.filter(([file]) => !existsSync(resolve(root, file)))

if (missing.length) {
  throw new Error(`Missing ${missing.map(([, label]) => label).join(', ')}`)
}

const router = readFileSync(resolve(root, 'src/router.js'), 'utf8')
const app = readFileSync(resolve(root, 'src/App.vue'), 'utf8')
const marketingHome = readFileSync(resolve(root, 'src/pages/MarketingHomePage.vue'), 'utf8')
const marketingNavbar = readFileSync(resolve(root, 'src/components/marketing/MarketingNavbar.vue'), 'utf8')
const dashboard = readFileSync(resolve(root, 'src/pages/DashboardPage.vue'), 'utf8')
const inspectionDesk = readFileSync(resolve(root, 'src/pages/InspectionDeskPage.vue'), 'utf8')
const knowledgeBase = readFileSync(resolve(root, 'src/pages/KnowledgeBasePage.vue'), 'utf8')
const history = readFileSync(resolve(root, 'src/pages/HistoryPage.vue'), 'utf8')
const statistics = readFileSync(resolve(root, 'src/pages/StatisticsPage.vue'), 'utf8')
const settings = readFileSync(resolve(root, 'src/pages/SettingsPage.vue'), 'utf8')
const appTopNav = readFileSync(resolve(root, 'src/components/app/AppTopNav.vue'), 'utf8')
const theme = readFileSync(resolve(root, 'src/theme.js'), 'utf8')
const staticLandingPages = ['pricing.html', 'solution.html', 'security.html', 'cases.html']
const staticLandingContent = staticLandingPages.map((file) => [
  file,
  readFileSync(resolve(root, file), 'utf8'),
])

if (!router.includes("path: '/'") || !router.includes("path: '/dashboard'") || !router.includes("path: '/inspection-desk'") || !router.includes("path: '/knowledge-base'") || !router.includes("path: '/history'") || !router.includes("path: '/statistics'") || !router.includes("path: '/settings'")) {
  throw new Error('Router must expose /, /dashboard, /inspection-desk, /knowledge-base, /history, /statistics, and /settings')
}

if (!router.includes('MarketingHomePage')) {
  throw new Error('Root route must render the Vue marketing home page')
}

if (!app.includes('<RouterView')) {
  throw new Error('App.vue must render RouterView')
}

if (!dashboard.includes('极速载入案卷') || !dashboard.includes('当前挂载标尺')) {
  throw new Error('Dashboard page must contain Stitch dashboard sections')
}

if (!dashboard.includes('AppTopNav') || dashboard.includes('<nav class="dashboard-nav"')) {
  throw new Error('Dashboard page must reuse AppTopNav instead of declaring its own top nav')
}

if (!inspectionDesk.includes('智能审查诊断书') || !inspectionDesk.includes('物理销毁案卷') || !inspectionDesk.includes('A区数据中心项目招标文件')) {
  throw new Error('Inspection desk page must restore the Stitch diagnostic terminal sections')
}

if (!inspectionDesk.includes('AppTopNav') || !router.includes("path: '/inspection-desk'")) {
  throw new Error('Inspection desk must remain available as the report detail route')
}

if (!knowledgeBase.includes('企业专属参考卷宗库') || !knowledgeBase.includes('上传新卷宗') || !knowledgeBase.includes('重命名') || !knowledgeBase.includes('删除')) {
  throw new Error('Knowledge base page must restore the Stitch asset management sections')
}

if (!knowledgeBase.includes('AppTopNav') || !appTopNav.includes('/knowledge-base') || !appTopNav.includes('知识库')) {
  throw new Error('Knowledge base page must use shared AppTopNav with a 知识库 link')
}

if (!appTopNav.includes("'dashboard' },\n  { label: '体检台', href: '/history'") || !appTopNav.includes("'inspection' },\n  { label: '知识库'") || !appTopNav.includes("'knowledge' },\n  { label: '数据统计', href: '/statistics'") || !appTopNav.includes("'statistics' },\n  { label: '设置'")) {
  throw new Error('AppTopNav order must be 靶场、体检台、知识库、数据统计、设置')
}

if (appTopNav.includes("{ label: '历史'")) {
  throw new Error('AppTopNav must rename 历史 to 数据统计')
}

if (!history.includes('审查档案库') || !history.includes('A区数据中心项目招标文件_v2.pdf') || !history.includes('案卷已物理销毁')) {
  throw new Error('History page must restore the Stitch archive table sections')
}

if (!history.includes('AppTopNav') || !appTopNav.includes('/history') || !appTopNav.includes('体检台')) {
  throw new Error('History page must be the 体检台 list entry and use shared AppTopNav')
}

if (!history.includes('active="inspection"') || !history.includes('/inspection-desk') || !history.includes('查看报告')) {
  throw new Error('History list must highlight 体检台 and link records to inspection details')
}

if (!statistics.includes('AppTopNav') || !statistics.includes('active="statistics"') || !statistics.includes('数据统计') || !statistics.includes('额度消耗') || !statistics.includes('上传文档数') || !statistics.includes('违禁词出现率') || !statistics.includes('体检趋势')) {
  throw new Error('Statistics page must show MVP metrics: 上传文档数、违禁词出现率、额度消耗 and trend')
}

if (appTopNav.includes('实验室')) {
  throw new Error('AppTopNav must not include the 实验室 navigation item')
}

if (!settings.includes('系统配置与权限矩阵') || !settings.includes('令鉴与配额') || !settings.includes('数据安全锁')) {
  throw new Error('Settings page must restore the Stitch system settings sections')
}

if (!settings.includes('AppTopNav') || !appTopNav.includes('/settings') || !appTopNav.includes('设置')) {
  throw new Error('Settings page must use shared AppTopNav with a 设置 link')
}

if (!appTopNav.includes('无待处理工作') || !appTopNav.includes('切换账号') || !appTopNav.includes('退出账号')) {
  throw new Error('AppTopNav must provide notification and account popovers')
}

if (!appTopNav.includes('toggleNotifications') || !appTopNav.includes('toggleAccountMenu') || !appTopNav.includes('goToSettings')) {
  throw new Error('AppTopNav icons must have notification, account, and settings actions')
}

if (!appTopNav.includes('themeMode') || !appTopNav.includes('toggleThemeMenu') || !appTopNav.includes('applyThemeMode')) {
  throw new Error('AppTopNav must provide a theme mode toggle')
}

if (!appTopNav.includes('深色') || !appTopNav.includes('浅色') || !appTopNav.includes('系统配置')) {
  throw new Error('Theme toggle must expose 深色、浅色、系统配置 options')
}

if (!theme.includes('localStorage') || !theme.includes('matchMedia') || !theme.includes('dataset.theme')) {
  throw new Error('Theme mode must persist preference, support system mode, and update document theme')
}

if (!appTopNav.includes('隐私协议') || !appTopNav.includes('服务条款')) {
  throw new Error('Account popover must include privacy and terms links')
}

if (!appTopNav.includes('notification-panel') || !appTopNav.includes('无待处理工作')) {
  throw new Error('AppTopNav notification icon must open a notification popover')
}

const style = readFileSync(resolve(root, 'src/style.css'), 'utf8')

if (!style.includes('[data-theme="light"]') || !style.includes('--bg: #f7f1e3') || !style.includes('浅色主题')) {
  throw new Error('Global styles must define the DESIGN.md-inspired light theme')
}

for (const selector of [
  '.archive-table tbody tr:nth-child(even):not(.destroyed)',
  '.archive-table .destroyed',
  '.history-footer',
  '.document-pane',
  '.diagnostic-pane',
  '.document-sheet',
  '.citation-box',
  '.record-item',
  '.engine-preview',
  '.binding-chip',
  '.binding-chip small',
  '.binding-chip.active small',
  '.stat-card',
  '.analytics-panel',
  '.quota-ring',
  '.risk-grid div',
]) {
  if (!style.includes(`[data-theme="light"] ${selector}`)) {
    throw new Error(`Light theme must override dark scoped selector: ${selector}`)
  }
}

if (!appTopNav.includes('account-menu') || !appTopNav.includes('切换账号') || !appTopNav.includes('退出账号') || !appTopNav.includes('隐私协议') || !appTopNav.includes('服务条款')) {
  throw new Error('AppTopNav avatar must open the account menu with required actions')
}

if (!marketingHome.includes('业务提交前审查 Agent') || !marketingHome.includes('客户案例') || !marketingHome.includes('版本与定价')) {
  throw new Error('Marketing home must combine positioning, cases, and pricing content')
}

if (!marketingNavbar.includes('句龙 · 照胆') || !marketingNavbar.includes('href="/"')) {
  throw new Error('Marketing brand must be 句龙 · 照胆 and link to /')
}

for (const legacyFile of [
  'src/pages/LandingPage.vue',
  'src/components/AppNavbar.vue',
  'src/components/AppSidebar.vue',
  'src/components/AppFooter.vue',
]) {
  if (existsSync(resolve(root, legacyFile))) {
    throw new Error(`Legacy system 1 file must be removed: ${legacyFile}`)
  }
}

for (const [file, content] of staticLandingContent) {
  if (!content.includes('句龙 · 照胆')) {
    throw new Error(`${file} must use product name 句龙 · 照胆`)
  }

  if (!content.includes('href="/"')) {
    throw new Error(`${file} brand/breadcrumb should link back to the Vue marketing home page at /`)
  }
}

console.log('Route contract verified')
