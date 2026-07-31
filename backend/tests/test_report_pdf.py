"""report_pdf 服务单测：覆盖 HTML 模板渲染（不依赖 weasyprint 系统库）。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.report_pdf import (
    _build_html,
    _fallback_pdf,
    _wrap_text,
    render_report_pdf,
)


def _fake_record(**overrides):
    base = dict(
        document_name="测试合同.docx",
        document_type_label="合同",
        overall_risk="high",
        summary="存在 2 处风险点，建议补充验收标准。",
        regulation_refs=["民法典合同编", "合同审查依据"],
        issues=[
            {
                "location": "第三条 付款条款",
                "severity": "error",
                "category": "隐含风险",
                "original": "甲方应在验收后付款。",
                "suggestion": "明确验收标准与付款时限。",
                "regulation_ref": "民法典合同编",
            },
            {
                "title": "条款不完整",
                "severity": "warning",
                "suggestion": "补充验收标准。",
            },
        ],
        created_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_html_contains_design_elements():
    """HTML 模板应包含 Imperial Circuitry 设计元素与全部报告数据。"""
    html = _build_html(_fake_record())

    assert "REF.ZD-REPORT" in html
    assert "测试合同 审查报告" in html
    assert "句龙 · 照胆" in html
    assert "测试合同.docx" in html
    assert "合同" in html
    assert "较高风险" in html  # high 风险中文标签
    assert "存在 2 处风险点" in html
    assert "民法典合同编" in html
    assert "第三条 付款条款" in html  # 用 location 作为标题
    assert "条款不完整" in html  # 兼容旧 title 字段
    assert "明确验收标准" in html  # suggestion
    assert "@page" in html  # A4 页面规则
    assert "counter(page)" in html  # 页码


def test_build_html_escapes_special_chars():
    """HTML 应转义特殊字符，防注入。"""
    record = SimpleNamespace(
        document_name="<script>.docx",
        document_type_label="合同",
        overall_risk="low",
        summary="<b>摘要</b>",
        regulation_refs=[],
        issues=[],
        created_at=None,
    )
    html = _build_html(record)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_build_html_empty_issues():
    """无问题时应显示空状态提示。"""
    record = SimpleNamespace(
        document_name="ok.docx",
        document_type_label="合同",
        overall_risk="low",
        summary="无风险",
        regulation_refs=None,
        issues=None,
        created_at=None,
    )
    html = _build_html(record)
    assert "未发现明确风险" in html
    assert "低风险" in html


def test_render_report_pdf_fallback_returns_pdf_magic():
    """weasyprint 不可用时应回退裸 PDF，仍以 %PDF 开头。"""
    with patch("app.services.report_pdf._fallback_pdf") as mock_fallback:
        mock_fallback.return_value = b"%PDF-1.4-fallback"
        # 强制 weasyprint import 失败，走 fallback
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise ImportError("no weasyprint in test env")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            result = render_report_pdf(_fake_record())
        finally:
            builtins.__import__ = real_import

        assert result.startswith(b"%PDF")
        mock_fallback.assert_called_once()


def test_wrap_text_breaks_long_cjk_line():
    """超长中文行应按宽度折行，避免右侧裁切。"""
    long = "甲" * 80
    parts = _wrap_text(long, max_units=42.0)
    assert len(parts) >= 2
    assert "".join(parts) == long
    assert all(len(p) <= 42 for p in parts)


def test_wrap_text_preserves_explicit_newlines():
    parts = _wrap_text("第一行\n第二行", max_units=42.0)
    assert parts == ["第一行", "第二行"]


def _extract_fallback_text(pdf: bytes) -> str:
    """从 fallback PDF 的 Tj hex 内容流还原全文（忽略折行）。"""
    import re

    chunks = re.findall(rb"<([0-9A-F]+)> Tj", pdf)
    return "".join(bytes.fromhex(chunk.decode("ascii")).decode("utf-16-be") for chunk in chunks)


def test_fallback_pdf_includes_full_long_suggestion():
    """长建议文本应完整写入 PDF 内容流（折行后拼接仍完整）。"""
    long_suggestion = (
        "删除“乙方不得提出任何异议”，改为“调整范围应经双方书面确认；"
        "因此增加或减少的工程量，应按本合同约定价款相应调整工期和结算金额。”"
        "并同步明确变更审批流程与时限。"
    )
    record = _fake_record(
        summary="本合同权利义务严重失衡，多处条款赋予甲方单方决定权并免除其基本义务，"
        "将付款、变更、解除、安全等核心风险过度转嫁乙方，违约金畸高且存在逻辑矛盾，整体法律风险极高。",
        issues=[
            {
                "location": "2.2",
                "severity": "error",
                "suggestion": long_suggestion,
            }
        ]
        + [
            {
                "location": f"条款{i}",
                "severity": "warning",
                "suggestion": f"建议修订条款{i}，明确双方权利义务与违约责任承担方式。",
            }
            for i in range(20)
        ],
    )
    pdf = _fallback_pdf(record)
    assert pdf.startswith(b"%PDF")
    text = _extract_fallback_text(pdf)
    assert long_suggestion in text
    assert "较高风险" in text  # 风险等级中文化
    assert "建议：删除“乙方不得提出任何异议”" in text
    # 长列表应触发多页
    assert b"/Count 2 >>" in pdf or pdf.count(b"/Type /Page ") >= 2
