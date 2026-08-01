"""合同初审分类与风险最终化契约。

这些测试先固化任务 1 的边界，具体分类器和风险策略由后续任务实现。
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=True, reason="分类器将在任务 5 实现")
@pytest.mark.asyncio
async def test_engineering_and_contract_dimensions_are_independent() -> None:
    from app.services.contract_classifier import classify_contract

    result = await classify_contract(
        filename="市政道路劳务合同.docx",
        text="本合同用于市政道路施工，乙方承担劳务分包工作。",
    )

    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.engineering_type_key != result.contract_type_key


@pytest.mark.xfail(strict=True, reason="分类器将在任务 5 实现")
@pytest.mark.asyncio
async def test_unknown_category_low_confidence_and_timeout_share_safe_fallback() -> None:
    from app.services.contract_classifier import classify_contract

    unknown = await classify_contract(filename="项目资料.txt", text="没有明确类别线索")
    assert unknown.engineering_type_key == "general-engineering"
    assert unknown.contract_type_key == "other"
    assert unknown.confidence == "low"

    async def timed_out_model(*_args, **_kwargs):
        raise TimeoutError

    timed_out = await classify_contract(
        filename="施工合同.txt",
        text="甲乙双方签订合同",
        model=timed_out_model,
    )
    assert timed_out.engineering_type_key == "general-engineering"
    assert timed_out.contract_type_key == "other"
    assert timed_out.requires_confirmation is True


@pytest.mark.xfail(strict=True, reason="风险最终化将在任务 11 实现")
@pytest.mark.parametrize("invalid_risk", [None, "unknown", "严重"])
def test_invalid_overall_risk_is_replaced_and_issue_severity_can_only_raise(
    invalid_risk: object,
) -> None:
    from app.services.risk_policy import finalize_overall_risk

    assert finalize_overall_risk(invalid_risk, []) == "low"
    assert finalize_overall_risk("low", [{"severity": "high"}]) == "high"
    assert finalize_overall_risk("high", [{"severity": "medium"}]) == "high"


@pytest.mark.xfail(strict=True, reason="历史记录兼容展示将在任务 6/17 实现")
def test_legacy_record_without_new_classification_fields_has_compatibility_display() -> None:
    from app.services.inspection_history import classification_display

    display = classification_display(
        {
            "application_scenario": "contract",
            "final_engineering_type": None,
            "final_contract_type": None,
        }
    )

    assert display == "历史记录 / 通用工程合同"
