# 浅色主题重设（水墨青釉 + 赛博朋克点缀）实施计划

## 总览

本计划基于最新设计文档 `docs/designs/2026-07-24-light-theme-chinese-cyber-design.md`。实现目标是仅重设浅色主题为“宣纸白 + 釉里青 + 古铜金 + 玉青/朱砂状态色”，并把霓虹青严格限制在 hover、focus、active、selected、loading 等交互态；深色主题只同步字体令牌，不改变现有金棕配色。

实施采用“先固定静态契约 → 建立单一令牌源 → 分区迁移浅色覆盖 → 补齐交互/加载装饰 → 自动化与视觉回归”的顺序。无后端、API、数据模型、路由或主题状态逻辑变更，不新增依赖。

**代码勘查后的实施校正**：

1. Google Fonts 当前由 `frontend/src/style.css:1` 的 `@import` 加载，`frontend/src/main.js` 不含字体 URL。为延续现有加载方式，本计划更新 `style.css`，不在 `main.js` 注入 DOM 或重复加载字体。
2. `frontend/src/style.css` 目前存在三处浅色令牌/别名块（约第 27、738、2417 行），后定义会覆盖前定义；必须收敛到顶部唯一的 `html[data-theme="light"]` 令牌源。
3. `frontend/scripts/verify-routes.mjs` 仍硬编码旧值 `--bg: #f7f1e3`，当前 `npm run test:routes` 已失败。实施必须先把该断言改成新设计契约，不能把现有失败误判为新回归。
4. `frontend/scripts/design-token-baseline.json` 当前 `accepted` 为空。新原始色值应统一声明为 `--color-*` primitive，语义令牌只引用 `var(...)`；原则上不通过 baseline 白名单放行新硬编码色值。
5. 组件内存在 scoped 旧色样式，但批准范围不允许修改页面/组件。浅色覆盖继续放在 `style.css` 的全局覆盖层，并用足够明确的选择器处理 scoped 样式；若视觉验证证明无法可靠覆盖，应暂停并申请扩大设计范围，而不是静默修改 `*.vue`。

### 范围

- **修改** `frontend/src/style.css`
- **修改** `frontend/scripts/verify-routes.mjs`
- **修改** `frontend/scripts/design-token-baseline.json`（仅收紧策略说明，`accepted` 预期仍为空）
- **不修改** `frontend/src/main.js`、`frontend/src/theme.js`、`frontend/src/composables/useTheme.js`
- **不修改** `frontend/src/pages/*.vue`、`frontend/src/components/**/*.vue`
- **不修改** 后端、API、数据模型、数据库和部署配置

### 完成标准

- 浅色根令牌的 computed value 与设计文档调色板完全一致。
- 静态背景/卡片不出现网格、云纹、印章或常驻霓虹光；cyan 只在交互、选中和加载态出现。
- `DashboardPage`、`PricingPage`、`LoginPage`、`RegisterPage`、`MarketingHomePage`、`SettingsPage` 的浅色主题完成桌面与移动端回归。
- 深色主题除 `--font-display`/`--font-body` 字体栈外，现有颜色 computed value 不变。
- `npm run test:theme`、`npm run test:routes`、`npm run design:check`、`npm run build` 全部通过，浏览器 console 无 CSS/资源错误。

## 前置准备

- [x] 已读取最新设计：`docs/designs/2026-07-24-light-theme-chinese-cyber-design.md`。
- [x] 用户已要求基于该设计进入实施规划，视为设计已批准。
- [x] 已确认 `npm run test:theme` 当前通过。
- [x] 已确认 `npm run design:check` 当前通过。
- [x] 已记录 `npm run test:routes` 当前因旧浅色断言失败：`Global styles must define the DESIGN.md-inspired light theme`。
- [ ] 实施前运行 `cd frontend && npm run build`，确认生产构建基线；若失败，先记录为前置阻塞。
- [ ] 实施前分别保存浅色/深色六个关键页面的基线截图，供最终回归对比；截图不提交仓库。
- [ ] 准备可访问 `/dashboard`、`/settings` 的本地测试账号或既有认证态。
- [ ] 保留现有无关工作区变更，不覆盖 `.opencode/state/openwolf-lite/anatomy-lite.json` 和设计文档。
- [ ] 若执行中被迫修改任何 JS/Vue 函数、类或方法，先按 `AGENTS.md` 对目标符号运行 GitNexus upstream impact；HIGH/CRITICAL 必须先告警并取得确认。

## 任务列表

### 任务 1: 将旧浅色断言改为新设计契约（红） (~4 min)

