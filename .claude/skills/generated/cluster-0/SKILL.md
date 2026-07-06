---
name: cluster-0
description: "Skill for the Cluster_0 area of Goulong-Zhaodan. 11 symbols across 1 files."
---

# Cluster_0

11 symbols | 1 files | Cohesion: 91%

## When to Use

- Working with code in `CLI/`
- Understanding how ZhaodanCliError, usage, parseArgs work
- Modifying cluster_0-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `CLI/src/index.ts` | ZhaodanCliError, usage, parseArgs, getString, getNumber (+6) |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ZhaodanCliError` | Class | `CLI/src/index.ts` | 11 |
| `usage` | Function | `CLI/src/index.ts` | 55 |
| `parseArgs` | Function | `CLI/src/index.ts` | 76 |
| `getString` | Function | `CLI/src/index.ts` | 98 |
| `getNumber` | Function | `CLI/src/index.ts` | 109 |
| `scenario` | Function | `CLI/src/index.ts` | 122 |
| `readLocalFile` | Function | `CLI/src/index.ts` | 130 |
| `toArrayBuffer` | Function | `CLI/src/index.ts` | 141 |
| `run` | Function | `CLI/src/index.ts` | 145 |
| `printResult` | Function | `CLI/src/index.ts` | 226 |
| `main` | Function | `CLI/src/index.ts` | 245 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → ZhaodanCliError` | cross_community | 5 |
| `Main → ApiUrl` | cross_community | 4 |
| `Main → ParseResponse` | cross_community | 4 |
| `Main → Usage` | intra_community | 3 |
| `Scenario → ZhaodanCliError` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Cluster_1 | 1 calls |

## How to Explore

1. `gitnexus_context({name: "ZhaodanCliError"})` — see callers and callees
2. `gitnexus_query({query: "cluster_0"})` — find related execution flows
3. Read key files listed above for implementation details
