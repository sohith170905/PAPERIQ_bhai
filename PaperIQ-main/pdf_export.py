"""In-memory PDF generation module for PaperIQ using ReportLab + DejaVuSans Unicode TTF fonts."""
from __future__ import annotations

import datetime
import io
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils import clean_plain_text

# ---------------------------------------------------------------------------
# Font Registration (DejaVuSans Unicode TTF family)
# ---------------------------------------------------------------------------
_FONT_REGISTERED = False
_FONT_FAMILY = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_ITALIC = "Helvetica-Oblique"
_FONT_BOLD_ITALIC = "Helvetica-BoldOblique"


def _ensure_unicode_fonts() -> None:
    """Register bundled DejaVuSans Unicode TTF fonts once per process."""
    global _FONT_REGISTERED, _FONT_FAMILY, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC
    if _FONT_REGISTERED:
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "fonts"),
        os.path.join(os.getcwd(), "fonts"),
    ]
    font_dir = next((d for d in candidates if os.path.isdir(d)), None)
    if font_dir:
        reg_path = os.path.join(font_dir, "DejaVuSans.ttf")
        bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
        ital_path = os.path.join(font_dir, "DejaVuSans-Oblique.ttf")
        bi_path = os.path.join(font_dir, "DejaVuSans-BoldOblique.ttf")
        if os.path.isfile(reg_path) and os.path.isfile(bold_path):
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", reg_path))
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
                if os.path.isfile(ital_path):
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", ital_path))
                else:
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", reg_path))
                if os.path.isfile(bi_path):
                    pdfmetrics.registerFont(TTFont("DejaVuSans-BoldOblique", bi_path))
                else:
                    pdfmetrics.registerFont(TTFont("DejaVuSans-BoldOblique", bold_path))

                pdfmetrics.registerFontFamily(
                    "DejaVuSans",
                    normal="DejaVuSans",
                    bold="DejaVuSans-Bold",
                    italic="DejaVuSans-Oblique",
                    boldItalic="DejaVuSans-BoldOblique",
                )
                _FONT_FAMILY = "DejaVuSans"
                _FONT_BOLD = "DejaVuSans-Bold"
                _FONT_ITALIC = "DejaVuSans-Oblique"
                _FONT_BOLD_ITALIC = "DejaVuSans-BoldOblique"
            except Exception:
                pass
    _FONT_REGISTERED = True


