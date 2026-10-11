"""
PaperIQ — Researcher Page 5: Ask PaperIQ (C5 — Researcher Version)
==================================================================
Requirements:
- Suggested questions tailored to researchers (9 exact questions).
- Scope selector: "Current paper" vs "Selected papers in a project".
- Every answer must cite the supporting passage and section label.
- If retrieval relevance is below threshold, answer "I could not find this in the paper" rather than guessing.
- Chat history is saved per paper/scope for that researcher, and Download Chat (PDF + TXT) is provided.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List
import streamlit as st

import auth
import pdf_export
import research_engine
import summarizer
from utils import render_html, safe_text, unescape_text


def render_researcher_ask_paperiq(
    theme: Dict[str, str],
    username: str,
) -> None:
    """Render Researcher Page 5: Ask PaperIQ (C5)."""
    render_html([
        '<div style="margin-bottom: 16px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">💬 Evidence-Grounded Research Q&amp;A</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Ask PaperIQ (Researcher Mode)</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Query a single manuscript or interrogate multiple manuscripts across a research project. Every response cites exact supporting passages and section labels.</p>',
        '</div>',
    ])

    library_papers = auth.get_researcher_library(username)
    projects = auth.get_user_projects(username)

    if not library_papers and not st.session_state.get("text"):
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px dashed {theme["border_color"]}; border-radius: 12px; padding: 28px 20px; text-align: center;">',
            f'<div style="font-size: 16px; font-weight: 700; color: {theme["text_primary"]};">No manuscripts available to query</div>',
            f'<div style="font-size: 13px; color: {theme["text_muted"]}; margin-top: 4px;">Upload and evaluate a paper in <b>Analyze Research Paper</b> first to enable Ask PaperIQ.</div>',
            '</div>',
        ])
        return

    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            f"<div style='font-size: 14px; font-weight: 700; color: {theme['text_primary']}; margin-bottom: 4px;'>🎯 Interrogation Scope &amp; Manuscript Selection</div>",
        ])
        sc1, sc2 = st.columns([1.3, 2.2], gap="medium")
        with sc1:
            scope_choice = st.radio(
                "Query Scope",
                options=["Current paper", "Selected papers in a project"],
                index=0,
                key="res_ask_scope_radio",
            )

        target_papers: List[Dict[str, Any]] = []
        scope_key = "single_default"
        scope_title_label = "Current Manuscript"

        with sc2:
            if scope_choice == "Current paper":
                if library_papers:
                    p_map: Dict[str, Dict[str, Any]] = {}
                    for p in library_papers:
                        raw_t_str = unescape_text(p.get("extracted_text") or p.get("summary") or "")
                        c_title = unescape_text(p.get("paper_title") or p.get("filename") or "Manuscript")
                        if research_engine.is_citation_or_header_line(c_title):
                            c_title = research_engine.extract_paper_metadata(raw_t_str, filename=p.get("filename", "")).get("title") or c_title
                        yr_s = unescape_text(str(p.get("year") or "")).strip() or "n.d."
                        base_lbl = f"{c_title} ({yr_s})"
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
                    chosen_p_lbl = st.selectbox("Select Manuscript to Query", options=list(p_map.keys()), index=default_idx, key="res_ask_single_paper_sel")
                    p_rec = p_map[chosen_p_lbl]
                    raw_t = unescape_text(p_rec.get("extracted_text") or p_rec.get("summary") or "")
                    secs_t = p_rec.get("sections") if isinstance(p_rec.get("sections"), dict) and p_rec.get("sections") else summarizer.segment_paper_sections(raw_t)
                    c_title = unescape_text(p_rec.get("paper_title") or p_rec.get("filename") or "Manuscript")
                    if research_engine.is_citation_or_header_line(c_title):
                        c_title = research_engine.extract_paper_metadata(raw_t, filename=p_rec.get("filename", "")).get("title") or c_title
                    target_papers = [{
                        "id": p_rec["id"],
                        "title": c_title,
                        "text": raw_t,
                        "sections": secs_t,
                        "profile": (p_rec.get("metrics") or {}).get("research_profile") if isinstance(p_rec.get("metrics"), dict) else None,
                    }]
                    scope_key = f"paper:{p_rec['id']}"
                    scope_title_label = target_papers[0]["title"]
                elif st.session_state.get("text"):
                    raw_t = unescape_text(st.session_state.get("text") or "")
                    t_title = unescape_text(st.session_state.get("paper_title") or "Current Manuscript")
                    if research_engine.is_citation_or_header_line(t_title):
                        t_title = research_engine.extract_paper_metadata(raw_t).get("title") or t_title
                    target_papers = [{
                        "id": None,
                        "title": t_title,
                        "text": raw_t,
                        "sections": st.session_state.get("sections") or summarizer.segment_paper_sections(raw_t),
                    }]
                    scope_key = "paper:session"
                    scope_title_label = t_title
            else:
                # Selected papers in a project
                if not projects:
                    st.warning("No projects exist yet. Create a project in **Research Library** or select papers from your library below.")
                    proj_candidates = library_papers
                    selected_proj_id = "all"
                else:
                    proj_opts = {f"{pr['name']} ({pr['paper_count']} papers)": pr["id"] for pr in projects}
                    sel_proj_lbl = st.selectbox("Select Project", options=list(proj_opts.keys()), key="res_ask_proj_sel")
                    selected_proj_id = proj_opts[sel_proj_lbl]
                    proj_candidates = [
                        p for p in library_papers
                        if any(pr["id"] == selected_proj_id for pr in (p.get("projects") or []))
                    ]
                    if not proj_candidates:
                        st.caption("No papers assigned to this project yet; showing all library papers.")
                        proj_candidates = library_papers

                cand_map: Dict[str, Dict[str, Any]] = {}
                for p in proj_candidates:
                    raw_t_str = unescape_text(p.get("extracted_text") or p.get("summary") or "")
                    c_title = unescape_text(p.get("paper_title") or p.get("filename") or "Manuscript")
                    if research_engine.is_citation_or_header_line(c_title):
                        c_title = research_engine.extract_paper_metadata(raw_t_str, filename=p.get("filename", "")).get("title") or c_title
                    yr_s = unescape_text(str(p.get("year") or "")).strip() or "n.d."
                    base_lbl = f"{c_title} ({yr_s})"
                    lbl = base_lbl if base_lbl not in cand_map else f"{base_lbl} — {unescape_text(p.get('domain') or 'Research')}"
                    if lbl in cand_map:
                        lbl = f"{lbl} #{len(cand_map) + 1}"
                    cand_map[lbl] = p

                default_multi = list(cand_map.keys())[:3]
                sel_multi_lbls = st.multiselect(
                    "Select Project Manuscripts to Interrogate",
                    options=list(cand_map.keys()),
                    default=default_multi,
                    key="res_ask_multi_papers_sel",
                )
                for lbl in sel_multi_lbls:
                    p_rec = cand_map[lbl]
                    raw_t = unescape_text(p_rec.get("extracted_text") or p_rec.get("summary") or "")
                    secs_t = p_rec.get("sections") if isinstance(p_rec.get("sections"), dict) and p_rec.get("sections") else summarizer.segment_paper_sections(raw_t)
                    c_title = unescape_text(p_rec.get("paper_title") or p_rec.get("filename") or "Manuscript")
                    if research_engine.is_citation_or_header_line(c_title):
                        c_title = research_engine.extract_paper_metadata(raw_t, filename=p_rec.get("filename", "")).get("title") or c_title
                    target_papers.append({
                        "id": p_rec["id"],
                        "title": c_title,
                        "text": raw_t,
                        "sections": secs_t,
                        "profile": (p_rec.get("metrics") or {}).get("research_profile") if isinstance(p_rec.get("metrics"), dict) else None,
                    })
                scope_key = f"project:{selected_proj_id}:{'_'.join(str(p['id']) for p in target_papers)}"
                scope_title_label = f"Project Synthesis ({len(target_papers)} papers)"

    # Suggested Researcher Questions (9 exact buttons inside a clean section card)
    suggested_questions = research_engine.RESEARCHER_SUGGESTED_QUESTIONS
    triggered_question = None

    with st.container(border=True):
        render_html([
            '<span class="res-card-scope"></span>',
            '<span class="res-suggested-q-scope"></span>',
            f"<div style='font-size: 12px; font-weight: 700; color: {theme['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;'>💡 Suggested Researcher Questions</div>",
        ])
        for row_idx in range(0, len(suggested_questions), 3):
            q_cols = st.columns(3, gap="small")
            for c_i in range(3):
                if row_idx + c_i < len(suggested_questions):
                    q_str = suggested_questions[row_idx + c_i]
                    with q_cols[c_i]:
                        if st.button(q_str, key=f"res_sug_q_{row_idx + c_i}", use_container_width=True):
                            triggered_question = q_str

    # Custom Question Input Form
    with st.form("res_ask_question_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns([3.8, 1.0], gap="small")
        with f_c1:
            custom_q = st.text_input(
                "Ask a research question about methodology, datasets, findings, limitations, or cross-paper synthesis...",
                label_visibility="collapsed",
                placeholder="Ask a research question (e.g., What statistical models or datasets were used?)...",
            )
        with f_c2:
            sub_q = st.form_submit_button("Ask PaperIQ →", type="primary", use_container_width=True)
        if sub_q and custom_q.strip():
            triggered_question = custom_q.strip()

    # Execute Question & Save Turn
    if triggered_question and target_papers:
        mode_flag = "single" if scope_choice == "Current paper" else "multi"
        ans_bundle = research_engine.answer_researcher_question(
            triggered_question, target_papers, scope_mode=mode_flag
        )
        primary_aid = target_papers[0].get("id") if len(target_papers) == 1 else None
        auth.save_paper_chat_turn(
            username=username,
            scope_key=scope_key,
            question=triggered_question,
            answer=ans_bundle["answer"],
            citations=ans_bundle["citations"],
            analysis_id=primary_aid,
        )

    # Load Persisted Chat History for this Scope
    chat_turns = auth.get_paper_chat_history(username, scope_key)

    if not chat_turns:
        render_html([
            f'<div style="background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 10px; padding: 18px; margin-top: 10px; font-size: 13px; color: {theme["text_muted"]}; text-align: center;">',
            'Click any suggested researcher question above or enter a custom query to retrieve passage-cited answers from your selected manuscript(s).',
            '</div>',
        ])
        return

    # Action bar: Download Chat PDF, Download Chat TXT, Clear History
    act_c1, act_c2, act_c3 = st.columns([1.4, 1.4, 1.0])
    with act_c1:
        pdf_turns = [
            {
                "question": t["question"],
                "answer": t["answer"],
                "citations": t["citations"],
                "timestamp": t["created_at"],
            }
            for t in chat_turns
        ]
        try:
            chat_pdf_bytes = pdf_export.build_chat_pdf(scope_title_label, pdf_turns)
            st.download_button(
                "⬇ Download Chat Transcript (PDF)",
                data=chat_pdf_bytes,
                file_name=pdf_export.get_pdf_filename(scope_title_label, "Researcher_QA_Chat"),
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="res_ask_dl_pdf",
            )
        except Exception as pdf_err:
            st.error(f"Could not generate Chat PDF: {pdf_err}")
    with act_c2:
        txt_lines = [
            "=" * 72,
            f"PAPERIQ RESEARCHER Q&A TRANSCRIPT — {scope_title_label}",
            "=" * 72,
        ]
        for idx, t in enumerate(chat_turns, start=1):
            txt_lines.append(f"\nQ{idx} ({t.get('created_at', '')}): {t['question']}")
            txt_lines.append(f"Answer: {t['answer']}")
            for c_ev in t.get("citations") or []:
                txt_lines.append(f"  - [{c_ev.get('paper_title', '')} | Section: {c_ev.get('section', '')} | Match Strength: {c_ev.get('confidence', 'High')}]: \"{c_ev.get('passage', '')}\"")
        st.download_button(
            "⬇ Download Chat Transcript (TXT)",
            data="\n".join(txt_lines).encode("utf-8"),
            file_name="PaperIQ_Researcher_Chat_Transcript.txt",
            mime="text/plain",
            use_container_width=True,
            key="res_ask_dl_txt",
        )
    with act_c3:
        if st.button("🗑️ Clear Chat History", key="res_ask_clear_btn", use_container_width=True):
            auth.clear_paper_chat_history(username, scope_key)
            st.rerun()

    # Render Chat Turns (Newest First)
    for idx, turn in enumerate(reversed(chat_turns)):
        q_txt = unescape_text(turn.get("question") or "")
        a_txt = unescape_text(turn.get("answer") or "")
        cits = turn.get("citations") or []
        ts_str = str(turn.get("created_at") or "")[:16]

        cite_boxes: List[str] = []
        for c_item in cits:
            p_ref = unescape_text(c_item.get("paper_title") or "")
            sec_ref = unescape_text(c_item.get("section") or "Manuscript")
            pas_ref = unescape_text(c_item.get("passage") or "")
            conf_ref = unescape_text(c_item.get("confidence") or "High")
            cite_boxes.extend([
                f'<div style="background: {theme["bg_card"]}; border: 1px solid {theme["border_color"]}; border-left: 3px solid #06B6D4; border-radius: 6px; padding: 8px 12px; margin-top: 6px;">',
                f'<div style="font-size: 11.5px; font-weight: 700; color: #22d3ee; margin-bottom: 3px;">📄 {safe_text(p_ref)} &nbsp;•&nbsp; 📍 Section: {safe_text(sec_ref)} &nbsp;•&nbsp; <span style="color: {theme["text_muted"]};">Match Strength: {safe_text(conf_ref)}</span></div>',
                f'<div style="font-size: 12.5px; color: {theme["text_secondary"]}; font-style: italic; line-height: 1.45;">"{safe_text(pas_ref)}"</div>',
                '</div>',
            ])

        render_html([
            f'<div class="iq-card" style="padding: 16px 20px !important; margin-top: 12px; border-left: 4px solid {theme["accent_purple"]};">',
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">',
            f'<div style="font-size: 14.5px; font-weight: 700; color: {theme["text_primary"]};">❓ {safe_text(q_txt)}</div>',
            f'<span style="font-size: 11px; color: {theme["text_muted"]};">{safe_text(ts_str)}</span>',
            '</div>',
            f'<div style="font-size: 13.5px; color: {theme["text_primary"]}; line-height: 1.55; margin-bottom: 8px;">{safe_text(a_txt)}</div>',
            f'<div style="font-size: 11.5px; font-weight: 700; color: {theme["text_muted"]}; text-transform: uppercase; margin-top: 8px;">Supporting Manuscript Passages ({len(cits)})</div>' if cits else '',
            *cite_boxes,
            '</div>',
        ])
