---
name: composables
description: "Skill for the Composables area of Goulong-Zhaodan. 20 symbols across 6 files."
---

# Composables

20 symbols | 6 files | Cohesion: 67%

## When to Use

- Working with code in `frontend/`
- Understanding how listOrders, getCurrentSubscription, cancelSubscription work
- Modifying composables-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/composables/useAuth.js` | clearAuthState, getAuthHeaders, fetchWithAuth, refreshToken, logout (+6) |
| `frontend/src/services/paymentApi.js` | listOrders, getCurrentSubscription, cancelSubscription, listDeductions |
| `frontend/src/pages/LoginPage.vue` | handleSmsLogin, handlePasswordLogin |
| `frontend/src/pages/StatisticsPage.vue` | fetchStats |
| `frontend/src/pages/RegisterPage.vue` | handleRegister |
| `frontend/src/pages/PricingPage.vue` | handleBuy |

## Entry Points

Start here when exploring this area:

- **`listOrders`** (Function) — `frontend/src/services/paymentApi.js:28`
- **`getCurrentSubscription`** (Function) — `frontend/src/services/paymentApi.js:44`
- **`cancelSubscription`** (Function) — `frontend/src/services/paymentApi.js:50`
- **`listDeductions`** (Function) — `frontend/src/services/paymentApi.js:55`
- **`fetchStats`** (Function) — `frontend/src/pages/StatisticsPage.vue:47`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `listOrders` | Function | `frontend/src/services/paymentApi.js` | 28 |
| `getCurrentSubscription` | Function | `frontend/src/services/paymentApi.js` | 44 |
| `cancelSubscription` | Function | `frontend/src/services/paymentApi.js` | 50 |
| `listDeductions` | Function | `frontend/src/services/paymentApi.js` | 55 |
| `fetchStats` | Function | `frontend/src/pages/StatisticsPage.vue` | 47 |
| `handleSmsLogin` | Function | `frontend/src/pages/LoginPage.vue` | 71 |
| `handlePasswordLogin` | Function | `frontend/src/pages/LoginPage.vue` | 92 |
| `handleRegister` | Function | `frontend/src/pages/RegisterPage.vue` | 125 |
| `handleBuy` | Function | `frontend/src/pages/PricingPage.vue` | 41 |
| `clearAuthState` | Function | `frontend/src/composables/useAuth.js` | 8 |
| `getAuthHeaders` | Function | `frontend/src/composables/useAuth.js` | 26 |
| `fetchWithAuth` | Function | `frontend/src/composables/useAuth.js` | 31 |
| `refreshToken` | Function | `frontend/src/composables/useAuth.js` | 169 |
| `logout` | Function | `frontend/src/composables/useAuth.js` | 182 |
| `readError` | Function | `frontend/src/composables/useAuth.js` | 51 |
| `saveSession` | Function | `frontend/src/composables/useAuth.js` | 59 |
| `login` | Function | `frontend/src/composables/useAuth.js` | 66 |
| `loginByCode` | Function | `frontend/src/composables/useAuth.js` | 89 |
| `register` | Function | `frontend/src/composables/useAuth.js` | 141 |
| `isLoggedIn` | Function | `frontend/src/composables/useAuth.js` | 22 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `HandleCopyClick → GetAuthHeaders` | cross_community | 5 |
| `HandleCopyClick → RefreshToken` | cross_community | 5 |
| `HandleCopyClick → ClearAuthState` | cross_community | 5 |
| `InitOrder → GetAuthHeaders` | cross_community | 5 |
| `InitOrder → RefreshToken` | cross_community | 5 |
| `InitOrder → ClearAuthState` | cross_community | 5 |
| `ConfirmAction2 → GetAuthHeaders` | cross_community | 5 |
| `ConfirmAction2 → RefreshToken` | cross_community | 5 |
| `ReviewPendingRecord → GetAuthHeaders` | cross_community | 5 |
| `ReviewPendingRecord → RefreshToken` | cross_community | 5 |

## How to Explore

1. `gitnexus_context({name: "listOrders"})` — see callers and callees
2. `gitnexus_query({query: "composables"})` — find related execution flows
3. Read key files listed above for implementation details