- **描述**: 在现有路由契约脚本中删除 `--bg: #f7f1e3` 旧断言，改为数据驱动的浅色主题契约：检查 6 个基础色、釉里青/古铜/玉青/霓虹青、4 个状态色、3 个字体令牌、Noto Serif/Sans 字体 URL、语义令牌以及关键交互/加载选择器。增加旧金棕浅色 primitive 和 `Imperial Circuitry` 注释不得继续存在的断言。
- **文件**:
  - 修改 `frontend/scripts/verify-routes.mjs`
- **测试**: 在 `frontend/` 执行 `npm run test:routes`。
- **验证**: 脚本不再因 `#f7f1e3` 失败，而是明确报告缺少新青釉令牌或交互选择器；确认测试对当前旧 CSS 为红。
- **依赖**: 无

### 任务 2: 更新字体加载 URL 与全局字体令牌 (~4 min)

- **描述**: 更新 `style.css:1` 的 Google Fonts `@import`，加入 `Noto Serif SC` 与 `Noto Sans SC` 的 400/500/600/700 字重，并保留 Material Symbols、JetBrains Mono 及现有正文回退所需字体。将 `:root` 的 `--font-display`、`--font-body`、`--font-mono` 精确改为设计中的字体栈；不改深色颜色令牌，不修改 `main.js`。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check`。
- **验证**: CSS 中只存在一次 Google Fonts 导入；URL 同时含 Noto Serif SC/Noto Sans SC 四档字重；字体声明通过 token 表达，`design:check` 仍通过。
- **依赖**: 任务 1

### 任务 3: 建立唯一浅色 primitive 与语义令牌源 (~5 min)

- **描述**: 重写顶部 `html[data-theme="light"]`：以 `--color-*` 声明设计给定的基础、强调、cyber 和状态原始色，再建立 `--bg`/`--surface`/`--surface-2`/`--text`/`--muted`/`--line`/`--gold` 兼容别名，以及 `--page-bg`、`--card-bg`、`--divider-bg`、`--card-border`、`--text-primary`、`--text-muted`、`--text-link`、`--text-accent`、`--primary-bg`、`--primary-fg`、`--primary-hover`、`--secondary-border`、`--focus-ring`、`--hover-glow`、`--loading-bar` 等语义令牌。删除约第 738、2417 行重复变量块，将 `color-scheme: light` 合并到唯一根块；保留 `[data-theme="dark"] { color-scheme: dark; }`。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check`；用文本检查确认精确的 `html[data-theme="light"] {` 令牌块只有一处。
- **验证**: 六个基础色分别为 `#f5f1e8/#ffffff/#eef0eb/#1c1f1d/#5b6168/#d4d6cf`，主色/hover/金/玉分别为 `#1f5f5b/#2d8a85/#b08847/#6b8e7f`，cyan 为 `#00d9c4`；所有非 `--color-*` 令牌均通过 `var(...)` 映射。
- **依赖**: 任务 2

### 任务 4: 清理浅色静态背景与纹理 (~4 min)

- **描述**: 将浅色 `body/#app`、`.dashboard-page`、`.knowledge-page`、`.marketing-shell`、`.settings-page`、`.history-page`、`.inspection-page`、登录/注册画布的背景改为纯色或极轻的 surface 线性渐变。删除浅色常驻 radial cyan、网格线和暖金纹理；对 `.grid-pattern` 明确禁用背景图/显示，确保静态界面没有云纹、网格或赛博光晕。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check`。
- **验证**: 浅色基础容器仅引用 `--page-bg`/`--card-bg`/`--divider-bg`；静态背景规则不再引用 `--cyber-cyan`、`--cyber-glow` 或网格 `background-image`。
- **依赖**: 任务 3

### 任务 5: 统一共享文字、边框、按钮、输入与焦点态 (~5 min)

- **描述**: 重映射浅色共享标题、正文、弱化文本、链接、导航、卡片边框、输入框和弹层到语义令牌。主按钮默认使用釉里青 + 白字，次按钮默认使用淡青线；hover/active 才切换浅釉里青并显示 1px cyan 描边/微光。为链接、按钮、输入、select、textarea 和菜单项补统一 `:focus-visible` 焦点环，避免只依赖 hover。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check`；键盘 Tab 检查一个按钮与一个输入框的焦点环。
- **验证**: 默认态无 cyan 光晕；hover/active/focus 可见但不遮挡文字；主按钮文字对比清晰，disabled 状态不误触发霓虹效果。
- **依赖**: 任务 4

### 任务 6: 迁移 Dashboard 与知识库浅色覆盖 (~5 min)

