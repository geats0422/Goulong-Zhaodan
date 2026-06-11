from __future__ import annotations

from app.prompts.inspection_prompts import (
    CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
    CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT,
    format_inspection_prompt,
    format_summary_prompt,
    get_prompts_for_scenario,
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


CONTRACT_REVIEW_DIMENSIONS = [
    "权利义务",
    "违约责任",
    "金额",
    "履约",
    "不可抗力",
    "争议解决",
    "绝对化用语",
]


def test_contract_regulation_prompt_includes_core_dimensions():
    for dim in CONTRACT_REVIEW_DIMENSIONS:
        assert dim in CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT, f"缺少合同审查维度: {dim}"


def test_contract_inspection_prompt_includes_core_dimensions():
    for dim in CONTRACT_REVIEW_DIMENSIONS:
        assert dim in CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT, f"缺少合同审查维度: {dim}"


def test_get_prompts_for_scenario_contract():
    prompts = get_prompts_for_scenario("contract")
    assert prompts["regulation"] == CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT
    assert prompts["inspection"] == CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT


def test_get_prompts_for_scenario_bidding_uses_defaults():
    from app.prompts.inspection_prompts import (
        COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
        REGULATION_ANALYST_SYSTEM_PROMPT,
    )
    prompts = get_prompts_for_scenario("bidding")
    assert prompts["regulation"] == REGULATION_ANALYST_SYSTEM_PROMPT
    assert prompts["inspection"] == COMPLIANCE_INSPECTOR_SYSTEM_PROMPT


def test_get_prompts_for_scenario_unknown_falls_back_to_bidding():
    from app.prompts.inspection_prompts import (
        COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
        REGULATION_ANALYST_SYSTEM_PROMPT,
    )
    prompts = get_prompts_for_scenario("unknown")
    assert prompts["regulation"] == REGULATION_ANALYST_SYSTEM_PROMPT
    assert prompts["inspection"] == COMPLIANCE_INSPECTOR_SYSTEM_PROMPT
