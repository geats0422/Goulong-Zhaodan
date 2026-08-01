"""服务端风险等级归一化。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

RISK_LEVELS = ("low", "medium", "high", "critical")


def finalize_overall_risk(model_risk: Any, issues: Any) -> str:
    """只允许合法标签，并按问题最高严重等级提升风险。"""
    final = model_risk if model_risk in RISK_LEVELS else "low"
    if not isinstance(issues, Iterable) or isinstance(issues, (str, bytes, Mapping)):
        return final
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        severity = issue.get("severity")
        if severity in RISK_LEVELS and RISK_LEVELS.index(severity) > RISK_LEVELS.index(final):
            final = severity
    return final
