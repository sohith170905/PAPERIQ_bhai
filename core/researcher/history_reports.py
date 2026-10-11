"""
PaperIQ — Researcher Page 7: Research History & Reports (C7 — EXTEND)
=====================================================================
Requirements:
- Show saved analyses AND saved comparisons (filterable by project, searchable).
- Export options (both PDF and TXT) for:
  * Paper Report (metadata + research profile + summary + writing scores + findings)
  * Comparison Report (comparison matrix + synthesis + scores)
  * Insights Report (keywords, themes, gaps, trends, future work)
  * Project Report (all papers in a project + cross-paper synthesis + researcher notes)
- Delete with confirmation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import render_html, safe_text, unescape_text


def render_research_history_and_reports(
    theme: Dict[str, str],
    username: str,
    navigate_to: Callable[[str], None],
    load_analysis_into_session: Callable[[Dict[str, Any]], None],
) -> None:
    """Render Researcher Page 7: Research History & Reports (C7)."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">🗂️ Scholarly Archive &amp; Dossiers</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Research History &amp; Reports</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Access your chronological evaluation archive, saved multi-paper comparisons, and export publication-grade Paper, Insights, Comparison, and Project Reports in PDF &amp; TXT.</p>',
        '</div>',
    ])

    library_papers = auth.get_researcher_library(username)
    projects = auth.get_user_projects(username)
    saved_comparisons = auth.get_user_comparisons(username)

    # Filter & Search Bar
    with st.container(border=True):
        render_html('<span class="res-card-scope"></span>')
        fc1, fc2 = st.columns([2.4, 1.3], gap="medium")
        with fc1:
            search_q = st.text_input(
                "🔍 Search History & Reports (Title, Author, Domain, Project, Comparison)",
                value="",
                placeholder="Filter by title, author, keyword, or domain...",
                key="res_hist_search_q",
            )
        with fc2:
            proj_opts = ["All Projects"] + [p["name"] for p in projects] + ["Unassigned Papers"]
            proj_filter = st.selectbox("Filter by Project", options=proj_opts, key="res_hist_proj_filter")

    tab_papers, tab_comparisons, tab_projects = st.tabs([
        f"📄 Evaluated Manuscripts ({len(library_papers)})",
        f"🔄 Saved Comparisons ({len(saved_comparisons)})",
        f"📁 Project Dossier Reports ({len(projects)})",
    ])

    # =======================================================================
    # TAB 1: Evaluated Manuscripts (Paper Report PDF/TXT + Insights Report PDF/TXT + Delete)
    # =======================================================================
    with tab_papers:
        q_low = search_q.strip().lower()
        filtered_papers = []
        for p in library_papers:
            p_title = unescape_text(p.get("paper_title") or p.get("filename") or "")
            p_auth = unescape_text(p.get("authors") or "")
            p_dom = unescape_text(p.get("domain") or "")
            p_projs = [pr["name"] for pr in (p.get("projects") or [])]

            if proj_filter == "Unassigned Papers" and p_projs:
                continue
            elif proj_filter not in ("All Projects", "Unassigned Papers") and proj_filter not in p_projs:
                continue

            if q_low and q_low not in f"{p_title} {p_auth} {p_dom} {' '.join(p_projs)}".lower():
                continue
            filtered_papers.append(p)

        if not filtered_papers:
            st.info("No evaluated manuscripts match the current filter.")
        else:
            for p in filtered_papers:
                aid = p["id"]
                raw_text = unescape_text(p.get("extracted_text") or p.get("summary") or "")
                secs = p.get("sections") if isinstance(p.get("sections"), dict) and p.get("sections") else summarizer.segment_paper_sections(raw_text)
                raw_stored_title = unescape_text(p.get("paper_title") or p.get("filename") or "Untitled Manuscript")
                auto_meta = research_engine.extract_paper_metadata(
                    raw_text,
                    filename=p.get("filename", ""),
                    title_override=None if research_engine.is_citation_or_header_line(raw_stored_title) else raw_stored_title,
                )
                title = auto_meta["title"] if research_engine.is_citation_or_header_line(raw_stored_title) else raw_stored_title

                stored_auth = unescape_text(p.get("authors") or "")
                authors = auto_meta.get("authors", "Not found") if not stored_auth or stored_auth == "Unknown Authors" else stored_auth
                year = unescape_text(p.get("year") or auto_meta.get("year") or "")
                stored_jr = unescape_text(p.get("journal") or "")
                journal = auto_meta.get("journal", "Manuscript / Preprint") if not stored_jr or stored_jr == "Manuscript / Preprint" else stored_jr
                domain = unescape_text(p.get("domain") or "")
                if not domain or domain == "General":
                    domain = auto_meta.get("domain") or "Interdisciplinary"
                kws = auto_meta.get("keywords") or p.get("keywords") or []

                profile = research_engine.extract_research_profile(raw_text, secs)
                counts_info = summarizer.compute_text_counts(raw_text)
                scores_dict = research_engine.compute_researcher_quality_scores(raw_text, secs, base_res=p)
                findings = research_engine.generate_text_grounded_findings(raw_text, secs, counts_info, scores_dict, profile)
                insights_bundle = research_engine.extract_honest_research_insights(raw_text, secs)

                paper_rep_payload = {
                    "title": title,
                    "paper_title": title,
                    "metadata": {"authors": authors, "year": year, "journal": journal, "domain": domain, "keywords": kws},
                    "profile": profile,
                    "findings": findings,
                    "summary": p.get("summary") or "",
                    "overall_score": scores_dict["overall_score"],
                    "structure_score": scores_dict["structure_score"],
                    "clarity_score": scores_dict["clarity_score"],
                    "coherence_score": scores_dict["coherence_score"],
                    "citation_score": scores_dict["citation_score"],
                    "readability_score": scores_dict["readability_score"],
                }

                p_projs = [pr["name"] for pr in (p.get("projects") or [])]
                proj_str = f" • 📁 {', '.join(p_projs)}" if p_projs else ""

                with st.container(border=True):
                    render_html([
                        '<span class="res-item-scope"></span>',
                        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">',
                        '<div>',
                        f'<div style="font-size: 15.5px; font-weight: 700; color: {theme["text_primary"]};" title="{safe_text(title)}">📄 {safe_text(title)}</div>',
                        f'<div style="font-size: 12px; color: {theme["text_secondary"]}; margin-top: 3px; line-height: 1.45;">👤 {safe_text(authors)} {f"({safe_text(year)})" if year else ""} &nbsp;•&nbsp; 🏛️ {safe_text(journal)} &nbsp;•&nbsp; 🧭 {safe_text(domain)} &nbsp;•&nbsp; 🕒 {safe_text(str(p.get("timestamp") or "")[:16])} &nbsp;•&nbsp; <b style="color: {theme["success_text"]};">{scores_dict["overall_score"]:.1f}/100</b>{safe_text(proj_str)}</div>',
                        '</div>',
                        '</div>',
                    ])

                    b1, b2, b3, b4, b5, b6 = st.columns([1.05, 1.15, 1.15, 1.15, 1.15, 1.05], gap="small")
                    with b1:
                        if st.button("🔬 Open", key=f"hist_open_{aid}", use_container_width=True):
                            load_analysis_into_session(p)
                            st.session_state["current_analysis_id"] = aid
                            navigate_to("📄 Analyze Research Paper")
                            st.rerun()
                    with b2:
                        try:
                            p_pdf = pdf_export.build_researcher_paper_pdf(paper_rep_payload)
                            st.download_button(
                                "⬇ Paper PDF",
                                data=p_pdf,
                                file_name=pdf_export.get_pdf_filename(title, "Paper_Report"),
                                mime="application/pdf",
                                key=f"hist_ppdf_{aid}",
                                use_container_width=True,
                            )
                        except Exception as pdf_err:
                            st.error(f"PDF error: {pdf_err}")
                    with b3:
                        p_txt = pdf_export.build_researcher_paper_txt(paper_rep_payload)
                        st.download_button(
                            "⬇ Paper TXT",
                            data=p_txt.encode("utf-8"),
                            file_name=pdf_export.get_pdf_filename(title, "Paper_Report").replace(".pdf", ".txt"),
                            mime="text/plain",
                            key=f"hist_ptxt_{aid}",
                            use_container_width=True,
                        )
                    with b4:
                        try:
                            i_pdf = pdf_export.build_insights_pdf(title, insights_bundle, {"domain": domain})
                            st.download_button(
                                "⬇ Insights PDF",
                                data=i_pdf,
                                file_name=pdf_export.get_pdf_filename(title, "Insights_Report"),
                                mime="application/pdf",
                                key=f"hist_ipdf_{aid}",
                                use_container_width=True,
                            )
                        except Exception as pdf_err:
                            st.error(f"PDF error: {pdf_err}")
                    with b5:
                        i_txt = pdf_export.build_insights_txt(title, insights_bundle, {"domain": domain})
                        st.download_button(
                            "⬇ Insights TXT",
                            data=i_txt.encode("utf-8"),
                            file_name=pdf_export.get_pdf_filename(title, "Insights_Report").replace(".pdf", ".txt"),
                            mime="text/plain",
                            key=f"hist_itxt_{aid}",
                            use_container_width=True,
                        )
                    with b6:
                        with st.popover("🗑️ Delete", use_container_width=True):
                            st.caption(f"Delete '{title[:40]}'?")
                            if st.button("Confirm Delete", key=f"hist_del_p_{aid}", type="primary", use_container_width=True):
                                auth.delete_user_analysis(username, aid)
                                st.rerun()

    # =======================================================================
    # TAB 2: Saved Multi-Paper Comparisons (Comparison Report PDF/TXT + Delete)
    # =======================================================================
    with tab_comparisons:
        if not saved_comparisons:
            st.info("No saved multi-paper comparisons yet. Run a comparison in **Advanced Paper Comparison** to archive it here.")
        else:
            for cmp_rec in saved_comparisons:
                cid = cmp_rec["id"]
                c_title = unescape_text(cmp_rec.get("title") or f"Comparison #{cid}")
                c_ts = str(cmp_rec.get("created_at") or "")[:16]
                m_json = cmp_rec.get("matrix_json") or {}
                c_papers = m_json.get("papers") or []

                if q_low and q_low not in c_title.lower():
                    continue

                with st.container(border=True):
                    render_html([
                        '<span class="res-item-scope"></span>',
                        f'<div style="font-size: 15px; font-weight: 700; color: {theme["text_primary"]};" title="{safe_text(c_title)}">🔄 {safe_text(c_title)}</div>',
                        f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 3px;">Compared {len(c_papers)} manuscripts • Saved on {safe_text(c_ts)}</div>',
                    ])
                    cc1, cc2, cc3, cc4 = st.columns([1.2, 1.4, 1.4, 1.0], gap="small")
                    with cc1:
                        if st.button("🔬 View Matrix", key=f"hist_view_cmp_{cid}", use_container_width=True):
                            st.session_state["res_active_comparison"] = m_json
                            st.session_state["res_active_comparison_papers"] = c_papers
                            navigate_to("🔄 Advanced Paper Comparison")
                            st.rerun()
                    with cc2:
                        if c_papers:
                            try:
                                c_pdf = pdf_export.build_comparison_pdf(c_papers, m_json)
                                st.download_button(
                                    "⬇ Comparison PDF",
                                    data=c_pdf,
                                    file_name=pdf_export.get_pdf_filename(c_title, "Comparison_Report"),
                                    mime="application/pdf",
                                    key=f"hist_cpdf_{cid}",
                                    use_container_width=True,
                                )
                            except Exception as pdf_err:
                                st.error(f"PDF error: {pdf_err}")
                    with cc3:
                        if c_papers:
                            c_txt = pdf_export.build_researcher_comparison_txt(c_papers, m_json)
                            st.download_button(
                                "⬇ Comparison TXT",
                                data=c_txt.encode("utf-8"),
                                file_name=pdf_export.get_pdf_filename(c_title, "Comparison_Report").replace(".pdf", ".txt"),
                                mime="text/plain",
                                key=f"hist_ctxt_{cid}",
                                use_container_width=True,
                            )
                    with cc4:
                        with st.popover("🗑️ Delete", use_container_width=True):
                            st.caption("Delete this saved comparison?")
                            if st.button("Confirm Delete", key=f"hist_del_cmp_{cid}", type="primary", use_container_width=True):
                                auth.delete_comparison_record(username, cid)
                                st.rerun()

    # =======================================================================
    # TAB 3: Project Dossier Reports (All papers in project + cross-paper synthesis + notes)
    # =======================================================================
    with tab_projects:
        if not projects:
            st.info("No projects created yet. Create a project in **Research Library** to generate Project Dossier Reports.")
        else:
            for proj in projects:
                pid = proj["id"]
                pname = unescape_text(proj.get("name") or "Project")
                pdesc = unescape_text(proj.get("description") or "No description provided.")
                proj_papers = [
                    p for p in library_papers
                    if any(pr["id"] == pid for pr in (p.get("projects") or []))
                ]

                # Prepare enriched paper list and notes for project report
                enriched_proj_papers: List[Dict[str, Any]] = []
                proj_notes: List[Dict[str, Any]] = []
                for pp in proj_papers:
                    rt = unescape_text(pp.get("extracted_text") or pp.get("summary") or "")
                    pt_raw = unescape_text(pp.get("paper_title") or pp.get("filename") or "Manuscript")
                    if research_engine.is_citation_or_header_line(pt_raw):
                        pt = research_engine.extract_paper_metadata(rt, filename=pp.get("filename", "")).get("title") or pt_raw
                    else:
                        pt = pt_raw
                    sc_map = pp.get("sections") if isinstance(pp.get("sections"), dict) and pp.get("sections") else summarizer.segment_paper_sections(rt)
                    pr_map = research_engine.extract_research_profile(rt, sc_map)
                    sc_res = research_engine.compute_researcher_quality_scores(rt, sc_map, base_res=pp)
                    enriched_proj_papers.append({
                        "id": pp["id"],
                        "title": pt,
                        "text": rt,
                        "sections": sc_map,
                        "profile": pr_map,
                        "metadata": {
                            "authors": unescape_text(pp.get("authors") or "Not found"),
                            "year": unescape_text(pp.get("year") or ""),
                            "domain": unescape_text(pp.get("domain") or "Interdisciplinary"),
                            "keywords": pp.get("keywords") or [],
                        },
                        "overall_score": float(sc_res.get("overall_score") or 0.0),
                        "scores": sc_res,
                    })
                    for n_item in pp.get("notes") or []:
                        proj_notes.append({
                            "paper_title": pt,
                            "note_text": unescape_text(n_item.get("note_text") or ""),
                            "created_at": str(n_item.get("created_at") or "")[:16],
                        })

                proj_matrix = (
                    research_engine.build_comparison_matrix_and_synthesis(enriched_proj_papers[:3])
                    if len(enriched_proj_papers) >= 2
                    else {}
                )

                with st.container(border=True):
                    render_html([
                        '<span class="res-item-scope"></span>',
                        f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]};">📁 {safe_text(pname)}</div>',
                        f'<div style="font-size: 12.5px; color: {theme["text_secondary"]}; margin-top: 2px;">{safe_text(pdesc)}</div>',
                        f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 4px;"><b>{len(enriched_proj_papers)}</b> assigned manuscripts • <b>{len(proj_notes)}</b> researcher notes</div>',
                    ])
                    pc1, pc2, pc3 = st.columns([1.3, 1.5, 1.5], gap="small")
                    with pc1:
                        if st.button("📚 Open in Library", key=f"hist_open_proj_{pid}", use_container_width=True):
                            st.session_state["library_selected_project_id"] = pid
                            navigate_to("📚 Research Library")
                            st.rerun()
                    with pc2:
                        try:
                            pr_pdf = pdf_export.build_project_report_pdf(proj, enriched_proj_papers, proj_matrix, proj_notes)
                            st.download_button(
                                "⬇ Project Report (PDF)",
                                data=pr_pdf,
                                file_name=pdf_export.get_pdf_filename(pname, "Project_Report"),
                                mime="application/pdf",
                                type="primary",
                                key=f"hist_pr_pdf_{pid}",
                                use_container_width=True,
                            )
                        except Exception as pdf_err:
                            st.error(f"PDF error: {pdf_err}")
                    with pc3:
                        pr_txt = pdf_export.build_project_report_txt(proj, enriched_proj_papers, proj_matrix, proj_notes)
                        st.download_button(
                            "⬇ Project Report (TXT)",
                            data=pr_txt.encode("utf-8"),
                            file_name=pdf_export.get_pdf_filename(pname, "Project_Report").replace(".pdf", ".txt"),
                            mime="text/plain",
                            key=f"hist_pr_txt_{pid}",
                            use_container_width=True,
                        )
