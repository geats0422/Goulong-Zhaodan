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


@pytest.mark.asyncio
async def test_model_response_requires_non_empty_evidence_and_keeps_rules() -> None:
    async def invalid_model(**_: object) -> dict[str, object]:
        return {
            "engineering_type_key": "municipal-road",
            "contract_type_key": "professional-subcontract",
            "confidence": "high",
            "evidence": [],
        }

    result = await classify_contract(
        filename="市政道路劳务分包合同.docx",
        text="市政道路施工，劳务分包。",
        model=invalid_model,
    )

    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.source == "rule"
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_model_input_is_bounded_and_masked() -> None:
    captured: dict[str, object] = {}

    async def model(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "engineering_type_key": "general-engineering",
            "contract_type_key": "other",
            "confidence": "high",
            "evidence": ["通用"],
        }

    result = await classify_contract(
        filename="甲方13800138000" + "x" * 1000,
        text="联系人 13800138000\n" + "市政道路" + "x" * 30000,
        model=model,
        max_filename_chars=64,
        max_text_chars=100,
    )

    assert result.source == "model"
    assert len(str(captured["filename"])) <= 64
    assert len(str(captured["text"])) <= 100 + len("\n...[内容已截断]")
    assert "13800138000" not in str(captured["text"])


@pytest.mark.asyncio
async def test_rule_screening_sent_to_model_is_whitelisted_and_bounded() -> None:
    captured: dict[str, object] = {}

    async def model(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "engineering_type_key": "general-engineering",
            "contract_type_key": "other",
            "confidence": "medium",
            "evidence": ["规则"],
        }

    await classify_contract(
        filename="合同.txt",
        text="正文",
        rule_screening={
            "engineering_type_key": "municipal-road",
            "contract_type_key": "labor-subcontract",
            "evidence": ["证据" * 1000] * 100,
            "secret": "不应外发",
        },
        model=model,
    )

    sent_rules = captured["rule_screening"]
    assert isinstance(sent_rules, dict)
    assert "secret" not in sent_rules
    assert len(str(sent_rules)) <= 2500