- **描述**: 将 `.dashboard-nav`、`.dashboard-brand`、`.dashboard-links`、`.dropzone-card`、`.glass-card`、`.asset-card`、`.upload-button`、`.status-chip`、通知/账户/主题菜单和知识库标题装饰从旧金棕硬编码迁移到新语义令牌。静态标题装饰使用古铜金，卡片 hover/菜单 active 才使用 cyan 描边和微光。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check && npm run build`。
- **验证**: `/dashboard` 与 `/knowledge-base` 浅色下卡片为白/青灰、文字为墨色；hover 前无 cyan，hover 后出现青釉 + 微弱霓虹；既有布局和点击区域不变。
- **依赖**: 任务 5

### 任务 7: 迁移历史与体检工作台浅色覆盖 (~5 min)

- **描述**: 将 `.archive-*`、`.history-*`、`.document-*`、`.diagnostic-*`、`.issue-*`、`.record-item`、`.engine-preview`、`.citation-box` 等规则迁移到 surface/text/line/status 令牌。错误与高风险使用朱砂，正常/完成使用玉青，提示信息使用釉里青，警告使用古铜金；保留文档高亮语义但移除旧红绿现代色和静态 cyan 光。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check && npm run build`。
- **验证**: 历史表格奇偶行、销毁态、体检问题卡、引用框和文档标记均可读；`verify-routes.mjs` 要求的历史/体检浅色选择器仍全部存在。
- **依赖**: 任务 6（同一 CSS 文件串行，避免覆盖冲突）

### 任务 8: 迁移统计与设置页浅色覆盖 (~5 min)

- **描述**: 将 `.stat-card`、`.analytics-panel`、`.quota-ring`、`.risk-grid`、`.settings-*`、`.model-card`、`.plan-card`、`.apikey-*`、`.switch-*`、账单额度条和设置弹窗迁移到新令牌。selected/active 使用釉里青边框，成功消息用玉青，错误消息用朱砂，额度预警用古铜金；移除旧金棕 rgba 与现代亮绿色硬编码。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check && npm run build`。
- **验证**: `/statistics` 和 `/settings` 默认、selected、success、warning、error 状态颜色符合设计；表单值、placeholder、禁用项均保持可读。
- **依赖**: 任务 7

### 任务 9: 迁移登录与注册页浅色覆盖 (~5 min)

- **描述**: 更新 `html[data-theme="light"] .login-page/.register-page` 覆盖：画布/品牌面板改宣纸白与浅青灰，标题用墨色和展示字体，链接/主按钮用釉里青，分隔线/标题短线用古铜金，错误提示用朱砂；输入 focus、短信按钮、密码按钮、主题按钮 hover 才出现 cyan 交互点缀。保持表单结构、校验和主题切换逻辑不变。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check && npm run build`。
- **验证**: `/login`、`/register` 的默认/聚焦/错误/disabled/hover 五种状态可辨；不修改任何 Vue 逻辑或模板。
- **依赖**: 任务 8

### 任务 10: 迁移营销首页与定价等公开页浅色覆盖 (~5 min)

