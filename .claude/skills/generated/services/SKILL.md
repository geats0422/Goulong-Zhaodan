---
name: services
description: "Skill for the Services area of Goulong-Zhaodan. 189 symbols across 35 files."
---

# Services

189 symbols | 35 files | Cohesion: 77%

## When to Use

- Working with code in `backend/`
- Understanding how get_bucket, get_oss_key, is_oss_enabled work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/services/wechatpay_v2_client.py` | _xml_to_dict, apply_deduction, verify_callback_sign, parse_callback_xml, get_wechatpay_v2_client (+12) |
| `backend/app/services/email_service.py` | _load_template, _render, _wrap_email, _get_dm_client, _send_via_aliyun (+11) |
| `backend/app/services/wechatpay_client.py` | _generate_nonce, _sign, _build_authorization, _request, create_native_order (+10) |
| `backend/app/services/subscription_service.py` | _next_deduct_at, get_contract_by_code, handle_contract_callback, _parse_dt, _apply_subscription (+10) |
| `backend/app/services/markdown_converter.py` | __init__, _sector_offset, _read_sector, _read_fat, _sector_chain (+10) |
| `backend/app/services/sms_service.py` | generate_code, _rate_key, check_rate_limit, _get_aliyun_client, _send_via_aliyun (+8) |
| `backend/app/services/file_storage.py` | is_oss_enabled, _validate_storage_path, _local_path, ensure_storage_dir, save_file (+3) |
| `frontend/src/services/settingsApi.js` | parseResponse, getSettingsOverview, updatePassword, updateKnowledgeDocument, createTabooWord (+3) |
| `backend/app/services/payment_service.py` | _generate_out_trade_no, _client_ip_or_default, create_native_order, sync_order_status, handle_callback (+3) |
| `frontend/src/services/inspectionApi.js` | parseResponse, parseInspectionFile, inspectParsedSession, burnInspectionRecord, stripExtension (+3) |

## Entry Points

Start here when exploring this area:

- **`get_bucket`** (Function) — `backend/app/core/oss_client.py:16`
- **`get_oss_key`** (Function) — `backend/app/core/oss_client.py:42`
- **`is_oss_enabled`** (Function) — `backend/app/services/file_storage.py:15`
- **`ensure_storage_dir`** (Function) — `backend/app/services/file_storage.py:53`
- **`save_file`** (Function) — `backend/app/services/file_storage.py:62`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `WorkerSettings` | Class | `backend/app/workers/config.py` | 6 |
| `get_bucket` | Function | `backend/app/core/oss_client.py` | 16 |
| `get_oss_key` | Function | `backend/app/core/oss_client.py` | 42 |
| `is_oss_enabled` | Function | `backend/app/services/file_storage.py` | 15 |
| `ensure_storage_dir` | Function | `backend/app/services/file_storage.py` | 53 |
| `save_file` | Function | `backend/app/services/file_storage.py` | 62 |
| `read_file` | Function | `backend/app/services/file_storage.py` | 76 |
| `delete_file` | Function | `backend/app/services/file_storage.py` | 86 |
| `file_exists` | Function | `backend/app/services/file_storage.py` | 105 |
| `ingest_document_content` | Function | `backend/app/services/knowledge_ingestion.py` | 28 |
| `import_single_file` | Function | `backend/scripts/import_default_knowledge.py` | 81 |
| `test_ensure_storage_dir` | Function | `backend/tests/test_infrastructure.py` | 82 |
| `test_save_file` | Function | `backend/tests/test_infrastructure.py` | 89 |
| `getSettingsOverview` | Function | `frontend/src/services/settingsApi.js` | 16 |
| `updatePassword` | Function | `frontend/src/services/settingsApi.js` | 28 |
| `updateKnowledgeDocument` | Function | `frontend/src/services/settingsApi.js` | 36 |
| `createTabooWord` | Function | `frontend/src/services/settingsApi.js` | 44 |
| `updateTabooWord` | Function | `frontend/src/services/settingsApi.js` | 52 |
| `deleteTabooWord` | Function | `frontend/src/services/settingsApi.js` | 60 |
| `updateApiKey` | Function | `frontend/src/services/settingsApi.js` | 82 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Agent_parse → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _readable_score` | cross_community | 8 |
| `Agent_parse → _read_mini_stream` | cross_community | 7 |
| `Wechat_unified_callback → _generate_nonce` | cross_community | 7 |
| `Wechat_unified_callback → _sign` | cross_community | 7 |
| `Parse_inspection_file → _read_mini_stream` | cross_community | 7 |
| `_extract_inspection_text → _sector_offset` | cross_community | 7 |
| `Wechatpay_notify → _generate_nonce` | cross_community | 6 |
| `Wechatpay_notify → _sign` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Composables | 13 calls |
| Tests | 9 calls |
| V1 | 3 calls |
| Pages | 1 calls |
| Agents | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_bucket"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
