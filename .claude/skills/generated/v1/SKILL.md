---
name: v1
description: "Skill for the V1 area of Goulong-Zhaodan. 122 symbols across 24 files."
---

# V1

122 symbols | 24 files | Cohesion: 72%

## When to Use

- Working with code in `backend/`
- Understanding how upload_and_ingest, validate_file_type, safe_path_segment work
- Modifying v1-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/api/v1/inspection.py` | _validate_inspection_filename, _inspection_file_format, _clean_inspection_markdown, _read_inspection_upload_text, _extract_inspection_text (+26) |
| `backend/app/api/v1/settings.py` | _current_user_id, _taboo_response, update_knowledge_document_setting, create_taboo_word, update_taboo_word (+18) |
| `backend/app/api/v1/knowledge.py` | _safe_path_segment, _get_or_create_subcategory, _build_display_name, upload_and_ingest, _current_user_id (+7) |
| `backend/app/api/v1/auth.py` | send_sms_code, send_email_code, register, refresh, _set_refresh_cookie (+6) |
| `backend/app/core/auth.py` | create_access_token, decode_token, is_refresh_token_revoked, get_current_user, create_refresh_token (+4) |
| `backend/app/api/v1/agent.py` | _job_response, create_inspect_job, create_parse_job, _record_list_item, _record_detail (+3) |
| `backend/tests/test_infrastructure.py` | test_validate_file_type_valid, test_validate_file_type_invalid, test_build_storage_path, test_build_storage_path_version |
| `backend/app/services/inspection_runner.py` | inspection_record_to_history_dict, append_history_record, create_pending_inspection_record |
| `backend/app/services/file_storage.py` | safe_path_segment, build_storage_path |
| `backend/tests/test_agent_worker_tasks.py` | test_run_parse_creates_pending_record_with_text_payload, test_run_parse_raises_on_missing_text |

## Entry Points

Start here when exploring this area:

- **`upload_and_ingest`** (Function) — `backend/app/api/v1/knowledge.py:275`
- **`validate_file_type`** (Function) — `backend/app/core/constants.py:29`
- **`safe_path_segment`** (Function) — `backend/app/services/file_storage.py:22`
- **`build_storage_path`** (Function) — `backend/app/services/file_storage.py:43`
- **`test_validate_file_type_valid`** (Function) — `backend/tests/test_infrastructure.py:58`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `TabooWordCreateRequest` | Class | `backend/app/api/v1/settings.py` | 187 |
| `TabooWordUpdateRequest` | Class | `backend/app/api/v1/settings.py` | 217 |
| `ApiKeyResponse` | Class | `backend/app/api/v1/settings.py` | 536 |
| `CreateApiKeyResponse` | Class | `backend/app/api/v1/settings.py` | 551 |
| `upload_and_ingest` | Function | `backend/app/api/v1/knowledge.py` | 275 |
| `validate_file_type` | Function | `backend/app/core/constants.py` | 29 |
| `safe_path_segment` | Function | `backend/app/services/file_storage.py` | 22 |
| `build_storage_path` | Function | `backend/app/services/file_storage.py` | 43 |
| `test_validate_file_type_valid` | Function | `backend/tests/test_infrastructure.py` | 58 |
| `test_validate_file_type_invalid` | Function | `backend/tests/test_infrastructure.py` | 67 |
| `test_build_storage_path` | Function | `backend/tests/test_infrastructure.py` | 72 |
| `test_build_storage_path_version` | Function | `backend/tests/test_infrastructure.py` | 77 |
| `upload_and_inspect` | Function | `backend/app/api/v1/inspection.py` | 462 |
| `validate_file_magic` | Function | `backend/app/core/file_magic.py` | 18 |
| `test_run_parse_creates_pending_record_with_text_payload` | Function | `backend/tests/test_agent_worker_tasks.py` | 246 |
| `test_run_parse_raises_on_missing_text` | Function | `backend/tests/test_agent_worker_tasks.py` | 283 |
| `update_knowledge_document_setting` | Function | `backend/app/api/v1/settings.py` | 431 |
| `create_taboo_word` | Function | `backend/app/api/v1/settings.py` | 464 |
| `update_taboo_word` | Function | `backend/app/api/v1/settings.py` | 482 |
| `delete_taboo_word` | Function | `backend/app/api/v1/settings.py` | 513 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Agent_parse → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _sector_chain` | cross_community | 8 |
| `Parse_inspection_file → _readable_score` | cross_community | 8 |
| `Agent_parse → _read_mini_stream` | cross_community | 7 |
| `Parse_inspection_file → _read_mini_stream` | cross_community | 7 |
| `_extract_inspection_text → _sector_offset` | cross_community | 7 |
| `Agent_parse → _convert_docx_to_text` | cross_community | 5 |
| `Upload_and_inspect → _convert_docx_to_text` | cross_community | 5 |
| `Upload_and_inspect → _make_model` | cross_community | 5 |
| `Upload_and_inspect → _prompt_char_budget` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 19 calls |
| Services | 4 calls |
| Cluster_103 | 2 calls |

## How to Explore

1. `gitnexus_context({name: "upload_and_ingest"})` — see callers and callees
2. `gitnexus_query({query: "v1"})` — find related execution flows
3. Read key files listed above for implementation details
