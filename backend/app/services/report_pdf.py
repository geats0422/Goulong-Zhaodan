from __future__ import annotations

from datetime import datetime
from pathlib import Path

_RISK_STYLE: dict[str, tuple[str, str]] = {
    "low": ("低风险", "#2e7d32"),
    "medium": ("中等风险", "#d4882a"),
    "high": ("较高风险", "#c0392b"),
    "critical": ("严重风险", "#7b1f1f"),
}

_SEVERITY_STYLE: dict[str, tuple[str, str]] = {
    "error": ("错误", "#c0392b"),
    "warning": ("警告", "#d4882a"),
    "info": ("提示", "#2a6c8f"),
}

_CSS = """
@page {
  size: A4;
  margin: 1.6cm 1.8cm 2cm;
  @bottom-center {
    content: "句龙 · 照胆 · 智能合规初审  |  第 " counter(page) " / " counter(pages) " 页";
    font-family: "JetBrains Mono","Consolas",monospace;
    font-size: 8.5px;
    color: #99907c;
    letter-spacing: 0.06em;
  }
}
* { box-sizing: border-box; }
body {
  font-family: "Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
  color: #1f1a12;
  background: #fffaf0;
  font-size: 11px;
  line-height: 1.7;
  margin: 0;
}
.report-ref {
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 9px;
  color: #9b7416;
  letter-spacing: 0.18em;
}
h1.report-title {
  font-family: "Noto Serif SC","Source Han Serif SC","Songti SC",serif;
  font-size: 26px;
  font-weight: 700;
  color: #1f1a12;
  margin: 6px 0 4px;
  letter-spacing: 0.02em;
}
.report-subtitle { color: #66563a; font-size: 11px; margin: 0 0 14px; }
.gold-rule {
  height: 2px;
  margin: 14px 0;
  background: linear-gradient(90deg, #9b7416, rgba(155,116,22,0.15) 70%, transparent);
}
.meta-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
.meta-table td { border: 1px solid rgba(155,116,22,0.22); padding: 9px 12px; vertical-align: middle; }
.meta-label {
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 8.5px;
  color: #9b7416;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  display: block;
  margin-bottom: 3px;
}
.meta-value { color: #1f1a12; font-size: 11px; }
.section-label {
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 9px;
  color: #9b7416;
  letter-spacing: 0.16em;
}
h2.section-title {
  font-family: "Noto Serif SC","Source Han Serif SC","Songti SC",serif;
  font-size: 16px;
  color: #1f1a12;
  margin: 4px 0 10px;
}
.badge {
  display: inline-block;
  padding: 3px 10px;
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #fffaf0;
}
.chip {
  display: inline-block;
  padding: 3px 9px;
  margin: 0 5px 5px 0;
  border: 1px solid rgba(155,116,22,0.35);
  color: #66563a;
  font-size: 10px;
  background: rgba(155,116,22,0.06);
}
.issue-card {
  border: 1px solid rgba(155,116,22,0.22);
  padding: 12px 14px;
  margin-bottom: 10px;
  page-break-inside: avoid;
}
.issue-title {
  font-family: "Noto Serif SC","Source Han Serif SC","Songti SC",serif;
  font-size: 13px;
  font-weight: 600;
  color: #1f1a12;
}
.issue-meta { font-size: 10px; color: #66563a; margin-top: 3px; }
.issue-original {
  border-left: 2px solid #9b7416;
  padding: 5px 10px;
  margin: 6px 0;
  background: rgba(155,116,22,0.05);
  color: #3a3220;
  font-size: 10px;
}
.issue-suggestion { font-size: 10.5px; color: #1f1a12; margin-top: 4px; }
.issue-ref {
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 9px;
  color: #9b7416;
  margin-top: 5px;
}
.summary-body { color: #1f1a12; font-size: 11px; line-height: 1.8; }
.empty-note { color: #66563a; font-size: 11px; padding: 14px; border: 1px dashed rgba(155,116,22,0.3); }
.report-footer-mark {
  margin-top: 22px;
  padding-top: 10px;
  border-top: 1px solid rgba(155,116,22,0.18);
  font-family: "JetBrains Mono","Consolas",monospace;
  font-size: 8.5px;
  color: #99907c;
  letter-spacing: 0.1em;
  text-align: center;
}
"""


def _strip_ext(document_name: str) -> str:
    suffix = Path(document_name).suffix
    return document_name[: -len(suffix)] if suffix else document_name