- **描述**: 更新 `.pricing-*`、`.restored-card`、`.future-plan-card`、`.battle-card`、`.case-*`、`.security-*`、`.solution-*`、`.vault-*` 等浅色覆盖。营销首页/定价卡默认只用纸白、青灰、墨色、古铜金；移除静态 radial cyan，featured/hover/active 时才允许 cyan 细描边或微光。同步 FAQ、价格、CTA 与标签文字对比度。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check && npm run build`。
- **验证**: `/`、`/pricing`、`/cases`、`/security`、`/solution` 的静态卡片无常驻霓虹，hover/active 反馈一致；营销内容与布局不变。
- **依赖**: 任务 9

### 任务 11: 补齐电路边角、状态色与扫描线加载态 (~5 min)

- **描述**: 在浅色交互覆盖层中补齐三类特殊装饰：① active/selected 卡片左上角使用内联 SVG mask 的 2–3px 电路边角，仅应用于选中/激活态；② `.progress-bar-fill`、`.quota-bar-fill` 使用青釉渐变并增加右侧扫描线动画；③ loading spinner/进度信息使用釉里青 + cyan 微光。新增独立命名的 keyframes，避免与组件中的 `spin` 冲突，并在 `prefers-reduced-motion: reduce` 下关闭扫描动画。
- **文件**:
  - 修改 `frontend/src/style.css`
- **测试**: `cd frontend && npm run test:routes && npm run design:check`。
- **验证**: 新主题静态契约转绿；电路边角只在 active/selected 出现；进度条变化仍响应现有 inline width；减少动态效果设置下扫描线停止。
- **依赖**: 任务 10

### 任务 12: 收紧设计令牌 baseline (~3 min)

- **描述**: 更新 baseline 的策略说明，明确“原始色只允许 `--color-*`，语义令牌必须引用 primitive”；保持 `accepted: []`。若 checker 报出本计划新增硬编码，不加入例外，而是回到 `style.css` 抽取 primitive/alias；只有无法用 token 表达且有书面理由时才允许精确白名单。
- **文件**:
  - 修改 `frontend/scripts/design-token-baseline.json`
  - 必要时修正 `frontend/src/style.css`
- **测试**: `cd frontend && npm run design:check`。
- **验证**: `design:check passed`，baseline 无宽泛正则或新硬编码例外，JSON 可解析。
- **依赖**: 任务 11

### 任务 13: 运行前端自动化与生产构建回归 (~5 min)

- **描述**: 依次运行主题逻辑、路由/样式契约、设计令牌检查和 Vite 生产构建，逐项记录命令与结果。项目当前没有 `lint`、`typecheck`、ESLint 或 vue-tsc 脚本，本轮不新增依赖；以现有 `design:check` + `build` 作为 CSS/构建门禁，并明确记录该工具链缺口，避免虚假声称 lint/typecheck 已执行。
- **文件**: 无（仅验证；若失败只修复本计划涉及的三个文件）
- **测试**:
  - `cd frontend && npm run test:theme`
  - `cd frontend && npm run test:routes`
  - `cd frontend && npm run design:check`
  - `cd frontend && npm run build`
- **验证**: 四条命令退出码均为 0；构建产物无 CSS 解析警告或重复字体导入警告。
- **依赖**: 任务 12

### 任务 14: 浅色视觉验收批次 A（工作台/设置/定价） (~5 min)

- **描述**: 启动前端并切换 light，在 1440×900 检查 `/dashboard`、`/settings`、`/pricing`；分别检查默认、hover、focus、selected、loading/status 状态，读取根元素 computed style 核对关键令牌。保存临时截图用于对比，不提交仓库。
- **文件**: 无（仅浏览器验证）
- **测试**: 浏览器交互 + console 检查。
- **验证**: 三页无旧金棕大面积背景、无静态霓虹/纹理；釉里青按钮、古铜装饰、传统状态色和扫描线均符合设计；console 无 CSS/字体错误。
- **依赖**: 任务 13

### 任务 15: 浅色视觉验收批次 B（首页/登录/注册） (~5 min)

- **描述**: 在 1440×900 检查 `/`、`/login`、`/register`；覆盖主 CTA、营销卡、表单 focus、错误提示、disabled 和主题切换。确认展示标题为中文衬线、正文为中文无衬线、数字/代码保持等宽。
- **文件**: 无（仅浏览器验证）
- **测试**: 浏览器交互 + Network/console 检查 Noto Serif SC、Noto Sans SC 请求。
- **验证**: 三页视觉一致，字体有 fallback 时布局不跳变，Google Fonts 请求失败时仍可用系统中文字体正常显示。
- **依赖**: 任务 13；可与任务 14 并行

### 任务 16: 深色主题不变性回归 (~5 min)

- **描述**: 将六个关键页面切回 dark，核对现有金棕科技配色、卡片、状态和交互未被浅色选择器污染；通过 computed style 检查 `--color-bg/#0e0e0e`、`--color-surface/#171717`、`--color-primary/#e9c349` 等深色 primitive 未改变，仅字体令牌变化。
- **文件**: 无（仅浏览器验证）
- **测试**: dark/light 来回切换两次并刷新，检查持久化和 system 模式。
- **验证**: 深色截图与基线除字体外无可见配色差异；`npm run test:theme` 再次通过。
- **依赖**: 任务 14、任务 15

### 任务 17: 移动端、键盘与降级验收 (~5 min)

- **描述**: 在 390×844 复查首页、登录、Dashboard 和设置页；用键盘遍历主要交互，检查 focus-ring、文本对比、横向溢出和 reduced-motion。清空/禁用字体缓存一次，确认 fallback 栈可用；检查浏览器 console 无 CSS 错误。
- **文件**: 无（仅浏览器验证）
- **测试**: 移动视口、键盘 Tab/Enter、`prefers-reduced-motion: reduce`、字体请求失败模拟。
- **验证**: 无横向滚动和文字裁切；焦点始终可见；扫描线在 reduced-motion 下停止；关键文本满足正常阅读对比度。
- **依赖**: 任务 16

