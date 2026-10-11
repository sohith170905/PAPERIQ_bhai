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
# Plotly Chart Export Helpers (Pure-Python Pillow PNG Renderer — Zero Subprocess Hangs)
# ---------------------------------------------------------------------------
def export_plotly_fig_to_png(
    fig: Optional[go.Figure], width: int = 620, height: int = 340
) -> Optional[bytes]:
    """Export a Plotly Figure (Scatterpolar radar or Bar chart) to PNG bytes in memory
    using pure-Python Pillow drawing so it never spawns or hangs an external Chromium process."""
    if fig is None:
        return None
    try:
        from PIL import Image, ImageDraw

        w = max(int(width), 320)
        h = max(int(height), 220)
        img = Image.new("RGB", (w, h), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Border & subtle header background
        draw.rectangle([0, 0, w - 1, h - 1], outline=(203, 213, 225), width=2)
        draw.rectangle([2, 2, w - 3, 34], fill=(248, 250, 252))
        title_txt = ""
        try:
            title_txt = clean_plain_text(fig.layout.title.text or "")
        except Exception:
            title_txt = "PaperIQ Evaluation Chart"
        if title_txt:
            draw.text((16, 10), title_txt[:65], fill=(15, 23, 42))

        traces = list(fig.data) if hasattr(fig, "data") and fig.data else []
        palette_rgb = [
            (2, 132, 199),
            (139, 92, 246),
            (16, 185, 129),
            (245, 158, 11),
            (239, 68, 68),
        ]

        is_polar = any(getattr(t, "type", "") == "scatterpolar" for t in traces)
        if is_polar:
            cx, cy = w // 2, (h + 24) // 2
            radius = min(w, h - 55) // 2 - 28
            # Draw concentric web rings
            for frac in (0.25, 0.5, 0.75, 1.0):
                rr = int(radius * frac)
                draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(226, 232, 240), width=1)
            for idx, tr in enumerate(traces):
                r_vals = [float(x or 0.0) for x in (getattr(tr, "r", None) or [])]
                theta_vals = [str(x) for x in (getattr(tr, "theta", None) or [])]
                if len(r_vals) > 1 and theta_vals and theta_vals[0] == theta_vals[-1]:
                    r_vals = r_vals[:-1]
                    theta_vals = theta_vals[:-1]
                n_pts = max(len(r_vals), 1)
                pts = []
                for i_pt, rv in enumerate(r_vals):
                    ang = -math.pi / 2 + (2 * math.pi * i_pt / n_pts)
                    dist = radius * min(max(rv, 0.0), 100.0) / 100.0
                    px = int(cx + dist * math.cos(ang))
                    py = int(cy + dist * math.sin(ang))
                    pts.append((px, py))
                    if idx == 0 and i_pt < len(theta_vals):
                        lx = int(cx + (radius + 16) * math.cos(ang)) - 18
                        ly = int(cy + (radius + 14) * math.sin(ang)) - 5
                        draw.text((lx, ly), clean_plain_text(theta_vals[i_pt])[:12], fill=(51, 65, 85))
                if len(pts) >= 3:
                    col = palette_rgb[idx % len(palette_rgb)]
                    draw.line(pts + [pts[0]], fill=col, width=3)
                    for px, py in pts:
                        draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=col)
        else:
            # Bar chart rendering
            left_x, right_x = 95, w - 35
            top_y, bot_y = 48, h - 36
            plot_w = max(right_x - left_x, 100)
            plot_h = max(bot_y - top_y, 80)
            draw.line([(left_x, top_y), (left_x, bot_y), (right_x, bot_y)], fill=(148, 163, 184), width=2)

            n_traces = max(len(traces), 1)
            for idx, tr in enumerate(traces):
                col = palette_rgb[idx % len(palette_rgb)]
                orient = getattr(tr, "orientation", "v") or "v"
                if orient == "h":
                    x_vals = [float(v or 0.0) for v in (getattr(tr, "x", None) or [])]
                    y_lbls = [str(v) for v in (getattr(tr, "y", None) or [])]
                    n_bars = max(len(x_vals), 1)
                    band_h = plot_h / n_bars
                    for b_i, xv in enumerate(x_vals):
                        by0 = int(top_y + b_i * band_h + 6)
                        by1 = int(top_y + (b_i + 1) * band_h - 6)
                        bw = int(plot_w * min(max(xv, 0.0), 100.0) / 100.0)
                        draw.rectangle([left_x + 1, by0, left_x + 1 + max(bw, 4), max(by1, by0 + 4)], fill=col)
                        if b_i < len(y_lbls):
                            draw.text((8, (by0 + by1) // 2 - 5), clean_plain_text(y_lbls[b_i])[:12], fill=(30, 41, 59))
                        draw.text((left_x + bw + 6, (by0 + by1) // 2 - 5), f"{xv:.1f}", fill=(15, 23, 42))
                else:
                    x_lbls = [str(v) for v in (getattr(tr, "x", None) or [])]
                    y_vals = [float(v or 0.0) for v in (getattr(tr, "y", None) or [])]
                    n_cats = max(len(y_vals), 1)
                    cat_w = plot_w / n_cats
                    bar_w = max(int((cat_w - 14) / n_traces), 6)
                    for c_i, yv in enumerate(y_vals):
                        bx0 = int(left_x + c_i * cat_w + 7 + idx * bar_w)
                        bx1 = bx0 + bar_w - 2
                        bh = int(plot_h * min(max(yv, 0.0), 100.0) / 100.0)
                        by0 = bot_y - max(bh, 3)
                        draw.rectangle([bx0, by0, bx1, bot_y - 1], fill=col)
                        if idx == 0 and c_i < len(x_lbls):
                            draw.text((int(left_x + c_i * cat_w + 6), bot_y + 8), clean_plain_text(x_lbls[c_i])[:10], fill=(30, 41, 59))

        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except Exception:
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

    import summarizer as _sum_mod
    main_text = _sum_mod.normalize_summary_limitations_label(str(main_text or ""))

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
    import summarizer as _sum_mod
    raw_exec_sum = _sum_mod.normalize_summary_limitations_label(str(rec.get("executive_summary") or rec.get("summary") or ""))
    exec_sum = clean_plain_text(raw_exec_sum).strip()
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

    # Optional Researcher Structured Content Matrix (Objectives, Methodology, Data, Findings, Limitations, Contributions)
    matrix_rows = comparison_data.get("matrix_rows") or []
    cross_domain_notice = clean_plain_text(comparison_data.get("cross_domain_notice") or "").strip()
    if cross_domain_notice:
        story.append(Paragraph(f"<b>Cross-Domain Notice:</b> {_rl_text(cross_domain_notice)}", styles["body"]))
        story.append(Spacer(1, 4))

    if matrix_rows and len(papers) >= 2:
        story.append(Paragraph("Structured Research Content Matrix", styles["h1"]))
        n_papers = len(papers)
        dim_w = 34 * mm
        each_w = (140 * mm) / max(n_papers, 1)
        m_header = [Paragraph("Dimension", styles["table_header"])]
        for idx, p in enumerate(papers, start=1):
            pt = clean_plain_text(p.get("clean_title") or p.get("title") or p.get("paper_title") or f"Paper {idx}")
            m_header.append(Paragraph(_rl_text(f"P{idx}: {pt[:42]}"), styles["table_header"]))
        m_tbl_data = [m_header]
        for row in matrix_rows:
            dim_name = clean_plain_text(row.get("dimension") or "")
            cells = row.get("cells") or []
            r_cells = [Paragraph(_rl_text(dim_name), styles["table_cell_bold"])]
            for c_idx in range(n_papers):
                c_val = clean_plain_text(cells[c_idx] if c_idx < len(cells) else "Not found in this manuscript")
                r_cells.append(Paragraph(_rl_text(c_val[:380]), styles["table_cell"]))
            m_tbl_data.append(r_cells)
        m_table = Table(m_tbl_data, colWidths=[dim_w] + [each_w] * n_papers, repeatRows=1)
        m_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(m_table)
        story.append(Spacer(1, 8))

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
                        snip = clean_plain_text(ev.get("text") or ev.get("snippet") or ev.get("passage") or ev.get("quote") or "")
                        p_ref = clean_plain_text(ev.get("paper_title") or "")
                        prefix_lbl = f"{p_ref} — {sec}" if p_ref else sec
                        story.append(
                            Paragraph(f"• <b>[{_rl_text(prefix_lbl)}]</b> {_rl_text(snip)}", styles["bullet"])
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
                                snip = clean_plain_text(ev.get("text") or ev.get("snippet") or ev.get("passage") or ev.get("quote") or "")
                                p_ref = clean_plain_text(ev.get("paper_title") or "")
                                prefix_lbl = f"{p_ref} — {sec}" if p_ref else sec
                                story.append(
                                    Paragraph(f"• <b>[{_rl_text(prefix_lbl)}]</b> {_rl_text(snip)}", styles["bullet"])
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


# ---------------------------------------------------------------------------
# 5. Researcher Paper Report (PDF + TXT): Metadata + Research Profile + Summary + Scores
# ---------------------------------------------------------------------------
def build_researcher_paper_pdf(record: Dict[str, Any]) -> bytes:
    """Generate a Researcher Paper Evaluation PDF (Metadata + Research Profile primary + Summary + Writing Quality)."""
    styles = _get_styles()
    title = clean_plain_text(record.get("title") or record.get("paper_title") or record.get("filename") or "Research Manuscript")
    meta = record.get("metadata") or {}
    authors = clean_plain_text(meta.get("authors") or record.get("authors") or "Unknown Authors")
    year = clean_plain_text(meta.get("year") or record.get("year") or "n.d.")
    journal = clean_plain_text(meta.get("journal") or record.get("journal") or "Manuscript / Preprint")
    domain = clean_plain_text(meta.get("domain") or record.get("domain") or "Interdisciplinary")
    keywords = meta.get("keywords") or record.get("keywords") or []
    gen_ts = clean_plain_text(record.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    story: List[Any] = []
    story.append(Paragraph(_rl_text(title), styles["title"]))
    story.append(
        Paragraph(
            _rl_text(f"Authors: {authors} ({year})  |  Venue: {journal}  |  Domain: {domain}"),
            styles["subtitle"],
        )
    )
    if keywords:
        kw_str = ", ".join(clean_plain_text(k) for k in keywords[:12])
        story.append(Paragraph(f"<b>Keywords:</b> {_rl_text(kw_str)}", styles["meta"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=8))

    # 1. Primary Research Profile (6 structured fields)
    story.append(Paragraph("1. Structured Research Profile", styles["h1"]))
    profile = record.get("profile") or {}
    field_order = [
        ("objective", "Research Objective"),
        ("methodology", "Methodology & Study Design"),
        ("data_materials", "Data / Sample / Materials"),
        ("key_results", "Key Quantitative & Empirical Results"),
        ("contributions", "Main Contributions"),
        ("limitations", "Limitations & Constraints"),
    ]
    prof_rows = [
        [
            Paragraph("Profile Dimension", styles["table_header"]),
            Paragraph("Extracted Content", styles["table_header"]),
            Paragraph("Section / Confidence", styles["table_header"]),
        ]
    ]
    for f_key, f_lbl in field_order:
        f_obj = profile.get(f_key) or {}
        val = clean_plain_text(f_obj.get("value") or "Not found in this manuscript")
        sec = clean_plain_text(f_obj.get("section") or "—")
        conf = clean_plain_text(f_obj.get("confidence") or "Not Found")
        prof_rows.append(
            [
                Paragraph(_rl_text(f_lbl), styles["table_cell_bold"]),
                Paragraph(_rl_text(val), styles["table_cell"]),
                Paragraph(_rl_text(f"{sec} ({conf})"), styles["table_cell"]),
            ]
        )
    p_tbl = Table(prof_rows, colWidths=[38 * mm, 102 * mm, 34 * mm], repeatRows=1)
    p_tbl.setStyle(
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
    story.append(p_tbl)
    story.append(Spacer(1, 8))

    # 2. Grounded Research Findings
    findings = record.get("findings") or []
    if findings:
        story.append(Paragraph("2. Text-Grounded Research Findings", styles["h1"]))
        for f_item in findings:
            if isinstance(f_item, dict):
                cat = clean_plain_text(f_item.get("category") or "Finding")
                sec = clean_plain_text(f_item.get("section") or "Manuscript")
                det = clean_plain_text(f_item.get("detail") or "")
                story.append(Paragraph(f"• <b>{_rl_text(cat)} [{_rl_text(sec)}]:</b> {_rl_text(det)}", styles["bullet"]))
            else:
                story.append(Paragraph(f"• {_rl_text(clean_plain_text(f_item))}", styles["bullet"]))
        story.append(Spacer(1, 6))

    # 3. Executive Summary
    summary_txt = clean_plain_text(record.get("summary") or "")
    if summary_txt:
        story.append(Paragraph("3. Manuscript Summary", styles["h1"]))
        for para in re.split(r"\n\s*\n|\n", summary_txt):
            if para.strip():
                story.append(Paragraph(_rl_text(para.strip()), styles["body"]))

    # 4. Secondary Manuscript Writing Quality
    story.append(Paragraph("4. Manuscript Writing Quality (Secondary Assessment)", styles["h1"]))
    dims = _extract_paper_5_dims(record)
    overall = float(record.get("overall_score") or record.get("composite") or 0.0)
    story.append(Paragraph(f"<b>Composite Quality Score:</b> {overall:.1f}/100", styles["body"]))
    for d_name, d_val, d_desc in dims:
        story.append(Paragraph(f"• <b>{_rl_text(d_name)}:</b> {d_val:.1f}/100 — {_rl_text(d_desc)}", styles["bullet"]))

    return _build_pdf_document(story, header_title=f"Researcher Report — {title[:45]}", generated_at=gen_ts)


def build_researcher_paper_txt(record: Dict[str, Any]) -> str:
    """Generate clean UTF-8 plain text for a Researcher Paper Report."""
    title = clean_plain_text(record.get("title") or record.get("paper_title") or "Research Manuscript")
    meta = record.get("metadata") or {}
    authors = clean_plain_text(meta.get("authors") or record.get("authors") or "Unknown Authors")
    year = clean_plain_text(meta.get("year") or record.get("year") or "n.d.")
    journal = clean_plain_text(meta.get("journal") or record.get("journal") or "Manuscript / Preprint")
    domain = clean_plain_text(meta.get("domain") or record.get("domain") or "Interdisciplinary")
    keywords = meta.get("keywords") or record.get("keywords") or []

    lines = [
        "=" * 76,
        f"PAPERIQ RESEARCHER MANUSCRIPT REPORT: {title}",
        "=" * 76,
        f"Authors : {authors}",
        f"Year    : {year}",
        f"Venue   : {journal}",
        f"Domain  : {domain}",
        f"Keywords: {', '.join(clean_plain_text(k) for k in keywords) if keywords else 'None extracted'}",
        "-" * 76,
        "1. STRUCTURED RESEARCH PROFILE",
        "-" * 76,
    ]
    profile = record.get("profile") or {}
    for f_key, f_lbl in [
        ("objective", "Research Objective"),
        ("methodology", "Methodology & Design"),
        ("data_materials", "Data / Sample / Materials"),
        ("key_results", "Key Results"),
        ("contributions", "Main Contributions"),
        ("limitations", "Limitations"),
    ]:
        f_obj = profile.get(f_key) or {}
        val = clean_plain_text(f_obj.get("value") or "Not found in this manuscript")
        sec = clean_plain_text(f_obj.get("section") or "—")
        conf = clean_plain_text(f_obj.get("confidence") or "Not Found")
        lines.append(f"[{f_lbl}] (Section: {sec} | Confidence: {conf})")
        lines.append(f"  {val}")
        lines.append("")

    findings = record.get("findings") or []
    if findings:
        lines.extend(["-" * 76, "2. TEXT-GROUNDED RESEARCH FINDINGS", "-" * 76])
        for f_item in findings:
            if isinstance(f_item, dict):
                lines.append(f"* {clean_plain_text(f_item.get('category', 'Finding'))} [{clean_plain_text(f_item.get('section', ''))}]: {clean_plain_text(f_item.get('detail', ''))}")
            else:
                lines.append(f"* {clean_plain_text(f_item)}")
        lines.append("")

    summary_txt = clean_plain_text(record.get("summary") or "")
    if summary_txt:
        lines.extend(["-" * 76, "3. MANUSCRIPT SUMMARY", "-" * 76, summary_txt, ""])

    lines.extend(["-" * 76, "4. MANUSCRIPT WRITING QUALITY (SECONDARY)", "-" * 76])
    overall = float(record.get("overall_score") or record.get("composite") or 0.0)
    lines.append(f"Composite Writing Score: {overall:.1f}/100")
    for d_name, d_val, _ in _extract_paper_5_dims(record):
        lines.append(f"  - {d_name}: {d_val:.1f}/100")
    lines.append("=" * 76)
    return "\n".join(lines)


def build_researcher_comparison_txt(papers: Sequence[Dict[str, Any]], comparison_data: Dict[str, Any]) -> str:
    """Generate clean UTF-8 plain text for a Researcher Multi-Paper Comparison Report."""
    lines = [
        "=" * 76,
        "PAPERIQ ADVANCED PAPER COMPARISON REPORT",
        "=" * 76,
        f"Compared Manuscripts ({len(papers)}):",
    ]
    for idx, p in enumerate(papers, start=1):
        pt = clean_plain_text(p.get("title") or p.get("paper_title") or f"Paper {idx}")
        dom = clean_plain_text(p.get("domain") or (p.get("metadata") or {}).get("domain") or "Interdisciplinary")
        lines.append(f"  {idx}. {pt} [{dom}]")
    lines.append("")

    notice = clean_plain_text(comparison_data.get("cross_domain_notice") or "")
    if notice:
        lines.extend([f"NOTE: {notice}", ""])

    lines.extend(["-" * 76, "1. STRUCTURED COMPARISON MATRIX", "-" * 76])
    for row in comparison_data.get("matrix_rows") or []:
        dim = clean_plain_text(row.get("dimension") or "")
        lines.append(f"### {dim}")
        cells = row.get("cells") or []
        for idx, p in enumerate(papers):
            pt = clean_plain_text(p.get("title") or f"Paper {idx + 1}")
            val = clean_plain_text(cells[idx] if idx < len(cells) else "Not found in this manuscript")
            lines.append(f"  - Paper {idx + 1} ({pt[:45]}): {val}")
        lines.append("")

    lines.extend(["-" * 76, "2. COMPARATIVE SYNTHESIS", "-" * 76, "Similarities:"])
    for sim in comparison_data.get("similarities") or []:
        lines.append(f"  * {clean_plain_text(sim)}")
    lines.append("\nDifferences:")
    for diff in comparison_data.get("differences") or []:
        lines.append(f"  * {clean_plain_text(diff)}")
    lines.append("=" * 76)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Research Insights Report (PDF + TXT): Keywords, Themes, Gaps, Trends, Future Work
# ---------------------------------------------------------------------------
def build_insights_pdf(
    paper_title: str,
    insights_data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Generate a PDF report for Research Insights (Keywords, Themes, Gaps, Trends, Future Work)."""
    styles = _get_styles()
    metadata = metadata or {}
    clean_title = clean_plain_text(paper_title or "Untitled Manuscript")
    domain = clean_plain_text(insights_data.get("domain") or metadata.get("domain") or "Interdisciplinary")
    gen_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    story: List[Any] = []
    story.append(Paragraph(_rl_text(f"Research Insights Report — {clean_title}"), styles["title"]))
    story.append(Paragraph(_rl_text(f"Discipline: {domain}   |   Generated: {gen_ts}"), styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=8))

    # 1. Keywords & Research Themes
    story.append(Paragraph("1. Extracted Keywords & Research Themes", styles["h1"]))
    kws = insights_data.get("keywords") or []
    if kws:
        kw_str = ", ".join(f"{clean_plain_text(k['term'])} ({k['count']})" for k in kws[:15] if isinstance(k, dict))
        story.append(Paragraph(f"<b>Top Keywords (with frequencies):</b> {_rl_text(kw_str)}", styles["body"]))
    themes = insights_data.get("themes") or []
    for th in themes:
        t_name = clean_plain_text(th.get("theme") or "Theme")
        t_kws = ", ".join(clean_plain_text(x) for x in (th.get("keywords") or []))
        story.append(Paragraph(f"• <b>{_rl_text(t_name)} ({th.get('mentions', 0)} mentions):</b> {_rl_text(t_kws)}", styles["bullet"]))
    story.append(Spacer(1, 6))

    # 2. Core Summary Cards (Methodology, Data Sources, Key Findings)
    story.append(Paragraph("2. Core Research Summary Cards", styles["h1"]))
    cards = insights_data.get("cards") or {}
    for c_key in ("methodology", "data_sources", "key_findings"):
        c_obj = cards.get(c_key) or {}
        c_title = clean_plain_text(c_obj.get("title") or c_key.title())
        c_txt = clean_plain_text(c_obj.get("text") or "Not found in this manuscript")
        c_sec = clean_plain_text(c_obj.get("section") or "—")
        story.append(Paragraph(f"<b>{_rl_text(c_title)} [{_rl_text(c_sec)}]:</b> {_rl_text(c_txt)}", styles["body"]))

    # 3. Literature Gaps & Opportunities
    story.append(Paragraph("3. Literature Gaps & Research Opportunities", styles["h1"]))
    gaps = insights_data.get("gaps") or []
    if gaps:
        for idx, g in enumerate(gaps, start=1):
            q = clean_plain_text(g.get("quote") or "")
            sec = clean_plain_text(g.get("section") or "Manuscript")
            opp = clean_plain_text(g.get("opportunity") or "")
            story.append(Paragraph(f"• <b>Gap {idx} [{_rl_text(sec)}]:</b> \"{_rl_text(q)}\"", styles["bullet"]))
            if opp:
                story.append(Paragraph(f"  <i>Opportunity:</i> {_rl_text(opp)}", styles["bullet"]))
    else:
        story.append(Paragraph("Not found in this manuscript.", styles["body"]))

    # 4. Temporal & Quantitative Trends
    story.append(Paragraph("4. Temporal & Quantitative Trends", styles["h1"]))
    trends = insights_data.get("trends") or []
    if trends:
        for tr in trends:
            per = clean_plain_text(tr.get("period") or "Reported Period")
            stmt = clean_plain_text(tr.get("statement") or "")
            sec = clean_plain_text(tr.get("section") or "Results")
            story.append(Paragraph(f"• <b>[{_rl_text(per)} | {_rl_text(sec)}]:</b> {_rl_text(stmt)}", styles["bullet"]))
    else:
        story.append(Paragraph("No trend data found.", styles["body"]))

    # 5. Future Research Directions
    story.append(Paragraph("5. Author-Stated Future Research Directions", styles["h1"]))
    futures = insights_data.get("future_directions") or []
    if futures:
        for fd in futures:
            stmt = clean_plain_text(fd.get("statement") or "")
            sec = clean_plain_text(fd.get("section") or "Conclusion")
            story.append(Paragraph(f"• <b>[{_rl_text(sec)}]:</b> {_rl_text(stmt)}", styles["bullet"]))
    else:
        story.append(Paragraph("Not stated by the authors.", styles["body"]))

    return _build_pdf_document(story, header_title=f"Research Insights — {clean_title[:42]}", generated_at=gen_ts)


def build_insights_txt(
    paper_title: str,
    insights_data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate clean UTF-8 plain text for a Research Insights Report."""
    clean_title = clean_plain_text(paper_title or "Untitled Manuscript")
    domain = clean_plain_text(insights_data.get("domain") or (metadata or {}).get("domain") or "Interdisciplinary")
    lines = [
        "=" * 76,
        f"PAPERIQ RESEARCH INSIGHTS REPORT: {clean_title}",
        f"Discipline: {domain}",
        "=" * 76,
        "1. KEYWORDS & THEMES",
        "-" * 76,
    ]
    kws = insights_data.get("keywords") or []
    if kws:
        lines.append("Keywords: " + ", ".join(f"{clean_plain_text(k['term'])} ({k['count']})" for k in kws if isinstance(k, dict)))
    for th in insights_data.get("themes") or []:
        lines.append(f"  * {clean_plain_text(th.get('theme', ''))}: {', '.join(clean_plain_text(x) for x in th.get('keywords', []))}")

    lines.extend(["", "-" * 76, "2. METHODOLOGY, DATA SOURCES & KEY FINDINGS", "-" * 76])
    cards = insights_data.get("cards") or {}
    for c_key in ("methodology", "data_sources", "key_findings"):
        c_obj = cards.get(c_key) or {}
        lines.append(f"[{clean_plain_text(c_obj.get('title', c_key))}] ({clean_plain_text(c_obj.get('section', '—'))}):")
        lines.append(f"  {clean_plain_text(c_obj.get('text', 'Not found in this manuscript'))}\n")

    lines.extend(["-" * 76, "3. LITERATURE GAPS & OPPORTUNITIES", "-" * 76])
    gaps = insights_data.get("gaps") or []
    if gaps:
        for idx, g in enumerate(gaps, start=1):
            lines.append(f"  {idx}. [{clean_plain_text(g.get('section', ''))}] \"{clean_plain_text(g.get('quote', ''))}\"")
            lines.append(f"     Opportunity: {clean_plain_text(g.get('opportunity', ''))}")
    else:
        lines.append("  Not found in this manuscript.")

    lines.extend(["", "-" * 76, "4. TEMPORAL & QUANTITATIVE TRENDS", "-" * 76])
    trends = insights_data.get("trends") or []
    if trends:
        for tr in trends:
            lines.append(f"  * [{clean_plain_text(tr.get('period', ''))} | {clean_plain_text(tr.get('section', ''))}] {clean_plain_text(tr.get('statement', ''))}")
    else:
        lines.append("  No trend data found.")

    lines.extend(["", "-" * 76, "5. FUTURE RESEARCH DIRECTIONS", "-" * 76])
    futures = insights_data.get("future_directions") or []
    if futures:
        for fd in futures:
            lines.append(f"  * [{clean_plain_text(fd.get('section', ''))}] {clean_plain_text(fd.get('statement', ''))}")
    else:
        lines.append("  Not stated by the authors.")

    lines.append("=" * 76)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Project Report (PDF + TXT): All Papers in Project + Synthesis + Notes
# ---------------------------------------------------------------------------
def build_project_report_pdf(
    project: Dict[str, Any],
    papers: Sequence[Dict[str, Any]],
    matrix_data: Optional[Dict[str, Any]] = None,
    notes: Optional[Sequence[Dict[str, Any]]] = None,
) -> bytes:
    """Generate a comprehensive Project Dossier PDF containing all papers in a project,
    their profiles, cross-paper synthesis, and researcher notes."""
    styles = _get_styles()
    proj_name = clean_plain_text(project.get("name") or "Research Project")
    proj_desc = clean_plain_text(project.get("description") or "No project description provided.")
    gen_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    story: List[Any] = []
    story.append(Paragraph(_rl_text(f"Research Project Report: {proj_name}"), styles["title"]))
    story.append(
        Paragraph(
            _rl_text(f"Manuscripts in Project: {len(papers)}   |   Exported: {gen_ts}"),
            styles["subtitle"],
        )
    )
    story.append(Paragraph(f"<b>Project Scope:</b> {_rl_text(proj_desc)}", styles["body"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=8))

    # 1. Project Paper Inventory
    story.append(Paragraph("1. Project Manuscript Inventory", styles["h1"]))
    if not papers:
        story.append(Paragraph("No manuscripts are currently assigned to this project.", styles["body"]))
    else:
        for idx, p in enumerate(papers, start=1):
            pt = clean_plain_text(p.get("title") or p.get("paper_title") or p.get("filename") or f"Paper {idx}")
            meta = p.get("metadata") or {}
            auths = clean_plain_text(meta.get("authors") or p.get("authors") or "Unknown Authors")
            yr = clean_plain_text(meta.get("year") or p.get("year") or "n.d.")
            dom = clean_plain_text(meta.get("domain") or p.get("domain") or "Interdisciplinary")
            sc = float(p.get("overall_score") or (p.get("scores") or {}).get("overall_score") or 0.0)
            story.append(
                Paragraph(
                    f"<b>{idx}. {_rl_text(pt)}</b> — {_rl_text(auths)} ({_rl_text(yr)}) | Domain: {_rl_text(dom)} | Score: {sc:.1f}/100",
                    styles["h2"],
                )
            )
            prof = p.get("profile") or {}
            for fk, fl in [("objective", "Objective"), ("methodology", "Methodology"), ("key_results", "Key Results"), ("limitations", "Limitations")]:
                fval = clean_plain_text((prof.get(fk) or {}).get("value") or "Not found in this manuscript")
                story.append(Paragraph(f"• <b>{fl}:</b> {_rl_text(fval[:280])}", styles["bullet"]))

    # 2. Cross-Paper Comparative Synthesis
    if matrix_data and (matrix_data.get("similarities") or matrix_data.get("differences")):
        story.append(Paragraph("2. Cross-Paper Synthesis", styles["h1"]))
        for sim in matrix_data.get("similarities") or []:
            story.append(Paragraph(f"• <b>Shared Pattern:</b> {_rl_text(clean_plain_text(sim))}", styles["bullet"]))
        for diff in matrix_data.get("differences") or []:
            story.append(Paragraph(f"• <b>Key Divergence:</b> {_rl_text(clean_plain_text(diff))}", styles["bullet"]))

    # 3. Researcher Notes
    story.append(Paragraph("3. Researcher Project & Paper Notes", styles["h1"]))
    if notes:
        for n_item in notes:
            nt = clean_plain_text(n_item.get("note_text") or "")
            np_title = clean_plain_text(n_item.get("paper_title") or "Manuscript Note")
            nts = clean_plain_text(n_item.get("created_at") or "")
            story.append(Paragraph(f"• <b>[{_rl_text(np_title)} | {_rl_text(nts)}]:</b> {_rl_text(nt)}", styles["bullet"]))
    else:
        story.append(Paragraph("No researcher notes recorded for papers in this project.", styles["body"]))

    return _build_pdf_document(story, header_title=f"Project Report — {proj_name[:42]}", generated_at=gen_ts)


def build_project_report_txt(
    project: Dict[str, Any],
    papers: Sequence[Dict[str, Any]],
    matrix_data: Optional[Dict[str, Any]] = None,
    notes: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    """Generate clean UTF-8 plain text for a Project Report."""
    proj_name = clean_plain_text(project.get("name") or "Research Project")
    proj_desc = clean_plain_text(project.get("description") or "No project description provided.")
    lines = [
        "=" * 76,
        f"PAPERIQ RESEARCH PROJECT REPORT: {proj_name}",
        f"Description: {proj_desc}",
        f"Total Manuscripts: {len(papers)}",
        "=" * 76,
        "1. PROJECT MANUSCRIPTS",
        "-" * 76,
    ]
    for idx, p in enumerate(papers, start=1):
        pt = clean_plain_text(p.get("title") or p.get("paper_title") or f"Paper {idx}")
        meta = p.get("metadata") or {}
        auths = clean_plain_text(meta.get("authors") or p.get("authors") or "Unknown Authors")
        yr = clean_plain_text(meta.get("year") or p.get("year") or "n.d.")
        dom = clean_plain_text(meta.get("domain") or p.get("domain") or "Interdisciplinary")
        lines.append(f"{idx}. {pt} ({auths}, {yr}) [{dom}]")
        prof = p.get("profile") or {}
        for fk, fl in [("objective", "Objective"), ("methodology", "Methodology"), ("key_results", "Key Results"), ("limitations", "Limitations")]:
            fval = clean_plain_text((prof.get(fk) or {}).get("value") or "Not found in this manuscript")
            lines.append(f"   - {fl}: {fval}")
        lines.append("")

    if matrix_data and (matrix_data.get("similarities") or matrix_data.get("differences")):
        lines.extend(["-" * 76, "2. CROSS-PAPER SYNTHESIS", "-" * 76])
        for sim in matrix_data.get("similarities") or []:
            lines.append(f"  * [Similarity] {clean_plain_text(sim)}")
        for diff in matrix_data.get("differences") or []:
            lines.append(f"  * [Difference] {clean_plain_text(diff)}")
        lines.append("")

    lines.extend(["-" * 76, "3. RESEARCHER NOTES", "-" * 76])
    if notes:
        for n_item in notes:
            lines.append(f"  * [{clean_plain_text(n_item.get('paper_title', 'Paper'))}] {clean_plain_text(n_item.get('note_text', ''))}")
    else:
        lines.append("  No researcher notes recorded.")
    lines.append("=" * 76)
    return "\n".join(lines)

