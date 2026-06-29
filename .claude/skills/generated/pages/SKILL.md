---
name: pages
description: "Skill for the Pages area of Goulong-Zhaodan. 18 symbols across 6 files."
---

# Pages

18 symbols | 6 files | Cohesion: 74%

## When to Use

- Working with code in `frontend/`
- Understanding how fetchInspectionRecords, deleteInspectionRecord, loadRecords work
- Modifying pages-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/pages/SettingsPage.vue` | saveIdentity, toggleBurnAfterRead, selectModel, confirmUpgrade |
| `frontend/src/pages/DashboardPage.vue` | riskText, riskTone, loadRecentRecords, handleModalClose |
| `frontend/src/pages/KnowledgeBasePage.vue` | mapDocumentStatus, getIcon, fetchAllData, submitUpload |
| `frontend/src/pages/HistoryPage.vue` | loadRecords, goToPage, removeRecord |
| `frontend/src/services/inspectionApi.js` | fetchInspectionRecords, deleteInspectionRecord |
| `frontend/src/services/settingsApi.js` | updateProfile |

## Entry Points

Start here when exploring this area:

- **`fetchInspectionRecords`** (Function) — `frontend/src/services/inspectionApi.js:48`
- **`deleteInspectionRecord`** (Function) — `frontend/src/services/inspectionApi.js:58`
- **`loadRecords`** (Function) — `frontend/src/pages/HistoryPage.vue:44`
- **`goToPage`** (Function) — `frontend/src/pages/HistoryPage.vue:63`
- **`removeRecord`** (Function) — `frontend/src/pages/HistoryPage.vue:92`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `fetchInspectionRecords` | Function | `frontend/src/services/inspectionApi.js` | 48 |
| `deleteInspectionRecord` | Function | `frontend/src/services/inspectionApi.js` | 58 |
| `loadRecords` | Function | `frontend/src/pages/HistoryPage.vue` | 44 |
| `goToPage` | Function | `frontend/src/pages/HistoryPage.vue` | 63 |
| `removeRecord` | Function | `frontend/src/pages/HistoryPage.vue` | 92 |
| `updateProfile` | Function | `frontend/src/services/settingsApi.js` | 20 |
| `saveIdentity` | Function | `frontend/src/pages/SettingsPage.vue` | 127 |
| `toggleBurnAfterRead` | Function | `frontend/src/pages/SettingsPage.vue` | 190 |
| `selectModel` | Function | `frontend/src/pages/SettingsPage.vue` | 204 |
| `confirmUpgrade` | Function | `frontend/src/pages/SettingsPage.vue` | 230 |
| `riskText` | Function | `frontend/src/pages/DashboardPage.vue` | 17 |
| `riskTone` | Function | `frontend/src/pages/DashboardPage.vue` | 25 |
| `loadRecentRecords` | Function | `frontend/src/pages/DashboardPage.vue` | 29 |
| `handleModalClose` | Function | `frontend/src/pages/DashboardPage.vue` | 50 |
| `mapDocumentStatus` | Function | `frontend/src/pages/KnowledgeBasePage.vue` | 27 |
| `getIcon` | Function | `frontend/src/pages/KnowledgeBasePage.vue` | 35 |
| `fetchAllData` | Function | `frontend/src/pages/KnowledgeBasePage.vue` | 45 |
| `submitUpload` | Function | `frontend/src/pages/KnowledgeBasePage.vue` | 98 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `ReviewPendingRecord → GetAuthHeaders` | cross_community | 5 |
| `ReviewPendingRecord → RefreshToken` | cross_community | 5 |
| `ReviewPendingRecord → ClearAuthState` | cross_community | 5 |
| `RemoveRecord → GetAuthHeaders` | cross_community | 5 |
| `RemoveRecord → RefreshToken` | cross_community | 5 |
| `RemoveRecord → ClearAuthState` | cross_community | 5 |
| `HandleModalClose → GetAuthHeaders` | cross_community | 5 |
| `HandleModalClose → RefreshToken` | cross_community | 5 |
| `HandleModalClose → ClearAuthState` | cross_community | 5 |
| `GoToPage → GetAuthHeaders` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 8 calls |

## How to Explore

1. `gitnexus_context({name: "fetchInspectionRecords"})` — see callers and callees
2. `gitnexus_query({query: "pages"})` — find related execution flows
3. Read key files listed above for implementation details
