from __future__ import annotations

from app.prompts.inspection_prompts import (
    format_inspection_prompt,
    format_summary_prompt,
)

TEST_PROMPT_CHAR_BUDGET = 6000


def test_inspection_prompt_keeps_combined_context_under_budget() -> None:
    document_text = "合同条款" * 3000
    regulation_result = "法规分析结果" * 500

    prompt = format_inspection_prompt(
        document_text,
        regulation_result,
        {"snippets": [], "sources": []},
        max_length=TEST_PROMPT_CHAR_BUDGET,
    )

    assert len(prompt) <= TEST_PROMPT_CHAR_BUDGET + 200
    assert "[内容已截断]" in prompt
    assert "法规分析结果" in prompt


def test_summary_prompt_truncates_large_intermediate_results() -> None:
    regulation_result = "法规分析结果" * 1200
    inspection_result = "合规检查结果" * 1200

    prompt = format_summary_prompt(regulation_result, inspection_result, ["民法典合同编"], max_length=TEST_PROMPT_CHAR_BUDGET)

    assert len(prompt) <= TEST_PROMPT_CHAR_BUDGET + 200
    assert "[内容已截断]" in prompt
    assert "民法典合同编" in prompt
