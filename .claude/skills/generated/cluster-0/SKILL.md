---
name: cluster-0
description: "Skill for the Cluster_0 area of Goulong-Zhaodan. 5 symbols across 1 files."
---

# Cluster_0

5 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `MCP/`
- Understanding how ZhaodanApiError, requireApiKey, apiUrl work
- Modifying cluster_0-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MCP/src/index.ts` | ZhaodanApiError, requireApiKey, apiUrl, parseResponse, requestJson |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ZhaodanApiError` | Class | `MCP/src/index.ts` | 14 |
| `requireApiKey` | Function | `MCP/src/index.ts` | 24 |
| `apiUrl` | Function | `MCP/src/index.ts` | 33 |
| `parseResponse` | Function | `MCP/src/index.ts` | 37 |
| `requestJson` | Function | `MCP/src/index.ts` | 59 |

## How to Explore

1. `gitnexus_context({name: "ZhaodanApiError"})` — see callers and callees
2. `gitnexus_query({query: "cluster_0"})` — find related execution flows
3. Read key files listed above for implementation details
