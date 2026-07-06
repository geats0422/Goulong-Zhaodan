---
name: cluster-103
description: "Skill for the Cluster_103 area of Goulong-Zhaodan. 4 symbols across 1 files."
---

# Cluster_103

4 symbols | 1 files | Cohesion: 75%

## When to Use

- Working with code in `backend/`
- Understanding how record_failure, get_wait_seconds, check work
- Modifying cluster_103-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/core/login_throttle.py` | _cleanup, record_failure, get_wait_seconds, check |

## Entry Points

Start here when exploring this area:

- **`record_failure`** (Method) — `backend/app/core/login_throttle.py:14`
- **`get_wait_seconds`** (Method) — `backend/app/core/login_throttle.py:18`
- **`check`** (Method) — `backend/app/core/login_throttle.py:30`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `record_failure` | Method | `backend/app/core/login_throttle.py` | 14 |
| `get_wait_seconds` | Method | `backend/app/core/login_throttle.py` | 18 |
| `check` | Method | `backend/app/core/login_throttle.py` | 30 |
| `_cleanup` | Method | `backend/app/core/login_throttle.py` | 10 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Login → _cleanup` | cross_community | 4 |

## How to Explore

1. `gitnexus_context({name: "record_failure"})` — see callers and callees
2. `gitnexus_query({query: "cluster_103"})` — find related execution flows
3. Read key files listed above for implementation details
