# 摩擦日志 (Friction Log)

> 跨会话摩擦事件登记。每次 /insights 自动汇总。

## 2026-07-11

### 支付回调 405 → nginx 代理规则遗漏
- **严重度**: 🟡 中
- **事件**: 照胆 `/payment/native` 返回 405；nginx `location` 未覆盖 `/payment/` `/subscription/`
- **触发**: 新增前端 API 路由但未同步 nginx 转发规则
- **解决**: nginx conf 补 `/payment/` `/subscription/` 转发
- **预防**: 新增 API 路由时必须同时检查 nginx 实际文件 + 仓库模板两处

### Pydantic datetime 序列化 500
- **严重度**: 🟡 中
- **事件**: `PaymentOrderListItem` 声明 `str | None` 但 ORM 返回 `datetime`，导致 `/payment/orders` 500
- **触发**: 后端修复 commit 后只重建 nginx 未重建 zhaodan-backend
- **解决**: `str | None` → `datetime | None`；重建后端容器
- **预防**: 修改后端代码后必须重建对应后端镜像，不能只重建 nginx

### nginx /settings/ 劫持 SPA 路由
- **严重度**: 🟡 中
- **事件**: `location /settings/` 同时拦截页面 URL 和 API 路径，导致强刷 404
- **触发**: 前缀匹配未区分 SPA 页面 vs API 转发
- **解决**: 加 `location = /settings/` 精确匹配优先走 SPA fallback
- **预防**: 设计 nginx 代理规则时区分精确匹配与前缀匹配

### AI bash 工具环境混淆
- **严重度**: 🔴 高
- **事件**: AI 在沙盒 bash 执行 `git push`，用户 Tabby pull 不到提交
- **触发**: AI 误认为 bash 工具能操作用户服务器
- **解决**: 明确 bash 工具运行在沙盒，与用户 Tabby 是独立环境
- **预防**: 所有服务器操作只给文字版命令，让用户自己在 Tabby 执行

### 二维码白块（CDN 依赖）
- **严重度**: 🟡 中
- **事件**: 照胆 PaymentModal 二维码显示白块
- **触发**: 运行时 CDN 加载 qrcodejs 失败
- **解决**: 改为内置 `qrcode` npm 包，`QRCode.toDataURL()` 生成
- **预防**: 前端不依赖运行时 CDN 加载关键功能库

## 摩擦事件模板

```markdown
### [简短标题]
- **严重度**: 🔴/🟡/🟢
- **事件**: [发生了什么]
- **触发**: [根本原因]
- **解决**: [如何修复]
- **预防**: [如何避免再次发生]
- **状态**: [已解决/进行中/待观察]
```
