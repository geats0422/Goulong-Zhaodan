---
name: prompts
description: "Skill for the Prompts area of Goulong-Zhaodan. 12 symbols across 3 files."
---

# Prompts

12 symbols | 3 files | Cohesion: 65%

## When to Use

- Working with code in `backend/`
- Understanding how format_regulation_prompt, format_summary_prompt, test_format_regulation_prompt_masks_phone work
- Modifying prompts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend/app/prompts/inspection_prompts.py` | _prompt_char_budget, _truncate_text, format_regulation_prompt, format_summary_prompt, _safe_mask (+2) |
| `backend/tests/test_data_masking.py` | test_format_regulation_prompt_masks_phone, test_format_prompt_keeps_normal_text, test_format_inspection_prompt_masks_id_card |
| `backend/tests/test_inspection_prompts.py` | test_summary_prompt_truncates_large_intermediate_results, test_inspection_prompt_keeps_combined_context_under_budget |

## Entry Points

Start here when exploring this area:

- **`format_regulation_prompt`** (Function) — `backend/app/prompts/inspection_prompts.py:152`
- **`format_summary_prompt`** (Function) — `backend/app/prompts/inspection_prompts.py:223`
- **`test_format_regulation_prompt_masks_phone`** (Function) — `backend/tests/test_data_masking.py:116`
- **`test_format_prompt_keeps_normal_text`** (Function) — `backend/tests/test_data_masking.py:132`
- **`test_summary_prompt_truncates_large_intermediate_results`** (Function) — `backend/tests/test_inspection_prompts.py:29`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `format_regulation_prompt` | Function | `backend/app/prompts/inspection_prompts.py` | 152 |
| `format_summary_prompt` | Function | `backend/app/prompts/inspection_prompts.py` | 223 |
| `test_format_regulation_prompt_masks_phone` | Function | `backend/tests/test_data_masking.py` | 116 |
| `test_format_prompt_keeps_normal_text` | Function | `backend/tests/test_data_masking.py` | 132 |
| `test_summary_prompt_truncates_large_intermediate_results` | Function | `backend/tests/test_inspection_prompts.py` | 29 |
| `format_regulation_base_context` | Function | `backend/app/prompts/inspection_prompts.py` | 170 |
| `format_inspection_prompt` | Function | `backend/app/prompts/inspection_prompts.py` | 184 |
| `test_format_inspection_prompt_masks_id_card` | Function | `backend/tests/test_data_masking.py` | 122 |
| `test_inspection_prompt_keeps_combined_context_under_budget` | Function | `backend/tests/test_inspection_prompts.py` | 13 |
| `_prompt_char_budget` | Function | `backend/app/prompts/inspection_prompts.py` | 16 |
| `_truncate_text` | Function | `backend/app/prompts/inspection_prompts.py` | 20 |
| `_safe_mask` | Function | `backend/app/prompts/inspection_prompts.py` | 145 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `_run_inspect → Mask_sensitive_data` | cross_community | 6 |
| `Agent_inspect → _prompt_char_budget` | cross_community | 5 |
| `Agent_inspect → Format_regulation_base_context` | cross_community | 5 |
| `Agent_inspect → _truncate_text` | cross_community | 5 |
| `Upload_and_inspect → _prompt_char_budget` | cross_community | 5 |
| `Upload_and_inspect → Format_regulation_base_context` | cross_community | 5 |
| `Upload_and_inspect → _truncate_text` | cross_community | 5 |
| `Inspect_session → _prompt_char_budget` | cross_community | 5 |
| `Inspect_session → Format_regulation_base_context` | cross_community | 5 |
| `Inspect_session → _truncate_text` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 1 calls |

## How to Explore

1. `gitnexus_context({name: "format_regulation_prompt"})` — see callers and callees
2. `gitnexus_query({query: "prompts"})` — find related execution flows
3. Read key files listed above for implementation details
