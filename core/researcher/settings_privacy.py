"""
PaperIQ — Researcher Page 8: Settings & Privacy (C8)
====================================================
Requirements:
- Account profile, appearance/theme, active-analysis reset.
- Data management:
    * Clear history
    * Delete a project only (keep papers)
    * Delete a project and its papers
    * Export my data (JSON of metadata, notes, projects)
    * Delete all my data (with confirmation)
- Privacy explanation of what is stored locally in SQLite vs in session memory,
  and explicit notice that researchers can only access their own papers (no sharing).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict
import streamlit as st

import auth
from utils import render_html, safe_text, unescape_text


def render_researcher_settings_and_privacy(
    theme: Dict[str, str],
    username: str,
    user_data: Dict[str, Any],
) -> None:
    """Render Researcher Page 8: Settings & Privacy (C8)."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">⚙️ Account, Governance &amp; Data Control</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">Settings &amp; Privacy</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Manage your researcher profile, interface appearance, active session workspace, project lifecycle, and local SQLite data governance.</p>',
        '</div>',
    ])

    col_prof, col_app = st.columns(2, gap="large")

    # 1. Account Profile Card
    with col_prof:
        email_val = user_data.get("email") or "Not specified"
        role_val = user_data.get("role") or "Researcher"
        raw_created = user_data.get("created_at") or auth.get_user_created_at(username)
        created_val = str(raw_created)[:16] if raw_created else "2026-03-01"
        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f'<h3 style="margin: 0 0 10px 0; font-size: 17px; font-weight: 700; color: {theme["text_primary"]};">👤 Researcher Account Profile</h3>',
                f'<div style="font-size: 13.5px; color: {theme["text_secondary"]}; line-height: 2.05; background: {theme["bg_card_inner"]}; border: 1px solid {theme["border_color"]}; border-radius: 8px; padding: 14px 16px;">',
                f'<div><b>Username:</b> <span style="color: {theme["text_primary"]};">{safe_text(username)}</span></div>',
                f'<div><b>Email:</b> <span style="color: {theme["text_primary"]};">{safe_text(email_val)}</span></div>',
                f'<div><b>Workspace Role:</b> <span style="background: {theme["badge_role_bg"]}; color: {theme["badge_role_text"]}; border: 1px solid {theme["badge_role_border"]}; border-radius: 4px; padding: 1px 7px; font-size: 12px; font-weight: 700;">🔬 {safe_text(role_val)}</span></div>',
                f'<div><b>Member Since:</b> <span style="color: {theme["text_muted"]};">{safe_text(created_val)}</span></div>',
                '</div>',
            ])

    # 2. Appearance & Active Session Reset
    with col_app:
        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f"<h3 style='margin: 0 0 6px 0; font-size: 17px; font-weight: 700; color: {theme['text_primary']};'>🎨 Appearance &amp; Active Session</h3>",
            ])
            theme_opts = ["Dark", "Light", "System"]
            curr_t = st.session_state.get("theme_preference", "Dark")
            if curr_t not in theme_opts:
                curr_t = "Dark"
            new_t = st.selectbox("Interface Theme Preference", options=theme_opts, index=theme_opts.index(curr_t), key="res_set_theme_sel")
            if new_t != st.session_state.get("theme_preference"):
                st.session_state["theme_preference"] = new_t
                st.rerun()

            st.caption("Resetting the active session clears in-memory uploaded file buffers without deleting saved library records.")
            if st.button("🔄 Reset Active In-Memory Analysis", key="res_set_reset_active", use_container_width=True):
                for k in [
                    "text", "sections", "results", "active_analysis", "current_analysis_id",
                    "summary_result", "summary_doc_text", "summary_doc_name",
                    "res_preview_filename", "res_preview_raw", "res_preview_clean", "res_preview_meta",
                    "res_active_comparison", "res_active_comparison_papers",
                ]:
                    st.session_state.pop(k, None)
                st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                st.success("✓ Active in-memory session reset.")
                st.rerun()

    # =======================================================================
    # 3. Data Management (Projects, Export JSON, Clear History, Delete All Data)
    # =======================================================================
    render_html([
        '<div style="margin: 16px 0 10px 0;">',
        f'<h3 style="margin: 0; font-size: 19px; font-weight: 800; color: {theme["text_primary"]};">🗄️ Researcher Data Management</h3>',
        '</div>',
    ])

    dm_c1, dm_c2 = st.columns(2, gap="large")

    # Left: Project Deletion Controls (Delete project only vs Delete project AND its papers)
    with dm_c1:
        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f"<div style='font-size: 15px; font-weight: 700; color: {theme['text_primary']}; margin-bottom: 4px;'>🗂️ Project Deletion Controls</div>",
            ])
            st.caption("Choose whether to remove only a project folder (keeping its papers in your library) or delete both the project and its assigned manuscripts.")
            projects = auth.get_user_projects(username)
            if not projects:
                st.info("You currently have no projects to delete.")
            else:
                p_map = {f"{p['name']} ({p['paper_count']} papers)": p["id"] for p in projects}
                sel_p_lbl = st.selectbox("Select Project", options=list(p_map.keys()), key="res_set_del_proj_sel")
                sel_pid = p_map[sel_p_lbl]

                p_b1, p_b2 = st.columns(2, gap="small")
                with p_b1:
                    if st.button("🗑️ Delete Project Only", key="res_set_del_proj_only", use_container_width=True):
                        ok, msg = auth.delete_project(username, sel_pid, delete_papers=False)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with p_b2:
                    with st.popover("⚠️ Delete Project + Papers", use_container_width=True):
                        st.warning("This will permanently delete the project AND all manuscripts assigned to it.")
                        if st.button("Confirm Delete Project & Papers", key="res_set_del_proj_and_papers", type="primary", use_container_width=True):
                            ok, msg = auth.delete_project(username, sel_pid, delete_papers=True)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # Right: Export My Data (JSON) + Clear History + Delete All My Data
    with dm_c2:
        with st.container(border=True):
            render_html([
                '<span class="res-card-scope"></span>',
                f"<div style='font-size: 15px; font-weight: 700; color: {theme['text_primary']}; margin-bottom: 4px;'>📦 Portable Data Export &amp; Repository Purge</div>",
            ])
            st.caption("Download a portable JSON backup of all your manuscripts, projects, metadata, tags, notes, and evaluations, or purge your local repository.")
            export_bundle = auth.export_researcher_data_json(username)
            export_bytes = json.dumps(export_bundle, indent=2, ensure_ascii=False).encode("utf-8")
            st.download_button(
                "⬇ Export My Data (JSON — Metadata, Projects, Notes)",
                data=export_bytes,
                file_name=f"PaperIQ_Researcher_Data_{username}.json",
                mime="application/json",
                type="primary",
                use_container_width=True,
                key="res_set_export_json_btn",
            )

            c_clr1, c_clr2 = st.columns(2, gap="small")
            with c_clr1:
                with st.popover("🧹 Clear History", use_container_width=True):
                    st.caption("Delete all saved paper evaluations from your history?")
                    if st.button("Confirm Clear History", key="res_set_confirm_clear_hist", type="primary", use_container_width=True):
                        auth.clear_all_user_analyses(username)
                        st.success("All saved paper evaluations cleared.")
                        st.rerun()
            with c_clr2:
                with st.popover("🚨 Delete All Data", use_container_width=True):
                    st.error("Permanently delete ALL your papers, projects, metadata, tags, notes, comparisons, and chats?")
                    if st.button("Confirm Delete All My Data", key="res_set_confirm_del_all", type="primary", use_container_width=True):
                        auth.delete_all_researcher_data(username)
                        st.success("All researcher data for your account has been permanently deleted.")
                        st.rerun()

    # =======================================================================
    # 4. Privacy & Ownership Architecture Statement
    # =======================================================================
    render_html([
        f'<div class="iq-card" style="padding: 18px 22px !important; margin-top: 18px; border-left: 4px solid #10B981;">',
        f'<h3 style="margin: 0 0 8px 0; font-size: 17px; font-weight: 700; color: {theme["text_primary"]};">🔒 Local SQLite Storage, Session Memory &amp; Strict Single-User Ownership</h3>',
        f'<ul style="margin: 0; padding-left: 18px; font-size: 13px; color: {theme["text_secondary"]}; line-height: 1.65;">',
        '<li><b>Strict Account Isolation (No Cross-User Sharing):</b> Researchers can only access their own uploaded papers, projects, metadata, tags, comparisons, and notes. Cross-user sharing or multi-user collaboration is intentionally not enabled; every database query filters by your authenticated <code>user_id</code> and verifies ownership before any read, update, or delete operation.</li>',
        '<li><b>Local SQLite Persistence (<code>users.db</code>):</b> Saved evaluations, extracted Research Profiles, bibliographic metadata, projects, tags, and researcher notes are stored locally in the application SQLite database so your library persists across sessions.</li>',
        '<li><b>Ephemeral Session Memory:</b> Raw file bytes uploaded during a session are processed in memory and can be cleared immediately using <i>Reset Active In-Memory Analysis</i> above.</li>',
        '</ul>',
        '</div>',
    ])
