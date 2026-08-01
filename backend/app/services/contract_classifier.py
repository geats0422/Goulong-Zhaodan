"""合同初审分类：规则初筛与可取消的模型推荐。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.core.data_masking import mask_sensitive_data
from app.prompts.inspection_prompts import CONTRACT_CLASSIFIER_SYSTEM_PROMPT
ENGINEERING_TYPE_KEYS = {
    "building-construction",
    "municipal-road",
    "decoration-renovation",
    "mechanical-electrical-installation",
    "steel-structure",
    "general-engineering",
}
CONTRACT_TYPE_KEYS = {"labor-subcontract", "professional-subcontract", "other"}
DEFAULT_ENGINEERING_TYPE = "general-engineering"
DEFAULT_CONTRACT_TYPE = "other"
CONFIDENCES = {"high", "medium", "low"}
MAX_FILENAME_CHARS = 512
MAX_TEXT_CHARS = 12000
MAX_KEYWORDS = 20
MAX_KEYWORD_CHARS = 100

_ENGINEERING_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("building-construction", ("房建", "房屋建筑", "建筑工程")),
    ("municipal-road", ("市政道路", "市政路", "道路工程", "公路工程")),
    ("decoration-renovation", ("装饰装修", "装修工程", "精装修")),
    ("mechanical-electrical-installation", ("机电安装", "机电工程")),
    ("steel-structure", ("钢结构",)),
)
_CONTRACT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("labor-subcontract", ("劳务分包", "劳务合同")),
    ("professional-subcontract", ("专业工程分包", "专业分包", "工程分包")),
)


@dataclass(frozen=True)
class ContractClassification:
    engineering_type_key: str
    contract_type_key: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    source: str = "fallback"
    requires_confirmation: bool = True


class ContractClassificationModelResponse(BaseModel):
    """模型输出边界；类别 key 由分类器按维度独立校验。"""

    model_config = ConfigDict(extra="forbid")

    engineering_type_key: str
    contract_type_key: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str] = Field(min_length=1)


ModelCallable = Callable[..., Awaitable[object]]


def _rule_dimension(
    value: str,
    rules: tuple[tuple[str, tuple[str, ...]], ...],
    default: str,
) -> tuple[str, list[str]]:
    matches = [(key, keyword) for key, keywords in rules for keyword in keywords if keyword in value]
    if not matches:
        return default, []
    return matches[0][0], [keyword for _, keyword in matches]


def screen_contract_rules(*, filename: str, text: str, keywords: list[str] | None = None) -> dict[str, Any]:
    """按文件名、章节标题和正文关键词完成无网络规则初筛。"""
    combined = "\n".join((filename or "", text or "", *(keywords or [])))
    engineering_key, engineering_evidence = _rule_dimension(combined, _ENGINEERING_RULES, DEFAULT_ENGINEERING_TYPE)
    contract_key, contract_evidence = _rule_dimension(combined, _CONTRACT_RULES, DEFAULT_CONTRACT_TYPE)
    evidence = list(dict.fromkeys(engineering_evidence + contract_evidence))
    matched = bool(evidence)
    return {
        "engineering_type_key": engineering_key,
        "contract_type_key": contract_key,
        "confidence": "medium" if matched else "low",
        "evidence": evidence,
        "source": "rule",
        "requires_confirmation": True,
    }


def _fallback(rule_screening: Mapping[str, Any] | None) -> ContractClassification:
    """异常时保留合法规则维度；没有合法规则时才使用通用默认值。"""
    rule = rule_screening or {}
    engineering = rule.get("engineering_type_key")
    contract = rule.get("contract_type_key")
    if engineering not in ENGINEERING_TYPE_KEYS:
        engineering = DEFAULT_ENGINEERING_TYPE
    if contract not in CONTRACT_TYPE_KEYS:
        contract = DEFAULT_CONTRACT_TYPE
    evidence = rule.get("evidence", [])
    return ContractClassification(
        engineering_type_key=engineering,
        contract_type_key=contract,
        confidence="low",
        evidence=[item for item in evidence if isinstance(item, str)],
        source="rule" if rule.get("evidence") else "fallback",
        requires_confirmation=True,
    )


def _model_result(value: object) -> ContractClassification | None:
    if not isinstance(value, Mapping):
        return None
    try:
        response = ContractClassificationModelResponse.model_validate(value)
    except Exception:
        return None
    engineering = response.engineering_type_key
    contract = response.contract_type_key
    normalized_confidence = response.confidence
    unknown_dimension = engineering not in ENGINEERING_TYPE_KEYS or contract not in CONTRACT_TYPE_KEYS
    if unknown_dimension:
        normalized_confidence = "low"
    return ContractClassification(
        engineering_type_key=engineering if engineering in ENGINEERING_TYPE_KEYS else DEFAULT_ENGINEERING_TYPE,
        contract_type_key=contract if contract in CONTRACT_TYPE_KEYS else DEFAULT_CONTRACT_TYPE,
        confidence=normalized_confidence,
        evidence=response.evidence,
        source="model",
        requires_confirmation=normalized_confidence != "high" or unknown_dimension,
    )


def _truncate(value: str, limit: int) -> str:
    marker = "\n...[内容已截断]"
    if len(value) <= limit:
        return value
    if limit <= len(marker):
        return marker[:limit]
    return f"{value[: limit - len(marker)]}{marker}"


def _model_inputs(filename: str, text: str, rules: Mapping[str, Any], *, max_filename_chars: int, max_text_chars: int) -> tuple[str, str, dict[str, Any]]:
    safe_filename = _truncate(mask_sensitive_data(filename or "").text, max_filename_chars)
    safe_text = _truncate(mask_sensitive_data(text or "").text, max_text_chars)
    safe_rules = dict(rules)
    if "evidence" in rules:
        safe_rules["evidence"] = [
            _truncate(item, MAX_KEYWORD_CHARS)
            for item in rules.get("evidence", [])[:MAX_KEYWORDS]
            if isinstance(item, str)
        ]
    return safe_filename, safe_text, safe_rules


def get_contract_classifier_model() -> ModelCallable:
    """创建现有 PydanticAI abstraction 的可替换适配器。"""
    from pydantic_ai import Agent

    from app.agents import _make_model

    agent = Agent(
        _make_model(),
        output_type=ContractClassificationModelResponse,
        instructions=CONTRACT_CLASSIFIER_SYSTEM_PROMPT,
        model_settings={"temperature": 0.0},
    )

    async def run(*, filename: str, text: str, rule_screening: Mapping[str, Any]) -> object:
        prompt = (
            f"文件名：{filename}\n规则初筛：{dict(rule_screening)}\n"
            f"正文：{text}\n请仅输出结构化分类结果。"
        )
        result = await agent.run(prompt)
        return result.output.model_dump()

    return run


async def classify_contract(
    *,
    filename: str,
    text: str,
    keywords: list[str] | None = None,
    rule_screening: Mapping[str, Any] | None = None,
    model: ModelCallable | None = None,
    timeout_seconds: float = 5.0,
    max_filename_chars: int = MAX_FILENAME_CHARS,
    max_text_chars: int = MAX_TEXT_CHARS,
) -> ContractClassification:
    """返回独立工程/合同维度推荐；模型失败不会阻塞后续 Step 2。

    ``CancelledError`` 特意不捕获，保证请求取消能沿调用链传播；超时和普通异常安全降级。
    """
    rules = dict(rule_screening or screen_contract_rules(filename=filename, text=text, keywords=keywords))
    if not (text or "".join(keywords or [])):
        return _fallback(rules)
    if model is None:
        try:
            model = get_contract_classifier_model()
        except Exception:
            return _fallback(rules)
    safe_filename, safe_text, safe_rules = _model_inputs(
        filename,
        text,
        rules,
        max_filename_chars=max_filename_chars,
        max_text_chars=max_text_chars,
    )
    try:
        raw = await asyncio.wait_for(
            model(filename=safe_filename, text=safe_text, rule_screening=safe_rules),
            timeout=timeout_seconds,
        )
    except (TimeoutError, asyncio.TimeoutError):
        return _fallback(rules)
    except asyncio.CancelledError:
        raise
    except Exception:
        return _fallback(rules)
    parsed = _model_result(raw)
    return parsed if parsed is not None else _fallback(rules)
