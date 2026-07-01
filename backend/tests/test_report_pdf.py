"""report_pdf 服务单测：覆盖 HTML 模板渲染（不依赖 weasyprint 系统库）。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.report_pdf import _build_html, render_report_pdf


def _fake_record():
    return SimpleNamespace(
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