### 任务 18: 最终范围与影响复核 (~4 min)

- **描述**: 检查最终 diff，确认变更仅覆盖计划中的 CSS、静态契约和 baseline；搜索旧浅色 palette/注释残留；运行 GitNexus 变更检测并记录受影响流程。不得把既有 `.opencode/state` 或未提交设计文档误纳入实现提交。
- **文件**: 无（仅验证）
- **测试**:
  - `git diff -- frontend/src/style.css frontend/scripts/verify-routes.mjs frontend/scripts/design-token-baseline.json`
  - `cd frontend && npm run test:theme && npm run test:routes && npm run design:check && npm run build`
  - `gitnexus_detect_changes(scope="all", repo="Goulong-Zhaodan")`
- **验证**: 无后端、Vue 组件、主题逻辑或 API 变更；所有自动化命令通过；GitNexus 影响仅为前端视觉/静态契约范围；工作区无意外文件。
- **依赖**: 任务 17

## 并行机会

- 任务 1（静态契约）与任务 2（字体）技术上涉及不同文件，但为保持红-绿证据，建议先完成任务 1 再执行任务 2。
- 任务 6–11 逻辑上按页面分区独立，但都修改 `frontend/src/style.css`，**不建议并行**，应串行执行以避免 CSS 顺序和合并冲突。
- 任务 14 与任务 15 可在自动化验证通过后由两个独立浏览器上下文并行执行。
- 任务 16 必须等待两批浅色截图完成，任务 18 必须最后执行。

## 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 三处浅色变量块发生级联覆盖，computed value 与源码顶部不一致 | 高 | 高 | 任务 3 收敛到唯一根块；自动契约 + computed style 双重核对 |
| Vue scoped 样式优先级高于全局浅色覆盖 | 中 | 高 | 使用带页面上下文的明确选择器；视觉逐状态验证；仍无法覆盖则暂停并申请扩范围 |
| 清理 1200+ 行浅色覆盖时遗漏旧金棕硬编码 | 高 | 中 | 按页面串行迁移；最终搜索旧 primitive/rgba；六页截图验收 |
| cyan 被用于静态背景，偏离“仅交互态” | 中 | 中 | 自动契约拒绝旧静态主题描述；静态/hover 前后截图对比；代码审查 cyber token 使用位置 |
| 新中文字体加载慢或 Google Fonts 不可达 | 中 | 中 | 保留完整本地中文 fallback；`display=swap`；Network 失败模拟检查布局 |
| 扫描线动画造成眩晕或耗电 | 低 | 中 | 仅 loading 时启用；使用轻量 transform；支持 `prefers-reduced-motion` |
| baseline 通过白名单掩盖新硬编码 | 低 | 中 | `accepted` 保持空；所有原始色放入 `--color-*`，语义层只用 `var(...)` |
| 深色主题被共享规则污染 | 低 | 高 | 所有新配色规则限定在 light；核对深色 primitive computed value 与基线截图 |
| 现有 `test:routes` 基线已失败导致回归归因错误 | 已发生 | 中 | 任务 1 先替换旧断言并保留明确红测试证据 |

## 测试策略

| 层级 | 内容 | 覆盖目标 |
|------|------|----------|
| 静态契约 | `npm run test:routes` | 精确 palette、字体 URL、语义令牌、关键 light 选择器、交互/加载装饰 |
| 主题逻辑回归 | `npm run test:theme` | light/dark/system 持久化与 data-theme 行为不变 |
| 设计门禁 | `npm run design:check` | 禁止新增非 token 色值和字体声明 |
| 构建验证 | `npm run build` | Vue/Vite/CSS 解析和生产打包 |
| 视觉验收 | 六个关键页面，1440×900 与 390×844 | 色彩、字体、布局、静态/交互状态一致性 |
| 可访问性 | 键盘焦点、对比度、reduced-motion、字体降级 | 可读、可操作、动画可降级 |
| 深色回归 | 六个关键页面 dark 截图 + computed tokens | 深色仅字体变化，颜色不回归 |
| 影响检查 | Git diff + GitNexus detect changes | 变更限制在批准的前端视觉范围 |

## 执行顺序建议

严格按任务 1→13 完成静态契约和 CSS 迁移，再并行执行任务 14/15 的浅色视觉验收，随后完成任务 16/17 的深色与移动端回归，最后用任务 18 收口范围和影响。若任一视觉任务要求修改 Vue 组件，先停下并更新设计/计划范围。

## 下一步

计划文档保存后，建议运行 `/execute 1`，从“将旧浅色断言改为新设计契约（红）”开始。
