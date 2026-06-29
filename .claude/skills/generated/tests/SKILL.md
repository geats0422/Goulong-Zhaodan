---
name: tests
description: "Skill for the Tests area of Goulong-Zhaodan. 302 symbols across 46 files."
---

# Tests

302 symbols | 46 files | Cohesion: 86%

## When to Use

- Working with code in `backend/`
- Understanding how register_user, create_agent_api_key, test_agent_me work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/tests/test_agent_api.py` | register_user, create_agent_api_key, test_agent_me, test_create_inspect_job, test_create_parse_job (+22) |
| `backend/tests/test_import_default_knowledge.py` | test_contract_keyword, test_bidding_keyword_bidding, test_bidding_keyword_government, test_contract_keyword_civil_code, test_bidding_keyword_evaluation (+16) |
| `backend/tests/test_settings_api.py` | register_and_auth, create_document, test_settings_overview_defaults, test_update_profile_is_user_scoped, test_update_password (+15) |
| `backend/tests/test_inspection_api.py` | register_and_auth, test_parse_returns_session_and_file_metadata, test_parse_detects_contract_document_type, test_parse_detects_bidding_document_type, test_parse_rejects_unsupported_format (+13) |
| `backend/tests/test_conversion_services.py` | test_returns_empty_for_empty_text, test_returns_nodes_for_markdown_with_headings, test_node_hierarchy_chapter_section_paragraph, test_parent_index_links_correctly, test_flat_text_without_headings (+13) |
| `backend/tests/test_data_masking.py` | test_mask_amount, test_mask_amount_yuan, test_mask_amount_billion, test_mask_phone, test_mask_id_card (+12) |
| `backend/tests/test_api_key_service.py` | test_create_api_key, test_create_api_key_with_template, test_create_api_key_custom, test_list_api_keys, test_list_api_keys_user_isolation (+10) |
| `backend/tests/test_api_key_settings_api.py` | register_and_auth, test_list_api_keys, test_list_api_keys_empty, test_get_api_key_secret_updates_last_viewed_at, test_get_api_key_secret_not_found (+10) |
| `backend/tests/test_knowledge_api.py` | _make_subcategory, _make_document, _result_scalar, _make_version, _make_node (+8) |
| `backend/tests/test_agent_worker_tasks.py` | _make_mock_session_ctx, test_inspect_task_success, test_inspect_task_failure, test_parse_task_success, test_parse_task_failure (+6) |

## Entry Points

Start here when exploring this area:

- **`register_user`** (Function) — `backend/tests/test_agent_api.py:60`
- **`create_agent_api_key`** (Function) — `backend/tests/test_agent_api.py:70`
- **`test_agent_me`** (Function) — `backend/tests/test_agent_api.py:91`
- **`test_create_inspect_job`** (Function) — `backend/tests/test_agent_api.py:115`
- **`test_create_parse_job`** (Function) — `backend/tests/test_agent_api.py:130`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `register_user` | Function | `backend/tests/test_agent_api.py` | 60 |
| `create_agent_api_key` | Function | `backend/tests/test_agent_api.py` | 70 |
| `test_agent_me` | Function | `backend/tests/test_agent_api.py` | 91 |
| `test_create_inspect_job` | Function | `backend/tests/test_agent_api.py` | 115 |
| `test_create_parse_job` | Function | `backend/tests/test_agent_api.py` | 130 |
| `test_get_job_status` | Function | `backend/tests/test_agent_api.py` | 145 |
| `test_get_job_not_found` | Function | `backend/tests/test_agent_api.py` | 163 |
| `test_get_job_not_owner` | Function | `backend/tests/test_agent_api.py` | 174 |
| `test_inspect_job_no_scope` | Function | `backend/tests/test_agent_api.py` | 191 |
| `test_me_wrong_scope` | Function | `backend/tests/test_agent_api.py` | 202 |
| `test_list_records` | Function | `backend/tests/test_agent_api.py` | 270 |
| `test_list_records_no_scope` | Function | `backend/tests/test_agent_api.py` | 290 |
| `test_get_record_detail` | Function | `backend/tests/test_agent_api.py` | 301 |
| `test_get_record_not_found` | Function | `backend/tests/test_agent_api.py` | 325 |
| `test_get_record_not_owner` | Function | `backend/tests/test_agent_api.py` | 336 |
| `test_knowledge_search` | Function | `backend/tests/test_agent_api.py` | 351 |
| `test_knowledge_search_no_scope` | Function | `backend/tests/test_agent_api.py` | 391 |
| `test_agent_inspect_success` | Function | `backend/tests/test_agent_api.py` | 406 |
| `test_agent_parse_creates_pending_record` | Function | `backend/tests/test_agent_api.py` | 430 |
| `test_agent_inspect_by_record_id` | Function | `backend/tests/test_agent_api.py` | 449 |

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
| Services | 13 calls |
| V1 | 7 calls |

## How to Explore

1. `gitnexus_context({name: "register_user"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
