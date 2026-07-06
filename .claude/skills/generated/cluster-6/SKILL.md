---
name: cluster-6
description: "Skill for the Cluster_6 area of Goulong-Zhaodan. 6 symbols across 1 files."
---

# Cluster_6

6 symbols | 1 files | Cohesion: 91%

## When to Use

- Working with code in `MCP/`
- Understanding how registerAllTools work
- Modifying cluster_6-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `MCP/src/shared.ts` | formatError, toolResult, toolError, readLocalFile, toArrayBuffer (+1) |

## Entry Points

Start here when exploring this area:

- **`registerAllTools`** (Function) — `MCP/src/shared.ts:114`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `registerAllTools` | Function | `MCP/src/shared.ts` | 114 |
| `formatError` | Function | `MCP/src/shared.ts` | 54 |
| `toolResult` | Function | `MCP/src/shared.ts` | 82 |
| `toolError` | Function | `MCP/src/shared.ts` | 91 |
| `readLocalFile` | Function | `MCP/src/shared.ts` | 98 |
| `toArrayBuffer` | Function | `MCP/src/shared.ts` | 109 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `RegisterAllTools → GetApiKey` | cross_community | 3 |
| `RegisterAllTools → ApiUrl` | cross_community | 3 |
| `RegisterAllTools → ParseResponse` | cross_community | 3 |
| `RegisterAllTools → ZhaodanApiError` | cross_community | 3 |
| `RegisterAllTools → FormatError` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Cluster_5 | 1 calls |

## How to Explore

1. `gitnexus_context({name: "registerAllTools"})` — see callers and callees
2. `gitnexus_query({query: "cluster_6"})` — find related execution flows
3. Read key files listed above for implementation details
