---
name: v1
description: "Skill for the V1 area of Goulong-Zhaodan. 116 symbols across 23 files."
---

# V1

116 symbols | 23 files | Cohesion: 76%

## When to Use

- Working with code in `backend/`
- Understanding how agent_parse, parse_inspection_file, validate_file_magic work
- Modifying v1-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/api/v1/inspection.py` | _validate_inspection_filename, _document_type_score, _detect_document_type, _inspection_file_format, _clean_inspection_markdown (+26) |
| `backend/app/api/v1/settings.py` | _current_user_id, _taboo_response, update_knowledge_document_setting, create_taboo_word, update_taboo_word (+18) |
| `backend/app/api/v1/knowledge.py` | _safe_path_segment, _get_or_create_subcategory, _build_display_name, upload_and_ingest, _current_user_id (+7) |
| `backend/app/api/v1/agent.py` | agent_parse, _job_response, create_inspect_job, create_parse_job, _record_list_item (+4) |
| `backend/app/core/auth.py` | create_access_token, create_refresh_token, decode_token, store_refresh_token, is_refresh_token_revoked (+4) |
| `backend/app/api/v1/auth.py` | _set_refresh_cookie, register, login, refresh, validate_password_strength (+1) |
| `backend/tests/test_infrastructure.py` | test_validate_file_type_valid, test_validate_file_type_invalid, test_validate_application_scenario_valid, test_validate_application_scenario_invalid |
| `backend/app/services/inspection_runner.py` | inspection_record_to_history_dict, append_history_record, create_pending_inspection_record |
| `backend/tests/test_agent_worker_tasks.py` | test_run_parse_creates_pending_record_with_text_payload, test_run_parse_raises_on_missing_text |
| `backend/app/core/constants.py` | validate_file_type, validate_application_scenario |

## Entry Points

Start here when exploring this area:

- **`agent_parse`** (Function) — `backend/app/api/v1/agent.py:187`
- **`parse_inspection_file`** (Function) — `backend/app/api/v1/inspection.py:495`
- **`validate_file_magic`** (Function) — `backend/app/core/file_magic.py:18`
- **`inspection_record_to_history_dict`** (Function) — `backend/app/services/inspection_runner.py:60`
- **`append_history_record`** (Function) — `backend/app/services/inspection_runner.py:76`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `TabooWordCreateRequest` | Class | `backend/app/api/v1/settings.py` | 187 |
| `TabooWordUpdateRequest` | Class | `backend/app/api/v1/settings.py` | 217 |
| `ApiKeyResponse` | Class | `backend/app/api/v1/settings.py` | 536 |
| `CreateApiKeyResponse` | Class | `backend/app/api/v1/settings.py` | 551 |
| `agent_parse` | Function | `backend/app/api/v1/agent.py` | 187 |
| `parse_inspection_file` | Function | `backend/app/api/v1/inspection.py` | 495 |
| `validate_file_magic` | Function | `backend/app/core/file_magic.py` | 18 |
| `inspection_record_to_history_dict` | Function | `backend/app/services/inspection_runner.py` | 60 |
| `append_history_record` | Function | `backend/app/services/inspection_runner.py` | 76 |
| `create_pending_inspection_record` | Function | `backend/app/services/inspection_runner.py` | 82 |
| `test_run_parse_creates_pending_record_with_text_payload` | Function | `backend/tests/test_agent_worker_tasks.py` | 246 |
| `test_run_parse_raises_on_missing_text` | Function | `backend/tests/test_agent_worker_tasks.py` | 283 |
| `register` | Function | `backend/app/api/v1/auth.py` | 90 |
| `login` | Function | `backend/app/api/v1/auth.py` | 155 |
| `refresh` | Function | `backend/app/api/v1/auth.py` | 202 |
| `create_access_token` | Function | `backend/app/core/auth.py` | 19 |
| `create_refresh_token` | Function | `backend/app/core/auth.py` | 24 |
| `decode_token` | Function | `backend/app/core/auth.py` | 32 |
| `store_refresh_token` | Function | `backend/app/core/auth.py` | 48 |
| `is_refresh_token_revoked` | Function | `backend/app/core/auth.py` | 55 |

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
| `_run_parse → _sector_chain` | cross_community | 7 |
| `_run_parse → _readable_score` | cross_community | 7 |
| `_run_parse → _read_mini_stream` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 16 calls |
| Services | 4 calls |
| Cluster_84 | 2 calls |

## How to Explore

1. `gitnexus_context({name: "agent_parse"})` — see callers and callees
2. `gitnexus_query({query: "v1"})` — find related execution flows
3. Read key files listed above for implementation details
