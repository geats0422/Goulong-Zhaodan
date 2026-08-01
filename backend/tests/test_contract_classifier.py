"""合同分类器的规则初筛与安全降级契约。"""

from __future__ import annotations

import asyncio

import pytest

from app.services.contract_classifier import classify_contract, screen_contract_rules


def test_rule_screening_uses_filename_sections_and_body_independently() -> None:
    result = screen_contract_rules(
        filename="市政道路劳务分包合同.docx",
        text="# 工程概况\n本项目为市政道路施工。\n## 分包范围\n乙方提供劳务分包。",
    )

    assert result["engineering_type_key"] == "municipal-road"
    assert result["contract_type_key"] == "labor-subcontract"
    assert "市政道路" in result["evidence"]
    assert "劳务分包" in result["evidence"]
    assert result["source"] == "rule"


@pytest.mark.asyncio
async def test_empty_text_without_model_is_safe_default() -> None:
    result = await classify_contract(filename="资料.txt", text="", model=None)

    assert result.engineering_type_key == "general-engineering"
    assert result.contract_type_key == "other"
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_cancelled_model_call_propagates_cancellation() -> None:
    async def cancelled_model(**_: object) -> dict[str, object]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await classify_contract(
            filename="合同.txt",
            text="甲乙双方签订工程施工合同。",
            model=cancelled_model,
        )
