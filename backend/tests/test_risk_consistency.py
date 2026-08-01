"""任务11：服务端风险等级最终化与快照保存的集成测试。

契约（见 docs/designs/2026-08-01-contract-inspection-type-and-quota-design.md
「风险报告一致性校验」）：

- ``overall_risk`` 只允许 low/medium/high/critical；非法值/缺失值按问题最高严重等级推导。
- 服务端按 issues 最高严重等级提升风险，不降低风险（标签冲突时取更高）。
- 所有 API、历史、PDF 使用服务端最终归一化的风险等级，不直接消费模型原始标签。
- 法规版本切换不改变旧报告来源快照。
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.models.knowledge import InspectionRecord  # noqa: E402
from app.services import inspection_runner  # noqa: E402
from app.services.report_pdf import _build_html  # noqa: E402
from goulong_auth.models import User  # noqa: E402


async def _create_test_user() -> uuid.UUID:
    """创建一个真实用户，满足 InspectionRecord.user_id 外键约束。"""
    async with async_session() as session:
        user = User(
            email=f"risk-{uuid.uuid4().hex[:8]}@test.com",
            nickname="risk_test_user",
            hashed_password="x",
        )
        session.add(user)
        await session.commit()
        return user.id


def _fake_classification():
    """稳定的分类结果，避免任务11测试触发真实分类器。"""
    return SimpleNamespace(
        engineering_type_key="general-engineering",
        contract_type_key="other",
        confidence="high",
        evidence=["测试证据"],
        source="rule",
        requires_confirmation=False,
    )


def _fake_regulation_base(*, rule_package_keys=None, sources=None):
    return {
        "snippets": [{"content": "合同审查依据"}],
        "sources": sources if sources is not None else [{"title": "民法典合同编"}],
        "rule_package_keys": rule_package_keys or ["pkg-general:v1"],
        "rule_package_key": (rule_package_keys or ["pkg-general:v1"])[0],
    }


def _patch_pipeline(monkeypatch, *, overall_risk, issues, regulation_base=None):
    """统一替换审查流水线的三个外部依赖。"""
    monkeypatch.setattr(
        inspection_runner,
        "classify_inspection_document",
        lambda **kwargs: _async_return(_fake_classification()),
    )
    monkeypatch.setattr(
        inspection_runner,
        "retrieve_regulation_base",
        lambda *a, **kw: _async_return(regulation_base or _fake_regulation_base()),
    )

    async def fake_run_inspection(document_text: str, deps):
        return SimpleNamespace(
            overall_risk=overall_risk,
            summary="测试摘要",
            issues=issues,
            regulation_refs=["民法典合同编"],
        )

    monkeypatch.setattr(inspection_runner, "run_inspection", fake_run_inspection)


async def _async_return(value):
    return value


async def _run_execute_inspection(monkeypatch, *, overall_risk, issues, regulation_base=None) -> tuple[object, InspectionRecord]:
    user_id = await _create_test_user()
    _patch_pipeline(
        monkeypatch,
        overall_risk=overall_risk,
        issues=issues,
        regulation_base=regulation_base,
    )
    async with async_session() as session:
        report = await inspection_runner.execute_inspection(
            db=session,
            user_id=user_id,
            document_name="测试合同.txt",
            text="甲乙双方签订工程施工合同，约定违约责任条款。",
            project_id="default",
            application_scenario="contract",
        )
        record = await session.get(InspectionRecord, report.id)
    return report, record


@pytest.mark.asyncio
async def test_label_conflict_model_lower_than_issue_is_raised(monkeypatch):
    """模型标签低于问题最高严重等级时，服务端按问题等级提升风险。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk="low",
        issues=[{"title": "致命缺陷", "severity": "critical"}],
    )
    assert report.overall_risk == "critical"
    assert record.overall_risk == "critical"


@pytest.mark.asyncio
async def test_missing_model_label_falls_back_to_issue_severity(monkeypatch):
    """模型返回 None/缺失标签时，按问题最高严重等级推导。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk=None,
        issues=[{"title": "高风险条款", "severity": "high"}],
    )
    assert report.overall_risk == "high"
    assert record.overall_risk == "high"


@pytest.mark.asyncio
async def test_missing_label_without_issues_defaults_to_low(monkeypatch):
    """模型标签缺失且无问题时，归一化为 low。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk=None,
        issues=[],
    )
    assert report.overall_risk == "low"
    assert record.overall_risk == "low"


@pytest.mark.asyncio
async def test_unknown_model_label_is_replaced_by_issue_severity(monkeypatch):
    """模型返回未知标签（非白名单）时，按问题等级推导。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk="unknown",
        issues=[{"title": "中风险", "severity": "medium"}],
    )
    assert report.overall_risk == "medium"
    assert record.overall_risk == "medium"


@pytest.mark.asyncio
async def test_higher_model_label_is_never_lowered_by_issues(monkeypatch):
    """服务端只提升不降低：模型 critical 不应被低等级 issue 拉低。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk="critical",
        issues=[{"title": "中等", "severity": "medium"}],
    )
    assert report.overall_risk == "critical"
    assert record.overall_risk == "critical"


@pytest.mark.asyncio
async def test_history_snapshot_and_pdf_use_final_risk_label(monkeypatch):
    """历史详情与 PDF 必须使用服务端最终归一化后的风险等级。"""
    report, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk="low",
        issues=[{"title": "严重违约", "severity": "critical"}],
    )
    # 落库后的 record 直接喂给 PDF 渲染器，应得到归一化后的中文标签。
    html = _build_html(record)
    assert "严重风险" in html  # critical 中文标签
    assert "critical" not in html  # 不应泄露原始英文标签


def test_pdf_renders_unknown_legacy_risk_as_neutral_label():
    """历史脏数据出现非白名单值时，PDF 不应直接渲染原始字符串。"""
    record = SimpleNamespace(
        document_name="历史报告.txt",
        document_type_label="合同",
        overall_risk="pending",  # 历史脏数据：非白名单
        summary="等待审查",
        regulation_refs=[],
        issues=[],
        created_at=None,
    )
    html = _build_html(record)
    assert "未知" in html
    assert "pending" not in html.lower()


@pytest.mark.asyncio
async def test_regulation_version_switch_keeps_legacy_report_snapshot(monkeypatch):
    """法规版本切换后，旧报告的规则包与来源快照不应被覆盖。"""
    legacy_keys = ["pkg-general:v1"]
    legacy_sources = [{"title": "民法典合同编（旧版本）"}]
    regulation_base = _fake_regulation_base(
        rule_package_keys=legacy_keys, sources=legacy_sources,
    )
    _, record = await _run_execute_inspection(
        monkeypatch,
        overall_risk="low",
        issues=[],
        regulation_base=regulation_base,
    )
    saved_id = record.id
    original_keys_snapshot = list(record.rule_package_keys_snapshot or [])
    original_sources_snapshot = list(record.knowledge_sources_snapshot or [])

    # 模拟法规升级：新版本包切换，但旧报告读取不得漂移。
    async with async_session() as session:
        restored = await session.get(InspectionRecord, saved_id)

    assert restored is not None
    assert list(restored.rule_package_keys_snapshot or []) == original_keys_snapshot
    assert restored.rule_package_keys_snapshot == legacy_keys
    assert list(restored.knowledge_sources_snapshot or []) == original_sources_snapshot
    assert restored.knowledge_sources_snapshot == legacy_sources
