"""合同初审分类、风险最终化和历史展示契约。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, create_autospec

import pytest

from app.services.contract_classifier import classify_contract


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
            "evidence": ["模型证据"],
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
            "evidence": ["模型证据"],
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
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
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
    assert result.engineering_type_key == "municipal-road"
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
    assert result.contract_type_key == "labor-subcontract"


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
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_model_timeout_error_returns_rule_screening_fallback() -> None:
    filename = "施工合同.txt"
    text = "甲乙双方签订合同"
    rules = _rule_screening()
    model = _model(side_effect=TimeoutError("model timeout"))

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.confidence == "low"
    assert result.requires_confirmation is True


@pytest.mark.asyncio
async def test_model_unexpected_error_returns_rule_screening_fallback() -> None:
    filename = "施工合同.txt"
    text = "甲乙双方签订合同"
    rules = _rule_screening()
    model = _model(side_effect=RuntimeError("model unavailable"))

    result = await classify_contract(
        filename=filename, text=text, rule_screening=rules, model=model
    )

    _assert_model_call(model, filename=filename, text=text, rule_screening=rules)
    assert result.engineering_type_key == "municipal-road"
    assert result.contract_type_key == "labor-subcontract"
    assert result.confidence == "low"
    assert result.requires_confirmation is True
