"""合同初审分类、风险最终化和历史展示契约。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def _classifier():
    module = pytest.importorskip(
        "app.services.contract_classifier",
        reason="任务 5 实现分类器后移除 importorskip",
    )
    return module.classify_contract


def _risk_finalizer():
    module = pytest.importorskip(
        "app.services.risk_policy",
        reason="任务 11 实现风险策略后移除 importorskip",
    )
    return module.finalize_overall_risk


@pytest.mark.asyncio
async def test_engineering_and_contract_dimensions_are_independent() -> None:
    classify_contract = _classifier()
    result = await classify_contract(
        filename="市政道路劳务合同.docx",
        text="本合同用于市政道路施工，乙方承担劳务分包工作。",
    )

    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.engineering_type_key != result.contract_type_key


@pytest.mark.asyncio
async def test_unknown_engineering_key_falls_back_without_changing_contract_key() -> None:
    classify_contract = _classifier()
    model = AsyncMock(
        return_value={
            "engineering_type_key": "not-an-engineering-type",
            "contract_type_key": "labor-subcontract",
            "confidence": "high",
        }
    )

    result = await classify_contract("合同.txt", "劳务分包合同", model=model)

    model.assert_awaited_once()
    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "labor-subcontract"


@pytest.mark.asyncio
async def test_unknown_contract_key_falls_back_without_changing_engineering_key() -> None:
    classify_contract = _classifier()
    model = AsyncMock(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "not-a-contract-type",
            "confidence": "high",
        }
    )

    result = await classify_contract("合同.txt", "市政道路施工合同", model=model)

    model.assert_awaited_once()
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "other"


@pytest.mark.asyncio
async def test_legal_categories_are_retained_when_confidence_is_low() -> None:
    classify_contract = _classifier()
    model = AsyncMock(
        return_value={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "professional-subcontract",
            "confidence": "low",
        }
    )

    result = await classify_contract("资料.txt", "市政道路相关合同", model=model)

    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "professional-subcontract"
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_model_timeout_calls_model_and_returns_confirmation_fallback() -> None:
    classify_contract = _classifier()
    model = AsyncMock(side_effect=TimeoutError)

    result = await classify_contract("施工合同.txt", "甲乙双方签订合同", model=model)

    model.assert_awaited_once()
    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "other"
    assert result.requires_confirmation is True


@pytest.mark.parametrize("invalid_risk", [None, "unknown", "严重"])
def test_invalid_overall_risk_defaults_to_low(invalid_risk: object) -> None:
    finalize_overall_risk = _risk_finalizer()

    assert finalize_overall_risk(invalid_risk, []) == "low"


def test_critical_issue_wins_across_multiple_issues() -> None:
    finalize_overall_risk = _risk_finalizer()

    assert finalize_overall_risk(
        "medium",
        [{"severity": "high"}, {"severity": "critical"}, {"severity": "low"}],
    ) == "critical"


def test_issue_severity_can_raise_but_never_lower_model_risk() -> None:
    finalize_overall_risk = _risk_finalizer()

    assert finalize_overall_risk("low", [{"severity": "high"}]) == "high"
    assert finalize_overall_risk("critical", [{"severity": "medium"}]) == "critical"


def test_invalid_issue_severity_is_ignored_and_empty_issues_keep_valid_risk() -> None:
    finalize_overall_risk = _risk_finalizer()

    assert finalize_overall_risk("medium", [{"severity": "not-a-risk"}, {}]) == "medium"
    assert finalize_overall_risk("high", []) == "high"


def test_legacy_record_with_missing_classification_fields_uses_compatibility_display() -> None:
    module = pytest.importorskip(
        "app.services.inspection_history",
        reason="任务 6/17 实现历史展示后移除 importorskip",
    )

    display = module.classification_display(
        {"application_scenario": "contract", "classification_source": "legacy"}
    )

    assert display == "历史记录 / 通用工程合同"


def test_archived_legacy_bidding_display_contract_is_explicitly_pending() -> None:
    try:
        from app.services.inspection_history import classification_display
    except ModuleNotFoundError:
        pytest.xfail(
            "后续任务需提供历史招投标归档展示接口；接口落地后移除本 xfail"
        )

    display = classification_display(
        {"application_scenario": "bidding", "classification_source": "archived_legacy"}
    )

    assert display == "历史记录 / 招投标资料已归档，无法按旧场景重审"
