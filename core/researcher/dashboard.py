"""
PaperIQ — Researcher Page 1: Researcher Dashboard (C1)
======================================================
Requirements:
- Stat cards: papers in library, active projects, disciplines, reports available.
- "Recent Evaluations" list (title, domain, score, date, View action).
- "Active Projects" list (name, paper count, last updated, Open action).
- "Research Activity" timeline (recent uploads, project creations, comparisons, reports).
- Quick actions: Analyze Paper, Open Library, Compare Papers, View Insights, Create Project.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List
import streamlit as st

import auth
import research_engine
from utils import render_html, safe_text, truncate_title_word_boundary, unescape_text


def render_researcher_dashboard(
    theme: Dict[str, str],
    username: str,
    navigate_to: Callable[[str], None],
    load_analysis_into_session: Callable[[Dict[str, Any]], None],
) -> None:
    """Render the Researcher Dashboard (C1)."""
    library_papers = auth.get_researcher_library(username)
    projects = auth.get_user_projects(username)
    comparisons = auth.get_user_comparisons(username)
    activities = auth.get_research_activity(username, limit=15)

    # Compute stat card metrics
    papers_count = len(library_papers)
    projects_count = len(projects)
    disciplines_set = set()
    for p in library_papers:
        dom = (p.get("domain") or "").strip()
        if not dom or dom == "General":
            dom = research_engine.detect_research_domain(p.get("extracted_text") or p.get("summary") or p.get("paper_title") or "")
        if dom:
            disciplines_set.add(dom)
    disciplines_count = len(disciplines_set)
    # Reports available: each paper has Paper + Insights reports, each comparison has Comparison report, each project has Project report
    reports_available = papers_count * 2 + len(comparisons) + projects_count

    # Hero Banner
    render_html([
        f'<div style="background: linear-gradient(135deg, {theme["bg_card"]} 0%, {theme["bg_card_inner"]} 100%); border: 1px solid {theme["accent_primary_border"]}; border-radius: 14px; padding: 22px 26px; margin-bottom: 20px;">',
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">',
        '<div>',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; letter-spacing: 0.06em; text-transform: uppercase;">🔬 Researcher Workspace</span>',
        f'<h1 style="margin: 8px 0 4px 0; font-size: 26px; font-weight: 800; color: {theme["text_primary"]};">Researcher Dashboard</h1>',
        f'<p style="margin: 0; font-size: 14px; color: {theme["text_muted"]};">Synthesize manuscript content, organize literature by project, benchmark methodologies, and uncover evidence-grounded research gaps.</p>',
        '</div>',
        f'<div style="text-align: right; font-size: 12.5px; color: {theme["text_secondary"]};">',
        f'<div>Signed in as <b style="color: {theme["text_primary"]};">{safe_text(username)}</b></div>',
        f'<div style="color: {theme["text_muted"]}; font-size: 11.5px; margin-top: 2px;">🔒 Private Single-Researcher Repository</div>',
        '</div>',
        '</div>',
        '</div>',
    ])

    # 4 Stat Cards
    c1, c2, c3, c4 = st.columns(4)
    stat_specs = [
        (c1, "📚 Papers in Library", str(papers_count), "Indexed manuscripts with research profiles", theme["accent_purple"]),
        (c2, "🗂️ Active Projects", str(projects_count), "Curated literature collections", "#06B6D4"),
        (c3, "🧭 Disciplines", str(disciplines_count), ", ".join(sorted(disciplines_set)[:2]) if disciplines_set else "No domains indexed yet", "#10B981"),
        (c4, "📑 Reports Available", str(reports_available), "Paper, Insights, Comparison & Project exports", "#F59E0B"),
    ]
    for col, label, val, sub, accent in stat_specs:
        with col:
            render_html([
                f'<div class="iq-card" style="padding: 16px 18px !important; border-top: 3px solid {accent}; min-height: 120px; display: flex; flex-direction: column; justify-content: space-between;">',
                '<div>',
                f'<div style="font-size: 12px; font-weight: 700; color: {theme["text_muted"]}; text-transform: uppercase; letter-spacing: 0.05em;">{safe_text(label)}</div>',
                f'<div style="font-size: 28px; font-weight: 800; color: {theme["text_primary"]}; margin: 6px 0 4px 0;">{safe_text(val)}</div>',
                '</div>',
                f'<div style="font-size: 11.5px; color: {theme["text_secondary"]}; line-height: 1.35;" title="{safe_text(sub)}">{safe_text(sub)}</div>',
                '</div>',
            ])

    # Quick Actions Bar
    render_html(f"<div style='font-size: 12px; font-weight: 700; color: {theme['text_muted']}; text-transform: uppercase; letter-spacing: 0.06em; margin: 14px 0 8px 2px;'>⚡ Quick Actions</div>")
    qa1, qa2, qa3, qa4, qa5 = st.columns(5, gap="small")
    with qa1:
        if st.button("📄 Analyze Paper", key="res_qa_analyze", use_container_width=True, type="primary"):
            navigate_to("📄 Analyze Research Paper")
            st.rerun()
    with qa2:
        if st.button("📚 Open Library", key="res_qa_library", use_container_width=True):
            navigate_to("📚 Research Library")
            st.rerun()
    with qa3:
        if st.button("🔄 Compare Papers", key="res_qa_compare", use_container_width=True):
            navigate_to("🔄 Advanced Paper Comparison")
            st.rerun()
    with qa4:
        if st.button("💡 View Insights", key="res_qa_insights", use_container_width=True):
            navigate_to("💡 Research Insights")
            st.rerun()
    with qa5:
        with st.popover("➕ Create Project", use_container_width=True):
            st.markdown("**Create New Research Project**")
            new_p_name = st.text_input("Project Name", key="dash_new_proj_name", placeholder="e.g., Millet Growth & Food Security")
            new_p_desc = st.text_area("Description (optional)", key="dash_new_proj_desc", height=68, placeholder="Literature review scope or benchmark goal...")
            if st.button("Create Project", key="dash_btn_create_proj", type="primary", use_container_width=True):
                ok, msg, pid = auth.create_project(username, new_p_name, new_p_desc)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    render_html("<div style='height: 12px;'></div>")

    # Main 2-Column Content: Left = Recent Evaluations, Right = Active Projects & Research Activity Timeline
    col_left, col_right = st.columns([1.35, 1.05], gap="large")

    with col_left:
        render_html([
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">',
            f'<h3 style="margin: 0; font-size: 18px; font-weight: 700; color: {theme["text_primary"]};">🧪 Recent Evaluations</h3>',
            f'<span style="font-size: 12px; color: {theme["text_muted"]};">Showing latest {min(len(library_papers), 6)} of {papers_count}</span>',
            '</div>',
        ])

        if not library_papers:
            render_html([
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 12px; padding: 28px 20px; text-align: center;">',
                f'<div style="font-size: 15px; font-weight: 600; color: {theme["text_primary"]}; margin-bottom: 6px;">Your Research Library is empty</div>',
                f'<div style="font-size: 13px; color: {theme["text_muted"]};">Upload a manuscript in <b>Analyze Research Paper</b> to extract its structured Research Profile, metadata, keywords, and domain classification.</div>',
                '</div>',
            ])
        else:
            for item in library_papers[:6]:
                aid = item["id"]
                raw_txt = unescape_text(item.get("extracted_text") or item.get("summary") or "")
                raw_t = unescape_text(item.get("paper_title") or item.get("filename") or "Untitled Manuscript")
                if research_engine.is_citation_or_header_line(raw_t):
                    p_title = research_engine.extract_paper_metadata(raw_txt, filename=item.get("filename", "")).get("title") or raw_t
                else:
                    p_title = raw_t
                p_dom = unescape_text(item.get("domain") or "Interdisciplinary")
                if p_dom == "General":
                    p_dom = research_engine.detect_research_domain(raw_txt or p_title)
                p_score = float(item.get("overall_score") or 0.0)
                p_date = str(item.get("timestamp") or "")[:16]
                raw_auth = unescape_text(item.get("authors") or "")
                p_authors = "Not found" if not raw_auth or raw_auth == "Unknown Authors" else raw_auth
                p_year = unescape_text(item.get("year") or "")
                p_projs = [pr["name"] for pr in (item.get("projects") or [])]
                proj_badges_html = "".join(
                    f'<span style="background: rgba(6,182,212,0.14); color: #22d3ee; border: 1px solid rgba(6,182,212,0.3); border-radius: 4px; padding: 1px 6px; font-size: 10.5px; font-weight: 600; margin-left: 5px;">📁 {safe_text(pn)}</span>'
                    for pn in p_projs[:2]
                )

                with st.container(border=True):
                    render_html('<span class="res-item-scope"></span>')
                    r_c1, r_c2 = st.columns([3.6, 1.1])
                    with r_c1:
                        render_html([
                            f'<div style="font-size: 14.5px; font-weight: 700; color: {theme["text_primary"]}; line-height: 1.35;" title="{safe_text(p_title)}">{safe_text(p_title)}</div>',
                            '<div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 5px; font-size: 12px;">',
                            f'<span style="background: {theme["accent_primary_subtle"]}; color: {theme["accent_purple"]}; border: 1px solid {theme["accent_primary_border"]}; border-radius: 4px; padding: 1px 7px; font-weight: 600;">{safe_text(p_dom)}</span>',
                            f'<span style="color: {theme["text_secondary"]};">👤 {safe_text(truncate_title_word_boundary(p_authors, 48))}{f" ({safe_text(p_year)})" if p_year else ""}</span>',
                            f'<span style="color: {theme["text_muted"]};">• 🕒 {safe_text(p_date)}</span>',
                            f'<span style="color: {theme["success_text"]}; font-weight: 700;">• Score: {p_score:.1f}/100</span>',
                            proj_badges_html,
                            '</div>',
                        ])
                    with r_c2:
                        if st.button("View →", key=f"dash_view_paper_{aid}", use_container_width=True):
                            load_analysis_into_session(item)
                            navigate_to("📄 Analyze Research Paper")
                            st.rerun()

    with col_right:
        # Active Projects List
        render_html([
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">',
            f'<h3 style="margin: 0; font-size: 18px; font-weight: 700; color: {theme["text_primary"]};">🗂️ Active Projects</h3>',
            f'<span style="font-size: 12px; color: {theme["text_muted"]};">{projects_count} total</span>',
            '</div>',
        ])

        if not projects:
            render_html([
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 12px; padding: 18px 16px; margin-bottom: 18px; text-align: center;">',
                f'<div style="font-size: 13.5px; font-weight: 600; color: {theme["text_primary"]};">No projects created yet</div>',
                f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 4px;">Use <b>➕ Create Project</b> above or visit <b>Research Library</b> to group manuscripts into projects.</div>',
                '</div>',
            ])
        else:
            for proj in projects[:5]:
                pid = proj["id"]
                pname = unescape_text(proj.get("name") or "Untitled Project")
                pcount = int(proj.get("paper_count") or 0)
                pupd = str(proj.get("updated_at") or proj.get("created_at") or "")[:16]
                with st.container(border=True):
                    render_html('<span class="res-item-scope"></span>')
                    p_c1, p_c2 = st.columns([3.2, 1.2])
                    with p_c1:
                        render_html([
                            f'<div style="font-size: 14px; font-weight: 700; color: {theme["text_primary"]};">📁 {safe_text(pname)}</div>',
                            f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 3px;"><b>{pcount}</b> {"paper" if pcount == 1 else "papers"} • Updated {safe_text(pupd)}</div>',
                        ])
                    with p_c2:
                        if st.button("Open →", key=f"dash_open_proj_{pid}", use_container_width=True):
                            st.session_state["library_selected_project_id"] = pid
                            navigate_to("📚 Research Library")
                            st.rerun()

        # Research Activity Timeline
        render_html([
            '<div style="margin-top: 18px; margin-bottom: 10px;">',
            f'<h3 style="margin: 0; font-size: 18px; font-weight: 700; color: {theme["text_primary"]};">⏱️ Research Activity Timeline</h3>',
            '</div>',
        ])

        if not activities and not library_papers:
            render_html([
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 12px; padding: 16px; font-size: 12.5px; color: {theme["text_muted"]};">',
                'No recent research activity logged yet. Actions such as manuscript evaluations, project creation, and multi-paper comparisons will appear here.',
                '</div>',
            ])
        else:
            timeline_items: List[Dict[str, str]] = []
            for act in activities[:8]:
                a_type = act.get("action_type", "")
                icon = "📌"
                if "PROJECT" in a_type:
                    icon = "🗂️"
                elif "COMPAR" in a_type:
                    icon = "🔄"
                elif "NOTE" in a_type:
                    icon = "📝"
                elif "ANALY" in a_type or "UPLOAD" in a_type:
                    icon = "📄"
                t_raw = unescape_text(act.get("target_title") or a_type.replace("_", " ").title())
                timeline_items.append({
                    "icon": icon,
                    "title": t_raw,
                    "details": unescape_text(act.get("details") or ""),
                    "ts": str(act.get("created_at") or "")[:16],
                })

            # Fallback if activity_log was just created and user already had papers
            if not timeline_items:
                for p in library_papers[:5]:
                    timeline_items.append({
                        "icon": "📄",
                        "title": unescape_text(p.get("paper_title") or p.get("filename") or "Paper Evaluated"),
                        "details": f"Evaluated in {unescape_text(p.get('domain') or 'Research')} ({float(p.get('overall_score') or 0):.1f}/100)",
                        "ts": str(p.get("timestamp") or "")[:16],
                    })

            rows_html = [
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 12px; padding: 14px 16px;">'
            ]
            for idx, t_item in enumerate(timeline_items[:7]):
                border_b = f"border-bottom: 1px solid {theme['border_divider']}; padding-bottom: 9px; margin-bottom: 9px;" if idx < len(timeline_items[:7]) - 1 else ""
                disp_t = truncate_title_word_boundary(t_item["title"], 60)
                rows_html.extend([
                    f'<div style="{border_b}">',
                    '<div style="display: flex; justify-content: space-between; align-items: center;">',
                    f'<span style="font-size: 13px; font-weight: 600; color: {theme["text_primary"]};" title="{safe_text(t_item["title"])}">{t_item["icon"]} {safe_text(disp_t)}</span>',
                    f'<span style="font-size: 11px; color: {theme["text_muted"]};">{safe_text(t_item["ts"])}</span>',
                    '</div>',
                    f'<div style="font-size: 12px; color: {theme["text_secondary"]}; margin-top: 2px;">{safe_text(truncate_title_word_boundary(t_item["details"], 95))}</div>',
                    '</div>',
                ])
            rows_html.append('</div>')
            render_html(rows_html)
