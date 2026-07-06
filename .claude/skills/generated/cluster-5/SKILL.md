---
name: cluster-5
description: "Skill for the Cluster_5 area of Goulong-Zhaodan. 5 symbols across 1 files."
---

# Cluster_5

5 symbols | 1 files | Cohesion: 89%

## When to Use

- Working with code in `MCP/`
- Understanding how ZhaodanApiError, getApiKey, apiUrl work
- Modifying cluster_5-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MCP/src/shared.ts` | ZhaodanApiError, getApiKey, apiUrl, parseResponse, requestJson |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ZhaodanApiError` | Class | `MCP/src/shared.ts` | 22 |
| `getApiKey` | Function | `MCP/src/shared.ts` | 32 |
| `apiUrl` | Function | `MCP/src/shared.ts` | 42 |
| `parseResponse` | Function | `MCP/src/shared.ts` | 46 |
| `requestJson` | Function | `MCP/src/shared.ts` | 68 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `RegisterAllTools → GetApiKey` | cross_community | 3 |
| `RegisterAllTools → ApiUrl` | cross_community | 3 |
| `RegisterAllTools → ParseResponse` | cross_community | 3 |
| `RegisterAllTools → ZhaodanApiError` | cross_community | 3 |

## How to Explore

1. `gitnexus_context({name: "ZhaodanApiError"})` — see callers and callees
2. `gitnexus_query({query: "cluster_5"})` — find related execution flows
3. Read key files listed above for implementation details
