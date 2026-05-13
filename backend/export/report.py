from __future__ import annotations

from io import BytesIO
from datetime import date

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as rl_colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_NAVY  = RGBColor(0x1A, 0x3A, 0x5C)
_TEAL  = RGBColor(0x08, 0x91, 0xB2)
_GRAY  = RGBColor(0x64, 0x74, 0x8B)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

_METHODOLOGY_LINES = [
    "Data Sources: myVASS, CCMS, KPM, NCDC",
    "Z-Score Standard: WHO 2006 Child Growth Standards (WHO_Anthro v3.2.2)",
    "Classification: WAZ<-2 SD=Underweight; HAZ<-2 SD=Stunted; WHZ<-2 SD=Wasted",
    "Quality Rules: KKM-defined completeness, consistency, and range checks",
    "Anomaly Detection: IsolationForest (contamination=0.05) + 3x IQR fence",
    "Pattern Classification: Decimal shift (x10/div10), digit transposition, column swap",
    "Risk Scoring: Weighted flag-sum (Stunting x25, Wasting x30, Underweight x20)",
    "KPI Benchmarks: NPAN 2021-2025 national targets; WHO Global Targets 2025",
    "Trend Analysis: Ordinary least-squares linear regression (>=3 periods per district)",
    "Trajectory: Forecasts 4 periods ahead; On Track if forecast <= NPAN target",
]


# == PPTX ======================================================================

def build_pptx_bytes(
    eda_result: dict,
    narrative: dict,
    kpi_result: dict | None = None,
) -> bytes:
    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    _add_title_slide(prs, blank, eda_result)
    _add_quality_slide(prs, blank, eda_result)
    _add_narrative_slide(prs, blank, narrative)
    _add_recommendations_slide(prs, blank, narrative)

    if kpi_result:
        _add_indicator_table_slide(prs, blank, kpi_result)
        _add_methodology_slide(prs, blank)

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _bg(slide, r, g, b):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(r, g, b)


