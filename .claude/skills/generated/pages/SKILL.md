---
name: pages
description: "Skill for the Pages area of Goulong-Zhaodan. 35 symbols across 9 files."
---

# Pages

35 symbols | 9 files | Cohesion: 76%

## When to Use

- Working with code in `frontend/`
- Understanding how listApiKeys, createApiKey, getApiKeySecret work
- Modifying pages-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/pages/SettingsPage.vue` | loadApiKeys, handleCopyClick, copyTextToClipboard, copyApiKey, confirmAction2 (+5) |
| `frontend/src/services/settingsApi.js` | listApiKeys, createApiKey, getApiKeySecret, revokeApiKey, updateProfile |
| `frontend/src/pages/DashboardPage.vue` | riskText, riskTone, loadRecentRecords, handleModalClose |
| `frontend/src/pages/KnowledgeBasePage.vue` | mapDocumentStatus, getIcon, fetchAllData, submitUpload |
| `frontend/src/pages/RegisterPage.vue` | startTimer, startSmsCountdown, startEmailCountdown |
| `frontend/src/pages/HistoryPage.vue` | loadRecords, goToPage, removeRecord |
| `frontend/src/composables/useAuth.js` | sendSmsCode, sendEmailCode |
| `frontend/src/pages/LoginPage.vue` | startCountdown, startSmsCountdown |
| `frontend/src/services/inspectionApi.js` | fetchInspectionRecords, deleteInspectionRecord |

## Entry Points

Start here when exploring this area:

- **`listApiKeys`** (Function) — `frontend/src/services/settingsApi.js:66`
- **`createApiKey`** (Function) — `frontend/src/services/settingsApi.js:70`
- **`getApiKeySecret`** (Function) — `frontend/src/services/settingsApi.js:78`
- **`revokeApiKey`** (Function) — `frontend/src/services/settingsApi.js:90`
- **`loadApiKeys`** (Function) — `frontend/src/pages/SettingsPage.vue:113`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `listApiKeys` | Function | `frontend/src/services/settingsApi.js` | 66 |
| `createApiKey` | Function | `frontend/src/services/settingsApi.js` | 70 |
| `getApiKeySecret` | Function | `frontend/src/services/settingsApi.js` | 78 |
| `revokeApiKey` | Function | `frontend/src/services/settingsApi.js` | 90 |
| `loadApiKeys` | Function | `frontend/src/pages/SettingsPage.vue` | 113 |
| `handleCopyClick` | Function | `frontend/src/pages/SettingsPage.vue` | 261 |
| `copyTextToClipboard` | Function | `frontend/src/pages/SettingsPage.vue` | 276 |
| `copyApiKey` | Function | `frontend/src/pages/SettingsPage.vue` | 299 |
| `confirmAction2` | Function | `frontend/src/pages/SettingsPage.vue` | 315 |
| `submitCreateApiKey` | Function | `frontend/src/pages/SettingsPage.vue` | 361 |
| `startCountdown` | Function | `frontend/src/pages/LoginPage.vue` | 42 |
| `startSmsCountdown` | Function | `frontend/src/pages/LoginPage.vue` | 57 |
| `startTimer` | Function | `frontend/src/pages/RegisterPage.vue` | 78 |
| `startSmsCountdown` | Function | `frontend/src/pages/RegisterPage.vue` | 97 |
| `startEmailCountdown` | Function | `frontend/src/pages/RegisterPage.vue` | 111 |
| `fetchInspectionRecords` | Function | `frontend/src/services/inspectionApi.js` | 48 |
| `deleteInspectionRecord` | Function | `frontend/src/services/inspectionApi.js` | 58 |
| `loadRecords` | Function | `frontend/src/pages/HistoryPage.vue` | 44 |
| `goToPage` | Function | `frontend/src/pages/HistoryPage.vue` | 63 |
| `removeRecord` | Function | `frontend/src/pages/HistoryPage.vue` | 92 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `HandleCopyClick → GetAuthHeaders` | cross_community | 5 |
| `HandleCopyClick → RefreshToken` | cross_community | 5 |
| `HandleCopyClick → ClearAuthState` | cross_community | 5 |
| `ConfirmAction2 → GetAuthHeaders` | cross_community | 5 |
| `ConfirmAction2 → RefreshToken` | cross_community | 5 |
| `ReviewPendingRecord → GetAuthHeaders` | cross_community | 5 |
| `ReviewPendingRecord → RefreshToken` | cross_community | 5 |
| `ReviewPendingRecord → ClearAuthState` | cross_community | 5 |
| `RemoveRecord → GetAuthHeaders` | cross_community | 5 |
| `RemoveRecord → RefreshToken` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Composables | 11 calls |
| Services | 7 calls |

## How to Explore

1. `gitnexus_context({name: "listApiKeys"})` — see callers and callees
2. `gitnexus_query({query: "pages"})` — find related execution flows
3. Read key files listed above for implementation details
