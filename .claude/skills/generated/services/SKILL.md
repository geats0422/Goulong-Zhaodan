---
name: services
description: "Skill for the Services area of Goulong-Zhaodan. 93 symbols across 22 files."
---

# Services

93 symbols | 22 files | Cohesion: 79%

## When to Use

- Working with code in `backend/`
- Understanding how getSettingsOverview, updatePassword, updateKnowledgeDocument work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/services/markdown_converter.py` | __init__, _sector_offset, _read_sector, _read_fat, _sector_chain (+10) |
| `frontend/src/services/settingsApi.js` | parseResponse, getSettingsOverview, updatePassword, updateKnowledgeDocument, createTabooWord (+7) |
| `frontend/src/pages/SettingsPage.vue` | loadSettings, loadApiKeys, submitChangePassword, confirmAction2, submitCreateApiKey (+4) |
| `frontend/src/services/inspectionApi.js` | parseResponse, parseInspectionFile, inspectParsedSession, burnInspectionRecord, stripExtension (+3) |
| `backend/app/services/page_indexer.py` | _parse_with_pageindex, _run_pageindex_md_to_tree, _convert_tree_list_to_nodes, _walk_tree, _fallback_parse (+3) |
| `frontend/src/composables/useAuth.js` | clearAuthState, getAuthHeaders, fetchWithAuth, refreshToken, logout |
| `backend/app/services/agent_job_service.py` | update_job_status, mark_job_running, mark_job_succeeded, mark_job_failed, enqueue_job |
| `frontend/src/pages/HistoryPage.vue` | burnRecordContent, exportRecord, exportReviewReport, viewRecord, reviewPendingRecord |
| `backend/app/services/inspection_runner.py` | merge_unique_words, load_user_taboo_words, allowed_regulation_refs, sanitize_inspection_result_refs, execute_inspection |
| `backend/tests/test_agent_job_service.py` | test_update_job_status, test_mark_job_running, test_mark_job_succeeded, test_mark_job_failed |

## Entry Points

Start here when exploring this area:

- **`getSettingsOverview`** (Function) — `frontend/src/services/settingsApi.js:16`
- **`updatePassword`** (Function) — `frontend/src/services/settingsApi.js:28`
- **`updateKnowledgeDocument`** (Function) — `frontend/src/services/settingsApi.js:36`
- **`createTabooWord`** (Function) — `frontend/src/services/settingsApi.js:44`
- **`updateTabooWord`** (Function) — `frontend/src/services/settingsApi.js:52`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `WorkerSettings` | Class | `backend/app/workers/config.py` | 6 |
| `getSettingsOverview` | Function | `frontend/src/services/settingsApi.js` | 16 |
| `updatePassword` | Function | `frontend/src/services/settingsApi.js` | 28 |
| `updateKnowledgeDocument` | Function | `frontend/src/services/settingsApi.js` | 36 |
| `createTabooWord` | Function | `frontend/src/services/settingsApi.js` | 44 |
| `updateTabooWord` | Function | `frontend/src/services/settingsApi.js` | 52 |
| `deleteTabooWord` | Function | `frontend/src/services/settingsApi.js` | 60 |
| `listApiKeys` | Function | `frontend/src/services/settingsApi.js` | 66 |
| `createApiKey` | Function | `frontend/src/services/settingsApi.js` | 70 |
| `getApiKeySecret` | Function | `frontend/src/services/settingsApi.js` | 78 |
| `updateApiKey` | Function | `frontend/src/services/settingsApi.js` | 82 |
| `revokeApiKey` | Function | `frontend/src/services/settingsApi.js` | 90 |
| `toggleDocument` | Function | `frontend/src/components/inspection/KnowledgeTogglePanel.vue` | 64 |
| `loadSettings` | Function | `frontend/src/pages/SettingsPage.vue` | 83 |
| `loadApiKeys` | Function | `frontend/src/pages/SettingsPage.vue` | 106 |
| `submitChangePassword` | Function | `frontend/src/pages/SettingsPage.vue` | 168 |
| `confirmAction2` | Function | `frontend/src/pages/SettingsPage.vue` | 271 |
| `submitCreateApiKey` | Function | `frontend/src/pages/SettingsPage.vue` | 318 |
| `toggleDocument` | Function | `frontend/src/pages/SettingsPage.vue` | 345 |
| `resetTabooForm` | Function | `frontend/src/pages/SettingsPage.vue` | 362 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Agent_parse → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _readable_score` | cross_community | 8 |
| `_run_parse → _sector_offset` | cross_community | 8 |
| `_read_inspection_upload_text → _sector_offset` | cross_community | 8 |
| `Agent_parse → _read_mini_stream` | cross_community | 7 |
| `Parse_inspection_file → _read_mini_stream` | cross_community | 7 |
| `Ingest_document_content → _sector_offset` | cross_community | 7 |
| `_run_parse → _sector_chain` | cross_community | 7 |
| `_run_parse → _readable_score` | cross_community | 7 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 7 calls |
| Pages | 1 calls |
| Agents | 1 calls |
| V1 | 1 calls |

## How to Explore

1. `gitnexus_context({name: "getSettingsOverview"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
