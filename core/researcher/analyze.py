"""
PaperIQ — Researcher Page 2: Analyze Research Paper (C2)
========================================================
Requirements:
- Upload PDF/DOCX/TXT.
- Auto-extract and show editable metadata: Title, Authors, Year, Journal/Venue, Detected Domain, Top Keywords.
- "Add to project" selector (choose existing or create new).
- PRIMARY output — "Research Profile" card:
    * Research Objective
    * Methodology
    * Data / Sample / Materials
    * Key Results (prioritizing sentences with numbers/percentages)
    * Main Contributions
    * Limitations
  Each field shows the detected source section, a confidence badge, and "Not found in this manuscript" if absent.
- Summary modes (Short / Medium / Long) with PDF + TXT download.
- SECONDARY output — collapsed "Manuscript Quality" section with the 5 writing dimensions + composite score.
- Findings generated directly from the extracted text and metrics of THAT paper (zero hardcoded template sentences).
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, List, Optional
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import format_title_with_tooltip_html, render_html, safe_text, truncate_title_word_boundary, unescape_text


def _confidence_badge_html(conf: str, theme: Dict[str, str]) -> str:
    c_up = (conf or "Not found").strip()
    if c_up == "High":
        bg, fg, bd = theme["success_bg"], theme["success_text"], theme["success_border"]
        lbl = "High Confidence"
    elif c_up in ("Moderate", "Medium"):
        bg, fg, bd = theme["warning_bg"], theme["warning_text"], theme["warning_border"]
        lbl = "Moderate Confidence"
    elif c_up == "Low":
        bg, fg, bd = "rgba(245,158,11,0.12)", "#fbbf24", "rgba(245,158,11,0.35)"
        lbl = "Low Confidence"
    else:
        bg, fg, bd = "rgba(148,163,184,0.12)", theme["text_muted"], theme["border_color"]
        lbl = "Not found"
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:2px 7px;font-size:10.5px;font-weight:700;">'
        f'{safe_text(lbl)}</span>'
    )


def render_analyze_research_paper(
    theme: Dict[str, str],
    username: str,
    navigate_to: Callable[[str], None],
    extract_text_from_file: Callable[[Any], str],
    clean_text: Callable[[str], str],
    analyze_full_document: Callable[[str], Dict[str, Any]],
    get_clean_display_title: Callable[..., str],
) -> None:
    """Render Researcher Page 2: Analyze Research Paper."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">🔬 Content-First Manuscript Evaluation</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Analyze Research Paper</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Extract structured Research Profiles (Objectives, Methodology, Data, Quantitative Results, Contributions, Limitations), edit bibliographic metadata, assign to projects, and generate source-grounded summaries.</p>',
        '</div>',
    ])

    # Unified Upload Section Card
    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 2px;">',
            f'<h3 style="margin: 0; font-size: 16px; color: {theme["text_primary"]}; font-weight: 700;">📄 Upload Research Manuscript</h3>',
            f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; border-radius: 6px; padding: 2px 8px; font-size: 11px; color: {theme["badge_role_text"]}; font-weight: 600;">PDF, DOCX, TXT • Max 30 MB</span>',
            '</div>',
            f'<p style="color: {theme["text_muted"]}; font-size: 12.5px; margin: 0 0 6px 0;">Upload a new manuscript or inspect a manuscript from your Research Library below.</p>',
        ])
        uploaded_file = st.file_uploader(
            "Upload research document",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=False,
            label_visibility="collapsed",
            key=f"res_file_uploader_{st.session_state.get('uploader_key', 0)}",
        )

    # Determine if user just uploaded a file
    if uploaded_file is not None:
        raw_bytes = uploaded_file.getvalue()
        file_size_mb = len(raw_bytes) / (1024 * 1024)
        if file_size_mb > 30.0:
            st.error(f"⚠️ File '{uploaded_file.name}' ({file_size_mb:.1f} MB) exceeds the 30 MB maximum upload size.")
            return
        ext = uploaded_file.name.rsplit(".", 1)[-1].upper() if "." in uploaded_file.name else "TXT"

        if st.session_state.get("res_preview_filename") != uploaded_file.name:
            try:
                extracted_raw = extract_text_from_file(uploaded_file)
            except Exception as ex:
                extracted_raw = f"__ERROR_EXCEPTION__: {ex}"

            st.session_state["res_preview_filename"] = uploaded_file.name
            st.session_state["res_preview_raw"] = extracted_raw
            if extracted_raw and not str(extracted_raw).startswith("__ERROR_"):
                cleaned_preview = clean_text(extracted_raw)
                st.session_state["res_preview_clean"] = cleaned_preview
                st.session_state["res_preview_meta"] = research_engine.extract_paper_metadata(
                    cleaned_preview, filename=uploaded_file.name
                )
            else:
                st.session_state["res_preview_clean"] = ""
                st.session_state["res_preview_meta"] = {}

        extracted_raw = st.session_state.get("res_preview_raw", "")
        cleaned_preview = st.session_state.get("res_preview_clean", "")
        preview_meta = st.session_state.get("res_preview_meta") or {}

        # Handle extraction errors clearly
        if str(extracted_raw).startswith("__ERROR_"):
            err_code = str(extracted_raw)
            if "SCANNED_PDF" in err_code:
                st.error("⚠️ Scanned or image-only PDF detected. Please use OCR or upload a text-based PDF, DOCX, or TXT manuscript.")
            elif "PASSWORD" in err_code:
                st.error("⚠️ Password-protected PDF detected. Please remove encryption before uploading.")
            elif "EMPTY" in err_code:
                st.error("⚠️ The uploaded file is empty or contains no readable text.")
            else:
                st.error(f"⚠️ Could not extract readable text from '{uploaded_file.name}'.")
            return

        counts = summarizer.compute_text_counts(cleaned_preview)
        word_count = counts["word_count"]
        sent_count = counts["sentence_count"]
        est_pages = max(1, math.ceil(word_count / 450)) if word_count > 0 else 1

        render_html([
            f'<div class="iq-card" style="padding: 14px 18px !important; margin-bottom: 14px; border-left: 4px solid {theme["success_text"]};">',
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">',
            f'<span style="font-size: 11px; font-weight: 700; color: {theme["success_text"]}; text-transform: uppercase; letter-spacing: 0.06em;">✓ Manuscript Ready for Research Profiling</span>',
            f'<span style="font-size: 11.5px; color: {theme["text_secondary"]};">{safe_text(ext)} • {file_size_mb:.2f} MB • {word_count:,} words • {sent_count:,} sentences (~{est_pages} pages)</span>',
            '</div>',
            f'<div style="font-size: 15px; font-weight: 700; color: {theme["text_primary"]};">📄 {safe_text(preview_meta.get("title") or uploaded_file.name)}</div>',
            '</div>',
        ])

        # Pre-analysis Editable Metadata & Project Assignment Form
        user_projects = auth.get_user_projects(username)
        proj_map_up = {p["name"]: p["id"] for p in user_projects}
        proj_options = ["— None (Keep in General Library) —"] + list(proj_map_up.keys()) + ["➕ Create New Project..."]

        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f"<div style='font-size: 14px; font-weight: 700; color: {theme['text_primary']}; margin-bottom: 6px;'>📋 Auto-Extracted Bibliographic Metadata &amp; Project Assignment (Editable)</div>",
            ])
            mc1, mc2 = st.columns([2.2, 1.2], gap="medium")
            with mc1:
                ed_title = st.text_input("Manuscript Title", value=preview_meta.get("title", uploaded_file.name), key="res_up_title")
                ed_authors = st.text_input("Authors", value=preview_meta.get("authors", "Not found"), key="res_up_authors")
            with mc2:
                ed_year = st.text_input("Publication Year", value=preview_meta.get("year", ""), key="res_up_year")
                ed_journal = st.text_input("Journal / Venue", value=preview_meta.get("journal", "Manuscript / Preprint"), key="res_up_journal")

            mc3, mc4, mc5 = st.columns([1.2, 1.4, 1.4], gap="medium")
            domain_choices = list(research_engine.DOMAIN_KEYWORDS.keys()) + ["Interdisciplinary / General Research"]
            detected_dom = preview_meta.get("domain") or "Interdisciplinary / General Research"
            if detected_dom not in domain_choices:
                domain_choices.insert(0, detected_dom)
            with mc3:
                ed_domain = st.selectbox("Detected Discipline / Domain", options=domain_choices, index=domain_choices.index(detected_dom), key="res_up_domain")
            with mc4:
                default_kws = ", ".join(preview_meta.get("keywords", [])[:10])
                ed_keywords_str = st.text_input("Top Keywords (comma-separated)", value=default_kws, key="res_up_keywords")
            with mc5:
                sel_proj_choice = st.selectbox("Add to Project", options=proj_options, key="res_up_proj_choice")

            inline_new_proj_name = ""
            if sel_proj_choice == "➕ Create New Project...":
                inline_new_proj_name = st.text_input("New Project Name", key="res_up_inline_proj_name", placeholder="e.g., Millet Growth & Agricultural Economics")

            ed_tags_str = st.text_input("Custom Library Tags (optional, comma-separated)", value="", key="res_up_tags", placeholder="e.g., empirical, benchmark, priority-read")

            render_html('<div style="height: 4px;"></div>')
            run_eval_btn = st.button(
                "🔬 Run Research Profile & Save to Library",
                type="primary",
                use_container_width=True,
                key="btn_res_run_full_eval",
            )

        if run_eval_btn:
            with st.status("Extracting structured Research Profile, indexing metadata, and computing manuscript metrics...", expanded=True) as status:
                st.write("✓ Cleaning text & segmenting academic sections...")
                sections_map = summarizer.segment_paper_sections(cleaned_preview)
                eval_res = analyze_full_document(cleaned_preview) or {}
                res_q_scores = research_engine.compute_researcher_quality_scores(
                    cleaned_preview, sections_map, base_res=eval_res
                )
                eval_res.update(res_q_scores)
                profile = research_engine.extract_research_profile(cleaned_preview, sections_map)
                counts_info = summarizer.compute_text_counts(cleaned_preview)
                findings_list = research_engine.generate_text_grounded_findings(
                    cleaned_preview, sections_map, counts_info, eval_res, profile
                )

                kw_list = [k.strip() for k in ed_keywords_str.split(",") if k.strip()]
                if not kw_list:
                    kw_list = preview_meta.get("keywords", [])
                themes_objs = research_engine.group_keywords_into_themes(
                    [{"term": k, "count": 2, "weight": 2.0} for k in kw_list],
                    domain=ed_domain,
                )
                topics_list = [t["theme"] for t in themes_objs]

                # Generate default Medium summary automatically so report is complete
                sum_res = summarizer.summarize_research_paper(
                    text=cleaned_preview,
                    summary_type="Medium",
                    filename=uploaded_file.name,
                    doc_title=ed_title.strip() or uploaded_file.name,
                )
                summary_text = sum_res.get("summary", "") if sum_res.get("success") else ""

                # Save to analyses table
                analysis_id = auth.save_user_analysis(
                    username=username,
                    filename=uploaded_file.name,
                    paper_title=ed_title.strip() or uploaded_file.name,
                    overall_score=float(eval_res.get("overall_score", 0.0)),
                    structure_score=float(eval_res.get("structure_score", 0.0)),
                    clarity_score=float(eval_res.get("clarity_score", 0.0)),
                    coherence_score=float(eval_res.get("coherence_score", 0.0)),
                    citation_score=float(eval_res.get("citation_score", 0.0)),
                    readability_score=float(eval_res.get("readability_score", 0.0)),
                    summary=summary_text,
                    feedback=findings_list,
                    extracted_text=cleaned_preview,
                    sections=sections_map,
                    metrics={
                        "word_count": counts_info["word_count"],
                        "sentence_count": counts_info["sentence_count"],
                        "citation_count": eval_res.get("citation_count", 0),
                        "in_text_citation_count": eval_res.get("in_text_citation_count", 0),
                        "reference_list_count": eval_res.get("reference_list_count", 0),
                        "driven_by": eval_res.get("driven_by", {}),
                        "research_profile": profile,
                        "findings": findings_list,
                    },
                    domain=ed_domain,
                )

                if analysis_id:
                    auth.upsert_paper_metadata(
                        username=username,
                        analysis_id=analysis_id,
                        authors=ed_authors.strip() or "Not found",
                        year=ed_year.strip(),
                        journal=ed_journal.strip() or "Manuscript / Preprint",
                        keywords=kw_list,
                        topics=topics_list,
                        domain=ed_domain,
                    )

                    # Handle project assignment
                    target_proj_id = None
                    if sel_proj_choice == "➕ Create New Project..." and inline_new_proj_name.strip():
                        ok_p, _, new_pid = auth.create_project(username, inline_new_proj_name.strip(), f"Created during analysis of {ed_title[:50]}")
                        if ok_p and new_pid:
                            target_proj_id = new_pid
                    elif sel_proj_choice in proj_map_up:
                        target_proj_id = proj_map_up[sel_proj_choice]

                    if target_proj_id:
                        auth.assign_paper_to_project(username, target_proj_id, analysis_id)

                    # Handle tags
                    tag_list = [t.strip() for t in ed_tags_str.split(",") if t.strip()]
                    if tag_list:
                        auth.set_paper_tags(username, analysis_id, tag_list)

                    auth.log_research_activity(
                        username,
                        "ANALYZE_PAPER",
                        ed_title.strip() or uploaded_file.name,
                        f"Extracted Research Profile in {ed_domain} ({counts_info['word_count']:,} words)",
                    )

                    # Load into active session
                    loaded = auth.get_single_analysis_for_user(username, analysis_id)
                    if loaded:
                        st.session_state["current_analysis_id"] = analysis_id
                        st.session_state["paper_title"] = ed_title.strip()
                        st.session_state["filename"] = uploaded_file.name
                        st.session_state["text"] = cleaned_preview
                        st.session_state["sections"] = sections_map
                        st.session_state["results"] = eval_res
                        st.session_state["active_analysis"] = eval_res
                        st.session_state["summary_result"] = sum_res
                        st.session_state["summary_doc_text"] = cleaned_preview
                        st.session_state["summary_doc_name"] = uploaded_file.name
                        st.session_state["res_active_record"] = loaded

                status.update(label="Research Profile extracted & saved to Library!", state="complete", expanded=False)
                st.success(f"✓ '{ed_title}' analyzed and indexed in your Research Library.")

    # -----------------------------------------------------------------------
    # Display Active Analyzed Paper (either just analyzed or loaded from Library/Dashboard)
    # -----------------------------------------------------------------------
    lib_list = auth.get_researcher_library(username)
    active_id = st.session_state.get("current_analysis_id")
    active_rec = None
    if active_id is not None and str(active_id).isdigit():
        active_rec = auth.get_single_analysis_for_user(username, int(active_id))
    if not active_rec and st.session_state.get("text"):
        # Synthesize in-memory record if user has text in session
        raw_t = unescape_text(st.session_state.get("text") or "")
        secs_t = st.session_state.get("sections") or summarizer.segment_paper_sections(raw_t)
        meta_t = research_engine.extract_paper_metadata(raw_t, filename=st.session_state.get("filename", ""), title_override=st.session_state.get("paper_title"))
        res_t = research_engine.compute_researcher_quality_scores(raw_t, secs_t, base_res=st.session_state.get("results") or {})
        active_rec = {
            "id": None,
            "paper_title": meta_t["title"],
            "filename": st.session_state.get("filename", "Manuscript.txt"),
            "extracted_text": raw_t,
            "sections": secs_t,
            "authors": meta_t["authors"],
            "year": meta_t["year"],
            "journal": meta_t["journal"],
            "domain": meta_t["domain"],
            "keywords": meta_t["keywords"],
            "topics": meta_t["topics"],
            "overall_score": res_t.get("overall_score", 0.0),
            "structure_score": res_t.get("structure_score", 0.0),
            "clarity_score": res_t.get("clarity_score", 0.0),
            "coherence_score": res_t.get("coherence_score", 0.0),
            "citation_score": res_t.get("citation_score", 0.0),
            "readability_score": res_t.get("readability_score", 0.0),
            "summary": (st.session_state.get("summary_result") or {}).get("summary", ""),
            "projects": [],
            "tags": [],
        }

    if not active_rec and lib_list:
        active_rec = auth.get_single_analysis_for_user(username, int(lib_list[0]["id"])) or lib_list[0]

    if lib_list:
        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f"<div style='font-size: 13.5px; font-weight: 700; color: {theme['text_primary']}; margin-bottom: 2px;'>📚 Switch Active Library Manuscript</div>",
            ])
            opts = {}
            curr_idx = 0
            for idx_p, p in enumerate(lib_list):
                yr_s = p.get("year") or "n.d."
                base_lbl = f"{unescape_text(p['paper_title'])} ({yr_s})"
                lbl = base_lbl if base_lbl not in opts else f"{base_lbl} — {p.get('domain', 'Research')}"
                opts[lbl] = p["id"]
                if active_rec and p["id"] == active_rec.get("id"):
                    curr_idx = idx_p
            c_pick1, c_pick2 = st.columns([3.2, 1.0], gap="small")
            with c_pick1:
                picked_lbl = st.selectbox("Select Library Manuscript", options=list(opts.keys()), index=curr_idx, label_visibility="collapsed", key="res_anl_pick_existing")
            with c_pick2:
                if st.button("Load Manuscript", key="res_anl_btn_load_existing", use_container_width=True, type="primary"):
                    st.session_state["current_analysis_id"] = opts[picked_lbl]
                    st.rerun()

    if not active_rec:
        return

    # Unpack active record
    rec_id = active_rec.get("id")
    p_text = unescape_text(active_rec.get("extracted_text") or st.session_state.get("text") or "")
    p_secs = active_rec.get("sections") if isinstance(active_rec.get("sections"), dict) and active_rec.get("sections") else summarizer.segment_paper_sections(p_text)
    # Ensure p_secs excludes Preamble and Keywords
    p_secs = {
        k: v for k, v in (p_secs or {}).items()
        if k and k != "Preamble" and not k.strip().lower().startswith("keyword")
    }
    raw_stored_title = unescape_text(active_rec.get("paper_title") or active_rec.get("filename") or "Untitled Manuscript")
    auto_meta = research_engine.extract_paper_metadata(
        p_text,
        filename=active_rec.get("filename", ""),
        title_override=None if research_engine.is_citation_or_header_line(raw_stored_title) else raw_stored_title,
    )
    p_title = auto_meta.get("title") or raw_stored_title

    stored_authors = unescape_text(active_rec.get("authors") or "")
    if not stored_authors or stored_authors == "Unknown Authors":
        p_authors = auto_meta.get("authors") or "Not found"
    else:
        p_authors = stored_authors

    p_year = unescape_text(active_rec.get("year") or auto_meta.get("year") or "")
    stored_journal = unescape_text(active_rec.get("journal") or "")
    if not stored_journal or (stored_journal == "Manuscript / Preprint" and auto_meta.get("journal") != "Manuscript / Preprint"):
        p_journal = auto_meta.get("journal") or "Manuscript / Preprint"
    else:
        p_journal = stored_journal

    p_domain = unescape_text(active_rec.get("domain") or auto_meta.get("domain") or "Interdisciplinary")
    if p_domain == "General":
        p_domain = auto_meta.get("domain") or "Interdisciplinary"
    p_keywords = auto_meta.get("keywords") or active_rec.get("keywords") or []
    p_topics = auto_meta.get("topics") or active_rec.get("topics") or []

    metrics_dict = active_rec.get("metrics") if isinstance(active_rec.get("metrics"), dict) else {}
    profile = research_engine.extract_research_profile(p_text, p_secs)
    counts_info = summarizer.compute_text_counts(p_text)
    scores_dict = research_engine.compute_researcher_quality_scores(p_text, p_secs, base_res=active_rec)
    findings = research_engine.generate_text_grounded_findings(p_text, p_secs, counts_info, scores_dict, profile)

    render_html(f"<hr style='border: none; border-top: 1px solid {theme['border_divider']}; margin: 18px 0;'>")

    # Active Paper Header & Metadata Banner
    kw_pills_html = "".join(
        f'<span style="background: {theme["bg_card"]}; border: 1px solid {theme["border_color"]}; color: {theme["text_secondary"]}; border-radius: 999px; padding: 2px 9px; font-size: 11.5px; font-weight: 600;">#{safe_text(k)}</span>'
        for k in p_keywords[:10]
    )
    proj_names = [pr["name"] for pr in (active_rec.get("projects") or [])]
    proj_pills_html = "".join(
        f'<span style="background: rgba(6,182,212,0.15); border: 1px solid rgba(6,182,212,0.35); color: #22d3ee; border-radius: 6px; padding: 2px 8px; font-size: 11.5px; font-weight: 700;">📁 {safe_text(pn)}</span>'
        for pn in proj_names
    )

    render_html([
        f'<div class="iq-card" style="padding: 20px 24px !important; margin-bottom: 16px; border-top: 3px solid {theme["accent_purple"]};">',
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">',
        '<div>',
        '<div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px;">',
        f'<span style="background: {theme["accent_primary_subtle"]}; border: 1px solid {theme["accent_primary_border"]}; color: {theme["accent_purple"]}; border-radius: 6px; padding: 2px 9px; font-size: 11.5px; font-weight: 700;">🧭 {safe_text(p_domain)}</span>',
        proj_pills_html,
        f'<span style="color: {theme["text_muted"]}; font-size: 12px;">• {counts_info["word_count"]:,} words • {counts_info["sentence_count"]:,} sentences • {len(p_secs)} sections • {scores_dict.get("in_text_citation_count", 0)} in-text citations ({scores_dict.get("reference_list_count", 0)} references)</span>',
        '</div>',
        f'<h2 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 800; color: {theme["text_primary"]}; line-height: 1.3;" title="{safe_text(p_title)}">{safe_text(p_title)}</h2>',
        f'<div style="font-size: 13.5px; color: {theme["text_secondary"]};">👤 <b>Authors:</b> {safe_text(p_authors)} &nbsp;|&nbsp; 📅 <b>Year:</b> {safe_text(p_year or "n.d.")} &nbsp;|&nbsp; 🏛️ <b>Venue:</b> {safe_text(p_journal)}</div>',
        '</div>',
        '</div>',
        f'<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px;">{kw_pills_html}</div>' if kw_pills_html else '',
        '</div>',
    ])

    # Editable Metadata, Refresh Metadata & Project Assignment Expander for Saved Paper
    if rec_id:
        with st.expander("✏️ Edit Manuscript Metadata, Refresh Extraction, Project Assignment & Tags", expanded=False):
            all_projs = auth.get_user_projects(username)
            curr_proj_ids = {pr["id"] for pr in (active_rec.get("projects") or [])}
            u_title = st.text_input("Manuscript Title", value=p_title, key=f"edit_meta_title_{rec_id}")
            e_c1, e_c2 = st.columns(2)
            with e_c1:
                u_authors = st.text_input("Authors", value=p_authors, key=f"edit_meta_auth_{rec_id}")
                u_year = st.text_input("Year", value=p_year, key=f"edit_meta_yr_{rec_id}")
                u_journal = st.text_input("Journal / Venue", value=p_journal, key=f"edit_meta_jr_{rec_id}")
            with e_c2:
                dom_opts = list(research_engine.DOMAIN_KEYWORDS.keys()) + ["Interdisciplinary / General Research"]
                if p_domain not in dom_opts:
                    dom_opts.insert(0, p_domain)
                u_domain = st.selectbox("Research Domain", options=dom_opts, index=dom_opts.index(p_domain), key=f"edit_meta_dom_{rec_id}")
                u_kws = st.text_input("Keywords (comma-separated)", value=", ".join(p_keywords), key=f"edit_meta_kws_{rec_id}")
                u_tags = st.text_input("Tags (comma-separated)", value=", ".join(active_rec.get("tags") or []), key=f"edit_meta_tags_{rec_id}")

            proj_name_map = {pr["name"]: pr["id"] for pr in all_projs}
            default_proj_names = [pr["name"] for pr in all_projs if pr["id"] in curr_proj_ids]
            sel_proj_names = st.multiselect(
                "Assigned Projects",
                options=list(proj_name_map.keys()),
                default=default_proj_names,
                key=f"edit_meta_projs_{rec_id}",
            )
            new_inline_p = st.text_input("Or create & assign to a new project", key=f"edit_meta_newproj_{rec_id}", placeholder="Enter new project name...")

            b_save_col, b_ref_col = st.columns(2)
            with b_save_col:
                if st.button("💾 Save Metadata & Project Changes", key=f"btn_save_meta_{rec_id}", type="primary", use_container_width=True):
                    kw_clean = [k.strip() for k in u_kws.split(",") if k.strip()]
                    if u_title.strip() and u_title.strip() != p_title:
                        conn_u = auth.get_db_connection()
                        try:
                            conn_u.execute("UPDATE analyses SET paper_title = ? WHERE id = ?", (u_title.strip(), rec_id))
                            conn_u.commit()
                        finally:
                            conn_u.close()
                    auth.upsert_paper_metadata(
                        username=username,
                        analysis_id=rec_id,
                        authors=u_authors.strip() or "Not found",
                        year=u_year.strip(),
                        journal=u_journal.strip() or "Manuscript / Preprint",
                        keywords=kw_clean,
                        topics=p_topics,
                        domain=u_domain,
                    )
                    chosen_pids = [proj_name_map[n] for n in sel_proj_names if n in proj_name_map]
                    if new_inline_p.strip():
                        ok_np, _, np_id = auth.create_project(username, new_inline_p.strip())
                        if ok_np and np_id:
                            chosen_pids.append(np_id)
                    auth.set_paper_projects(username, rec_id, chosen_pids)
                    auth.set_paper_tags(username, rec_id, [t.strip() for t in u_tags.split(",") if t.strip()])
                    st.session_state["paper_title"] = u_title.strip() or p_title
                    st.success("✓ Metadata, project assignments, and tags updated.")
                    st.rerun()
            with b_ref_col:
                if st.button("🔄 Refresh Metadata from Manuscript Text", key=f"btn_refresh_meta_{rec_id}", use_container_width=True):
                    ref_res = auth.refresh_paper_metadata(rec_id, username)
                    if ref_res.get("ok"):
                        st.session_state["paper_title"] = ref_res.get("title", p_title)
                        st.success(f"✓ Re-derived Title ('{ref_res.get('title')}'), Authors, Venue, Sections, and 5 Quality Scores.")
                        st.rerun()
                    else:
                        st.warning(ref_res.get("message", "Could not refresh metadata."))

    # =======================================================================
    # PRIMARY OUTPUT: Structured Research Profile Card (6 Fields)
    # =======================================================================
    render_html([
        '<div style="margin: 18px 0 10px 0;">',
        f'<h3 style="margin: 0; font-size: 20px; font-weight: 800; color: {theme["text_primary"]};">🔬 Primary Research Profile</h3>',
        f'<p style="margin: 2px 0 0 0; font-size: 13px; color: {theme["text_muted"]};">Extracted directly from manuscript sections. Fields without textual evidence are explicitly marked as <i>"Not found in this manuscript"</i>.</p>',
        '</div>',
    ])

    field_grid = [
        ("objective", "🎯 Research Objective", "#8B5CF6"),
        ("methodology", "⚙️ Methodology & Design", "#06B6D4"),
        ("data_materials", "🗄️ Data / Sample / Materials", "#10B981"),
        ("key_results", "📈 Key Results & Quantitative Findings", "#F59E0B"),
        ("contributions", "🌟 Main Contributions", "#3B82F6"),
        ("limitations", "⚠️ Limitations & Constraints", "#EF4444"),
    ]

    for row_start in range(0, len(field_grid), 2):
        cols = st.columns(2, gap="medium")
        for col_idx in range(2):
            f_key, f_title, f_color = field_grid[row_start + col_idx]
            f_data = profile.get(f_key) or {}
            f_found = bool(f_data.get("found"))
            f_val = unescape_text(f_data.get("value") or research_engine.NOT_FOUND_SENTINEL)
            f_sec = unescape_text(f_data.get("section") or "—")
            f_conf = unescape_text(f_data.get("confidence") or "Not Found")
            conf_badge = _confidence_badge_html(f_conf, theme)

            text_style = (
                f"color: {theme['text_primary']}; font-size: 13.5px; line-height: 1.55;"
                if f_found
                else f"color: {theme['text_muted']}; font-size: 13.5px; font-style: italic;"
            )
            with cols[col_idx]:
                render_html([
                    f'<div class="iq-card" style="padding: 16px 18px !important; border-left: 4px solid {f_color}; min-height: 165px; margin-bottom: 12px; display: flex; flex-direction: column; justify-content: space-between;">',
                    '<div>',
                    '<div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">',
                    f'<span style="font-size: 14px; font-weight: 700; color: {theme["text_primary"]};">{safe_text(f_title)}</span>',
                    conf_badge,
                    '</div>',
                    f'<div style="{text_style}">{safe_text(f_val)}</div>',
                    '</div>',
                    f'<div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid {theme["border_divider"]}; font-size: 11.5px; color: {theme["text_muted"]};">📍 Source Section: <b style="color: {theme["text_secondary"]};">{safe_text(f_sec)}</b></div>',
                    '</div>',
                ])

    # =======================================================================
    # Manuscript Structure & Evidence Density (Accurate Section & Citation Telemetry)
    # =======================================================================
    if findings:
        f_lines = [
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;">'
        ]
        for idx, fd in enumerate(findings):
            b_bot = f"border-bottom: 1px solid {theme['border_divider']}; padding-bottom: 10px; margin-bottom: 10px;" if idx < len(findings) - 1 else ""
            f_lines.extend([
                f'<div style="{b_bot}">',
                '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">',
                f'<span style="font-size: 12.5px; font-weight: 700; color: {theme["accent_purple"]};">📐 {safe_text(fd.get("category", "Manuscript Structure & Evidence Density"))}</span>',
                f'<span style="font-size: 11px; color: {theme["text_muted"]};">Scope: {safe_text(fd.get("section", "Full Manuscript"))}</span>',
                '</div>',
                f'<div style="font-size: 13.5px; color: {theme["text_primary"]}; line-height: 1.5;">{safe_text(fd.get("detail", ""))}</div>',
                '</div>',
            ])
        f_lines.append('</div>')
        render_html(f_lines)

    # =======================================================================
    # Multi-Mode Summarization (Short / Medium / Long) with PDF + TXT Download
    # =======================================================================
    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<div style="margin-bottom: 6px;">',
            f'<h3 style="margin: 0; font-size: 18px; font-weight: 700; color: {theme["text_primary"]};">📝 Source-Grounded Manuscript Summary</h3>',
            f'<p style="margin: 2px 0 0 0; font-size: 12.5px; color: {theme["text_muted"]};">Generate Short, Medium, or Long summaries strictly grounded in the manuscript text and export as PDF or TXT.</p>',
            '</div>',
        ])
        s_c1, s_c2 = st.columns([2.2, 1.2], gap="medium")
        with s_c1:
            sum_mode = st.radio(
                "Summary Detail Mode",
                options=["Short", "Medium", "Long"],
                index=1,
                horizontal=True,
                key="res_sum_mode_radio",
            )
        with s_c2:
            render_html('<div style="height: 20px;"></div>')
            gen_sum_btn = st.button("📝 Generate / Refresh Summary", key="res_btn_gen_summary", use_container_width=True, type="primary")

        if gen_sum_btn or not active_rec.get("summary"):
            if p_text and len(p_text.strip()) >= 40:
                s_out = summarizer.summarize_research_paper(
                    text=p_text,
                    summary_type=sum_mode,
                    filename=active_rec.get("filename", "Manuscript.txt"),
                    doc_title=p_title,
                )
                if s_out.get("success"):
                    st.session_state["res_current_summary_obj"] = s_out
                    active_rec["summary"] = s_out.get("summary", "")

        cur_sum_obj = st.session_state.get("res_current_summary_obj")
        if not cur_sum_obj and active_rec.get("summary"):
            cur_sum_obj = summarizer.summarize_research_paper(
                text=p_text,
                summary_type=sum_mode,
                filename=active_rec.get("filename", "Manuscript.txt"),
                doc_title=p_title,
            )
            st.session_state["res_current_summary_obj"] = cur_sum_obj

        if cur_sum_obj and cur_sum_obj.get("summary"):
            cur_sum_obj["summary"] = summarizer.normalize_summary_limitations_label(cur_sum_obj["summary"])
            st.markdown(unescape_text(cur_sum_obj["summary"]))
            dl1, dl2 = st.columns(2, gap="small")
            with dl1:
                try:
                    sum_pdf = pdf_export.build_summary_pdf(
                        paper_title=p_title,
                        mode=cur_sum_obj.get("summary_type", sum_mode),
                        summary_data=cur_sum_obj,
                        metadata={"domain": p_domain, "word_count": counts_info["word_count"], "overall_score": scores_dict["overall_score"]},
                    )
                    st.download_button(
                        "⬇ Download Summary (PDF)",
                        data=sum_pdf,
                        file_name=pdf_export.get_pdf_filename(p_title, f"Summary_{sum_mode}"),
                        mime="application/pdf",
                        use_container_width=True,
                        key="res_dl_sum_pdf",
                    )
                except Exception as pdf_err:
                    st.error(f"Could not generate Summary PDF: {pdf_err}")
            with dl2:
                sum_txt = summarizer.export_summary_as_txt(cur_sum_obj)
                st.download_button(
                    "⬇ Download Summary (TXT)",
                    data=sum_txt.encode("utf-8"),
                    file_name=summarizer.get_summary_export_filename(p_title, sum_mode),
                    mime="text/plain",
                    use_container_width=True,
                    key="res_dl_sum_txt",
                )

    # =======================================================================
    # Full Researcher Paper Report Export (PDF + TXT) & Cross-Page Shortcuts
    # =======================================================================
    report_payload = {
        "title": p_title,
        "paper_title": p_title,
        "metadata": {
            "authors": p_authors,
            "year": p_year,
            "journal": p_journal,
            "domain": p_domain,
            "keywords": p_keywords,
        },
        "profile": profile,
        "findings": findings,
        "summary": active_rec.get("summary") or "",
        "overall_score": scores_dict["overall_score"],
        "structure_score": scores_dict["structure_score"],
        "clarity_score": scores_dict["clarity_score"],
        "coherence_score": scores_dict["coherence_score"],
        "citation_score": scores_dict["citation_score"],
        "readability_score": scores_dict["readability_score"],
    }
    rp_c1, rp_c2, rp_c3, rp_c4 = st.columns(4, gap="small")
    with rp_c1:
        try:
            paper_pdf_bytes = pdf_export.build_researcher_paper_pdf(report_payload)
            st.download_button(
                "📄 Paper Report (PDF)",
                data=paper_pdf_bytes,
                file_name=pdf_export.get_pdf_filename(p_title, "Researcher_Paper_Report"),
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="res_dl_full_paper_pdf",
            )
        except Exception as pdf_err:
            st.error(f"Could not generate Paper Report PDF: {pdf_err}")
    with rp_c2:
        paper_txt_str = pdf_export.build_researcher_paper_txt(report_payload)
        st.download_button(
            "📝 Paper Report (TXT)",
            data=paper_txt_str.encode("utf-8"),
            file_name=pdf_export.get_pdf_filename(p_title, "Researcher_Paper_Report").replace(".pdf", ".txt"),
            mime="text/plain",
            use_container_width=True,
            key="res_dl_full_paper_txt",
        )
    with rp_c3:
        if st.button("💡 Research Insights →", key="res_anl_goto_insights", use_container_width=True):
            navigate_to("💡 Research Insights")
            st.rerun()
    with rp_c4:
        if st.button("💬 Ask PaperIQ →", key="res_anl_goto_ask", use_container_width=True):
            navigate_to("💬 Ask PaperIQ")
            st.rerun()

    # =======================================================================
    # SECONDARY OUTPUT: Collapsed "Manuscript Quality" Section (5 Distinct Dimensions)
    # =======================================================================
    render_html("<div style='height: 10px;'></div>")
    driven_by_map = scores_dict.get("driven_by") or {}
    with st.expander("📊 Manuscript Quality (Secondary Assessment — 5 Distinct Dimensions & Composite Score)", expanded=False):
        render_html([
            f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; padding: 10px 14px; background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px;">',
            f'<span style="font-size: 13px; color: {theme["text_secondary"]};">Weighted Composite = 25% Structure + 20% Clarity + 20% Coherence + 20% Citations + 15% Readability</span>',
            f'<span style="font-size: 16px; font-weight: 800; color: {theme["success_text"]};">Composite Quality: {scores_dict["overall_score"]:.1f}/100</span>',
            '</div>',
        ])
        dim_cols = st.columns(5)
        dim_items = [
            ("Structure & Organization (25%)", scores_dict["structure_score"], "structure_score"),
            ("Clarity & Academic Style (20%)", scores_dict["clarity_score"], "clarity_score"),
            ("Coherence & Flow (20%)", scores_dict["coherence_score"], "coherence_score"),
            ("Citations & Grounding (20%)", scores_dict["citation_score"], "citation_score"),
            ("Readability (15%)", scores_dict["readability_score"], "readability_score"),
        ]
        for idx, (d_lbl, d_val, d_key) in enumerate(dim_items):
            d_driver = driven_by_map.get(d_key, "")
            with dim_cols[idx]:
                render_html([
                    f'<div style="background: {theme["bg_card"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 12px 10px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">',
                    '<div>',
                    f'<div style="font-size: 11px; color: {theme["text_muted"]}; font-weight: 700;">{safe_text(d_lbl)}</div>',
                    f'<div style="font-size: 21px; font-weight: 800; color: {theme["text_primary"]}; margin: 6px 0;">{d_val:.1f}<span style="font-size: 11px; color: {theme["text_muted"]};">/100</span></div>',
                    '</div>',
                    f'<div style="font-size: 10.5px; color: {theme["text_secondary"]}; line-height: 1.35; margin-top: 6px; padding-top: 6px; border-top: 1px solid {theme["border_divider"]};">{safe_text(d_driver)}</div>' if d_driver else '',
                    '</div>',
                ])

