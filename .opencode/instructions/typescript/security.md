---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# TypeScript/JavaScript 安全

> 此文件扩展自 [common/security.md](../common/security.md)，包含 TypeScript/JavaScript 特定内容。

## 密钥管理

```typescript
// 永远不要：硬编码密钥
const apiKey = "sk-proj-xxxxx"

// 始终使用：环境变量
const apiKey = process.env.OPENAI_API_KEY

if (!apiKey) {
  throw new Error('OPENAI_API_KEY 未配置')
}
```

## 智能体支持

- 请使用 **security-reviewer** skill 进行全面的安全审计
