---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# TypeScript/JavaScript 模式

> 此文件扩展自 [common/patterns.md](../common/patterns.md)，包含 TypeScript/JavaScript 特定内容。

## API 响应格式

```typescript
interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  meta?: {
    total: number
    page: number
    limit: number
  }
}
```

## 自定义 Hook 模式

```typescript
export function useDebounce<T>(value: T, delay: number): T {
  // ...
}
```