def _esc(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_issues(issues: list[dict] | None) -> str:
    if not issues:
        return '<div class="empty-note">未发现明确风险。</div>'
    parts: list[str] = []
    for issue in issues:
        title = issue.get("location") or issue.get("title") or "未命名问题"
        sev = (issue.get("severity") or "info").lower()
        # 任务11：issue severity 与 overall_risk 共享 low/medium/high/critical 术语体系，
        # 命中风险样式时渲染中文标签；旧 error/warning/info 仍按 severity 样式渲染；
        # 其余未知值兜底为「提示」，不向用户泄露未经归一化的原始字符串。
        if sev in _RISK_STYLE:
            sev_label, sev_color = _RISK_STYLE[sev]
        else:
            sev_label, sev_color = _SEVERITY_STYLE.get(sev, ("提示", "#66563a"))
        category = issue.get("category") or ""
        original = issue.get("original") or ""
        suggestion = issue.get("suggestion") or ""
        ref = issue.get("regulation_ref") or ""
        card = f'<div class="issue-card"><div><span class="issue-title">{_esc(title)}</span>'
        card += f' <span class="badge" style="background:{sev_color}">{_esc(sev_label)}</span></div>'
        if category:
            card += f'<div class="issue-meta">分类：{_esc(category)}</div>'
        if original:
            card += f'<div class="issue-original">原文：{_esc(original)}</div>'
        if suggestion:
            card += f'<div class="issue-suggestion">建议：{_esc(suggestion)}</div>'
        if ref:
            card += f'<div class="issue-ref">依据 · {_esc(ref)}</div>'
        card += "</div>"
        parts.append(card)
    return "".join(parts)


def _build_html(record) -> str:
    title = f"{_strip_ext(record.document_name)} 审查报告"
    risk = (record.overall_risk or "").lower()
    # 任务11契约：UI/API/PDF 不直接消费未经服务端归一化的风险标签。
    # 非白名单值（历史脏数据、pending 等）统一展示为中性「未知」标签，避免泄露原始字符串。
    if risk not in _RISK_STYLE:
        risk_label, risk_color = "未知", "#66563a"
    else:
        risk_label, risk_color = _RISK_STYLE[risk]
    refs = record.regulation_refs or []
    created = record.created_at
    if isinstance(created, datetime):
        created_str = created.strftime("%Y-%m-%d %H:%M")
    else:
        created_str = str(created) if created else "—"
    refs_html = "".join(f'<span class="chip">{_esc(r)}</span>' for r in refs) or '<span class="chip">无</span>'
    issues_html = _render_issues(record.issues)
    issue_count = len(record.issues or [])
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
  <div class="report-ref">REF.ZD-REPORT · 智能合规初审</div>
  <h1 class="report-title">{_esc(title)}</h1>
  <p class="report-subtitle">句龙 · 照胆 · 业务提交前审查 Agent</p>
  <div class="gold-rule"></div>
  <table class="meta-table"><tr>
    <td style="width:48%"><span class="meta-label">文件名称</span><span class="meta-value">{_esc(record.document_name)}</span></td>
    <td style="width:27%"><span class="meta-label">审查类型</span><span class="meta-value">{_esc(record.document_type_label)}</span></td>
    <td style="width:25%"><span class="meta-label">风险等级</span><span class="badge" style="background:{risk_color}">{_esc(risk_label)}</span></td>
  </tr></table>
  <div style="margin-top:8px"><span class="meta-label">生成时间</span> <span class="meta-value">{_esc(created_str)}</span></div>
  <div class="gold-rule"></div>
  <div class="section-label">SUMMARY · 审查摘要</div>
  <h2 class="section-title">总体评价</h2>
  <div class="summary-body">{_esc(record.summary or "—")}</div>
  <div class="gold-rule"></div>
  <div class="section-label">REGULATION · 引用依据</div>
  <h2 class="section-title">法规与知识库来源</h2>
  <div>{refs_html}</div>
  <div class="gold-rule"></div>
  <div class="section-label">ISSUES · 问题清单（{issue_count}）</div>
  <h2 class="section-title">风险点与修改建议</h2>
  {issues_html}
  <div class="report-footer-mark">SECURED BY TIGER TALLY PROTOCOL · 句龙 · 照胆</div>
</body></html>"""


def _char_width_units(ch: str) -> float:
    """估算字符显示宽度（CJK≈1，ASCII≈0.5）。"""
    code = ord(ch)
    if code <= 0x7F:
        return 0.5
    if 0xFF61 <= code <= 0xFF9F:
        return 0.5
    return 1.0


def _wrap_text(text: str, max_units: float = 42.0) -> list[str]:
    """按估算宽度折行，保证长中文/长句不超出 PDF 页边。"""
    if not text:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    width = 0.0
    for ch in str(text).replace("\r\n", "\n").replace("\r", "\n"):
        if ch == "\n":
            lines.append("".join(current))
            current = []
            width = 0.0
            continue
        unit = _char_width_units(ch)
        if current and width + unit > max_units:
            lines.append("".join(current))
            current = [ch]
            width = unit
        else:
            current.append(ch)
            width += unit
    lines.append("".join(current))
    return lines


def _risk_label(risk: str | None) -> str:
    key = (risk or "").lower()
    # 非白名单值统一展示为「未知」，避免向用户泄露未经服务端归一化的原始标签。
    return _RISK_STYLE.get(key, ("未知", ""))[0]


def _severity_label(severity: str | None) -> str:
    key = (severity or "").lower()
    # 与 _render_issues 一致：风险样式优先，其次 severity 样式，未知值兜底为「提示」。
    if key in _RISK_STYLE:
        return _RISK_STYLE[key][0]
    return _SEVERITY_STYLE.get(key, ("提示", ""))[0]


def _fallback_pdf(record) -> bytes:
    """无 weasyprint 系统依赖时的兜底：裸 PDF 文本流（支持折行与多页）。"""
    title = f"{_strip_ext(record.document_name)} 审查报告"
    raw_lines = [
        title,
        f"文件名称：{record.document_name}",
        f"审查类型：{record.document_type_label or '—'}",
        f"风险等级：{_risk_label(record.overall_risk)}",
        f"摘要：{record.summary or '—'}",
        f"引用依据：{('、'.join(record.regulation_refs or [])) or '无'}",
        "问题列表：",
    ]
    if record.issues:
        for idx, issue in enumerate(record.issues, start=1):
            label = issue.get("location") or issue.get("title") or "未命名问题"
            severity = _severity_label(issue.get("severity"))
            raw_lines.append(f"{idx}. {label} · {severity}")
            if issue.get("original"):
                raw_lines.append(f"   原文：{issue['original']}")
            if issue.get("suggestion"):
                raw_lines.append(f"   建议：{issue['suggestion']}")
            if issue.get("regulation_ref"):
                raw_lines.append(f"   依据：{issue['regulation_ref']}")
    else:
        raw_lines.append("未发现明确风险。")

    wrapped: list[str] = []
    for line in raw_lines:
        wrapped.extend(_wrap_text(line, max_units=42.0))

    def _hex(value: str) -> str:
        return value.encode("utf-16-be", errors="replace").hex().upper()

    # A4: 595×842；左右边距 50；上下可用区约 780→60
    page_top = 780.0
    page_bottom = 56.0
    line_height = 16.0
    lines_per_page = max(1, int((page_top - page_bottom) / line_height))

    page_chunks: list[list[str]] = [
        wrapped[i : i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)
    ] or [[""]]

    # 对象布局：1 Catalog, 2 Pages, 3 Font, 4 CIDFont, 然后每页 Page+Content
    font_obj = (
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
        b"/Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"
    )
    cid_obj = (
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
        b"/DW 1000 >>"
    )

    page_objects: list[bytes] = []
    content_objects: list[bytes] = []
    page_ids: list[int] = []
    # object ids: 1=catalog 2=pages 3=font 4=cidfont; pages start at 5
    next_id = 5
    for chunk in page_chunks:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        text_ops = ["BT", "/F1 11 Tf", f"50 {page_top:.0f} Td"]
        for index, line in enumerate(chunk):
            if index:
                text_ops.append(f"0 -{line_height:.0f} Td")
            text_ops.append(f"<{_hex(line)}> Tj")
        text_ops.append("ET")
        stream = "\n".join(text_ops).encode("ascii")
        content_objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_obj = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    catalog_obj = b"<< /Type /Catalog /Pages 2 0 R >>"

    # 按 id 顺序组装：1 catalog, 2 pages, 3 font, 4 cid, then interleaved page/content
    objects_by_id: dict[int, bytes] = {
        1: catalog_obj,
        2: pages_obj,
        3: font_obj,
        4: cid_obj,
    }
    for page_obj, content_obj, page_id in zip(page_objects, content_objects, page_ids):
        objects_by_id[page_id] = page_obj
        objects_by_id[page_id + 1] = content_obj

    max_id = max(objects_by_id)
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0] * (max_id + 1)
    for obj_id in range(1, max_id + 1):
        offsets[obj_id] = len(pdf)
        pdf.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        pdf.extend(objects_by_id[obj_id])
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        pdf.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)


def render_report_pdf(record) -> bytes:
    """渲染审查报告 PDF。优先 weasyprint（HTML 模板），缺系统依赖时回退裸 PDF。"""
    try:
        from weasyprint import HTML

        return HTML(string=_build_html(record)).write_pdf()
    except Exception:
        return _fallback_pdf(record)
