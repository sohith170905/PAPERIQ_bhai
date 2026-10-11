"""
PaperIQ — Researcher Page 4: Advanced Paper Comparison (C4 — REBUILD)
=====================================================================
Requirements:
- Compare 2 or 3 papers, either uploaded OR picked from the Research Library (only the user's own papers).
- PRIMARY view — structured Comparison Matrix:
    * Objectives
    * Methodology
    * Data / Materials
    * Findings
    * Limitations
    * Contributions
    * Writing Quality (5 dims + overall)
- Highlight overlapping terms across papers.
- "Comparative Synthesis": data-driven similarities and differences referencing actual paper titles,
  domains, methods, datasets, and scores.
- If papers are from different domains, state clearly that they are cross-domain and explain that
  content differences reflect domain divergence.
- SECONDARY view — writing-score radar/bar chart LAST.
- Export Comparison Report as PDF + TXT.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
import plotly.graph_objects as go
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import render_html, safe_text, unescape_text


def render_advanced_paper_comparison(
    theme: Dict[str, str],
    username: str,
    extract_text_from_file: Callable[[Any], str],
    clean_text: Callable[[str], str],
    analyze_full_document: Callable[[str], Dict[str, Any]],
) -> None:
    """Render Researcher Page 4: Advanced Paper Comparison (C4)."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">🔄 Cross-Manuscript Synthesis</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Advanced Paper Comparison</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Benchmark 2 or 3 manuscripts side by side across Objectives, Methodology, Data/Materials, Empirical Findings, Limitations, Contributions, and secondary Writing Quality.</p>',
        '</div>',
    ])

    library_papers = auth.get_researcher_library(username)
    projects = auth.get_user_projects(username)

    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">',
            f'<div style="font-size: 15px; font-weight: 700; color: {theme["text_primary"]};">🗂️ Configure Manuscript Comparison</div>',
            f'<span style="font-size: 11.5px; color: {theme["text_muted"]}; background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 6px; padding: 2px 9px; font-weight: 600;">2–3 Manuscripts • Side-by-Side Matrix</span>',
            '</div>',
        ])
        source_mode = st.radio(
            "Select Manuscript Source for Comparison",
            options=[
                "📚 Pick from My Research Library (2–3 papers)",
                "📤 Upload 2–3 Manuscript Files Directly (PDF, DOCX, TXT)",
            ],
            horizontal=True,
            key="res_cmp_source_mode",
        )
        render_html(f'<hr style="border: none; border-top: 1px solid {theme["border_divider"]}; margin: 4px 0 8px 0;">')

        selected_papers_payload: List[Dict[str, Any]] = []

        if source_mode.startswith("📚"):
            if len(library_papers) < 2:
                st.info("ℹ️ You currently have fewer than 2 papers in your Research Library. Upload and analyze manuscripts first, or switch to **📤 Upload 2–3 Manuscript Files Directly** above.")
            else:
                # Optional quick filter by Project
                if projects:
                    p_opts = ["All Library Papers"] + [f"Project: {p['name']} ({p['paper_count']} papers)" for p in projects]
                    proj_quick = st.selectbox("Filter Library Picker by Project (optional)", options=p_opts, key="res_cmp_proj_quick")
                else:
                    proj_quick = "All Library Papers"

                candidate_papers = library_papers
                if proj_quick.startswith("Project: "):
                    target_pname = proj_quick.replace("Project: ", "", 1).rsplit(" (", 1)[0]
                    candidate_papers = [
                        p for p in library_papers
                        if any(pr["name"] == target_pname for pr in (p.get("projects") or []))
                    ]

                id_to_paper = {p["id"]: p for p in library_papers}
                label_map: Dict[str, int] = {}
                for p in candidate_papers:
                    raw_t_str = unescape_text(p.get("extracted_text") or p.get("summary") or "")
                    c_title = unescape_text(p.get("paper_title") or p.get("filename") or "Manuscript")
                    if research_engine.is_citation_or_header_line(c_title):
                        c_title = research_engine.extract_paper_metadata(raw_t_str, filename=p.get("filename", "")).get("title") or c_title
                    yr_s = unescape_text(str(p.get("year") or "")).strip() or "n.d."
                    base_lbl = f"{c_title} ({yr_s})"
                    lbl = base_lbl if base_lbl not in label_map else f"{base_lbl} — {unescape_text(p.get('domain') or 'Research')}"
                    if lbl in label_map:
                        lbl = f"{lbl} #{len(label_map) + 1}"
                    label_map[lbl] = p["id"]

                # Pre-populate from session_state["res_compare_selected_ids"] if set from Research Library
                pre_ids = [pid for pid in (st.session_state.get("res_compare_selected_ids") or []) if pid in id_to_paper][:3]
                default_labels = [lbl for lbl, pid in label_map.items() if pid in pre_ids]
                if len(default_labels) < 2 and len(label_map) >= 2:
                    default_labels = list(label_map.keys())[:2]

                chosen_labels = st.multiselect(
                    "Choose 2 or 3 Manuscripts from Your Library",
                    options=list(label_map.keys()),
                    default=default_labels[:3],
                    max_selections=3,
                    key="res_cmp_lib_multiselect",
                )

                for lbl in chosen_labels[:3]:
                    pid = label_map[lbl]
                    p_rec = id_to_paper[pid]
                    raw_t = unescape_text(p_rec.get("extracted_text") or p_rec.get("summary") or "")
                    secs_t = p_rec.get("sections") if isinstance(p_rec.get("sections"), dict) and p_rec.get("sections") else summarizer.segment_paper_sections(raw_t)
                    prof_t = research_engine.extract_research_profile(raw_t, secs_t)
                    raw_stored_title = unescape_text(p_rec.get("paper_title") or p_rec.get("filename") or "Manuscript")
                    auto_m = research_engine.extract_paper_metadata(
                        raw_t,
                        filename=p_rec.get("filename", ""),
                        title_override=None if research_engine.is_citation_or_header_line(raw_stored_title) else raw_stored_title,
                    )
                    res_sc = research_engine.compute_researcher_quality_scores(raw_t, secs_t, base_res=p_rec)
                    meta_t = {
                        "title": auto_m["title"] if research_engine.is_citation_or_header_line(raw_stored_title) else raw_stored_title,
                        "authors": auto_m["authors"] if p_rec.get("authors") in (None, "", "Unknown Authors") else unescape_text(p_rec.get("authors")),
                        "year": unescape_text(p_rec.get("year") or auto_m.get("year") or ""),
                        "journal": auto_m["journal"] if p_rec.get("journal") in (None, "", "Manuscript / Preprint") else unescape_text(p_rec.get("journal")),
                        "domain": unescape_text(p_rec.get("domain") or "") if p_rec.get("domain") not in (None, "", "General") else auto_m.get("domain"),
                        "keywords": auto_m.get("keywords") or p_rec.get("keywords") or [],
                    }
                    selected_papers_payload.append({
                        "id": pid,
                        "title": meta_t["title"],
                        "filename": p_rec.get("filename", ""),
                        "text": raw_t,
                        "sections": secs_t,
                        "metadata": meta_t,
                        "profile": prof_t,
                        "scores": res_sc,
                        "overall_score": float(res_sc.get("overall_score") or 0.0),
                        "structure_score": float(res_sc.get("structure_score") or 0.0),
                        "clarity_score": float(res_sc.get("clarity_score") or 0.0),
                        "coherence_score": float(res_sc.get("coherence_score") or 0.0),
                        "citation_score": float(res_sc.get("citation_score") or 0.0),
                        "readability_score": float(res_sc.get("readability_score") or 0.0),
                    })
        else:
            up_files = st.file_uploader(
                "Upload 2 or 3 research papers (PDF, DOCX, TXT • Max 30 MB each)",
                type=["pdf", "docx", "txt"],
                accept_multiple_files=True,
                key="res_cmp_direct_uploader",
            )
            if up_files:
                if len(up_files) < 2:
                    st.warning("Please upload at least 2 manuscripts to compare.")
                elif len(up_files) > 3:
                    st.warning("Comparing the first 3 uploaded manuscripts (maximum 3 supported simultaneously).")
                for uf in (up_files or [])[:3]:
                    raw_extr = extract_text_from_file(uf)
                    if raw_extr and not str(raw_extr).startswith("__ERROR_"):
                        cleaned_u = clean_text(raw_extr)
                        secs_u = summarizer.segment_paper_sections(cleaned_u)
                        meta_u = research_engine.extract_paper_metadata(cleaned_u, filename=uf.name)
                        prof_u = research_engine.extract_research_profile(cleaned_u, secs_u)
                        ev_u = research_engine.compute_researcher_quality_scores(
                            cleaned_u, secs_u, base_res=analyze_full_document(cleaned_u) or {}
                        )
                        selected_papers_payload.append({
                            "id": None,
                            "title": meta_u["title"],
                            "filename": uf.name,
                            "text": cleaned_u,
                            "sections": secs_u,
                            "metadata": meta_u,
                            "profile": prof_u,
                            "scores": ev_u,
                            "overall_score": float(ev_u.get("overall_score") or 0.0),
                            "structure_score": float(ev_u.get("structure_score") or 0.0),
                            "clarity_score": float(ev_u.get("clarity_score") or 0.0),
                            "coherence_score": float(ev_u.get("coherence_score") or 0.0),
                            "citation_score": float(ev_u.get("citation_score") or 0.0),
                            "readability_score": float(ev_u.get("readability_score") or 0.0),
                        })

        render_html('<div style="height: 4px;"></div>')
        run_cmp_btn = st.button(
            "🔬 Generate Structured Comparison Matrix",
            type="primary",
            use_container_width=True,
            disabled=len(selected_papers_payload) < 2,
            key="res_btn_generate_comparison",
        )

    if run_cmp_btn and len(selected_papers_payload) >= 2:
        comp_bundle = research_engine.build_comparison_matrix_and_synthesis(selected_papers_payload)
        st.session_state["res_active_comparison"] = comp_bundle
        st.session_state["res_active_comparison_papers"] = selected_papers_payload
        # Save comparison record for History & Reports
        c_title = " vs. ".join(p["title"] for p in comp_bundle["papers"])
        p_ids = [int(p["id"]) for p in comp_bundle["papers"] if p.get("id")]
        auth.save_comparison_record(username, c_title, p_ids, comp_bundle)

    # Also auto-build if 2+ library papers are selected and no active comparison exists yet
    if not st.session_state.get("res_active_comparison") and len(selected_papers_payload) >= 2:
        st.session_state["res_active_comparison"] = research_engine.build_comparison_matrix_and_synthesis(selected_papers_payload)
        st.session_state["res_active_comparison_papers"] = selected_papers_payload

    comp_bundle = st.session_state.get("res_active_comparison")
    comp_papers = st.session_state.get("res_active_comparison_papers") or selected_papers_payload

    if not comp_bundle or len(comp_bundle.get("papers") or []) < 2:
        return

    enriched_papers = comp_bundle["papers"]
    shared_terms = comp_bundle.get("shared_terms") or []
    matrix_rows = comp_bundle.get("matrix_rows") or []

    # Cross-Domain Notice Banner (if papers span distinct domains)
    if comp_bundle.get("is_cross_domain") and comp_bundle.get("cross_domain_notice"):
        render_html([
            f'<div style="background: {theme["warning_bg"]}; border: 1px solid {theme["warning_border"]}; border-left: 4px solid {theme["warning_text"]}; border-radius: 10px; padding: 12px 16px; margin: 14px 0;">',
            f'<div style="font-size: 13px; font-weight: 700; color: {theme["warning_text"]}; margin-bottom: 3px;">🧭 Cross-Domain Comparison Notice</div>',
            f'<div style="font-size: 13px; color: {theme["text_primary"]}; line-height: 1.45;">{safe_text(comp_bundle["cross_domain_notice"])}</div>',
            '</div>',
        ])

    # Shared Overlapping Terms Banner
    if shared_terms:
        term_chips = "".join(
            f'<span style="background:rgba(56,189,248,0.18);color:#7dd3fc;border:1px solid rgba(56,189,248,0.35);padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:600;">{safe_text(t)}</span>'
            for t in shared_terms[:14]
        )
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 10px; padding: 10px 16px; margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">',
            f'<span style="font-size: 12px; font-weight: 700; color: {theme["text_secondary"]}; margin-right: 4px;">🔗 Overlapping Terms Highlighted Below:</span>',
            term_chips,
            '</div>',
        ])

    # =======================================================================
    # PRIMARY VIEW 1: Structured Comparison Matrix Table
    # =======================================================================
    render_html([
        '<div style="margin: 14px 0 8px 0;">',
        f'<h3 style="margin: 0; font-size: 20px; font-weight: 800; color: {theme["text_primary"]};">1. Structured Research Content Matrix (Primary View)</h3>',
        f'<p style="margin: 2px 0 0 0; font-size: 12.5px; color: {theme["text_muted"]};">Side-by-side comparison of extracted Research Profiles. Overlapping conceptual terms are highlighted across columns.</p>',
        '</div>',
    ])

    tbl_html = [
        f'<div style="overflow-x: auto; border: 1px solid {theme["border_color"]}; border-radius: 12px; margin-bottom: 20px;">',
        f'<table style="width: 100%; border-collapse: collapse; background: {theme["bg_card"]}; font-size: 13px;">',
        '<thead>',
        f'<tr style="background: {theme["bg_card_inner"]}; border-bottom: 2px solid {theme["border_color"]};">',
        f'<th style="padding: 12px 14px; text-align: left; width: 17%; color: {theme["text_muted"]}; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em;">Research Dimension</th>',
    ]
    col_w = int(83 / len(enriched_papers))
    for ep in enriched_papers:
        full_t = ep["title"]
        tbl_html.append(
            f'<th style="padding: 12px 14px; text-align: left; width: {col_w}%; color: {theme["text_primary"]}; font-size: 13.5px; font-weight: 700; border-left: 1px solid {theme["border_divider"]};" title="{safe_text(full_t)}">'
            f'<div style="color: {theme["accent_purple"]}; font-size: 11px; text-transform: uppercase;">Paper {ep["index"]} • {safe_text(ep["domain"])}</div>'
            f'<div style="margin-top: 2px; line-height: 1.35;">{safe_text(full_t)}</div>'
            f'</th>'
        )
    tbl_html.extend(['</tr>', '</thead>', '<tbody>'])

    for r_idx, row in enumerate(matrix_rows):
        row_bg = theme["bg_card"] if r_idx % 2 == 0 else theme["bg_card_inner"]
        dim_lbl = row["dimension"]
        cells = row["cells"]
        secs = row.get("sections") or []
        tbl_html.append(f'<tr style="background: {row_bg}; border-bottom: 1px solid {theme["border_divider"]};">')
        tbl_html.append(
            f'<td style="padding: 12px 14px; vertical-align: top; font-weight: 700; color: {theme["text_primary"]};">{safe_text(dim_lbl)}</td>'
        )
        for c_i, cell_val in enumerate(cells):
            is_not_found = (cell_val == research_engine.NOT_FOUND_SENTINEL)
            formatted_cell = (
                f'<span style="color: {theme["text_muted"]}; font-style: italic;">{safe_text(cell_val)}</span>'
                if is_not_found
                else research_engine.highlight_shared_terms_html(cell_val, shared_terms)
            )
            sec_tag = ""
            if c_i < len(secs) and secs[c_i] and secs[c_i] != "—":
                sec_tag = f'<div style="margin-top: 6px; font-size: 11px; color: {theme["text_muted"]};">📍 Section: {safe_text(secs[c_i])}</div>'
            tbl_html.append(
                f'<td style="padding: 12px 14px; vertical-align: top; color: {theme["text_secondary"]}; line-height: 1.5; border-left: 1px solid {theme["border_divider"]};">'
                f'{formatted_cell}{sec_tag}'
                f'</td>'
            )
        tbl_html.append('</tr>')

    tbl_html.extend(['</tbody>', '</table>', '</div>'])
    render_html(tbl_html)

    # =======================================================================
    # PRIMARY VIEW 2: Data-Driven Comparative Synthesis (Similarities & Differences)
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 10px 0;">',
        f'<h3 style="margin: 0; font-size: 20px; font-weight: 800; color: {theme["text_primary"]};">2. Comparative Synthesis</h3>',
        '</div>',
    ])
    syn_c1, syn_c2 = st.columns(2, gap="medium")
    with syn_c1:
        sim_items = "".join(
            f'<li style="margin-bottom: 8px; line-height: 1.5;">{research_engine.highlight_shared_terms_html(s, shared_terms)}</li>'
            for s in (comp_bundle.get("similarities") or [])
        )
        render_html([
            f'<div class="iq-card" style="padding: 16px 20px !important; border-top: 3px solid {theme["success_text"]}; min-height: 185px;">',
            f'<div style="font-size: 14.5px; font-weight: 700; color: {theme["success_text"]}; margin-bottom: 10px;">🤝 Methodological &amp; Conceptual Similarities</div>',
            f'<ul style="margin: 0; padding-left: 18px; color: {theme["text_primary"]}; font-size: 13px;">{sim_items}</ul>',
            '</div>',
        ])
    with syn_c2:
        diff_items = "".join(
            f'<li style="margin-bottom: 8px; line-height: 1.5;">{safe_text(d)}</li>'
            for d in (comp_bundle.get("differences") or [])
        )
        render_html([
            f'<div class="iq-card" style="padding: 16px 20px !important; border-top: 3px solid #F59E0B; min-height: 185px;">',
            f'<div style="font-size: 14.5px; font-weight: 700; color: #F59E0B; margin-bottom: 10px;">⚡ Empirical &amp; Design Divergences</div>',
            f'<ul style="margin: 0; padding-left: 18px; color: {theme["text_primary"]}; font-size: 13px;">{diff_items}</ul>',
            '</div>',
        ])

    # Export Buttons (PDF + TXT)
    ex_c1, ex_c2 = st.columns(2)
    with ex_c1:
        try:
            cmp_pdf_bytes = pdf_export.build_comparison_pdf(comp_papers, comp_bundle)
            st.download_button(
                "⬇ Download Comparison Report (PDF)",
                data=cmp_pdf_bytes,
                file_name=pdf_export.get_pdf_filename("Multi_Paper_Comparison", "Comparison_Report"),
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="res_cmp_dl_pdf",
            )
        except Exception as pdf_err:
            st.error(f"Could not generate Comparison PDF: {pdf_err}")
    with ex_c2:
        cmp_txt_str = pdf_export.build_researcher_comparison_txt(enriched_papers, comp_bundle)
        st.download_button(
            "⬇ Download Comparison Report (TXT)",
            data=cmp_txt_str.encode("utf-8"),
            file_name="PaperIQ_Advanced_Paper_Comparison.txt",
            mime="text/plain",
            use_container_width=True,
            key="res_cmp_dl_txt",
        )

    # =======================================================================
    # SECONDARY VIEW (LAST): Writing-Score Radar & Bar Chart
    # =======================================================================
    render_html("<div style='height: 14px;'></div>")
    with st.expander("📊 Secondary View: Manuscript Writing Quality Comparison (Radar & Dimension Bar Charts)", expanded=False):
        dims = ["Structure", "Clarity", "Coherence", "Citations", "Readability"]
        dim_keys = ["structure_score", "clarity_score", "coherence_score", "citation_score", "readability_score"]
        palette = ["#8B5CF6", "#06B6D4", "#F59E0B"]

        ch_c1, ch_c2 = st.columns(2)
        with ch_c1:
            fig_r = go.Figure()
            for idx, ep in enumerate(enriched_papers):
                vals = [float(ep["scores"].get(dk, 0.0)) for dk in dim_keys]
                fig_r.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=dims + [dims[0]],
                    fill="toself",
                    name=f"P{ep['index']}: {ep['title'][:28]}",
                    line=dict(color=palette[idx % len(palette)], width=2),
                ))
            fig_r.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=theme["text_primary"]),
                margin=dict(l=30, r=30, t=30, b=30),
                height=320,
            )
            st.plotly_chart(fig_r, use_container_width=True)

        with ch_c2:
            fig_b = go.Figure()
            for idx, ep in enumerate(enriched_papers):
                vals = [float(ep["scores"].get(dk, 0.0)) for dk in dim_keys]
                fig_b.add_trace(go.Bar(
                    name=f"P{ep['index']}: {ep['title'][:28]}",
                    x=dims,
                    y=vals,
                    marker_color=palette[idx % len(palette)],
                ))
            fig_b.update_layout(
                barmode="group",
                yaxis=dict(range=[0, 108]),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=theme["text_primary"]),
                margin=dict(l=30, r=30, t=30, b=30),
                height=320,
            )
            st.plotly_chart(fig_b, use_container_width=True)
