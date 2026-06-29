---
name: composables
description: "Skill for the Composables area of Goulong-Zhaodan. 5 symbols across 3 files."
---

# Composables

5 symbols | 3 files | Cohesion: 100%

## When to Use

- Working with code in `frontend/`
- Understanding how handlePasswordLogin, handleRegister work
- Modifying composables-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/composables/useAuth.js` | login, register, readError |
| `frontend/src/pages/LoginPage.vue` | handlePasswordLogin |
| `frontend/src/pages/RegisterPage.vue` | handleRegister |

## Entry Points

Start here when exploring this area:

- **`handlePasswordLogin`** (Function) — `frontend/src/pages/LoginPage.vue:59`
- **`handleRegister`** (Function) — `frontend/src/pages/RegisterPage.vue:76`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `handlePasswordLogin` | Function | `frontend/src/pages/LoginPage.vue` | 59 |
| `handleRegister` | Function | `frontend/src/pages/RegisterPage.vue` | 76 |
| `login` | Function | `frontend/src/composables/useAuth.js` | 51 |
| `register` | Function | `frontend/src/composables/useAuth.js` | 77 |
| `readError` | Function | `frontend/src/composables/useAuth.js` | 120 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `HandlePasswordLogin → ReadError` | intra_community | 3 |
| `HandleRegister → ReadError` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "handlePasswordLogin"})` — see callers and callees
2. `gitnexus_query({query: "composables"})` — find related execution flows
3. Read key files listed above for implementation details
