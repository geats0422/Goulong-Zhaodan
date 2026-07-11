/**
 * 照胆前端业务数据目录（套餐 / 模型 / 权限）
 * PricingPage、SettingsPage 共享的单一数据源。
 * 权限范围与后端 app/core/api_key_scopes.py 对齐。
 */

// 团队 / 企业版占位特性（PricingPage 用）
export const PLAN_CATALOG = {
  team: {
    features: ['多人共享工作区', '统一订阅与配额池', '成员权限分级', '审查记录留痕'],
  },
  enterprise: {
    features: ['私有化部署', '内网数据边界', '审计日志导出', '专属合规策略', 'SSO 单点登录'],
  },
}

// 算力补充包（SettingsPage 账单页；价格与 PricingPage addons 一致）
export const POWER_PACKS = [
  {
    key: 'test_0_1',
    ref: 'REF.PACK-TEST',
    name: '支付测试包',
    price: '¥0.01',
    unit: '',
    recommended: false,
    features: [
      { text: '1 万 Token', ok: true },
      { text: '仅用于支付链路测试', ok: true },
      { text: '支付后立即到账', ok: true },
      { text: '非正式生产套餐', ok: false },
    ],
  },
  {
    key: 'light',
    ref: 'REF.PACK-LIGHT',
    name: '轻量包',
    price: '¥5',
    unit: '',
    recommended: false,
    features: [
      { text: '100 万 Token', ok: true },
      { text: '永久有效', ok: true },
      { text: '多文件材料包体检', ok: true },
      { text: 'Pro 专属深度审查', ok: false },
    ],
  },
  {
    key: 'standard',
    ref: 'REF.PACK-STD',
    name: '标准包',
    price: '¥18',
    unit: '',
    recommended: true,
    features: [
      { text: '500 万 Token', ok: true },
      { text: '永久有效', ok: true },
      { text: '多文件材料包体检', ok: true },
      { text: '核心漏洞精准定位', ok: true },
    ],
  },
  {
    key: 'large',
    ref: 'REF.PACK-LARGE',
    name: '大额包',
    price: '¥58',
    unit: '',
    recommended: false,
    features: [
      { text: '2000 万 Token', ok: true },
      { text: '永久有效', ok: true },
      { text: '高频深度审查', ok: true },
      { text: '仅 Pro 用户可购', ok: true },
    ],
  },
]

// 订阅方案（SettingsPage 升级弹窗；key 与后端 ALLOWED_PLANS 对齐）
export const SUB_PLANS = [
  {
    key: 'pro_monthly',
    ref: 'REF.SUB-M',
    name: 'Pro 月度',
    price: '¥49',
    period: '/ 月',
    recommended: false,
    actionLabel: '订阅月度',
    features: ['200 万 Token 月度额度', '无限次多文件材料包体检', '核心漏洞精准定位', 'Markdown / PDF 报告导出'],
  },
  {
    key: 'pro_quarterly',
    ref: 'REF.SUB-Q',
    name: 'Pro 季度',
    price: '¥139',
    period: '/ 季',
    recommended: false,
    actionLabel: '订阅季度',
    features: ['600 万 Token 季度额度', '无限次多文件材料包体检', '核心漏洞精准定位', 'Markdown / PDF 报告导出'],
  },
  {
    key: 'pro_yearly',
    ref: 'REF.SUB-Y',
    name: 'Pro 年度',
    price: '¥499',
    period: '/ 年',
    recommended: true,
    actionLabel: '获取年度特符',
    features: [
      '2400 万 Token 年度额度',
      '无限次多文件材料包体检',
      '核心漏洞精准定位',
      'Markdown / PDF 报告导出',
      '优先队列与专属授权令',
    ],
  },
]

// AI 模型目录（profile.model_name 可选值；与后端 settings.py MODEL_CATALOG 对齐）
export const MODEL_CATALOG = [
  {
    model_name: 'deepseek-ai/deepseek-v4-pro',
    label: 'DeepSeek V4 Pro',
    tier: '高准确度 · 慢',
    context: '128K',
  },
  {
    model_name: 'deepseek-ai/deepseek-v4-flash',
    label: 'DeepSeek V4 Flash',
    tier: '快速响应',
    context: '64K',
  },
]

// API Key 权限范围（自定义模板用；与后端 AVAILABLE_SCOPES 对齐，不含 records:delete）
export const API_KEY_SCOPES = [
  { key: 'profile:read', label: '读取身份', description: '查看昵称、头像等基础信息' },
  { key: 'inspection:run', label: '发起体检', description: '触发 AI 材料包审查任务' },
  { key: 'inspection:read', label: '读取报告', description: '查看历史体检记录与结论' },
  { key: 'knowledge:read', label: '读取知识库', description: '查询知识文档与索引节点' },
  { key: 'knowledge:write', label: '写入知识库', description: '新增或更新知识文档' },
  { key: 'settings:write', label: '修改设置', description: '更新偏好与模型配置' },
]

// API Key 权限模板（与后端 SCOPE_TEMPLATES_META 对齐，附自定义项）
export const SCOPE_TEMPLATES = [
  { key: 'mcp_readonly', label: 'MCP 只读', description: '仅查询历史报告与知识库，不可体检' },
  { key: 'cli_review', label: 'CLI 审查', description: '查询 + AI 体检，适用于 CLI 工具' },
  { key: 'agent_full_access', label: 'Agent 完整协作', description: '面向 Agent，含读写与 AI 生成' },
  { key: 'advanced_custom', label: '自定义权限', description: '按需勾选细粒度权限' },
]
