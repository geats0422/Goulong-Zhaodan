"""合同初审分类、风险最终化和历史展示契约。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, create_autospec

import pytest

from app.services.contract_classifier import classify_contract
from app.services.inspection_history import classification_display
from app.services.risk_policy import finalize_overall_risk


def _rule_screening() -> dict[str, str]:
    return {
        "engineering_type_key": "municipal-road",
        "contract_type_key": "labor-subcontract",
    }


async def _model_signature(
    *, filename: str, text: str, rule_screening: dict[str, str]
) -> dict[str, object]:
    """模型适配器的最小调用签名，测试禁止绕过该边界调用真实模型。"""
    return {
        "filename": filename,
        "text": text,
        "rule_screening": rule_screening,
    }


def _model(*, return_value: object = None, side_effect=None) -> AsyncMock:
    return create_autospec(
        _model_signature,
        spec_set=True,
        return_value=return_value,
        side_effect=side_effect,
    )


def _assert_model_call(
    model: AsyncMock,
    *,
    filename: str,
    text: str,
    rule_screening: dict[str, str],
) -> None:
    model.assert_awaited_once()
    call = model.await_args
    assert call.args == ()
    assert call.kwargs == {
        "filename": filename,
        "text": text,
        "rule_screening": rule_screening,
    }


@pytest.mark.asyncio
async def test_engineering_and_contract_dimensions_are_independent() -> None:
    filename = "市政道路劳务合同.docx"
    text = "本合同用于市政道路施工，乙方承担劳务分包工作。"
    rules = _rule_screening()
    model = _model(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "labor-subcontract",
            "confidence": "high",
            "evidence": ["市政道路", "劳务分包"],
        }
    )

    result = await classify_contract(
        filename=filename,
        text=text,
        rule_screening=rules,
        model=model,
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.engineering_type_key != result.contract_type_key
    assert result.evidence == ["市政道路", "劳务分包"]


@pytest.mark.asyncio
async def test_low_confidence_keeps_both_legal_categories_and_requires_confirmation() -> None:
    filename = "资料.txt"
    text = "市政道路相关合同"
    rules = _rule_screening()
    model = _model(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "professional-subcontract",
            "confidence": "low",
            "evidence": ["市政道路"],
        }
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "professional-subcontract"
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_unknown_engineering_key_falls_back_without_changing_contract_key() -> None:
    filename = "合同.txt"
    text = "劳务分包合同"
    rules = _rule_screening()
    model = _model(
        return_value={
            "engineering_type_key": "not-an-engineering-type",
            "contract_type_key": "labor-subcontract",
            "confidence": "high",
        }
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "labor-subcontract"


@pytest.mark.asyncio
async def test_unknown_contract_key_falls_back_without_changing_engineering_key() -> None:
    filename = "合同.txt"
    text = "市政道路施工合同"
    rules = _rule_screening()
    model = _model(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "not-a-contract-type",
            "confidence": "high",
        }
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "other"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malformed_response",
    [
        None,
        "not structured",
        {},
        {1: "non-string key"},
        {
            "engineering_type_key": "municipal-road",
            "contract_type_key": "labor-subcontract",
            "confidence": "high",
            "evidence": {"wrong": "type"},
        },
        {
            "engineering_type_key": "municipal-road",
            "contract_type_key": "labor-subcontract",
            "confidence": ["wrong", "type"],
            "evidence": ["valid shape"],
        },
    ],
    ids=["none", "string", "empty-dict", "non-string-key", "bad-evidence", "bad-confidence"],
)
async def test_malformed_model_response_falls_back_both_dimensions(
    malformed_response: object,
) -> None:
    filename = "资料.txt"
    text = "无法判断类别"
    rules = _rule_screening()
    model = _model(return_value=malformed_response)

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "other"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_missing_engineering_key_only_falls_back_engineering_dimension() -> None:
    filename = "合同.txt"
    text = "劳务分包合同"
    rules = _rule_screening()
    model = _model(
        return_value={"contract_type_key": "labor-subcontract", "confidence": "high"}
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "labor-subcontract"


@pytest.mark.asyncio
async def test_missing_contract_key_only_falls_back_contract_dimension() -> None:
    filename = "合同.txt"
    text = "市政道路施工合同"
    rules = _rule_screening()
    model = _model(
        return_value={"engineering_type_key": "municipal-road", "confidence": "high"}
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "other"


@pytest.mark.asyncio
async def test_illegal_confidence_is_normalized_to_low_confirmation() -> None:
    filename = "资料.txt"
    text = "市政道路相关合同"
    rules = _rule_screening()
    model = _model(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "professional-subcontract",
            "confidence": "certainly",
        }
    )

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_model_timeout_uses_deadline_and_confirmation_fallback() -> None:
    filename = "施工合同.txt"
    text = "甲乙双方签订合同"
    rules = _rule_screening()
    cancelled = asyncio.Event()

    async def never_finishes(**_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    model = _model(side_effect=never_finishes)

    result = await asyncio.wait_for(
        classify_contract(
            filename=filename,
            text=text,
            rule_screening=rules,
            model=model,
            timeout_seconds=0.05,
        ),
        timeout=0.5,
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert cancelled.is_set()
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.requires_confirmation is True


@pytest.mark.parametrize("model_risk", ["low", "medium", "high", "critical"])
def test_all_valid_overall_risk_values_are_preserved_without_issues(model_risk: str) -> None:
    assert finalize_overall_risk(model_risk, []) == model_risk


@pytest.mark.parametrize("invalid_risk", [None, "unknown", "严重", 1, {}])
def test_invalid_overall_risk_defaults_to_low(invalid_risk: object) -> None:
    assert finalize_overall_risk(invalid_risk, []) == "low"


def test_critical_issue_wins_across_multiple_issues() -> None:
    assert finalize_overall_risk(
        "medium",
        [{"severity": "high"}, {"severity": "critical"}, {"severity": "low"}],
    ) == "critical"


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_low_model_risk_is_raised_by_highest_issue_severity(severity: str) -> None:
    assert finalize_overall_risk("low", [{"severity": severity}]) == severity


def test_invalid_issue_severity_is_ignored_and_model_risk_is_not_lowered() -> None:
    assert finalize_overall_risk("medium", [{"severity": "not-a-risk"}, {}]) == "medium"
    assert finalize_overall_risk("critical", [{"severity": "medium"}]) == "critical"


@pytest.mark.parametrize("issues", [None, "not-a-list", {}, 1])
def test_non_list_issues_are_treated_as_empty(issues: object) -> None:
    assert finalize_overall_risk("high", issues) == "high"


def test_legacy_record_with_missing_classification_fields_uses_compatibility_display() -> None:
    display = classification_display(
        {"application_scenario": "contract", "classification_source": "legacy"}
    )

    assert display == "历史记录 / 通用工程合同"


def test_archived_legacy_bidding_display_is_a_strict_contract() -> None:
    display = classification_display(
        {"application_scenario": "bidding", "classification_source": "archived_legacy"}
    )

    assert display == "历史记录 / 招投标资料已归档，无法按旧场景重审"