def _txt(slide, text, l, t, w, h, size=18, bold=False, color=None, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color if color is not None else _WHITE


def _add_title_slide(prs, layout, eda):
    s = prs.slides.add_slide(layout)
    _bg(s, 0x1A, 0x3A, 0x5C)
    summary = eda.get("summary", {})
    source  = summary.get("source_type", "Unknown").upper()
    rows    = summary.get("total_rows", "N/A")
    today   = date.today().strftime("%d %B %Y")
    _txt(s, "SmartDQC", 0.5, 0.4, 8, 0.5, size=14, bold=True, color=_TEAL)
    _txt(s, "Data Quality Report", 0.5, 0.9, 10, 1.0, size=36, bold=True)
    _txt(s, f"Source: {source}  |  Records: {rows}  |  {today}",
         0.5, 2.0, 11, 0.5, size=14, color=RGBColor(0xA8, 0xC8, 0xD8))


def _add_quality_slide(prs, layout, eda):
    s = prs.slides.add_slide(layout)
    _bg(s, 0xF0, 0xF7, 0xFA)
    _txt(s, "Data Quality Overview", 0.5, 0.3, 10, 0.6,
         size=24, bold=True, color=_NAVY)
    quality    = eda.get("quality", {})
    indicators = eda.get("indicators", {})
    outliers   = eda.get("outliers", {})
    lines = [
        f"Overall Quality Score : {quality.get('overall_score', 'N/A')}",
        f"Completeness          : {quality.get('overall_completeness', 'N/A')}%",
        f"Missing Data Rate     : {quality.get('missing_rate', 'N/A')}",
        f"Outliers Flagged      : {outliers.get('total_flagged', 'N/A')}",
    ]
    for flag in ["stunting_rate", "wasting_rate", "underweight_rate", "overweight_rate"]:
        if flag in indicators:
            label = flag.replace("_rate", "").capitalize()
            val   = indicators[flag]
            if isinstance(val, float):
                val = round(val * 100, 1)
            lines.append(f"{label:22s}: {val}%")
    _txt(s, "\n".join(lines), 0.5, 1.1, 12, 5.5, size=14, color=_NAVY)


def _add_narrative_slide(prs, layout, narrative):
    s = prs.slides.add_slide(layout)
    _bg(s, 0x1A, 0x3A, 0x5C)
    _txt(s, "AI Analysis Summary", 0.5, 0.3, 10, 0.6, size=24, bold=True)
    exec_sum = narrative.get("executive_summary", {})
    _txt(s, "Bahasa Malaysia", 0.5, 1.1, 5, 0.4, size=11, bold=True, color=_TEAL)
    _txt(s, exec_sum.get("bm", "-"), 0.5, 1.55, 5.8, 4.5, size=12)
    _txt(s, "English", 6.9, 1.1, 5, 0.4, size=11, bold=True, color=_TEAL)
    _txt(s, exec_sum.get("en", "-"), 6.9, 1.55, 5.8, 4.5, size=12)


def _add_recommendations_slide(prs, layout, narrative):
    s = prs.slides.add_slide(layout)
    _bg(s, 0xF0, 0xF7, 0xFA)
    _txt(s, "Recommendations", 0.5, 0.3, 10, 0.6,
         size=24, bold=True, color=_NAVY)
    for i, rec in enumerate(narrative.get("recommendations", [])[:3]):
        y = 1.1 + i * 1.9
        priority = rec.get("priority", "").upper()
        _txt(s, f"[{priority}] {rec.get('action', '')}", 0.5, y, 12, 0.45,
             size=13, bold=True, color=_NAVY)
        _txt(s, rec.get("en", ""), 0.5, y + 0.45, 12, 1.3, size=11, color=_GRAY)


def _add_indicator_table_slide(prs, layout, kpi_result: dict):
    """Add a per-district indicator rate table slide."""
    breakdown = kpi_result.get("district_breakdown") or []
    if not breakdown:
        return

    s = prs.slides.add_slide(layout)
    _bg(s, 0xF0, 0xF7, 0xFA)
    _txt(s, "Indicator Summary by District", 0.5, 0.2, 12, 0.55,
         size=20, bold=True, color=_NAVY)

    headers    = ["District", "N", "Stunting %", "Wasting %", "Underweight %", "Overweight %"]
    table_rows = [headers]
    for row in breakdown[:10]:
        table_rows.append([
            str(row.get("district", "")),
            str(row.get("n_records", "")),
            str(row.get("stunting_rate_rate",    "-")),
            str(row.get("wasting_rate_rate",     "-")),
            str(row.get("underweight_rate_rate", "-")),
            str(row.get("overweight_rate_rate",  "-")),
        ])

    n_rows = len(table_rows)
    n_cols = len(headers)
    tbl    = s.shapes.add_table(
        n_rows, n_cols,
        Inches(0.4), Inches(0.9),
        Inches(12.5), Inches(min(0.45 * n_rows, 6.3)),
    ).table

    for r_idx, row_data in enumerate(table_rows):
        for c_idx, cell_val in enumerate(row_data):
            cell = tbl.cell(r_idx, c_idx)
            tf   = cell.text_frame
            tf.clear()
            para = tf.paragraphs[0]
            run  = para.add_run()
            run.text      = cell_val
            run.font.size = Pt(11 if r_idx == 0 else 10)
            run.font.bold = (r_idx == 0)
            if r_idx == 0:
                run.font.color.rgb = _WHITE
                cell.fill.solid()
                cell.fill.fore_color.rgb = _NAVY
            elif r_idx % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(0xF0, 0xF7, 0xFA)


def _add_methodology_slide(prs, layout):
    """Add a methodology appendix slide."""
    s = prs.slides.add_slide(layout)
    _bg(s, 0x1A, 0x3A, 0x5C)
    _txt(s, "Methodology Appendix", 0.5, 0.3, 12, 0.55, size=22, bold=True)
    body = "\n".join(f"- {line}" for line in _METHODOLOGY_LINES)
    _txt(s, body, 0.5, 1.05, 12.3, 6.0, size=11)


# == PDF =======================================================================

def build_pdf_bytes(
    eda_result: dict,
    narrative: dict,
    kpi_result: dict | None = None,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h1  = ParagraphStyle("H1",  parent=styles["Heading1"],  fontSize=20,
                         textColor=rl_colors.HexColor("#1A3A5C"))
    h2  = ParagraphStyle("H2",  parent=styles["Heading2"],  fontSize=14,
                         textColor=rl_colors.HexColor("#0891B2"))
    bod = ParagraphStyle("Body", parent=styles["Normal"],   fontSize=11, leading=16)
    sm  = ParagraphStyle("Sm",   parent=styles["Normal"],   fontSize=9,
                         textColor=rl_colors.HexColor("#64748B"))

    story = []
    today   = date.today().strftime("%d %B %Y")
    summary = eda_result.get("summary", {})

    story.append(Paragraph("SmartDQC - Data Quality Report", h1))
    story.append(Paragraph(
        f"Source: {summary.get('source_type','N/A').upper()}  |  "
        f"Records: {summary.get('total_rows','N/A')}  |  {today}", sm))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=rl_colors.HexColor("#0891B2")))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Data Quality Overview", h2))
    quality    = eda_result.get("quality", {})
    indicators = eda_result.get("indicators", {})
    outliers   = eda_result.get("outliers", {})
    q_rows = [
        ["Metric", "Value"],
        ["Overall Quality Score",  str(quality.get("overall_score", "N/A"))],
        ["Completeness",           f"{quality.get('overall_completeness','N/A')}%"],
        ["Missing Data Rate",      str(quality.get("missing_rate", "N/A"))],
        ["Outliers Flagged",       str(outliers.get("total_flagged", "N/A"))],
    ]
    for flag in ["stunting_rate", "wasting_rate", "underweight_rate", "overweight_rate"]:
        if flag in indicators:
            val = indicators[flag]
            if isinstance(val, float):
                val = round(val * 100, 1)
            q_rows.append([flag.replace("_rate", "").capitalize(), f"{val}%"])

    tbl = Table(q_rows, colWidths=[10*cm, 6*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), rl_colors.HexColor("#1A3A5C")),
        ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.white),
        ("FONTSIZE",       (0, 0), (-1, -1), 10),
        ("GRID",           (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2EEF4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl_colors.white, rl_colors.HexColor("#F0F7FA")]),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.6*cm))

    exec_sum = narrative.get("executive_summary", {})
    if exec_sum:
        story.append(Paragraph("AI Analysis Summary", h2))
        story.append(Paragraph(
            f"<b>Bahasa Malaysia</b><br/>{exec_sum.get('bm','')}", bod))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            f"<b>English</b><br/>{exec_sum.get('en','')}", bod))
        story.append(Spacer(1, 0.6*cm))

    recs = narrative.get("recommendations", [])
    if recs:
        story.append(Paragraph("Recommendations", h2))
        for rec in recs[:5]:
            story.append(Paragraph(
                f"<b>[{rec.get('priority','').upper()}] {rec.get('action','')}</b>", bod))
            story.append(Paragraph(rec.get("en", ""), bod))
            story.append(Spacer(1, 0.2*cm))

    if kpi_result:
        _build_pdf_indicator_table(story, kpi_result, h2, sm)
        _build_pdf_methodology_appendix(story, h2, sm)

    doc.build(story)
    return buf.getvalue()


