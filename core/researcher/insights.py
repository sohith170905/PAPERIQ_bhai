"""
PaperIQ — Researcher Page 6: Research Insights (C6 — REBUILD)
=============================================================
Requirements:
- REMOVE the "Writing Improvements" section (that is Student content).
- Show:
  1. Keywords & Research Themes: top TF-IDF / RAKE keywords and keyphrases (cleaned of stopwords,
     numbers, single letters, boilerplate), with frequencies, plus automatic grouping into themes.
  2. Literature Gaps & Opportunities: extracted ONLY from explicit gap/limitation statements in the
     paper, quoting the exact sentence and its section. If none exist, show "Not found in this manuscript".
     Never output generic boilerplate Opportunity text.
  3. Temporal / Quantitative Trends: extracted ONLY when the paper contains time-series, longitudinal,
     or period-based statements, showing actual numbers and periods. If none exist, show "No trend data found".
  4. Future Research Directions: extracted ONLY when the authors state future work / recommendations.
     If none exist, show "Not stated by the authors".
  5. Clean summary cards for Methodology, Data Sources, and Key Findings using complete, un-truncated sentences.
- Export Insights Report as PDF + TXT.
"""

from __future__ import annotations

from typing import Any, Dict, List
import plotly.graph_objects as go
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import render_html, safe_text, unescape_text


