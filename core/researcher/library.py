"""
PaperIQ — Researcher Page 3: Research Library (C3 — NEW)
========================================================
Requirements:
- Lists ONLY the logged-in researcher's papers.
- Search bar (title, authors, keywords, abstract/summary).
- Filters: by project, domain, author, keyword, year, tag.
- Sort: date, score, title, year.
- Group-by view switch: Project | Domain | Author | Keyword | Topic.
- Per-paper actions: View analysis, Assign/remove project, Edit tags,
  Add/edit researcher notes, Select for comparison, Download report, Delete (with confirmation).
- Project management: create / rename / delete project (deleting a project removes the project
  and its mappings, NOT the underlying papers, unless the user explicitly chooses
  "Delete project and its papers"); "Compare project papers" shortcut.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import format_title_with_tooltip_html, render_html, safe_text, truncate_title_word_boundary, unescape_text


def _enrich_library_paper(p: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every paper record in the library has canonical title, domain, keywords, topics, authors, year, venue."""
    out = dict(p)
    raw_text = unescape_text(out.get("extracted_text") or out.get("summary") or "")
    stored_title = unescape_text(out.get("paper_title") or out.get("filename") or "Untitled Manuscript")

    need_auto = (
        research_engine.is_citation_or_header_line(stored_title)
        or not out.get("keywords")
        or not out.get("topics")
        or out.get("domain") in (None, "", "General")
        or out.get("authors") in (None, "", "Unknown Authors")
        or out.get("journal") in (None, "", "Manuscript / Preprint")
    )
    auto_meta = (
        research_engine.extract_paper_metadata(
            raw_text,
            filename=out.get("filename", ""),
            title_override=None if research_engine.is_citation_or_header_line(stored_title) else stored_title,
        )
        if need_auto
        else {}
    )

    title = auto_meta.get("title") if research_engine.is_citation_or_header_line(stored_title) else stored_title
    out["clean_title"] = title or stored_title

    stored_authors = unescape_text(out.get("authors") or "")
    if not stored_authors or stored_authors == "Unknown Authors":
        authors = auto_meta.get("authors") or "Not found"
    else:
        authors = stored_authors

    year = unescape_text(out.get("year") or auto_meta.get("year") or "")
    stored_journal = unescape_text(out.get("journal") or "")
    if not stored_journal or (stored_journal == "Manuscript / Preprint" and auto_meta.get("journal") not in (None, "", "Manuscript / Preprint")):
        journal = auto_meta.get("journal") or "Manuscript / Preprint"
    else:
        journal = stored_journal

    domain = unescape_text(out.get("domain") or "")
    if not domain or domain == "General":
        domain = auto_meta.get("domain") or research_engine.detect_research_domain(raw_text or out["clean_title"])
    keywords = auto_meta.get("keywords") or out.get("keywords") or []
    topics = auto_meta.get("topics") or out.get("topics") or ["Core Subject & Entities"]

    out["authors"] = authors
    out["year"] = year
    out["journal"] = journal
    out["domain"] = domain
    out["keywords"] = [unescape_text(str(k)) for k in keywords if str(k).strip()]
    out["topics"] = [unescape_text(str(t)) for t in topics if str(t).strip()]
    return out


