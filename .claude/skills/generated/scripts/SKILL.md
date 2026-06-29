---
name: scripts
description: "Skill for the Scripts area of Goulong-Zhaodan. 3 symbols across 1 files."
---

# Scripts

3 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `backend/`
- Understanding how compute_tree_hash, snapshot, verify work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/scripts/verify_auth_dep.py` | compute_tree_hash, snapshot, verify |

## Entry Points

Start here when exploring this area:

- **`compute_tree_hash`** (Function) — `backend/scripts/verify_auth_dep.py:11`
- **`snapshot`** (Function) — `backend/scripts/verify_auth_dep.py:26`
- **`verify`** (Function) — `backend/scripts/verify_auth_dep.py:32`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `compute_tree_hash` | Function | `backend/scripts/verify_auth_dep.py` | 11 |
| `snapshot` | Function | `backend/scripts/verify_auth_dep.py` | 26 |
| `verify` | Function | `backend/scripts/verify_auth_dep.py` | 32 |

## How to Explore

1. `gitnexus_context({name: "compute_tree_hash"})` — see callers and callees
2. `gitnexus_query({query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
