"""基础工具与类型定义"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from pydantic import BaseModel


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionCategory(str, Enum):
    QUERY = "query"
    REVIEW = "review"
    APPROVE = "approve"
    MODIFY = "modify"
    REPORT = "report"
    ESCALATE = "escalate"


class ActionRisk(BaseModel):
    """工具风险元数据"""

    risk_level: str = "high"
    category: ActionCategory = ActionCategory.QUERY
    requires_approval: bool = True
    approval_level: str = "自动"
    irreversible: bool = False
    regulation_refs: list[str] = []
    retention_period: str = "10年"


def inspection_tool(
    *,
    risk_level: str = "medium",
    category: ActionCategory = ActionCategory.REVIEW,
    requires_approval: bool = False,
    approval_level: str = "自动",
    irreversible: bool = False,
    regulation_refs: list[str] | None = None,
    retention_period: str = "10年",
):
    """
    体检工具装饰器 — 为工具附加合规风险元数据。

    默认值 fail-closed：
    - risk_level 默认 medium
    - requires_approval 默认 False（体检台以审查为主，不直接修改）
    """
    risk = ActionRisk(
        risk_level=risk_level,
        category=category,
        requires_approval=requires_approval,
        approval_level=approval_level,
        irreversible=irreversible,
        regulation_refs=regulation_refs or [],
        retention_period=retention_period,
    )

    def decorator(func: Callable) -> Callable:
        func._inspection_risk = risk  # type: ignore[attr-defined]
        return func

    return decorator
