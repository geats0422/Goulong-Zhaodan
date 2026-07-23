# 浅色主题重设设计文档（水墨青釉 + 赛博朋克点缀）

## 目标

将照胆前端的浅色主题从当前的「金棕调」重构为「中国古风水墨青釉 + 赛博朋克点缀」风格。深色主题保持现状（金棕科技调），仅同步字体策略。

## 用户场景

- 用户在设置中切换到浅色主题 → 看到宣纸白底 + 釉里青强调 + 古铜金点缀 + 衬线标题的雅静界面
- 鼠标悬停按钮/卡片 → 出现青釉色 + 微弱霓虹青光晕（赛博朋克点缀）
- 状态高亮（成功/警告/错误/信息）使用传统色（玉青/古铜/朱砂/青釉）而非现代的红绿
- 加载进度条出现青釉填充 + 扫描线动画

## 技术方案

**仅重设浅色主题**（`html[data-theme="light"]` CSS 块）。深色主题仅同步字体策略。

字体策略（全局，深浅通用）：
- 大标题：`"Noto Serif SC", "Source Han Serif SC", "Songti SC", "SimSun", serif`
- 正文：`"Noto Sans SC", "Hanken Grotesk", "Noto Sans", sans-serif`
- 代码/数字：`"JetBrains Mono", monospace`

仅在交互态（hover / focus / active / loading）出现赛博朋克点缀。背景纯色/微渐变，无纹理/云纹/印章。

## 调色板

### 主调（古风水墨）
```
--bg            #f5f1e8   宣纸白偏米
--surface       #ffffff   卡片纯白
--surface-2     #eef0eb   浅青灰（分区背景）
--text          #1c1f1d   近黑墨
--text-muted    #5b6168   淡墨灰
--line          #d4d6cf   淡青线
```

### 强调色（釉里青/古铜/玉青）
```
--ink-primary   #1f5f5b   釉里青（主按钮/链接）
--ink-soft      #2d8a85   浅釉里青（hover）
--gold          #b08847   古铜金（点缀/分隔线/标题装饰）
--jade          #6b8e7f   玉青（次要点缀/成功）
```

### 赛博朋克点缀（仅交互态）
```
--cyber-cyan    #00d9c4   霓虹青（状态高光、hover 光晕）
--cyber-line    rgba(0, 217, 196, 0.32)  电纹描边
--cyber-glow    0 0 12px rgba(0, 217, 196, 0.28)
```

### 状态色（传统色，保持调性统一）
```
success:       #6b8e7f  玉青
warning:       #b08847  古铜金
error:         #a8453c  朱砂红（用现代描边处理）
info:          #1f5f5b  釉里青
```

## 语义令牌映射

| 语义令牌 | 浅色映射 | 用途 |
|---|---|---|
| `page-bg` | var(--bg) | 页面背景 |
| `card-bg` | var(--surface) | 卡片背景 |
| `divider-bg` | var(--surface-2) | 分区背景 |
| `card-border` | var(--line) | 卡片边框 |
| `text-primary` | var(--text) | 主要文字 |
| `text-muted` | var(--text-muted) | 次要文字 |
| `text-link` | var(--ink-primary) | 链接 |
| `text-accent` | var(--gold) | 强调/装饰文字 |
| `primary-bg` | var(--ink-primary) | 主按钮底色 |
| `primary-fg` | #ffffff | 主按钮文字 |
| `primary-hover` | var(--ink-soft) + var(--cyber-glow) | 主按钮 hover |
| `secondary-border` | var(--line) | 次按钮边框 |
| `secondary-hover` | var(--ink-soft) + var(--cyber-line) | 次按钮 hover |
| `focus-ring` | 0 0 0 2px var(--cyber-line) | 焦点环 |
| `hover-glow` | box-shadow: 0 0 12px var(--cyber-glow) | 卡片/按钮 hover 光晕 |
| `loading-bar` | 渐变青 + 扫描线 | 加载进度条 |

## 组件特殊装饰

- 卡片左上角：小型 SVG 电路边角（2-3px 宽），仅在卡片激活/选中态出现
- 进度条/能量条：青釉填充 + 右侧扫描线动画
- 主按钮 hover：青釉底 + 1px cyan 光晕描边
- 重要标题装饰：可选 underline 用 `--gold` 1px + 短横电路 motif

## 数据模型

无新数据结构。复用现有 `useTheme.js` + `theme.js` + `style.css` 变量系统。

唯一扩展：CSS 变量在 `:root` 块中新增：
- 字体变量 `--font-display` 改为 `"Noto Serif SC", ...`
- 浅色主题块（`html[data-theme="light"]`）新增青釉/赛博朋克令牌
- 现有金色令牌保留（深色用），但浅色用釉里青替代为主

## 接口设计

无新 API。组件代码继续引用语义令牌（`text-primary`、`primary-bg`），主题切换时原始令牌变化、语义令牌映射不变。

**Google Fonts 新增**：
```
?family=Noto+Serif+SC:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700
```

## 错误处理

无。纯样式重构，不影响逻辑。

## 测试策略

1. 视觉验证：手动切换 dark/light 主题，对比新旧视觉
2. 现有 `frontend/scripts/check-design-tokens.mjs` + `design-token-baseline.json` 继续生效
3. 关键页面回归：
   - DashboardPage（靶场）
   - PricingPage（定价）
   - LoginPage / RegisterPage
   - MarketingHomePage（首页）
   - SettingsPage（设置）
4. 浏览器 console 检查无 CSS 错误

## 改动范围

| 文件 | 改动 |
|---|---|
| `frontend/src/style.css` | 重设 `html[data-theme="light"]` 调色板；`:root` 字体变量改思源宋体；新增浅色语义令牌；保留深色 |
| `frontend/src/main.js` | Google Fonts URL 新增 Noto Serif SC + Noto Sans SC |
| `frontend/src/pages/*.vue` | 无需改动（消费语义令牌） |
| `frontend/scripts/design-token-baseline.json` | 接受新令牌基线 |

**无后端改动**。无 API 变更。无新组件。

## 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| 大量 `style.css` 改写容易引入回归 | 视觉对比检查 + 关键页面回归 |
| 衬线字体在长正文里可读性下降 | 衬线仅用于大标题/展示文案，正文保持 Noto Sans SC |
| 浅色传统色（朱砂）与现代警示习惯冲突 | 朱砂用于严重错误，warning/info 用古铜/青釉过渡，保留可读性 |
| 字体加载慢 | Google Fonts preload + font-display: swap（现状已有） |

## 范围确认

- ✅ 仅改浅色主题（深色仅同步字体）
- ✅ 字体策略全局统一（深浅都用同一套字体令牌）
- ✅ 背景无装饰图案（纯色/微渐变）
- ✅ 赛博朋克仅在交互态出现
- ✅ 状态色用传统色（玉青/古铜/朱砂/青釉）
- ✅ 范围：仅 `style.css` + `main.js` + `design-token-baseline.json`（约 3 个文件）
