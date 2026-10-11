"""
PaperIQ Role-Based Workspaces Module
Provides dedicated workspace views for Students and Researchers.
- Student Workspace: Focused on academic writing improvement, learning, and structural comprehension.
- Researcher Workspace: Focused on rigorous manuscript assessment, research evidence, and comparative analysis.
"""

import json
from datetime import datetime
import streamlit as st

from utils import render_html, safe_text, truncate_title_word_boundary, unescape_text


def render_student_dashboard(
    theme,
    username,
    user_history,
    navigate_to,
    get_overall_score,
    get_grade,
    get_clean_display_title,
    get_clean_report_filename,
    load_analysis_into_session,
):
    """Renders the Student Learning & Writing Workspace Dashboard."""
    render_html(
        [
            '<div style="margin-bottom: 20px;">',
            '<div style="display: flex; align-items: center; gap: 10px;">',
            '<span style="font-size: 26px;">🎓</span>',
            "<div>",
            f'<h1 style="margin: 0; font-size: 28px; color: {theme["text_primary"]};">Student Research Workspace</h1>',
            f'<p style="margin: 3px 0 0 0; color: {theme["text_muted"]}; font-size: 14.5px;">',
            f"Welcome back, <b>{safe_text(username)}</b>! Understand research papers, evaluate your writing clarity, and improve your academic style.",
            "</p>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )

    # Action Shortcuts
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        st.button("📄 Analyze Paper", type="primary", use_container_width=True, key="stu_btn_anl", on_click=navigate_to, args=("📄 Analyze Paper",))
    with col_b2:
        st.button("🔄 Compare Papers", use_container_width=True, key="stu_btn_cmp", on_click=navigate_to, args=("🔄 Compare Papers",))
    with col_b3:
        st.button("💬 Ask PaperIQ", use_container_width=True, key="stu_btn_ask", on_click=navigate_to, args=("💬 Ask PaperIQ",))
    with col_b4:
        st.button("📚 My History", use_container_width=True, key="stu_btn_hist", on_click=navigate_to, args=("📚 My History",))

    render_html("<br>")

    # Student Metrics
    total_analyzed = len(user_history)
    avg_score = round(sum(get_overall_score(h) for h in user_history) / total_analyzed, 1) if total_analyzed > 0 else 0.0
    best_score = round(max((get_overall_score(h) for h in user_history), default=0.0), 1)

    if total_analyzed == 0:
        proficiency = "New Student"
    elif avg_score >= 85:
        proficiency = "Advanced (Grade A)"
    elif avg_score >= 70:
        proficiency = "Proficient (Grade B)"
    elif avg_score >= 50:
        proficiency = "Developing (Grade C)"
    else:
        proficiency = "Foundational"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important; min-height: 104px; display: flex; flex-direction: column; justify-content: space-between;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Papers Analyzed</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["text_primary"]}; margin-top: 4px;">{total_analyzed}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">Stored in workspace</div>',
                "</div>",
            ]
        )
    with m2:
        val_avg_str = (
            f"{avg_score:.1f} <span style='font-size: 13px; font-weight: 600; color: {theme['text_muted']};'>/ 100</span>"
            if total_analyzed > 0
            else "—"
        )
        sub_avg_str = "Mean writing score" if total_analyzed > 0 else "No analysis data yet"
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important; min-height: 104px; display: flex; flex-direction: column; justify-content: space-between;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Average Writing Score</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["accent_purple"] if total_analyzed > 0 else theme["text_muted"]}; margin-top: 4px;">{val_avg_str}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">{sub_avg_str}</div>',
                "</div>",
            ]
        )
    with m3:
        val_best_str = (
            f"{best_score:.1f} <span style='font-size: 13px; font-weight: 600; color: {theme['text_muted']};'>/ 100</span>"
            if total_analyzed > 0
            else "—"
        )
        sub_best_str = "Highest evaluation recorded" if total_analyzed > 0 else "No analysis data yet"
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important; min-height: 104px; display: flex; flex-direction: column; justify-content: space-between;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Highest Writing Score</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["success_text"] if total_analyzed > 0 else theme["text_muted"]}; margin-top: 4px;">{val_best_str}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">{sub_best_str}</div>',
                "</div>",
            ]
        )
    with m4:
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important; min-height: 104px; display: flex; flex-direction: column; justify-content: space-between;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Writing Level</div>',
                f'<div style="font-size: 15px; font-weight: 800; color: {theme["text_primary"]}; margin-top: 6px; line-height: 1.25; white-space: normal; word-break: break-word;" title="{safe_text(proficiency)}">{safe_text(proficiency)}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">Academic writing tier</div>',
                "</div>",
            ]
        )

    render_html("<br>")

    # Student Academic Writing Improvement Center
    render_html(f"<h3 style='font-size: 19px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>📝 Academic Writing Improvement Center</h3>")

    if user_history:
        latest = user_history[0]
        l_score = get_overall_score(latest)
        res_meta = {}
        if latest.get("results_json"):
            try:
                res_meta = json.loads(latest["results_json"])
            except Exception:
                pass
        raw_title = unescape_text(latest.get("display_title") or res_meta.get("title") or latest.get("filename", "Paper"))
        clean_title = unescape_text(get_clean_display_title(latest.get("filename", "Paper"), stored_title=raw_title))

        raw_scores = res_meta.get("scores", {}) if isinstance(res_meta, dict) else {}
        if not raw_scores:
            raw_scores = {
                "Language Quality": float(latest.get("language_score") or l_score),
                "Structural Coherence": float(latest.get("coherence_score") or l_score),
                "Argumentation": float(latest.get("argumentation_score") or l_score),
                "Academic Style": float(latest.get("academic_style_score") or l_score),
                "Readability": float(latest.get("readability_score") or l_score),
            }

        dim_defs = [
            {
                "name": "Language Quality",
                "icon": "🗣️",
                "score": float(raw_scores.get("Language Quality", raw_scores.get("Language", raw_scores.get("language_quality", l_score)))),
                "weakness": "Repeated phrasing, passive syntactic constructions, or colloquial tone detected.",
                "explanation": "Precise vocabulary and varied sentence cadence ensure clarity for academic readers.",
                "tip": "Replace conversational filler verbs with analytical verbs ('demonstrates', 'synthesizes', 'substantiates').",
            },
            {
                "name": "Structural Coherence",
                "icon": "🧩",
                "score": float(raw_scores.get("Structural Coherence", raw_scores.get("Coherence", raw_scores.get("structural_coherence", l_score)))),
                "weakness": "Transitions between paragraphs lack explicit logical signposts and topic sentences.",
                "explanation": "Logical sequencing between premise, evidence, and deduction guides peer comprehension.",
                "tip": "Start each paragraph with a clear claim, then use deductive markers ('Consequently', 'Furthermore', 'In contrast').",
            },
            {
                "name": "Argumentation & Evidence",
                "icon": "⚖️",
                "score": float(raw_scores.get("Argumentation", raw_scores.get("Reasoning", raw_scores.get("argumentation", l_score)))),
                "weakness": "Analytical claims require stronger empirical citations and counterargument mitigation.",
                "explanation": "Grounding arguments with verifiable evidence and caveats guards against critical review flaws.",
                "tip": "Directly tie each empirical observation back to your research questions and address limitations.",
            },
            {
                "name": "Academic Style",
                "icon": "📖",
                "score": float(raw_scores.get("Academic Style", raw_scores.get("Sophistication", raw_scores.get("academic_style", l_score)))),
                "weakness": "Occasional subjective modifiers or excessive first-person narrative framing.",
                "explanation": "Formal scholarly register maintains objectivity and establishes empirical authority.",
                "tip": "Eliminate hyperbole ('huge', 'remarkable'); maintain neutral, evidence-first academic prose.",
            },
            {
                "name": "Readability",
                "icon": "👓",
                "score": float(raw_scores.get("Readability", raw_scores.get("readability", l_score))),
                "weakness": "Excessively dense multi-clause sentences resulting in cognitive fatigue.",
                "explanation": "Balancing complex ideas with readable syntax maximizes reader retention.",
                "tip": "Split multi-clause sentences into concise independent statements when introducing variables or results.",
            },
        ]

        sorted_dims = sorted(dim_defs, key=lambda d: d["score"])
        top_2_recommendations = sorted_dims[:2]

        with st.container(border=True):
            render_html(
                [
                    '<div style="margin-bottom: 12px;">',
                    f'<span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["info_text"]}; letter-spacing: 0.05em;">Targeted Feedback Based on Latest Analysis</span>',
                    f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]}; margin-top: 2px;">📄 {safe_text(clean_title)}</div>',
                    f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 2px;">Overall Writing Quality: <b>{l_score:.1f} / 100 (Grade {safe_text(get_grade(l_score))})</b> • Top 2 Priority Recommendations:</div>',
                    "</div>",
                ]
            )

            rec_cols = st.columns(2)
            for idx_c, r in enumerate(top_2_recommendations):
                with rec_cols[idx_c]:
                    score_color = (
                        theme["accent_purple"]
                        if r["score"] >= 75
                        else (theme["warning_text"] if r["score"] >= 60 else theme["error_text"])
                    )
                    render_html(
                        [
                            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 14px 16px; min-height: 165px; display: flex; flex-direction: column; justify-content: space-between;">',
                            "<div>",
                            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">',
                            f'<span style="font-weight: 700; color: {theme["text_primary"]}; font-size: 14px;">{r["icon"]} {safe_text(r["name"])}</span>',
                            f'<span style="font-size: 12px; font-weight: 800; color: {score_color};">{r["score"]:.1f}/100</span>',
                            "</div>",
                            f'<div style="font-size: 12.5px; color: {theme["text_secondary"]}; margin-top: 4px; line-height: 1.45;"><b>Focus Area:</b> {safe_text(r["weakness"])}</div>',
                            f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 6px; line-height: 1.4;"><b>Rationale:</b> {safe_text(r["explanation"])}</div>',
                            "</div>",
                            f'<div style="font-size: 12px; color: {theme["info_text"]}; font-weight: 600; margin-top: 8px; border-top: 1px solid {theme["border_subtle"]}; padding-top: 6px;">💡 <b>Tip:</b> {safe_text(r["tip"])}</div>',
                            "</div>",
                        ]
                    )

            render_html("<div style='height: 8px;'></div>")
            if st.button("📊 View Complete Report →", key="btn_stu_goto_active", use_container_width=True):
                load_analysis_into_session(latest)
                navigate_to("📊 Analysis")
                st.rerun()

    else:
        render_html(
            [
                '<div class="iq-card" style="text-align: center; padding: 36px 20px !important;">',
                '<div style="font-size: 34px; margin-bottom: 8px;">📚</div>',
                f'<h4 style="color: {theme["text_primary"]}; margin: 0;">Start Your Academic Writing Journey</h4>',
                f'<p style="color: {theme["text_muted"]}; margin: 6px 0 16px 0; font-size: 14px; max-width: 580px; margin-left: auto; margin-right: auto;">Upload an academic paper or essay in <b>Analyze Paper</b> to receive multidimensional scoring, actionable writing suggestions, and executive summaries.</p>',
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 14px 18px; text-align: left; max-width: 600px; margin: 0 auto; font-size: 12.5px; color: {theme["text_secondary"]}; line-height: 1.6;">',
                "<b>💡 Quick Student Writing Checklist:</b><br>",
                "1. <b>Thesis Clarity:</b> State your primary hypothesis or inquiry in the introduction.<br>",
                "2. <b>Discourse Markers:</b> Connect paragraphs using logical transitions ('Consequently', 'Furthermore').<br>",
                "3. <b>Evidence Grounding:</b> Support claims with empirical citations and avoid unsubstantiated assertions.<br>",
                "4. <b>Objective Tone:</b> Maintain formal, neutral academic phrasing throughout your draft.",
                "</div>",
                "</div>",
            ]
        )

    render_html("<br>")
    render_html(f"<h3 style='font-size: 19px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>Recent Analyses</h3>")

    if not user_history:
        st.caption("No papers analyzed yet. Your recent analysis history will appear here.")
    else:
        for idx, item in enumerate(user_history[:3]):
            item_score = get_overall_score(item)
            grade = get_grade(item_score)
            res_meta = {}
            if item.get("results_json"):
                try:
                    res_meta = json.loads(item["results_json"])
                except Exception:
                    pass
            stored_title = unescape_text(item.get("display_title") or res_meta.get("title"))
            clean_display_title = unescape_text(get_clean_display_title(item.get("filename"), stored_title=stored_title))
            clean_fn = get_clean_report_filename(item.get("filename"))

            with st.container(border=True):
                col_info, col_score, col_act1, col_act2 = st.columns([3.8, 2.2, 1.8, 1.8])
                with col_info:
                    render_html(
                        [
                            f'<div style="font-weight: 700; color: {theme["text_primary"]}; font-size: 14.5px; line-height: 1.35; word-break: break-word;" title="{safe_text(clean_display_title)}">📄 {safe_text(clean_display_title)}</div>',
                            f'<div style="color: {theme["text_muted"]}; font-size: 12px; margin-top: 3px;">Domain: <b style="color: {theme["info_text"]};">{safe_text(item.get("domain", "General Academic"))}</b> &nbsp;•&nbsp; Date: {safe_text(item.get("created_at", ""))}</div>',
                        ]
                    )
                with col_score:
                    render_html(
                        [
                            f'<div style="font-size: 14.5px; font-weight: 800; color: {theme["accent_purple"]}; margin-top: 6px;">',
                            f"Score: {item_score:.1f} / 100 &nbsp;",
                            f'<span style="background: {theme["badge_role_bg"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 8px; border: 1px solid {theme["badge_role_border"]};">Grade {safe_text(grade)}</span>',
                            "</div>",
                        ]
                    )
                with col_act1:
                    if st.button("View Analysis", key=f"stu_dash_view_{item.get('id', idx)}", use_container_width=True):
                        load_analysis_into_session(item)
                        navigate_to("📊 Analysis")
                        st.rerun()
                with col_act2:
                    if item.get("pdf"):
                        st.download_button(
                            "Download Report",
                            data=item["pdf"],
                            file_name=clean_fn,
                            mime="application/pdf",
                            key=f"stu_dash_down_{item.get('id', idx)}",
                            use_container_width=True,
                        )

        if len(user_history) > 3:
            render_html("<div style='margin-top: 8px;'></div>")
            if st.button(
                f"📚 View All History ({len(user_history)} papers) →",
                key="stu_dash_view_all_hist",
                use_container_width=True,
                on_click=navigate_to,
                args=("📚 My History",),
            ):
                navigate_to("📚 My History")
                st.rerun()