def _rl_text(val: Any) -> str:
    """Clean text via clean_plain_text (unescapes HTML entities & strips HTML tags),
    then escape XML control chars (&, <, >) for ReportLab Paragraph XML parser."""
    plain = clean_plain_text(val)
    # Remove control characters except newline and tab
    plain = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", plain)
    return (
        plain.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def sanitize_filename_part(title: Any, max_len: int = 48) -> str:
    """Sanitize a paper title for safe PDF filenames: PaperIQ_<sanitized_title>_<type>_<date>.pdf."""
    clean = clean_plain_text(title)
    clean = re.sub(r"\.(pdf|docx|txt)$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"[^\w\s-]", "", clean)
    clean = re.sub(r"[\s_-]+", "_", clean).strip("_")
    if not clean:
        clean = "Research_Paper"
    if len(clean) > max_len:
        clean = clean[:max_len].rstrip("_")
    return clean


def get_pdf_filename(paper_title: Any, report_type: str, date_str: Optional[str] = None) -> str:
    """Return standardized PDF filename: PaperIQ_{sanitized_title}_{type}_{date}.pdf."""
    sanitized_title = sanitize_filename_part(paper_title)
    sanitized_type = sanitize_filename_part(report_type, max_len=24)
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y%m%d")
    return f"PaperIQ_{sanitized_title}_{sanitized_type}_{date_str}.pdf"


# ---------------------------------------------------------------------------
# Numbered Canvas with Header & Footer ("Page X of Y")
# ---------------------------------------------------------------------------
class _PaperIQNumberedCanvas(canvas.Canvas):
    """Custom ReportLab Canvas that renders a consistent PaperIQ header,
    paper title, generation timestamp, and 'Page X of Y' footer on every page."""

    def __init__(self, *args, **kwargs):
        self._header_title = clean_plain_text(kwargs.pop("header_title", "PaperIQ Report"))
        self._generated_at = clean_plain_text(
            kwargs.pop("generated_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_header_footer(self, page_count: int):
        _ensure_unicode_fonts()
        width, height = A4
        margin_x = 18 * mm

        self.saveState()
        # Header bar
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(margin_x, height - 16 * mm, width - margin_x, height - 16 * mm)

        self.setFont(_FONT_BOLD, 8.5)
        self.setFillColor(colors.HexColor("#0F172A"))
        self.drawString(margin_x, height - 13 * mm, "PaperIQ — AI-Powered Research Insight Analyzer")

        self.setFont(_FONT_FAMILY, 8)
        self.setFillColor(colors.HexColor("#475569"))
        short_title = self._header_title
        if len(short_title) > 52:
            short_title = short_title[:49].rstrip() + "…"
        self.drawRightString(width - margin_x, height - 13 * mm, short_title)

        # Footer bar
        self.line(margin_x, 15 * mm, width - margin_x, 15 * mm)
        self.setFont(_FONT_FAMILY, 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(margin_x, 10.5 * mm, f"Generated: {self._generated_at}")
        self.drawRightString(
            width - margin_x,
            10.5 * mm,
            f"Page {self._pageNumber} of {page_count}",
        )
        self.restoreState()


def _get_styles() -> Dict[str, ParagraphStyle]:
    """Create a cohesive set of ReportLab ParagraphStyles using DejaVuSans."""
    _ensure_unicode_fonts()
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "PIQ_Title",
            parent=base["Title"],
            fontName=_FONT_BOLD,
            fontSize=16,
            leading=21,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "PIQ_Subtitle",
            parent=base["Normal"],
            fontName=_FONT_FAMILY,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "PIQ_H1",
            parent=base["Heading1"],
            fontName=_FONT_BOLD,
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#0369A1"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "PIQ_H2",
            parent=base["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "PIQ_Body",
            parent=base["BodyText"],
            fontName=_FONT_FAMILY,
            fontSize=9.5,
            leading=14,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "PIQ_Bullet",
            parent=base["BodyText"],
            fontName=_FONT_FAMILY,
            fontSize=9.5,
            leading=13.5,
            leftIndent=12,
            firstLineIndent=-8,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "PIQ_Meta",
            parent=base["Normal"],
            fontName=_FONT_ITALIC,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "PIQ_TableHeader",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#FFFFFF"),
        ),
        "table_cell": ParagraphStyle(
            "PIQ_TableCell",
            parent=base["Normal"],
            fontName=_FONT_FAMILY,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#1E293B"),
        ),
        "table_cell_bold": ParagraphStyle(
            "PIQ_TableCellBold",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#0F172A"),
        ),
    }


# ---------------------------------------------------------------------------
# Plotly Chart Export Helpers (with Kaleido PNG + graceful fallback)
# ---------------------------------------------------------------------------
def export_plotly_fig_to_png(
    fig: Optional[go.Figure], width: int = 620, height: int = 340
) -> Optional[bytes]:
    """Export a Plotly Figure to PNG bytes in memory using Kaleido.
    Returns None if Kaleido is unavailable or export fails."""
    if fig is None:
        return None
    for attempt in range(2):
        try:
            return fig.to_image(format="png", width=width, height=height, scale=1.5)
        except Exception:
            if attempt == 0:
                import time
                time.sleep(0.4)
    return None


def _make_single_paper_charts(
    scores_dict: Dict[str, float]
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """Build radar chart and horizontal bar chart PNG bytes for a single paper's 5 dimensions."""
    if not scores_dict:
        return None, None

    labels = list(scores_dict.keys())
    vals = [float(scores_dict[k]) for k in labels]

    radar_png = None
    bar_png = None
    try:
        fig_radar = go.Figure(
            data=go.Scatterpolar(
                r=vals + [vals[0]],
                theta=labels + [labels[0]],
                fill="toself",
                fillcolor="rgba(2, 132, 199, 0.25)",
                line=dict(color="#0284C7", width=2.5),
                marker=dict(color="#0369A1", size=6),
            )
        )
        fig_radar.update_layout(
            title=dict(text="Dimension Score Profile (Radar)", font=dict(size=13, color="#0F172A")),
            polar=dict(
                bgcolor="#F8FAFC",
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9, color="#475569")),
                angularaxis=dict(tickfont=dict(size=10, color="#0F172A")),
            ),
            paper_bgcolor="#FFFFFF",
            margin=dict(l=45, r=45, t=45, b=30),
            showlegend=False,
        )
        radar_png = export_plotly_fig_to_png(fig_radar, width=540, height=320)
    except Exception:
        radar_png = None

    try:
        bar_colors = [
            "#16A34A" if v >= 80 else ("#0284C7" if v >= 65 else ("#D97706" if v >= 50 else "#DC2626"))
            for v in vals
        ]
        fig_bar = go.Figure(
            data=go.Bar(
                x=vals,
                y=labels,
                orientation="h",
                marker_color=bar_colors,
                text=[f"{v:.1f}%" for v in vals],
                textposition="outside",
            )
        )
        fig_bar.update_layout(
            title=dict(text="Dimension Breakdown (Bar Chart)", font=dict(size=13, color="#0F172A")),
            xaxis=dict(range=[0, 112], title="Score (/100)", gridcolor="#E2E8F0"),
            yaxis=dict(autorange="reversed"),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#F8FAFC",
            margin=dict(l=120, r=40, t=45, b=35),
            showlegend=False,
        )
        bar_png = export_plotly_fig_to_png(fig_bar, width=560, height=280)
    except Exception:
        bar_png = None

    return radar_png, bar_png


def _extract_paper_5_dims(rec: Dict[str, Any]) -> List[Tuple[str, float, str]]:
    """Extract the 5 dimension (label, score, default_explanation) tuples from either app.py's
    scores dict ('Language Quality', 'Structural Coherence', 'Argumentation', 'Academic Style', 'Readability'),
    'Dimensions' dict, or flat keys ('readability_score', 'vocab_score', etc.)."""
    raw_scores = (
        rec.get("scores")
        if isinstance(rec.get("scores"), dict)
        else (rec.get("Dimensions") if isinstance(rec.get("Dimensions"), dict) else {})
    )

    # Check if app.py's 5 dimensions are present
    if any(
        k in raw_scores or k in rec
        for k in ("Language Quality", "Structural Coherence", "Argumentation", "Academic Style", "language_score", "coherence_score")
    ):
        app_defs = [
            (
                "Language Quality",
                ["Language Quality", "Language", "language_score", "language_quality"],
                "Evaluates syntactic cadence, sentence length calibration, and formal academic phrasing.",
            ),
            (
                "Structural Coherence",
                ["Structural Coherence", "Coherence", "coherence_score", "structural_coherence"],
                "Measures transitional discourse markers, section organization, and logical flow.",
            ),
            (
                "Argumentation",
                ["Argumentation", "Reasoning", "argumentation_score", "argumentation"],
                "Assesses causal links, empirical grounding, and evidentiary support for claims.",
            ),
            (
                "Academic Style",
                ["Academic Style", "Sophistication", "academic_style_score", "academic_style"],
                "Evaluates lexical diversity, scholarly register, and technical vocabulary precision.",
            ),
            (
                "Readability",
                ["Readability", "readability_score", "readability"],
                "Measures sentence accessibility and reading ease calibrated for academic prose.",
            ),
        ]
        out: List[Tuple[str, float, str]] = []
        for label, keys, desc in app_defs:
            val = None
            for k in keys:
                if k in raw_scores and raw_scores[k] is not None:
                    val = raw_scores[k]
                    break
                if k in rec and rec[k] is not None:
                    val = rec[k]
                    break
            out.append((label, float(val or 0.0), desc))
        return out

    # Otherwise check if standard flat keys exist
    if any(k in rec or k in raw_scores for k in ("readability_score", "vocab_score", "structure_score", "citation_score", "completeness_score", "Vocabulary", "Structure", "Citation")):
        std_defs = [
            ("Readability", ["readability_score", "readability", "Readability"], "Measures sentence clarity, Flesch reading ease, and prose accessibility."),
            ("Vocabulary", ["vocab_score", "vocabulary", "Vocabulary"], "Evaluates lexical diversity, academic terminology depth, and precision."),
            ("Structure", ["structure_score", "structure", "Structure"], "Assesses IMRaD section organization, heading hierarchy, and logical flow."),
            ("Citation", ["citation_score", "citation", "Citation"], "Evaluates in-text citation density, bibliography rigor, and empirical grounding."),
            ("Completeness", ["completeness_score", "completeness", "Completeness"], "Measures coverage of abstract, methodology, results, discussion, and references."),
        ]
        out = []
        for label, keys, desc in std_defs:
            val = None
            for k in keys:
                if k in rec and rec[k] is not None:
                    val = rec[k]
                    break
                if k in raw_scores and raw_scores[k] is not None:
                    val = raw_scores[k]
                    break
            out.append((label, float(val or 0.0), desc))
        return out

    # Fallback: if raw_scores is a non-empty dict with custom dimension names
    if raw_scores:
        return [
            (str(k), float(v or 0.0), f"Evaluates {str(k).lower()} quality and scholarly rigor.")
            for k, v in raw_scores.items()
        ]

    return [
        ("Readability", 0.0, "Measures sentence clarity, Flesch reading ease, and prose accessibility."),
        ("Vocabulary", 0.0, "Evaluates lexical diversity, academic terminology depth, and precision."),
        ("Structure", 0.0, "Assesses IMRaD section organization, heading hierarchy, and logical flow."),
        ("Citation", 0.0, "Evaluates in-text citation density, bibliography rigor, and empirical grounding."),
        ("Completeness", 0.0, "Measures coverage of abstract, methodology, results, discussion, and references."),
    ]


def _make_comparison_charts(
    papers: Sequence[Dict[str, Any]]
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """Build multi-paper radar chart and grouped bar chart PNG bytes for Compare Papers."""
    if not papers:
        return None, None

    palette = ["#8B5CF6", "#06B6D4", "#F59E0B", "#10B981", "#EF4444", "#2563EB"]
    first_dims = _extract_paper_5_dims(papers[0])
    dims = [d[0] for d in first_dims]

    radar_png = None
    bar_png = None
    try:
        fig_radar = go.Figure()
        for idx, p in enumerate(papers):
            p_label = clean_plain_text(p.get("short_label") or p.get("clean_title") or p.get("title") or p.get("filename") or f"Paper {idx + 1}")
            if len(p_label) > 34:
                p_label = p_label[:31].rstrip() + "…"
            p_dims = dict((d[0], d[1]) for d in _extract_paper_5_dims(p))
            vals = [float(p_dims.get(d, 0.0)) for d in dims]
            color = palette[idx % len(palette)]
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=dims + [dims[0]],
                    fill="toself",
                    name=p_label,
                    line=dict(color=color, width=2),
                    opacity=0.75,
                )
            )
        fig_radar.update_layout(
            title=dict(text="Multi-Paper Radar Comparison", font=dict(size=13, color="#0F172A")),
            polar=dict(
                bgcolor="#F8FAFC",
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=8)),
            ),
            paper_bgcolor="#FFFFFF",
            margin=dict(l=45, r=45, t=45, b=45),
            legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        )
        radar_png = export_plotly_fig_to_png(fig_radar, width=580, height=340)
    except Exception:
        radar_png = None

    try:
        fig_bar = go.Figure()
        for idx, p in enumerate(papers):
            p_label = clean_plain_text(p.get("short_label") or p.get("clean_title") or p.get("title") or p.get("filename") or f"Paper {idx + 1}")
            if len(p_label) > 34:
                p_label = p_label[:31].rstrip() + "…"
            p_dims = dict((d[0], d[1]) for d in _extract_paper_5_dims(p))
            vals = [float(p_dims.get(d, 0.0)) for d in dims]
            color = palette[idx % len(palette)]
            fig_bar.add_trace(
                go.Bar(
                    name=p_label,
                    x=dims,
                    y=vals,
                    marker_color=color,
                    text=[f"{v:.0f}" for v in vals],
                    textposition="outside",
                )
            )
        fig_bar.update_layout(
            title=dict(text="Dimension-by-Dimension Score Comparison", font=dict(size=13, color="#0F172A")),
            barmode="group",
            yaxis=dict(range=[0, 112], title="Score (/100)", gridcolor="#E2E8F0"),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#F8FAFC",
            margin=dict(l=45, r=30, t=45, b=55),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        )
        bar_png = export_plotly_fig_to_png(fig_bar, width=580, height=320)
    except Exception:
        bar_png = None

    return radar_png, bar_png


