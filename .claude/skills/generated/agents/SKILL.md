---
name: agents
description: "Skill for the Agents area of Goulong-Zhaodan. 7 symbols across 2 files."
---

# Agents

7 symbols | 2 files | Cohesion: 83%

## When to Use

- Working with code in `backend/`
- Understanding how get_regulation_analyst, get_compliance_inspector, get_inspection_agent work
- Modifying agents-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/agents/__init__.py` | _make_model, get_regulation_analyst, get_compliance_inspector, get_inspection_agent, __getattr__ |
| `backend/app/agents/inspector.py` | _allowed_refs, run_inspection |

## Entry Points

Start here when exploring this area:

- **`get_regulation_analyst`** (Function) — `backend/app/agents/__init__.py:40`
- **`get_compliance_inspector`** (Function) — `backend/app/agents/__init__.py:58`
- **`get_inspection_agent`** (Function) — `backend/app/agents/__init__.py:75`
- **`run_inspection`** (Function) — `backend/app/agents/inspector.py:37`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_regulation_analyst` | Function | `backend/app/agents/__init__.py` | 40 |
| `get_compliance_inspector` | Function | `backend/app/agents/__init__.py` | 58 |
| `get_inspection_agent` | Function | `backend/app/agents/__init__.py` | 75 |
| `run_inspection` | Function | `backend/app/agents/inspector.py` | 37 |
| `_make_model` | Function | `backend/app/agents/__init__.py` | 24 |
| `__getattr__` | Function | `backend/app/agents/__init__.py` | 87 |
| `_allowed_refs` | Function | `backend/app/agents/inspector.py` | 16 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Agent_inspect → _make_model` | cross_community | 5 |
| `Agent_inspect → _prompt_char_budget` | cross_community | 5 |
| `Agent_inspect → Format_regulation_base_context` | cross_community | 5 |
| `Agent_inspect → _truncate_text` | cross_community | 5 |
| `Upload_and_inspect → _make_model` | cross_community | 5 |
| `Upload_and_inspect → _prompt_char_budget` | cross_community | 5 |
| `Upload_and_inspect → Format_regulation_base_context` | cross_community | 5 |
| `Upload_and_inspect → _truncate_text` | cross_community | 5 |
| `Inspect_session → _make_model` | cross_community | 5 |
| `Inspect_session → _prompt_char_budget` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Prompts | 3 calls |

## How to Explore

1. `gitnexus_context({name: "get_regulation_analyst"})` — see callers and callees
2. `gitnexus_query({query: "agents"})` — find related execution flows
3. Read key files listed above for implementation details
