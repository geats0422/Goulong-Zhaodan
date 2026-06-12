"""体检台 Agent 协调逻辑"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.agents import get_compliance_inspector, get_inspection_agent, get_regulation_analyst
from app.prompts.inspection_prompts import (
    format_inspection_prompt,
    format_regulation_prompt,
    format_summary_prompt,
)
from app.core.deps import InspectionDeps


def _allowed_refs(deps: InspectionDeps) -> list[str]:
    regulation_base = deps.regulation_base or {}
    refs = [
        str(source.get("title", "")).strip()
        for source in regulation_base.get("sources", [])
        if str(source.get("title", "")).strip()
    ]
    refs.extend(f"违禁词:{word}" for word in (deps.taboo_words or []) if word)
    return refs


@dataclass
class InspectionResult:
    """体检报告结构化结果"""

    overall_risk: str  # low | medium | high | critical
    summary: str
    issues: list[dict[str, Any]]
    regulation_refs: list[str]


async def run_inspection(
    document_text: str,
    deps: InspectionDeps,
) -> InspectionResult:
    """
    运行体检台多 Agent 审查流水线。

    流程：法规分析 → 合规检查 → 汇总报告
    """
    scenario = deps.application_scenario

    # 阶段 1: 法规分析
    regulation_result = await get_regulation_analyst(scenario).run(
        format_regulation_prompt(document_text, deps.regulation_base),
        deps=deps,
    )

    # 阶段 2: 合规检查（包含违禁词、低级错误等）
    inspection_prompt = format_inspection_prompt(
        document_text=document_text,
        regulation_result=regulation_result.output,
        regulation_base=deps.regulation_base,
        taboo_words=deps.taboo_words,
    )

    inspection_result = await get_compliance_inspector(scenario).run(
        inspection_prompt,
        deps=deps,
    )

    # 阶段 3: 汇总报告
    summary_prompt = format_summary_prompt(
        regulation_result=regulation_result.output,
        inspection_result=inspection_result.output,
        allowed_refs=_allowed_refs(deps),
    )

    final_result = await get_inspection_agent().run(
        summary_prompt,
        deps=deps,
    )

    # 尝试解析 JSON
    try:
        data = json.loads(final_result.output)
    except json.JSONDecodeError:
        # 兜底结构
        data = {
            "overall_risk": "medium",
            "summary": final_result.output[:500],
            "issues": [],
            "regulation_refs": [],
        }

    return InspectionResult(
        overall_risk=data.get("overall_risk", "medium"),
        summary=data.get("summary", ""),
        issues=data.get("issues", []),
        regulation_refs=data.get("regulation_refs", []),
    )