def render_research_library(
    theme: Dict[str, str],
    username: str,
    navigate_to: Callable[[str], None],
    load_analysis_into_session: Callable[[Dict[str, Any]], None],
) -> None:
    """Render Researcher Page 3: Research Library (C3)."""
    raw_papers = auth.get_researcher_library(username)
    papers = [_enrich_library_paper(p) for p in raw_papers]
    projects = auth.get_user_projects(username)

    render_html([
        '<div style="margin-bottom: 16px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">📚 Personal Literature Repository</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Research Library</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Organize your evaluated manuscripts into projects, filter by bibliographic metadata, record scholarly notes, and launch multi-paper comparisons.</p>',
        '</div>',
    ])

    # =======================================================================
    # 1. Project Creation & Management Section Container
    # =======================================================================
    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">',
            f'<div style="font-size: 15px; font-weight: 700; color: {theme["text_primary"]};">🗂️ Research Project Management</div>',
            f'<span style="font-size: 11.5px; color: {theme["text_muted"]}; background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 6px; padding: 2px 9px; font-weight: 600;">{len(projects)} Active {"Project" if len(projects) == 1 else "Projects"}</span>',
            '</div>',
            f'<hr style="border: none; border-top: 1px solid {theme["border_divider"]}; margin: 4px 0 8px 0;">',
        ])
        pm_col1, pm_col2 = st.columns([1.05, 1.25], gap="medium")
        with pm_col1:
            render_html(f"<div style='font-size: 13px; font-weight: 700; color: {theme['accent_purple']}; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px;'>➕ Create New Project</div>")
            pn_c1, pn_c2 = st.columns(2, gap="small")
            with pn_c1:
                new_proj_name = st.text_input("Project Name", key="lib_new_proj_name", placeholder="e.g., Millet Growth & Food Security")
            with pn_c2:
                new_proj_desc = st.text_input("Description", key="lib_new_proj_desc", placeholder="Optional scope or research goal...")
            if st.button("➕ Create Project", key="lib_btn_create_proj", type="primary", use_container_width=True):
                ok, msg, new_pid = auth.create_project(username, new_proj_name, new_proj_desc)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with pm_col2:
            render_html(f"<div style='font-size: 13px; font-weight: 700; color: {theme['text_secondary']}; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px;'>📁 Manage Existing Projects ({len(projects)})</div>")
            if not projects:
                render_html([
                    f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 8px; padding: 22px 16px; text-align: center; color: {theme["text_muted"]}; font-size: 12.5px;">',
                    'No projects created yet. Enter a name on the left and click <b>Create Project</b> to organize manuscripts.',
                    '</div>',
                ])
            else:
                proj_map = {f"{p['name']} ({p['paper_count']} papers)": p for p in projects}
                sel_proj_lbl = st.selectbox("Select Project to Manage", options=list(proj_map.keys()), key="lib_manage_proj_select")
                sel_proj = proj_map[sel_proj_lbl]
                pid = sel_proj["id"]

                act_c1, act_c2, act_c3 = st.columns([1.15, 1.0, 1.0], gap="small")
                with act_c1:
                    if st.button("🔄 Compare", key=f"lib_cmp_proj_{pid}", use_container_width=True, type="primary", help="Compare papers assigned to this project"):
                        proj_paper_ids = [
                            p["id"] for p in papers
                            if any(pr["id"] == pid for pr in (p.get("projects") or []))
                        ]
                        if len(proj_paper_ids) < 2:
                            st.warning("Assign at least 2 papers to this project before launching comparison.")
                        else:
                            st.session_state["res_compare_selected_ids"] = proj_paper_ids[:3]
                            navigate_to("🔄 Advanced Paper Comparison")
                            st.rerun()

                with act_c2:
                    with st.popover("✏️ Rename", use_container_width=True):
                        rn_name = st.text_input("New Name", value=sel_proj["name"], key=f"lib_rn_name_{pid}")
                        rn_desc = st.text_input("Description", value=sel_proj.get("description") or "", key=f"lib_rn_desc_{pid}")
                        if st.button("Save Changes", key=f"lib_btn_rn_{pid}", type="primary", use_container_width=True):
                            ok_r, msg_r = auth.rename_project(username, pid, rn_name, rn_desc)
                            if ok_r:
                                st.success(msg_r)
                                st.rerun()
                            else:
                                st.error(msg_r)

                with act_c3:
                    with st.popover("🗑️ Delete", use_container_width=True):
                        st.markdown(f"**Delete '{sel_proj['name']}'?**")
                        del_mode = st.radio(
                            "Deletion Mode",
                            options=[
                                "Delete project only (keep papers in library)",
                                "Delete project AND delete its papers",
                            ],
                            index=0,
                            key=f"lib_del_proj_mode_{pid}",
                        )
                        if st.button("Confirm Delete Project", key=f"lib_confirm_del_proj_{pid}", type="primary", use_container_width=True):
                            del_papers_flag = "AND delete its papers" in del_mode
                            ok_d, msg_d = auth.delete_project(username, pid, delete_papers=del_papers_flag)
                            if ok_d:
                                if st.session_state.get("library_selected_project_id") == pid:
                                    st.session_state.pop("library_selected_project_id", None)
                                st.success(msg_d)
                                st.rerun()
                            else:
                                st.error(msg_d)

    # =======================================================================
    # 2. Search, Multi-Dimension Filters, Sort & Group-By Switch
    # =======================================================================
    all_domains = sorted({p["domain"] for p in papers if p.get("domain")})
    all_authors = sorted({p["authors"] for p in papers if p.get("authors")})
    all_years = sorted({p["year"] for p in papers if p.get("year")}, reverse=True)
    all_keywords = sorted({kw for p in papers for kw in (p.get("keywords") or [])})
    all_tags = sorted({tg for p in papers for tg in (p.get("tags") or [])})
    proj_filter_opts = ["All Projects"] + [p["name"] for p in projects] + ["Unassigned Papers"]

    # Pre-select project if navigated from Dashboard 'Open ->'
    default_proj_idx = 0
    pre_pid = st.session_state.get("library_selected_project_id")
    if pre_pid:
        for idx_p, pr in enumerate(projects, start=1):
            if pr["id"] == pre_pid:
                default_proj_idx = idx_p
                break

    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">',
            f'<div style="font-size: 15px; font-weight: 700; color: {theme["text_primary"]};">🔍 Search, Filter &amp; Group Manuscripts</div>',
            f'<span style="font-size: 11.5px; color: {theme["text_muted"]};">{len(papers)} total {"manuscript" if len(papers) == 1 else "manuscripts"} in library</span>',
            '</div>',
        ])
        s_col1, s_col2 = st.columns([2.4, 1.1], gap="medium")
        with s_col1:
            search_q = st.text_input(
                "Search Library (Title, Authors, Keywords, Summary/Abstract)",
                value="",
                placeholder="Type keyword, author name, method, or title phrase...",
                key="lib_search_query",
            )
        with s_col2:
            sort_by = st.selectbox(
                "Sort Papers By",
                options=["Date Added (Newest)", "Score (High → Low)", "Title (A → Z)", "Publication Year (Newest)"],
                key="lib_sort_by",
            )

        f1, f2, f3, f4, f5, f6 = st.columns(6, gap="small")
        with f1:
            f_proj = st.selectbox("Project", options=proj_filter_opts, index=default_proj_idx, key="lib_f_proj")
        with f2:
            f_dom = st.selectbox("Domain", options=["All Domains"] + all_domains, key="lib_f_dom")
        with f3:
            f_auth = st.selectbox("Author", options=["All Authors"] + all_authors, key="lib_f_auth")
        with f4:
            f_kw = st.selectbox("Keyword", options=["All Keywords"] + all_keywords, key="lib_f_kw")
        with f5:
            f_yr = st.selectbox("Year", options=["All Years"] + all_years, key="lib_f_yr")
        with f6:
            f_tag = st.selectbox("Tag", options=["All Tags"] + all_tags, key="lib_f_tag")

        render_html(f'<hr style="border: none; border-top: 1px solid {theme["border_divider"]}; margin: 4px 0 4px 0;">')
        group_by = st.radio(
            "Group View By",
            options=["Project", "Domain", "Author", "Keyword", "Topic"],
            horizontal=True,
            key="lib_group_by_switch",
        )

    # Apply filters
    filtered: List[Dict[str, Any]] = []
    q_low = search_q.strip().lower()
    for p in papers:
        if q_low:
            haystack = " ".join([
                p.get("clean_title", ""),
                p.get("authors", ""),
                " ".join(p.get("keywords") or []),
                p.get("summary") or "",
                (p.get("extracted_text") or "")[:2000],
            ]).lower()
            if q_low not in haystack:
                continue

        p_proj_names = [pr["name"] for pr in (p.get("projects") or [])]
        if f_proj == "Unassigned Papers" and p_proj_names:
            continue
        elif f_proj not in ("All Projects", "Unassigned Papers") and f_proj not in p_proj_names:
            continue

        if f_dom != "All Domains" and p.get("domain") != f_dom:
            continue
        if f_auth != "All Authors" and p.get("authors") != f_auth:
            continue
        if f_kw != "All Keywords" and f_kw not in (p.get("keywords") or []):
            continue
        if f_yr != "All Years" and p.get("year") != f_yr:
            continue
        if f_tag != "All Tags" and f_tag not in (p.get("tags") or []):
            continue

        filtered.append(p)

    # Apply sorting
    if sort_by == "Score (High → Low)":
        filtered.sort(key=lambda x: float(x.get("overall_score") or 0.0), reverse=True)
    elif sort_by == "Title (A → Z)":
        filtered.sort(key=lambda x: (x.get("clean_title") or "").lower())
    elif sort_by == "Publication Year (Newest)":
        filtered.sort(key=lambda x: str(x.get("year") or "0000"), reverse=True)
    else:
        filtered.sort(key=lambda x: (str(x.get("timestamp") or ""), int(x.get("id") or 0)), reverse=True)

    # Comparison Tray Bar (FIX 7 — Show full title with word-boundary ellipsis and tooltip, never [:40])
    selected_cmp_ids: List[int] = list(st.session_state.get("res_compare_selected_ids") or [])
    selected_cmp_ids = [cid for cid in selected_cmp_ids if any(p["id"] == cid for p in papers)]
    st.session_state["res_compare_selected_ids"] = selected_cmp_ids

    if selected_cmp_ids:
        sel_titles_html = " &nbsp;|&nbsp; ".join(
            f"<b style='color:{theme['text_primary']};'>{format_title_with_tooltip_html(p['clean_title'], max_chars=75)}</b>"
            for p in papers
            if p["id"] in selected_cmp_ids
        )
        tray_c1, tray_c2, tray_c3 = st.columns([3.0, 1.2, 0.8])
        with tray_c1:
            render_html([
                f'<div style="background: rgba(56,189,248,0.12); border: 1px solid rgba(56,189,248,0.35); border-radius: 10px; padding: 10px 14px; font-size: 13px; color: #7dd3fc;">',
                f'🔄 <b>Selected for Comparison ({len(selected_cmp_ids)}/3):</b> {sel_titles_html}',
                '</div>',
            ])
        with tray_c2:
            if st.button("🚀 Compare Selected Papers →", key="lib_tray_launch_cmp", type="primary", use_container_width=True, disabled=len(selected_cmp_ids) < 2):
                navigate_to("🔄 Advanced Paper Comparison")
                st.rerun()
        with tray_c3:
            if st.button("Clear Selection", key="lib_tray_clear_cmp", use_container_width=True):
                st.session_state["res_compare_selected_ids"] = []
                st.rerun()

    if not filtered:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 12px; padding: 30px 20px; text-align: center; margin-top: 12px;">',
            f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]};">No manuscripts match the current filters</div>',
            f'<div style="font-size: 13px; color: {theme["text_muted"]}; margin-top: 4px;">Upload a paper in <b>Analyze Research Paper</b> or clear your search/filter criteria above.</div>',
            '</div>',
        ])
        return

    # =======================================================================
    # 3. Group Papers According to `group_by` Switch
    # =======================================================================
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in filtered:
        if group_by == "Project":
            p_projs = [pr["name"] for pr in (p.get("projects") or [])]
            if p_projs:
                for pn in p_projs:
                    grouped[f"📁 Project: {pn}"].append(p)
            else:
                grouped["📂 Unassigned (General Library)"].append(p)
        elif group_by == "Domain":
            grouped[f"🧭 Domain: {p.get('domain') or 'Interdisciplinary'}"].append(p)
        elif group_by == "Author":
            grouped[f"👤 Author(s): {p.get('authors') or 'Not found'}"].append(p)
        elif group_by == "Keyword":
            kws = p.get("keywords") or []
            if kws:
                for kw in kws[:3]:
                    grouped[f"🏷️ Keyword: {kw}"].append(p)
            else:
                grouped["🏷️ Keyword: Unindexed"].append(p)
        elif group_by == "Topic":
            tops = p.get("topics") or []
            if tops:
                for tp in tops[:2]:
                    grouped[f"🔬 Topic: {tp}"].append(p)
            else:
                grouped["🔬 Topic: Core Subject & Entities"].append(p)

    # Render each group and its paper cards
    for grp_idx, (grp_title, grp_papers) in enumerate(grouped.items()):
        render_html([
            f'<div style="margin: 16px 0 8px 0; padding: 8px 14px; background: {theme["bg_card_inner"]}; border-left: 4px solid {theme["accent_purple"]}; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">',
            f'<span style="font-size: 14.5px; font-weight: 700; color: {theme["text_primary"]};">{safe_text(grp_title)}</span>',
            f'<span style="font-size: 12px; font-weight: 600; color: {theme["text_muted"]};">{len(grp_papers)} {"manuscript" if len(grp_papers) == 1 else "manuscripts"}</span>',
            '</div>',
        ])

        for p in grp_papers:
            aid = p["id"]
            u_key = f"{grp_idx}_{aid}"
            title = p["clean_title"]
            authors = p["authors"]
            year = p["year"]
            journal = p["journal"]
            domain = p["domain"]
            score = float(p.get("overall_score") or 0.0)
            p_projs = [pr["name"] for pr in (p.get("projects") or [])]
            p_tags = p.get("tags") or []
            p_kws = p.get("keywords") or []
            notes_list = p.get("notes") or []

            with st.container(border=True):
                render_html('<span class="res-item-scope"></span>')
                proj_badges = "".join(
                    f'<span style="background: rgba(6,182,212,0.15); color: #22d3ee; border: 1px solid rgba(6,182,212,0.35); border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 600;">📁 {safe_text(pn)}</span>'
                    for pn in p_projs
                )
                tag_badges = "".join(
                    f'<span style="background: rgba(16,185,129,0.14); color: #34d399; border: 1px solid rgba(16,185,129,0.3); border-radius: 5px; padding: 2px 8px; font-size: 11px; font-weight: 600;">🏷️ {safe_text(tg)}</span>'
                    for tg in p_tags
                )
                kw_spans = "".join(
                    f'<span style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; color: {theme["text_muted"]}; border-radius: 999px; padding: 2px 8px; font-size: 11px;">#{safe_text(kw)}</span>'
                    for kw in p_kws[:6]
                )
                badges_row = f'<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">{proj_badges}{tag_badges}{kw_spans}</div>' if (proj_badges or tag_badges or kw_spans) else ''

                render_html([
                    '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap;">',
                    f'<div style="font-size: 16.5px; font-weight: 700; color: {theme["text_primary"]}; line-height: 1.35; flex: 1; min-width: 240px;" title="{safe_text(title)}">📄 {safe_text(title)}</div>',
                    '<div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">',
                    f'<span style="background: {theme["accent_primary_subtle"]}; color: {theme["accent_purple"]}; border: 1px solid {theme["accent_primary_border"]}; border-radius: 6px; padding: 2px 9px; font-size: 11.5px; font-weight: 600;">🧭 {safe_text(domain)}</span>',
                    f'<span style="background: rgba(16,185,129,0.14); color: {theme["success_text"]}; border: 1px solid rgba(16,185,129,0.32); border-radius: 6px; padding: 2px 9px; font-size: 12px; font-weight: 800;">{score:.1f}/100</span>',
                    '</div>',
                    '</div>',
                    f'<div style="font-size: 13px; color: {theme["text_secondary"]}; margin-top: 6px; line-height: 1.45;">👤 <b>{safe_text(authors)}</b> {f"({safe_text(year)})" if year else ""} &nbsp;•&nbsp; 🏛️ {safe_text(journal)}</div>',
                    badges_row,
                    f'<hr style="border: none; border-top: 1px solid {theme["border_divider"]}; margin: 10px 0 6px 0;">',
                ])

                # Row 1: Primary Analysis, Comparison & Export Actions (4 equal columns)
                ac1, ac2, ac3, ac4 = st.columns(4, gap="small")
                with ac1:
                    if st.button("🔬 View Profile", key=f"lib_view_{u_key}", use_container_width=True):
                        load_analysis_into_session(p)
                        st.session_state["current_analysis_id"] = aid
                        navigate_to("📄 Analyze Research Paper")
                        st.rerun()

                with ac2:
                    is_in_cmp = aid in selected_cmp_ids
                    cmp_btn_lbl = "✓ In Comparison" if is_in_cmp else "➕ Select to Compare"
                    if st.button(cmp_btn_lbl, key=f"lib_sel_cmp_{u_key}", use_container_width=True, type="primary" if is_in_cmp else "secondary"):
                        if is_in_cmp:
                            selected_cmp_ids.remove(aid)
                        else:
                            if len(selected_cmp_ids) >= 3:
                                st.warning("Maximum 3 papers can be compared at once.")
                            else:
                                selected_cmp_ids.append(aid)
                        st.session_state["res_compare_selected_ids"] = selected_cmp_ids
                        st.rerun()

                with ac3:
                    # Build Paper Report PDF for quick download
                    raw_t = unescape_text(p.get("extracted_text") or "")
                    secs_t = p.get("sections") if isinstance(p.get("sections"), dict) else {}
                    prof_t = (p.get("metrics") or {}).get("research_profile") if isinstance(p.get("metrics"), dict) else None
                    if not prof_t:
                        prof_t = research_engine.extract_research_profile(raw_t, secs_t)
                    try:
                        rep_bytes = pdf_export.build_researcher_paper_pdf({
                            "title": title,
                            "metadata": {"authors": authors, "year": year, "journal": journal, "domain": domain, "keywords": p_kws},
                            "profile": prof_t,
                            "summary": p.get("summary") or "",
                            "overall_score": score,
                            "structure_score": p.get("structure_score", 0),
                            "clarity_score": p.get("clarity_score", 0),
                            "coherence_score": p.get("coherence_score", 0),
                            "citation_score": p.get("citation_score", 0),
                            "readability_score": p.get("readability_score", 0),
                        })
                        st.download_button(
                            "⬇ Report (PDF)",
                            data=rep_bytes,
                            file_name=pdf_export.get_pdf_filename(title, "Paper_Report"),
                            mime="application/pdf",
                            key=f"lib_dl_pdf_{u_key}",
                            use_container_width=True,
                        )
                    except Exception as pdf_err:
                        st.error(f"PDF error: {pdf_err}")

                with ac4:
                    if st.button("🔄 Refresh Metadata", key=f"lib_ref_meta_{u_key}", use_container_width=True):
                        ref_out = auth.refresh_paper_metadata(aid, username)
                        if ref_out.get("ok"):
                            st.success(f"✓ Refreshed '{ref_out.get('title')}'")
                            st.rerun()
                        else:
                            st.warning(ref_out.get("message", "Could not refresh metadata."))

                # Row 2: Curation & Repository Management (Projects, Tags, Notes, Delete)
                ac5, ac6, ac7, ac8 = st.columns(4, gap="small")
                with ac5:
                    with st.popover("📁 Projects", use_container_width=True):
                        p_name_map = {pr["name"]: pr["id"] for pr in projects}
                        curr_pnames = [pr["name"] for pr in (p.get("projects") or []) if pr["name"] in p_name_map]
                        chosen_pnames = st.multiselect(
                            "Assign to Projects",
                            options=list(p_name_map.keys()),
                            default=curr_pnames,
                            key=f"lib_ms_proj_{u_key}",
                        )
                        if st.button("Save Projects", key=f"lib_save_proj_{u_key}", type="primary", use_container_width=True):
                            auth.set_paper_projects(username, aid, [p_name_map[n] for n in chosen_pnames])
                            st.success("Updated projects!")
                            st.rerun()

                with ac6:
                    with st.popover("🏷️ Tags", use_container_width=True):
                        new_t_str = st.text_input(
                            "Tags (comma-separated)",
                            value=", ".join(p_tags),
                            key=f"lib_tags_in_{u_key}",
                        )
                        if st.button("Save Tags", key=f"lib_save_tags_{u_key}", type="primary", use_container_width=True):
                            auth.set_paper_tags(username, aid, [t.strip() for t in new_t_str.split(",") if t.strip()])
                            st.success("Tags saved!")
                            st.rerun()

                with ac7:
                    with st.popover(f"📝 Notes ({len(notes_list)})", use_container_width=True):
                        for n_item in notes_list:
                            nid = n_item["id"]
                            st.markdown(f"**{n_item.get('created_at', '')[:16]}:** {unescape_text(n_item.get('note_text', ''))}")
                            if st.button("Delete Note", key=f"lib_del_note_{u_key}_{nid}"):
                                auth.delete_research_note(username, nid)
                                st.rerun()
                        note_in = st.text_area("Add Researcher Note", key=f"lib_new_note_{u_key}", height=68, placeholder="Record methodological critique, key equation, or citation note...")
                        if st.button("Add Note", key=f"lib_btn_add_note_{u_key}", type="primary", use_container_width=True):
                            ok_n, msg_n, _ = auth.add_research_note(username, aid, note_in)
                            if ok_n:
                                st.success(msg_n)
                                st.rerun()
                            else:
                                st.error(msg_n)

                with ac8:
                    with st.popover("🗑️ Delete", use_container_width=True):
                        st.caption(f"Permanently delete '{truncate_title_word_boundary(title, 45)}' from your library?")
                        if st.button("Confirm Delete", key=f"lib_conf_del_paper_{u_key}", type="primary", use_container_width=True):
                            auth.delete_user_analysis(username, aid)
                            st.success("Manuscript deleted.")
                            st.rerun()