def _build_pdf_indicator_table(story: list, kpi_result: dict, h2, sm):
    breakdown = kpi_result.get("district_breakdown") or []
    if not breakdown:
        return

    story.append(Paragraph("Indicator Summary by District", h2))
    headers    = ["District", "N", "Stunting %", "Wasting %", "Underweight %", "Overweight %"]
    table_data = [headers]
    for row in breakdown:
        table_data.append([
            str(row.get("district", "")),
            str(row.get("n_records", "")),
            str(row.get("stunting_rate_rate",    "-")),
            str(row.get("wasting_rate_rate",     "-")),
            str(row.get("underweight_rate_rate", "-")),
            str(row.get("overweight_rate_rate",  "-")),
        ])

    tbl = Table(table_data, colWidths=[4*cm, 1.5*cm, 3*cm, 2.5*cm, 3.5*cm, 3*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), rl_colors.HexColor("#1A3A5C")),
        ("TEXTCOLOR",      (0, 0), (-1, 0), rl_colors.white),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("GRID",           (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#E2EEF4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl_colors.white, rl_colors.HexColor("#F0F7FA")]),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.6*cm))


def _build_pdf_methodology_appendix(story: list, h2, sm):
    story.append(Paragraph("Methodology Appendix", h2))
    for line in _METHODOLOGY_LINES:
        story.append(Paragraph(f"- {line}", sm))
    story.append(Spacer(1, 0.3*cm))
