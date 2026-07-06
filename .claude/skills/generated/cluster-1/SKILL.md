---
name: cluster-1
description: "Skill for the Cluster_1 area of Goulong-Zhaodan. 4 symbols across 1 files."
---

# Cluster_1

4 symbols | 1 files | Cohesion: 67%

## When to Use

- Working with code in `CLI/`
- Understanding how requireApiKey, apiUrl, parseResponse work
- Modifying cluster_1-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `CLI/src/index.ts` | requireApiKey, apiUrl, parseResponse, requestJson |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `requireApiKey` | Function | `CLI/src/index.ts` | 21 |
| `apiUrl` | Function | `CLI/src/index.ts` | 28 |
| `parseResponse` | Function | `CLI/src/index.ts` | 32 |
| `requestJson` | Function | `CLI/src/index.ts` | 40 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → ZhaodanCliError` | cross_community | 5 |
| `Main → ApiUrl` | cross_community | 4 |
| `Main → ParseResponse` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Cluster_0 | 2 calls |

## How to Explore

1. `gitnexus_context({name: "requireApiKey"})` — see callers and callees
2. `gitnexus_query({query: "cluster_1"})` — find related execution flows
3. Read key files listed above for implementation details
