"""风险最终化与历史展示测试（后续任务范围）。"""

from __future__ import annotations

import pytest

from app.services.inspection_history import classification_display
from app.services.risk_policy import finalize_overall_risk


@pytest.mark.parametrize("model_risk", ["low", "medium", "high", "critical"])
def test_all_valid_overall_risk_values_are_preserved_without_issues(model_risk: str) -> None:
    assert finalize_overall_risk(model_risk, []) == model_risk


@pytest.mark.parametrize("invalid_risk", [None, "unknown", "严重", 1, {}])
def test_invalid_overall_risk_defaults_to_low(invalid_risk: object) -> None:
    assert finalize_overall_risk(invalid_risk, []) == "low"


def test_critical_issue_wins_across_multiple_issues() -> None:
    assert finalize_overall_risk(
        "medium", [{"severity": "high"}, {"severity": "critical"}, {"severity": "low"}]
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
    assert classification_display({"application_scenario": "contract", "classification_source": "legacy"}) == "历史记录 / 通用工程合同"


def test_archived_legacy_bidding_display_is_a_strict_contract() -> None:
    assert classification_display({"application_scenario": "bidding", "classification_source": "archived_legacy"}) == "历史记录 / 招投标资料已归档，无法按旧场景重审"
