---
name: components
description: "Skill for the Components area of Goulong-Zhaodan. 9 symbols across 2 files."
---

# Components

9 symbols | 2 files | Cohesion: 84%

## When to Use

- Working with code in `frontend/`
- Understanding how createNativeOrder, getOrderStatus, createSubscription work
- Modifying components-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/components/PaymentModal.vue` | loadQrScript, renderQr, initOrder, startPolling, stopPolling |
| `frontend/src/services/paymentApi.js` | parseErr, createNativeOrder, getOrderStatus, createSubscription |

## Entry Points

Start here when exploring this area:

- **`createNativeOrder`** (Function) — `frontend/src/services/paymentApi.js:12`
- **`getOrderStatus`** (Function) — `frontend/src/services/paymentApi.js:22`
- **`createSubscription`** (Function) — `frontend/src/services/paymentApi.js:34`
- **`loadQrScript`** (Function) — `frontend/src/components/PaymentModal.vue:24`
- **`renderQr`** (Function) — `frontend/src/components/PaymentModal.vue:35`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `createNativeOrder` | Function | `frontend/src/services/paymentApi.js` | 12 |
| `getOrderStatus` | Function | `frontend/src/services/paymentApi.js` | 22 |
| `createSubscription` | Function | `frontend/src/services/paymentApi.js` | 34 |
| `loadQrScript` | Function | `frontend/src/components/PaymentModal.vue` | 24 |
| `renderQr` | Function | `frontend/src/components/PaymentModal.vue` | 35 |
| `initOrder` | Function | `frontend/src/components/PaymentModal.vue` | 47 |
| `startPolling` | Function | `frontend/src/components/PaymentModal.vue` | 65 |
| `stopPolling` | Function | `frontend/src/components/PaymentModal.vue` | 84 |
| `parseErr` | Function | `frontend/src/services/paymentApi.js` | 4 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `InitOrder → GetAuthHeaders` | cross_community | 5 |
| `InitOrder → RefreshToken` | cross_community | 5 |
| `InitOrder → ClearAuthState` | cross_community | 5 |
| `InitOrder → ParseErr` | intra_community | 3 |
| `InitOrder → StopPolling` | intra_community | 3 |
| `CreateSubscription → GetAuthHeaders` | cross_community | 3 |
| `CreateSubscription → RefreshToken` | cross_community | 3 |
| `CreateSubscription → ClearAuthState` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Composables | 3 calls |

## How to Explore

1. `gitnexus_context({name: "createNativeOrder"})` — see callers and callees
2. `gitnexus_query({query: "components"})` — find related execution flows
3. Read key files listed above for implementation details