def _build_pdf_document(
    story: List[Any],
    header_title: str,
    generated_at: Optional[str] = None,
) -> bytes:
    """Render a Platypus story into an in-memory PDF bytes buffer with _PaperIQNumberedCanvas."""
    _ensure_unicode_fonts()
    buf = io.BytesIO()
    gen_ts = generated_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=clean_plain_text(header_title),
        author="PaperIQ",
    )

    def _canvas_maker(*args, **kwargs):
        kwargs["header_title"] = header_title
        kwargs["generated_at"] = gen_ts
        return _PaperIQNumberedCanvas(*args, **kwargs)

    doc.build(story, canvasmaker=_canvas_maker)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Summary PDF: build_summary_pdf(paper_title, mode, summary_data, metadata)
# ---------------------------------------------------------------------------
def build_summary_pdf(
    paper_title: str,
    mode: str,
    summary_data: Any,
    metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate a clean in-memory PDF for a paper summary (Short/Medium/Long or section summary)."""
    styles = _get_styles()
    metadata = metadata or {}
    clean_title = clean_plain_text(paper_title or "Untitled Research Paper")
    clean_mode = clean_plain_text(mode or "Executive Summary")
    gen_ts = clean_plain_text(
        metadata.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    story: List[Any] = []
    story.append(Paragraph(_rl_text(clean_title), styles["title"]))
    meta_parts = [f"Summary Mode: {clean_mode}"]
    if metadata.get("domain"):
        meta_parts.append(f"Domain: {clean_plain_text(metadata['domain'])}")
    if metadata.get("word_count"):
        meta_parts.append(f"Document Words: {metadata['word_count']:,}")
    if metadata.get("overall_score") is not None:
        meta_parts.append(f"Composite Score: {float(metadata['overall_score']):.1f}/100")
    story.append(Paragraph(_rl_text("  |  ".join(meta_parts)), styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # Extract summary text and optional bullets/keywords/sections
    if isinstance(summary_data, dict):
        main_text = summary_data.get("summary") or summary_data.get("executive_summary") or summary_data.get("text") or ""
        bullets = summary_data.get("takeaways") or summary_data.get("bullets") or summary_data.get("key_points") or []
        sections = summary_data.get("section_summaries") or summary_data.get("sections") or {}
        keywords = summary_data.get("keywords") or metadata.get("keywords") or []
    else:
        main_text = str(summary_data or "")
        bullets = metadata.get("takeaways") or []
        sections = metadata.get("section_summaries") or {}
        keywords = metadata.get("keywords") or []

    story.append(Paragraph(_rl_text(f"Executive Summary ({clean_mode})"), styles["h1"]))
    if main_text:
        for para in re.split(r"\n\s*\n|\n", clean_plain_text(main_text)):
            para = para.strip()
            if not para:
                continue
            if para.startswith(("•", "-", "*")):
                bullet_txt = para.lstrip("•-* ").strip()
                story.append(Paragraph(f"• {_rl_text(bullet_txt)}", styles["bullet"]))
            else:
                story.append(Paragraph(_rl_text(para), styles["body"]))
    else:
        story.append(Paragraph("No summary text available.", styles["body"]))

    if bullets:
        story.append(Paragraph("Key Takeaways", styles["h1"]))
        for item in bullets:
            clean_item = clean_plain_text(item).lstrip("•-* ").strip()
            if clean_item:
                story.append(Paragraph(f"• {_rl_text(clean_item)}", styles["bullet"]))

    if keywords:
        story.append(Paragraph("Core Keywords & Concepts", styles["h1"]))
        kw_str = ", ".join(clean_plain_text(k) for k in keywords if clean_plain_text(k))
        story.append(Paragraph(_rl_text(kw_str), styles["body"]))

    if isinstance(sections, dict) and sections:
        story.append(Paragraph("Section-by-Section Breakdown", styles["h1"]))
        for sec_name, sec_body in sections.items():
            clean_sec_body = clean_plain_text(sec_body).strip()
            if not clean_sec_body:
                continue
            story.append(Paragraph(_rl_text(sec_name.replace("_", " ").title()), styles["h2"]))
            story.append(Paragraph(_rl_text(clean_sec_body), styles["body"]))

    return _build_pdf_document(story, header_title=clean_title, generated_at=gen_ts)


# ---------------------------------------------------------------------------
# 2. Analysis & Feedback PDF: build_analysis_pdf(analysis_record)
# ---------------------------------------------------------------------------
def build_analysis_pdf(analysis_record: Dict[str, Any]) -> bytes:
    """Generate a complete in-memory PDF report for a single paper analysis:
    title, domain, overall score & grade, 5 dimension scores with explanations,
    key findings, areas requiring attention (with Why & Action), document statistics,
    section summaries, and embedded radar + bar chart PNGs (with table fallback)."""
    styles = _get_styles()
    rec = analysis_record or {}

    clean_title = clean_plain_text(
        rec.get("paper_title") or rec.get("title") or rec.get("filename") or "Research Paper Analysis"
    )
    domain = clean_plain_text(rec.get("domain") or "General Research")
    gen_ts = clean_plain_text(
        rec.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    overall_score = float(rec.get("overall_score", rec.get("composite", rec.get("overall", 0.0))) or 0.0)
    grade = clean_plain_text(rec.get("grade") or "")
    if not grade:
        if overall_score >= 85:
            grade = "A+ (Excellent)"
        elif overall_score >= 75:
            grade = "A (Strong)"
        elif overall_score >= 65:
            grade = "B (Good)"
        elif overall_score >= 50:
            grade = "C (Fair)"
        else:
            grade = "D (Needs Revision)"

    # Extract 5 dimension scores
    extracted_dims = _extract_paper_5_dims(rec)
    scores_map: Dict[str, float] = {label: sc for label, sc, _ in extracted_dims}
    explanations = rec.get("dimension_explanations") or rec.get("explanations") or {}

    story: List[Any] = []
    # Title & Subtitle
    story.append(Paragraph(_rl_text(clean_title), styles["title"]))
    story.append(
        Paragraph(
            _rl_text(
                f"Academic Domain: {domain}   |   Composite Score: {overall_score:.1f}/100 ({grade})   |   Date: {gen_ts}"
            ),
            styles["subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # Score Summary Table
    story.append(Paragraph("1. Quality Score Card & Dimension Breakdown", styles["h1"]))
    table_rows = [
        [
            Paragraph("Dimension", styles["table_header"]),
            Paragraph("Score", styles["table_header"]),
            Paragraph("Status", styles["table_header"]),
            Paragraph("Diagnostic Explanation", styles["table_header"]),
        ]
    ]
    for label, sc, default_desc in extracted_dims:
        status_str = "Strong" if sc >= 80 else ("Good" if sc >= 65 else ("Moderate" if sc >= 50 else "Needs Work"))
        exp_text = clean_plain_text(
            explanations.get(label) or explanations.get(label.lower()) or default_desc
        )
        table_rows.append(
            [
                Paragraph(_rl_text(label), styles["table_cell_bold"]),
                Paragraph(_rl_text(f"{sc:.1f} / 100"), styles["table_cell_bold"]),
                Paragraph(_rl_text(status_str), styles["table_cell"]),
                Paragraph(_rl_text(exp_text), styles["table_cell"]),
            ]
        )
    table_rows.append(
        [
            Paragraph("Overall Composite", styles["table_cell_bold"]),
            Paragraph(_rl_text(f"{overall_score:.1f} / 100"), styles["table_cell_bold"]),
            Paragraph(_rl_text(grade), styles["table_cell_bold"]),
            Paragraph("Weighted multi-dimensional academic quality index.", styles["table_cell"]),
        ]
    )

    score_table = Table(table_rows, colWidths=[32 * mm, 24 * mm, 24 * mm, 94 * mm], repeatRows=1)
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E0F2FE")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(score_table)
    story.append(Spacer(1, 8))

    # Visual Charts (Radar + Bar chart PNGs)
    radar_png = rec.get("radar_png")
    bar_png = rec.get("bar_png")
    if not radar_png or not bar_png:
        auto_radar, auto_bar = _make_single_paper_charts(scores_map)
        radar_png = radar_png or auto_radar
        bar_png = bar_png or auto_bar

    if radar_png or bar_png:
        story.append(Paragraph("2. Visual Quality Profile", styles["h1"]))
        chart_cells = []
        if radar_png:
            chart_cells.append(RLImage(io.BytesIO(radar_png), width=84 * mm, height=50 * mm))
        if bar_png:
            chart_cells.append(RLImage(io.BytesIO(bar_png), width=86 * mm, height=45 * mm))
        if len(chart_cells) == 2:
            chart_tbl = Table([chart_cells], colWidths=[87 * mm, 87 * mm])
            chart_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            story.append(chart_tbl)
        elif len(chart_cells) == 1:
            story.append(chart_cells[0])
        story.append(Spacer(1, 6))

    # Document Statistics
    stats_dict = rec.get("stats") if isinstance(rec.get("stats"), dict) else {}
    word_count = int(rec.get("word_count") or stats_dict.get("word_count") or 0)
    sent_count = int(rec.get("sentence_count") or rec.get("sentences") or stats_dict.get("sentence_count") or 0)
    char_count = int(rec.get("char_count") or stats_dict.get("char_count") or 0)
    avg_sent_len = float(
        rec.get("avg_sentence_len")
        or stats_dict.get("avg_sentence_len")
        or (word_count / max(sent_count, 1) if word_count else 0.0)
    )
    flesch = float(
        rec.get("flesch_score")
        or rec.get("readability_score")
        or scores_map.get("Readability", 0.0)
        or 0.0
    )

    story.append(Paragraph("3. Document Statistics", styles["h1"]))
    stats_rows = [
        [
            Paragraph("Metric", styles["table_header"]),
            Paragraph("Value", styles["table_header"]),
            Paragraph("Metric", styles["table_header"]),
            Paragraph("Value", styles["table_header"]),
        ],
        [
            Paragraph("Total Word Count", styles["table_cell_bold"]),
            Paragraph(_rl_text(f"{word_count:,}"), styles["table_cell"]),
            Paragraph("Total Sentence Count", styles["table_cell_bold"]),
            Paragraph(_rl_text(f"{sent_count:,}"), styles["table_cell"]),
        ],
        [
            Paragraph("Avg. Sentence Length", styles["table_cell_bold"]),
            Paragraph(_rl_text(f"{avg_sent_len:.1f} words"), styles["table_cell"]),
            Paragraph("Readability / Flesch Index", styles["table_cell_bold"]),
            Paragraph(_rl_text(f"{flesch:.1f}"), styles["table_cell"]),
        ],
    ]
    if char_count > 0:
        stats_rows.append(
            [
                Paragraph("Character Count", styles["table_cell_bold"]),
                Paragraph(_rl_text(f"{char_count:,}"), styles["table_cell"]),
                Paragraph("Academic Domain", styles["table_cell_bold"]),
                Paragraph(_rl_text(domain), styles["table_cell"]),
            ]
        )
    stats_tbl = Table(stats_rows, colWidths=[45 * mm, 42 * mm, 45 * mm, 42 * mm], repeatRows=1)
    stats_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(stats_tbl)
    story.append(Spacer(1, 8))

    # Key Findings / Strengths
    findings = rec.get("key_findings") or rec.get("strengths") or []
    if not findings:
        sorted_dims = sorted(scores_map.items(), key=lambda x: x[1], reverse=True)
        findings = [
            f"Strong {dim} performance ({sc:.1f}/100) supporting manuscript rigor."
            for dim, sc in sorted_dims[:3]
        ]

    story.append(Paragraph("4. Key Findings & Manuscript Strengths", styles["h1"]))
    for item in findings:
        clean_item = clean_plain_text(item).lstrip("•-* ").strip()
        if clean_item:
            story.append(Paragraph(f"• {_rl_text(clean_item)}", styles["bullet"]))

    # Areas Requiring Attention (with Why & Action)
    attention_items = rec.get("attention_items") or rec.get("issues") or rec.get("weaknesses") or rec.get("feedback_items") or []
    if not attention_items:
        low_dims = sorted(scores_map.items(), key=lambda x: x[1])[:2]
        attention_items = [
            {
                "title": f"Enhance {dim} ({sc:.1f}/100)",
                "why": f"{dim} is currently the lowest-scoring dimension relative to peer benchmarks.",
                "action": f"Review and refine {dim.lower()} conventions, transitions, and supporting evidence.",
            }
            for dim, sc in low_dims
        ]

    story.append(Paragraph("5. Areas Requiring Attention (Why & Action Plan)", styles["h1"]))
    for idx, att in enumerate(attention_items, start=1):
        if isinstance(att, dict):
            head = clean_plain_text(
                att.get("title") or att.get("problem") or att.get("issue") or att.get("category") or att.get("dimension") or f"Area {idx}"
            )
            why = clean_plain_text(
                att.get("why") or att.get("why_it_matters") or att.get("reason") or att.get("explanation") or ""
            )
            action = clean_plain_text(
                att.get("action") or att.get("recommendation") or att.get("fix") or att.get("suggestion") or ""
            )
            story.append(Paragraph(_rl_text(f"{idx}. {head}"), styles["h2"]))
            if why:
                story.append(Paragraph(f"<b>Why it matters:</b> {_rl_text(why)}", styles["bullet"]))
            if action:
                story.append(Paragraph(f"<b>Recommended Action:</b> {_rl_text(action)}", styles["bullet"]))
        else:
            clean_att = clean_plain_text(att).lstrip("•-* ").strip()
            if clean_att:
                story.append(Paragraph(f"• {_rl_text(clean_att)}", styles["bullet"]))

    # Executive Summary & Section Summaries
    exec_sum = clean_plain_text(rec.get("executive_summary") or rec.get("summary") or "").strip()
    if exec_sum:
        story.append(Paragraph("6. Executive Summary", styles["h1"]))
        for para in re.split(r"\n\s*\n|\n", exec_sum):
            para = para.strip()
            if para:
                story.append(Paragraph(_rl_text(para), styles["body"]))

    sec_summaries = rec.get("section_summaries") or rec.get("sections") or {}
    if isinstance(sec_summaries, dict) and sec_summaries:
        story.append(Paragraph("7. Section Summaries", styles["h1"]))
        for sec_k, sec_v in sec_summaries.items():
            clean_v = clean_plain_text(sec_v).strip()
            if not clean_v or len(clean_v) < 20:
                continue
            sec_title = clean_plain_text(sec_k).replace("_", " ").title()
            story.append(Paragraph(_rl_text(sec_title), styles["h2"]))
            if len(clean_v) > 900:
                clean_v = clean_v[:897].rstrip() + "…"
            story.append(Paragraph(_rl_text(clean_v), styles["body"]))

    return _build_pdf_document(story, header_title=clean_title, generated_at=gen_ts)


# ---------------------------------------------------------------------------
# 3. Comparison PDF: build_comparison_pdf(papers, comparison_data)
# ---------------------------------------------------------------------------
def build_comparison_pdf(
    papers: Sequence[Dict[str, Any]],
    comparison_data: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate an in-memory PDF report for Compare Papers:
    side-by-side score table, winner & gap summaries, strengths & improvements per paper,
    comparative synthesis (similarities & differences), and embedded radar + bar chart PNGs."""
    styles = _get_styles()
    comparison_data = comparison_data or {}
    gen_ts = clean_plain_text(
        comparison_data.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    story: List[Any] = []
    story.append(Paragraph("Multi-Paper Comparative Quality & Synthesis Report", styles["title"]))
    story.append(
        Paragraph(
            _rl_text(f"Papers Compared: {len(papers)}   |   Generated: {gen_ts}"),
            styles["subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # 1. Winner & Gap Summary
    story.append(Paragraph("1. Executive Winner & Gap Summary", styles["h1"]))
    if papers:
        ranked = sorted(
            papers,
            key=lambda x: float(x.get("composite", x.get("overall_score", 0)) or 0),
            reverse=True,
        )
        top_p = ranked[0]
        top_title = clean_plain_text(top_p.get("clean_title") or top_p.get("title") or top_p.get("paper_title") or top_p.get("filename") or "Paper 1")
        top_score = float(top_p.get("composite", top_p.get("overall_score", 0)) or 0)
        story.append(
            Paragraph(
                f"<b>Highest Ranked Manuscript:</b> {_rl_text(top_title)} ({top_score:.1f}/100)",
                styles["body"],
            )
        )
        if len(ranked) > 1:
            runner_up = ranked[1]
            runner_title = clean_plain_text(runner_up.get("clean_title") or runner_up.get("title") or runner_up.get("paper_title") or runner_up.get("filename") or "Paper 2")
            runner_score = float(runner_up.get("composite", runner_up.get("overall_score", 0)) or 0)
            lead_gap = round(top_score - runner_score, 1)
            lowest_p = ranked[-1]
            lowest_score = float(lowest_p.get("composite", lowest_p.get("overall_score", 0)) or 0)
            spread = round(top_score - lowest_score, 1)
            story.append(
                Paragraph(
                    _rl_text(
                        f"Runner-Up: {runner_title} ({runner_score:.1f}/100, Lead Margin: +{lead_gap} pts)  |  "
                        f"Total Cohort Spread: {spread:.1f} pts"
                    ),
                    styles["body"],
                )
            )

    # 2. Side-by-Side Score Table
    story.append(Paragraph("2. Side-by-Side Score Table", styles["h1"]))
    first_dims = _extract_paper_5_dims(papers[0]) if papers else []
    dim_labels = [d[0] for d in first_dims] if first_dims else ["Readability", "Vocabulary", "Structure", "Citation", "Completeness"]
    short_hdrs = [lbl.split()[0][:7] + "." if len(lbl) > 8 else lbl for lbl in dim_labels]

    tbl_rows = [
        [
            Paragraph("Paper Title", styles["table_header"]),
            Paragraph("Overall", styles["table_header"]),
            *[Paragraph(_rl_text(sh), styles["table_header"]) for sh in short_hdrs],
        ]
    ]
    for idx, p in enumerate(papers, start=1):
        p_title = clean_plain_text(p.get("clean_title") or p.get("title") or p.get("paper_title") or p.get("filename") or f"Paper {idx}")
        comp = float(p.get("composite", p.get("overall_score", 0)) or 0)
        p_dim_dict = {d[0]: d[1] for d in _extract_paper_5_dims(p)}
        tbl_rows.append(
            [
                Paragraph(_rl_text(f"Paper {idx}: {p_title}"), styles["table_cell_bold"]),
                Paragraph(_rl_text(f"{comp:.1f}"), styles["table_cell_bold"]),
                *[Paragraph(_rl_text(f"{float(p_dim_dict.get(dl, 0.0)):.1f}"), styles["table_cell"]) for dl in dim_labels],
            ]
        )

    comp_table = Table(
        tbl_rows,
        colWidths=[66 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm],
        repeatRows=1,
    )
    comp_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(comp_table)
    story.append(Spacer(1, 8))

    # 3. Embedded Radar & Bar Charts
    radar_png = comparison_data.get("radar_png")
    bar_png = comparison_data.get("bar_png")
    if not radar_png or not bar_png:
        auto_radar, auto_bar = _make_comparison_charts(papers)
        radar_png = radar_png or auto_radar
        bar_png = bar_png or auto_bar

    if radar_png or bar_png:
        story.append(Paragraph("3. Visual Comparative Charts", styles["h1"]))
        chart_cells = []
        if radar_png:
            chart_cells.append(RLImage(io.BytesIO(radar_png), width=85 * mm, height=50 * mm))
        if bar_png:
            chart_cells.append(RLImage(io.BytesIO(bar_png), width=85 * mm, height=47 * mm))
        if len(chart_cells) == 2:
            c_tbl = Table([chart_cells], colWidths=[87 * mm, 87 * mm])
            c_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            story.append(c_tbl)
        elif len(chart_cells) == 1:
            story.append(chart_cells[0])
        story.append(Spacer(1, 6))

    # 4. Strengths & Areas for Improvement per Paper
    story.append(Paragraph("4. Strengths & Areas for Improvement per Paper", styles["h1"]))
    for idx, p in enumerate(papers, start=1):
        p_title = clean_plain_text(p.get("clean_title") or p.get("title") or p.get("paper_title") or p.get("filename") or f"Paper {idx}")
        comp = float(p.get("composite", p.get("overall_score", 0)) or 0)
        story.append(
            Paragraph(_rl_text(f"Paper {idx}: {p_title} (Overall: {comp:.1f}/100)"), styles["h2"])
        )
        p_dims = [(d[0], d[1]) for d in _extract_paper_5_dims(p)]
        p_dims_sorted = sorted(p_dims, key=lambda x: x[1], reverse=True)
        strengths = p.get("strengths") or [
            f"{d} ({v:.1f}/100)" for d, v in p_dims_sorted[:2]
        ]
        improvements = p.get("improvements") or [
            f"{d} ({v:.1f}/100)" for d, v in sorted(p_dims, key=lambda x: x[1])[:2]
        ]
        story.append(
            Paragraph(
                f"<b>Strengths:</b> {_rl_text('; '.join(clean_plain_text(s) for s in strengths))}",
                styles["bullet"],
            )
        )
        story.append(
            Paragraph(
                f"<b>Areas for Improvement:</b> {_rl_text('; '.join(clean_plain_text(w) for w in improvements))}",
                styles["bullet"],
            )
        )

    # 5. Comparative Synthesis (Similarities & Differences)
    story.append(Paragraph("5. Comparative Synthesis", styles["h1"]))
    similarities = comparison_data.get("similarities") or []
    differences = comparison_data.get("differences") or []
    synthesis_text = clean_plain_text(comparison_data.get("synthesis") or "").strip()

    if synthesis_text:
        story.append(Paragraph(_rl_text(synthesis_text), styles["body"]))

    if similarities:
        story.append(Paragraph("Cross-Paper Similarities & Shared Strengths", styles["h2"]))
        for sim in similarities:
            clean_sim = clean_plain_text(sim).lstrip("•-* ").strip()
            if clean_sim:
                story.append(Paragraph(f"• {_rl_text(clean_sim)}", styles["bullet"]))

    if differences:
        story.append(Paragraph("Key Methodological & Quality Differences", styles["h2"]))
        for diff in differences:
            clean_diff = clean_plain_text(diff).lstrip("•-* ").strip()
            if clean_diff:
                story.append(Paragraph(f"• {_rl_text(clean_diff)}", styles["bullet"]))

    if not similarities and not differences and not synthesis_text and len(papers) >= 2:
        for dl in dim_labels:
            vals = [dict((d[0], d[1]) for d in _extract_paper_5_dims(p)).get(dl, 0.0) for p in papers]
            gap = max(vals) - min(vals)
            if gap <= 8.0:
                story.append(
                    Paragraph(
                        f"• <b>Shared Consistency in {_rl_text(dl)}:</b> Papers score within a narrow {gap:.1f}-point band ({min(vals):.1f}–{max(vals):.1f}/100).",
                        styles["bullet"],
                    )
                )
            else:
                story.append(
                    Paragraph(
                        f"• <b>Divergence in {_rl_text(dl)}:</b> Scores span a {gap:.1f}-point gap ({min(vals):.1f} vs {max(vals):.1f}/100).",
                        styles["bullet"],
                    )
                )

    return _build_pdf_document(story, header_title="PaperIQ Multi-Paper Comparison", generated_at=gen_ts)


# ---------------------------------------------------------------------------
# 4. Ask PaperIQ Chat PDF: build_chat_pdf(paper_title, chat_history)
# ---------------------------------------------------------------------------
def build_chat_pdf(
    paper_title: str,
    chat_history: Sequence[Dict[str, Any]],
) -> bytes:
    """Generate an in-memory PDF transcript for Ask PaperIQ Q&A conversations,
    including paper title, each question, synthesized answer, supporting evidence
    with section labels, and timestamps."""
    styles = _get_styles()
    clean_title = clean_plain_text(paper_title or "Research Paper Q&A Session")
    gen_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    story: List[Any] = []
    story.append(Paragraph(_rl_text(f"Ask PaperIQ — Research Q&A Transcript"), styles["title"]))
    story.append(
        Paragraph(
            _rl_text(f"Active Paper: {clean_title}   |   Exported: {gen_ts}"),
            styles["subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    if not chat_history:
        story.append(Paragraph("No Q&A messages recorded in this session.", styles["body"]))
        return _build_pdf_document(story, header_title=clean_title, generated_at=gen_ts)

    # Support both paired Q&A dicts ({question, answer, citations/evidence, timestamp})
    # and role-based message lists ({role: 'user'/'assistant', content: ..., citations: ...})
    turn_num = 0
    i = 0
    n = len(chat_history)
    while i < n:
        msg = chat_history[i] or {}
        if "question" in msg or "answer" in msg:
            turn_num += 1
            q_text = clean_plain_text(msg.get("question") or "")
            a_text = clean_plain_text(msg.get("answer") or "")
            ts = clean_plain_text(msg.get("timestamp") or gen_ts)
            evidence = msg.get("evidence") or msg.get("citations") or msg.get("sources") or []
            conf = msg.get("confidence")

            story.append(Paragraph(_rl_text(f"Q{turn_num}: {q_text}"), styles["h1"]))
            meta_line = f"Timestamp: {ts}"
            if conf:
                meta_line += f"  |  Retrieval Confidence: {clean_plain_text(conf)}"
            story.append(Paragraph(_rl_text(meta_line), styles["meta"]))
            story.append(Paragraph(_rl_text(a_text), styles["body"]))

            if evidence:
                story.append(Paragraph("Supporting Evidence from Paper:", styles["h2"]))
                for ev in evidence:
                    if isinstance(ev, dict):
                        sec = clean_plain_text(ev.get("section") or ev.get("label") or "Document Excerpt")
                        snip = clean_plain_text(ev.get("text") or ev.get("snippet") or ev.get("quote") or "")
                        story.append(
                            Paragraph(f"• <b>[{_rl_text(sec)}]</b> {_rl_text(snip)}", styles["bullet"])
                        )
                    else:
                        story.append(Paragraph(f"• {_rl_text(clean_plain_text(ev))}", styles["bullet"]))
            story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#E2E8F0"), spaceBefore=6, spaceAfter=6))
            i += 1
        else:
            role = str(msg.get("role", "")).lower()
            content = clean_plain_text(msg.get("content") or msg.get("text") or "")
            ts = clean_plain_text(msg.get("timestamp") or gen_ts)
            if role == "user":
                turn_num += 1
                story.append(Paragraph(_rl_text(f"Q{turn_num}: {content}"), styles["h1"]))
                story.append(Paragraph(_rl_text(f"Asked: {ts}"), styles["meta"]))
                # Check if next message is assistant response
                if i + 1 < n and str((chat_history[i + 1] or {}).get("role", "")).lower() == "assistant":
                    ans_msg = chat_history[i + 1] or {}
                    a_text = clean_plain_text(ans_msg.get("content") or ans_msg.get("text") or "")
                    ans_ts = clean_plain_text(ans_msg.get("timestamp") or ts)
                    conf = ans_msg.get("confidence")
                    meta_line = f"Answered: {ans_ts}"
                    if conf:
                        meta_line += f"  |  Retrieval Confidence: {clean_plain_text(conf)}"
                    story.append(Paragraph(_rl_text(meta_line), styles["meta"]))
                    for para in re.split(r"\n\s*\n|\n", a_text):
                        para = para.strip()
                        if para:
                            story.append(Paragraph(_rl_text(para), styles["body"]))
                    evidence = ans_msg.get("evidence") or ans_msg.get("citations") or ans_msg.get("sources") or []
                    if evidence:
                        story.append(Paragraph("Supporting Evidence from Paper:", styles["h2"]))
                        for ev in evidence:
                            if isinstance(ev, dict):
                                sec = clean_plain_text(ev.get("section") or ev.get("label") or "Document Excerpt")
                                snip = clean_plain_text(ev.get("text") or ev.get("snippet") or ev.get("quote") or "")
                                story.append(
                                    Paragraph(f"• <b>[{_rl_text(sec)}]</b> {_rl_text(snip)}", styles["bullet"])
                                )
                            else:
                                story.append(Paragraph(f"• {_rl_text(clean_plain_text(ev))}", styles["bullet"]))
                    story.append(
                        HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#E2E8F0"), spaceBefore=6, spaceAfter=6)
                    )
                    i += 2
                    continue
            else:
                story.append(Paragraph(_rl_text(f"PaperIQ Response ({ts}):"), styles["h2"]))
                story.append(Paragraph(_rl_text(content), styles["body"]))
            i += 1

    return _build_pdf_document(story, header_title=clean_title, generated_at=gen_ts)
