# Step 1 文档预览布局优化设计

## 目标
将体检台步骤弹窗的 Step 1 从“居中文件摘要卡片 + 小预览框”调整为“左侧大文档预览 + 右侧文件信息操作栏”，让用户在上传后能像打开只读文档一样查看解析后的文档内容。

## 用户场景
用户在首页点击“发起智能初审”并选择文件后，弹窗进入 Step 1。用户期望左侧主要区域直接用于查看文档内容，右侧只放文件名、大小、格式、识别类型和“确认并继续”操作。

## 技术方案
复用现有 `DocumentPreviewPane` 渲染解析后的 `parsed_content`，在 `InspectionReviewModal` 的 Step 1 中改为双栏布局：左侧文档预览，右侧 `InspectionFileSummary` 与操作按钮。`InspectionFileSummary` 只负责元信息展示，避免内部再嵌套小滚动预览。

## 接口设计
后端接口保持不变，继续返回 `file.parsed_content`。前端 `previewText` 优先使用 `parsed_content`。

## 错误处理
解析失败仍在 Step 1 显示错误状态。解析成功后即展示左侧预览；若没有解析内容，`DocumentPreviewPane` 显示空态。

## 测试策略
运行前端构建验证 Vue 模板和样式无错误。必要时手动验证上传文件后 Step 1 左侧区域是否占满主要预览空间。