def render_research_insights(
    theme: Dict[str, str],
    username: str,
) -> None:
    """Render Researcher Page 6: Research Insights (C6)."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">💡 Honest Manuscript Intelligence</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Research Insights</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Evidence-backed thematic keyphrases, explicit literature gaps, quantitative period trends, and author-stated future directions — zero boilerplate.</p>',
        '</div>',
    ])

    library_papers = auth.get_researcher_library(username)

    # Select which paper from Library (or active session) to inspect
    selected_title = "Untitled Manuscript"
    selected_text = ""
    selected_sections: Dict[str, str] = {}
    selected_domain = "Interdisciplinary"

    if library_papers:
        p_map: Dict[str, Dict[str, Any]] = {}
        for p in library_papers:
            raw_t = unescape_text(p.get("paper_title") or p.get("filename") or "Manuscript")
            if research_engine.is_citation_or_header_line(raw_t):
                raw_t = research_engine.extract_paper_metadata(
                    unescape_text(p.get("extracted_text") or ""), filename=p.get("filename", "")
                ).get("title") or raw_t
            yr_str = unescape_text(str(p.get("year") or "")).strip() or "n.d."
            base_lbl = f"{raw_t} ({yr_str})"
            lbl = base_lbl if base_lbl not in p_map else f"{base_lbl} — {unescape_text(p.get('domain') or 'Research')}"
            if lbl in p_map:
                lbl = f"{lbl} #{len(p_map) + 1}"
            p_map[lbl] = p

        active_id = st.session_state.get("current_analysis_id")
        default_idx = 0
        for idx_p, p_item in enumerate(library_papers):
            if p_item["id"] == active_id:
                default_idx = idx_p
                break

        with st.container(border=True):
            render_html('<span class="res-card-scope"></span>')
            chosen_lbl = st.selectbox(
                "🔬 Select Manuscript for Deep Insights Extraction",
                options=list(p_map.keys()),
                index=default_idx,
                key="res_ins_paper_selector",
            )
            chosen_rec = p_map[chosen_lbl]
            st.session_state["current_analysis_id"] = chosen_rec["id"]
            selected_text = unescape_text(chosen_rec.get("extracted_text") or chosen_rec.get("summary") or "")
            raw_sel_title = unescape_text(chosen_rec.get("paper_title") or chosen_rec.get("filename") or "Manuscript")
            if research_engine.is_citation_or_header_line(raw_sel_title):
                selected_title = research_engine.extract_paper_metadata(
                    selected_text, filename=chosen_rec.get("filename", "")
                ).get("title") or raw_sel_title
            else:
                selected_title = raw_sel_title
            selected_sections = (
                chosen_rec.get("sections")
                if isinstance(chosen_rec.get("sections"), dict) and chosen_rec.get("sections")
                else summarizer.segment_paper_sections(selected_text)
            )
            selected_domain = unescape_text(chosen_rec.get("domain") or "")
    elif st.session_state.get("text"):
        selected_text = unescape_text(st.session_state.get("text") or "")
        raw_sel_title = unescape_text(st.session_state.get("paper_title") or "Current Manuscript")
        if research_engine.is_citation_or_header_line(raw_sel_title):
            selected_title = research_engine.extract_paper_metadata(selected_text).get("title") or raw_sel_title
        else:
            selected_title = raw_sel_title
        selected_sections = st.session_state.get("sections") or summarizer.segment_paper_sections(selected_text)
    else:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 12px; padding: 28px 20px; text-align: center;">',
            f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]};">No manuscript selected</div>',
            f'<div style="font-size: 13px; color: {theme["text_muted"]}; margin-top: 4px;">Upload and evaluate a paper in <b>Analyze Research Paper</b> first to extract Research Insights.</div>',
            '</div>',
        ])
        return

    insights = research_engine.extract_honest_research_insights(selected_text, selected_sections)
    if not selected_domain or selected_domain == "General":
        selected_domain = insights.get("domain") or "Interdisciplinary"

    # Top Active Manuscript & Export Card (PDF + TXT)
    with st.container(border=True):
        render_html('<span class="res-item-scope"></span>')
        dl_c1, dl_c2, dl_c3 = st.columns([2.2, 1.1, 1.1], gap="small")
        with dl_c1:
            render_html([
                f'<div style="padding: 2px 0;">',
                f'<div style="font-size: 16.5px; font-weight: 800; color: {theme["text_primary"]}; line-height: 1.3;" title="{safe_text(selected_title)}">📄 {safe_text(selected_title)}</div>',
                f'<div style="font-size: 12.5px; color: {theme["accent_purple"]}; font-weight: 600; margin-top: 3px;">🧭 Discipline: {safe_text(selected_domain)}</div>',
                '</div>',
            ])
        with dl_c2:
            try:
                ins_pdf = pdf_export.build_insights_pdf(selected_title, insights, {"domain": selected_domain})
                st.download_button(
                    "⬇ Insights Report (PDF)",
                    data=ins_pdf,
                    file_name=pdf_export.get_pdf_filename(selected_title, "Research_Insights"),
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                    key="res_ins_dl_pdf",
                )
            except Exception as pdf_err:
                st.error(f"Could not generate Insights PDF: {pdf_err}")
        with dl_c3:
            ins_txt = pdf_export.build_insights_txt(selected_title, insights, {"domain": selected_domain})
            st.download_button(
                "⬇ Insights Report (TXT)",
                data=ins_txt.encode("utf-8"),
                file_name=pdf_export.get_pdf_filename(selected_title, "Research_Insights").replace(".pdf", ".txt"),
                mime="text/plain",
                use_container_width=True,
                key="res_ins_dl_txt",
            )

    # =======================================================================
    # SECTION 1: Clean Complete-Sentence Summary Cards (Methodology, Data Sources, Key Findings)
    # =======================================================================
    render_html([
        '<div style="margin: 14px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">1. Core Manuscript Summary Cards</h3>',
        f'<p style="margin: 2px 0 0 0; font-size: 12.5px; color: {theme["text_muted"]};">Extracted using complete sentence boundaries (preserving decimal figures and stripping section heading numbers).</p>',
        '</div>',
    ])

    cards = insights.get("cards") or {}
    card_cols = st.columns(3, gap="medium")
    card_specs = [
        ("methodology", "⚙️ Methodology", "#06B6D4"),
        ("data_sources", "🗄️ Data Sources & Materials", "#10B981"),
        ("key_findings", "📈 Key Empirical Findings", "#F59E0B"),
    ]
    for idx, (c_key, c_label, c_color) in enumerate(card_specs):
        c_data = cards.get(c_key) or {}
        c_found = bool(c_data.get("found"))
        c_text = unescape_text(c_data.get("text") or research_engine.NOT_FOUND_SENTINEL)
        c_sec = unescape_text(c_data.get("section") or "—")
        t_style = (
            f"font-size: 13px; color: {theme['text_primary']}; line-height: 1.55;"
            if c_found
            else f"font-size: 13px; color: {theme['text_muted']}; font-style: italic;"
        )
        with card_cols[idx]:
            render_html([
                f'<div class="iq-card" style="padding: 16px 18px !important; border-top: 3px solid {c_color}; min-height: 195px; display: flex; flex-direction: column; justify-content: space-between;">',
                '<div>',
                f'<div style="font-size: 14.5px; font-weight: 700; color: {theme["text_primary"]}; margin-bottom: 8px;">{safe_text(c_label)}</div>',
                f'<div style="{t_style}">{safe_text(c_text)}</div>',
                '</div>',
                f'<div style="margin-top: 10px; padding-top: 6px; border-top: 1px solid {theme["border_divider"]}; font-size: 11px; color: {theme["text_muted"]};">📍 Section: {safe_text(c_sec)}</div>',
                '</div>',
            ])

    # =======================================================================
    # SECTION 2: Keywords (with frequencies) & Grouped Research Themes
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">2. Keywords &amp; Research Themes</h3>',
        '</div>',
    ])

    kws = insights.get("keywords") or []
    themes = insights.get("themes") or []

    kw_c1, kw_c2 = st.columns([1.25, 1.15], gap="medium")
    with kw_c1:
        if kws:
            kw_badges = "".join(
                f'<span style="background: {theme["bg_card"]}; border: 1px solid {theme["accent_primary_border"]}; border-radius: 8px; padding: 5px 10px; font-size: 12.5px; color: {theme["text_primary"]}; font-weight: 600;">'
                f'{safe_text(k["term"])} <span style="background: {theme["accent_primary_subtle"]}; color: {theme["accent_purple"]}; border-radius: 4px; padding: 1px 6px; font-size: 11px; margin-left: 4px;">{k["count"]}×</span>'
                f'</span>'
                for k in kws[:14]
            )
            render_html([
                f'<div class="iq-card" style="padding: 16px 18px !important;">',
                f'<div style="font-size: 13.5px; font-weight: 700; color: {theme["text_secondary"]}; margin-bottom: 10px;">🏷️ Top Extracted Keyphrases &amp; Frequencies</div>',
                f'<div style="display: flex; flex-wrap: wrap; gap: 8px;">{kw_badges}</div>',
                '</div>',
            ])
        else:
            st.info("Not found in this manuscript.")

    with kw_c2:
        if themes:
            theme_rows = [
                f'<div class="iq-card" style="padding: 16px 18px !important;">',
                f'<div style="font-size: 13.5px; font-weight: 700; color: {theme["text_secondary"]}; margin-bottom: 10px;">🧭 Automatically Grouped Research Themes</div>',
            ]
            for th in themes:
                t_name = th.get("theme", "Theme")
                t_terms = ", ".join(th.get("keywords") or [])
                t_cnt = th.get("mentions", 0)
                theme_rows.extend([
                    f'<div style="padding: 7px 10px; background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; margin-bottom: 7px;">',
                    '<div style="display: flex; justify-content: space-between; font-size: 12.5px; font-weight: 700;">',
                    f'<span style="color: {theme["accent_purple"]};">{safe_text(t_name)}</span>',
                    f'<span style="color: {theme["text_muted"]};">{t_cnt} mentions</span>',
                    '</div>',
                    f'<div style="font-size: 12px; color: {theme["text_secondary"]}; margin-top: 3px;">{safe_text(t_terms)}</div>',
                    '</div>',
                ])
            theme_rows.append('</div>')
            render_html(theme_rows)

    # =======================================================================
    # SECTION 3: Literature Gaps & Opportunities (Strictly Quote-Grounded)
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">3. Literature Gaps &amp; Research Opportunities</h3>',
        f'<p style="margin: 2px 0 0 0; font-size: 12.5px; color: {theme["text_muted"]};">Extracted strictly from explicit gap, constraint, or limitation statements in the manuscript.</p>',
        '</div>',
    ])

    gaps = insights.get("gaps") or []
    has_explicit_gaps = bool(insights.get("has_explicit_gaps"))
    if not gaps:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 10px; padding: 16px 20px; font-size: 13.5px; color: {theme["text_muted"]}; font-style: italic;">',
            f'No explicit research gaps stated — No explicit gap or limitation statements were detected in the text of this manuscript.',
            '</div>',
        ])
    else:
        if not has_explicit_gaps:
            render_html([
                f'<div style="background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.35); border-radius: 10px; padding: 11px 16px; margin-bottom: 10px; font-size: 13px; color: {theme["warning_text"]};">',
                '<b>No explicit research gaps stated by the authors:</b> The manuscript does not state study-specific gaps; the item below is a background constraint cited from prior literature.',
                '</div>',
            ])
        for idx, g in enumerate(gaps, start=1):
            is_bg = bool(g.get("is_cited_background"))
            g_label = g.get("label") or ("Background constraint cited from literature" if is_bg else f"Identified Gap #{idx}")
            border_c = "#F59E0B" if is_bg else "#EF4444"
            lbl_c = "#FBBF24" if is_bg else "#F87171"
            render_html([
                f'<div class="iq-card" style="padding: 15px 18px !important; border-left: 4px solid {border_c}; margin-bottom: 10px;">',
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">',
                f'<span style="font-size: 12.5px; font-weight: 700; color: {lbl_c};">🔍 {safe_text(g_label)}</span>',
                f'<span style="font-size: 11.5px; color: {theme["text_muted"]};">📍 Section: {safe_text(g.get("section", "Manuscript"))}</span>',
                '</div>',
                f'<div style="font-size: 13.5px; color: {theme["text_primary"]}; font-style: italic; line-height: 1.5; margin-bottom: 6px;">"{safe_text(g.get("quote", ""))}"</div>',
                f'<div style="font-size: 12.5px; color: {theme["success_text"]};"><b>Targeted Research Direction:</b> {safe_text(g.get("opportunity", ""))}</div>',
                '</div>',
            ])

    # =======================================================================
    # SECTION 4: Temporal / Quantitative Trends (or "No trend data found")
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">4. Temporal &amp; Quantitative Trends</h3>',
        '</div>',
    ])

    period_note = insights.get("period_boundary_note") or ""
    if period_note:
        render_html([
            f'<div style="background: rgba(56,189,248,0.10); border: 1px solid rgba(56,189,248,0.32); border-radius: 10px; padding: 10px 15px; margin-bottom: 10px; font-size: 12.5px; color: #7dd3fc;">',
            f'ℹ️ <b>Note:</b> {safe_text(period_note)}',
            '</div>',
        ])

    trends = insights.get("trends") or []
    if not trends:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 10px; padding: 16px 20px; font-size: 13.5px; color: {theme["text_muted"]}; font-style: italic;">',
            f'{safe_text(research_engine.NO_TREND_SENTINEL)} — This manuscript does not contain longitudinal, period-based, or time-series trend statements.',
            '</div>',
        ])
    else:
        for tr in trends:
            dir_lbl = tr.get("direction", "")
            render_html([
                f'<div class="iq-card" style="padding: 14px 18px !important; border-left: 4px solid #06B6D4; margin-bottom: 9px;">',
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 6px;">',
                '<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">',
                f'<span style="background: rgba(6,182,212,0.16); color: #22d3ee; border: 1px solid rgba(6,182,212,0.35); border-radius: 4px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;">📅 {safe_text(tr.get("period", "Reported Period"))}</span>',
                f'<span style="background: {theme["bg_card_inner"]}; color: {theme["text_secondary"]}; border: 1px solid {theme["border_color"]}; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;">{safe_text(dir_lbl)}</span>' if dir_lbl else '',
                '</div>',
                f'<span style="font-size: 11.5px; color: {theme["warning_text"]}; font-weight: 600;">📊 Reported Figures: {safe_text(tr.get("metrics", ""))} &nbsp;|&nbsp; 📍 {safe_text(tr.get("section", "Results"))}</span>',
                '</div>',
                f'<div style="font-size: 13.5px; color: {theme["text_primary"]}; line-height: 1.5; margin-top: 4px;">{safe_text(tr.get("statement", ""))}</div>',
                '</div>',
            ])

    # =======================================================================
    # SECTION 5: Future Research Directions (or "Not stated by the authors")
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">5. Author-Stated Future Research Directions</h3>',
        '</div>',
    ])

    future_dirs = insights.get("future_directions") or []
    if not future_dirs:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 10px; padding: 16px 20px; font-size: 13.5px; color: {theme["text_muted"]}; font-style: italic;">',
            f'{safe_text(research_engine.NOT_STATED_SENTINEL)} — No explicit future work or recommendation statements were found in this manuscript.',
            '</div>',
        ])
    else:
        for fd in future_dirs:
            render_html([
                f'<div class="iq-card" style="padding: 14px 18px !important; border-left: 4px solid #10B981; margin-bottom: 9px;">',
                f'<div style="font-size: 11.5px; font-weight: 700; color: {theme["success_text"]}; margin-bottom: 4px;">🔭 Future Direction &nbsp;•&nbsp; 📍 Section: {safe_text(fd.get("section", "Conclusion"))}</div>',
                f'<div style="font-size: 13.5px; color: {theme["text_primary"]}; line-height: 1.5;">{safe_text(fd.get("statement", ""))}</div>',
                '</div>',
            ])