def render_researcher_dashboard(
    theme,
    username,
    user_history,
    navigate_to,
    get_overall_score,
    get_grade,
    get_clean_display_title,
    get_clean_report_filename,
    load_analysis_into_session,
):
    """Renders the Researcher Intelligence Workspace Dashboard."""
    render_html(
        [
            '<div style="margin-bottom: 20px;">',
            '<div style="display: flex; align-items: center; gap: 10px;">',
            '<span style="font-size: 26px;">🔬</span>',
            "<div>",
            f'<h1 style="margin: 0; font-size: 28px; color: {theme["text_primary"]};">Researcher Intelligence Workspace</h1>',
            f'<p style="margin: 3px 0 0 0; color: {theme["text_muted"]}; font-size: 14.5px;">',
            f"Welcome, Researcher <b>{safe_text(username)}</b>. Rigorous manuscript evaluation, evidence-grounded research extraction, and comparative analysis.",
            "</p>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )

    # Action Shortcuts
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        st.button("+ Analyze Manuscript", type="primary", use_container_width=True, key="res_btn_anl", on_click=navigate_to, args=("📄 Analyze Manuscript",))
    with col_b2:
        st.button("🔄 Compare Manuscripts", use_container_width=True, key="res_btn_cmp", on_click=navigate_to, args=("🔄 Compare Manuscripts",))
    with col_b3:
        st.button("💡 Research Insights", use_container_width=True, key="res_btn_ins", on_click=navigate_to, args=("💡 Research Insights",))
    with col_b4:
        st.button("📚 Research History", use_container_width=True, key="res_btn_hist", on_click=navigate_to, args=("📚 Research History",))

    render_html("<br>")

    # Researcher Metrics
    total_analyzed = len(user_history)
    avg_score = round(sum(get_overall_score(h) for h in user_history) / total_analyzed, 1) if total_analyzed > 0 else 0.0
    domains_count = len(set(h.get("domain", "General Academic") for h in user_history)) if total_analyzed > 0 else 0
    reports_gen = sum(1 for h in user_history if h.get("pdf"))

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Manuscripts Evaluated</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["text_primary"]}; margin-top: 4px;">{total_analyzed}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">Stored in workspace</div>',
                "</div>",
            ]
        )
    with m2:
        val_m_str = (
            f"{avg_score:.1f} <span style='font-size: 13px; font-weight: 600; color: {theme['text_muted']};'>/ 100</span>"
            if total_analyzed > 0
            else "—"
        )
        sub_m_str = "Mean score across papers" if total_analyzed > 0 else "No manuscripts analyzed yet"
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Mean Manuscript Score</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["accent_purple"] if total_analyzed > 0 else theme["text_muted"]}; margin-top: 4px;">{val_m_str}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">{sub_m_str}</div>',
                "</div>",
            ]
        )
    with m3:
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Research Disciplines</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["info_text"] if total_analyzed > 0 else theme["text_muted"]}; margin-top: 4px;">{domains_count}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">Unique academic fields</div>',
                "</div>",
            ]
        )
    with m4:
        render_html(
            [
                '<div class="iq-card" style="padding: 14px 16px !important; margin-bottom: 0 !important;">',
                f'<div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["text_muted"]}; letter-spacing: 0.05em;">Archived Reports</div>',
                f'<div style="font-size: 26px; font-weight: 800; color: {theme["success_text"] if total_analyzed > 0 else theme["text_muted"]}; margin-top: 4px;">{reports_gen}</div>',
                f'<div style="font-size: 11px; color: {theme["text_muted"]}; margin-top: 2px;">Downloadable PDFs ready</div>',
                "</div>",
            ]
        )

    render_html("<br>")

    # Recent Research Insights Spotlight
    render_html(f"<h3 style='font-size: 19px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>🔍 Latest Research Findings & Evidence</h3>")

    if user_history:
        latest = user_history[0]
        res_meta = {}
        if latest.get("results_json"):
            try:
                res_meta = json.loads(latest["results_json"])
            except Exception:
                pass
        raw_title = unescape_text(latest.get("display_title") or res_meta.get("title") or latest.get("filename", "Paper"))
        clean_title = unescape_text(get_clean_display_title(latest.get("filename", "Paper"), stored_title=raw_title))
        meth_data = res_meta.get("methodology_and_findings", {})

        with st.container(border=True):
            render_html(
                [
                    '<div style="margin-bottom: 12px;">',
                    f'<span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: {theme["accent_purple"]}; letter-spacing: 0.05em;">Manuscript Intelligence Spotlight</span>',
                    f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]}; margin-top: 2px;">📄 {safe_text(clean_title)}</div>',
                    f'<div style="font-size: 12px; color: {theme["text_muted"]}; margin-top: 2px;">Discipline: <b style="color: {theme["info_text"]};">{safe_text(latest.get("domain", "General Academic"))}</b> &nbsp;•&nbsp; Date: {safe_text(latest.get("created_at", ""))}</div>',
                    "</div>",
                ]
            )

            c_r1, c_r2, c_r3 = st.columns(3)
            with c_r1:
                meth_excerpt = unescape_text(meth_data.get("methodology", "Methodological framework extracted from manuscript sections."))[:180]
                render_html(
                    [
                        f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 12px 14px; min-height: 120px;">',
                        f'<div style="font-weight: 700; color: {theme["info_text"]}; font-size: 13px;">🎯 Study Objectives & Design</div>',
                        f'<p style="font-size: 12px; color: {theme["text_secondary"]}; margin: 6px 0 0 0; line-height: 1.5;">{safe_text(meth_excerpt)}...</p>',
                        "</div>",
                    ]
                )
            with c_r2:
                find_excerpt = unescape_text(meth_data.get("findings", "Key experimental or empirical results identified in document content."))[:180]
                render_html(
                    [
                        f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 12px 14px; min-height: 120px;">',
                        f'<div style="font-weight: 700; color: {theme["success_text"]}; font-size: 13px;">📊 Principal Empirical Findings</div>',
                        f'<p style="font-size: 12px; color: {theme["text_secondary"]}; margin: 6px 0 0 0; line-height: 1.5;">{safe_text(find_excerpt)}...</p>',
                        "</div>",
                    ]
                )
            with c_r3:
                render_html(
                    [
                        f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 12px 14px; min-height: 120px;">',
                        f'<div style="font-weight: 700; color: {theme["warning_text"]}; font-size: 13px;">⚠️ Limitations & Research Gaps</div>',
                        f'<p style="font-size: 12px; color: {theme["text_secondary"]}; margin: 6px 0 0 0; line-height: 1.5;">Explicit constraints and unresolved challenges reported by the authors to inform future study extensions.</p>',
                        "</div>",
                    ]
                )

            st.write("")
            col_act_a, col_act_b = st.columns([1.5, 1.5])
            with col_act_a:
                if st.button("💡 Explore Full Research Insights →", key="btn_res_goto_insights", use_container_width=True):
                    load_analysis_into_session(latest)
                    navigate_to("💡 Research Insights")
                    st.rerun()
            with col_act_b:
                if st.button("📊 View Dimensional Evaluation →", key="btn_res_goto_eval", use_container_width=True):
                    load_analysis_into_session(latest)
                    navigate_to("📊 Manuscript Evaluation")
                    st.rerun()

    else:
        render_html(
            [
                '<div class="iq-card" style="text-align: center; padding: 36px 20px !important;">',
                '<div style="font-size: 34px; margin-bottom: 8px;">🔬</div>',
                f'<h4 style="color: {theme["text_primary"]}; margin: 0;">No Manuscripts Evaluated Yet</h4>',
                f'<p style="color: {theme["text_muted"]}; margin: 6px 0 16px 0; font-size: 14px; max-width: 580px; margin-left: auto; margin-right: auto;">Upload an academic manuscript in <b>Analyze Manuscript</b> to extract empirical methodology, research gaps, author-stated contributions, and comparative metrics.</p>',
                f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 14px 18px; text-align: left; max-width: 600px; margin: 0 auto; font-size: 12.5px; color: {theme["text_secondary"]}; line-height: 1.6;">',
                "<b>🛡️ Researcher Protocol Notice:</b><br>",
                "PaperIQ evaluates computational stylistic rigor, argumentation density, and textual cohesion. It does not independently authenticate empirical laboratory veracity, prove scientific novelty, or substitute for peer review.",
                "</div>",
                "</div>",
            ]
        )

    render_html("<br>")
    render_html(f"<h3 style='font-size: 19px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>Recent Manuscript Evaluations</h3>")

    if not user_history:
        st.caption("No manuscripts evaluated yet.")
    else:
        for idx, item in enumerate(user_history[:5]):
            item_score = get_overall_score(item)
            grade = get_grade(item_score)
            res_meta = {}
            if item.get("results_json"):
                try:
                    res_meta = json.loads(item["results_json"])
                except Exception:
                    pass
            stored_title = unescape_text(item.get("display_title") or res_meta.get("title"))
            clean_display_title = unescape_text(get_clean_display_title(item.get("filename"), stored_title=stored_title))
            truncated_title = truncate_title_word_boundary(clean_display_title, max_chars=52)
            clean_fn = get_clean_report_filename(item.get("filename"))

            with st.container(border=True):
                col_info, col_score, col_act1, col_act2 = st.columns([4.2, 2.2, 1.8, 1.8])
                with col_info:
                    render_html(
                        [
                            f'<div style="font-weight: 700; color: {theme["text_primary"]}; font-size: 14.5px;" title="{safe_text(clean_display_title)}">📄 {safe_text(truncated_title)}</div>',
                            f'<div style="color: {theme["text_muted"]}; font-size: 12px; margin-top: 3px;">Discipline: <b style="color: {theme["info_text"]};">{safe_text(item.get("domain", "General Academic"))}</b> &nbsp;•&nbsp; Date: {safe_text(item.get("created_at", ""))}</div>',
                        ]
                    )
                with col_score:
                    render_html(
                        [
                            f'<div style="font-size: 14.5px; font-weight: 800; color: {theme["accent_purple"]}; margin-top: 6px;">',
                            f"Score: {item_score:.1f} / 100 &nbsp;",
                            f'<span style="background: {theme["badge_role_bg"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 8px; border: 1px solid {theme["badge_role_border"]};">Grade {safe_text(grade)}</span>',
                            "</div>",
                        ]
                    )
                with col_act1:
                    if st.button("View Evaluation", key=f"res_dash_view_{item.get('id', idx)}", use_container_width=True):
                        load_analysis_into_session(item)
                        navigate_to("📊 Manuscript Evaluation")
                        st.rerun()
                with col_act2:
                    if item.get("pdf"):
                        st.download_button(
                            "Download Report",
                            data=item["pdf"],
                            file_name=clean_fn,
                            mime="application/pdf",
                            key=f"res_dash_down_{item.get('id', idx)}",
                            use_container_width=True,
                        )
