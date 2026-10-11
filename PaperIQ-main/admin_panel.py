"""
PaperIQ Administrator Control Center Module
Provides comprehensive, production-conscious administration interfaces:
1. Admin Dashboard with 100% real database metrics, activity chart, and recent activity panels
2. User Management & Role Governance with search, filters, pagination, user details, and account actions
3. Login & Audit Logs with action type, outcome, and date filtering, plus safe CSV exports
4. Institutional Saved Papers Repository with search, domain filtering, and manuscript downloads
5. Document Upload Audit History
6. Upload Research Paper to Institutional Repository
7. Analytics & Intelligence Reports with real database Plotly charts and export hub
8. System Health Diagnostics with live SQLite latency and integrity checks
9. Storage & Data Management with database compaction (VACUUM) and retention tools
"""

import streamlit as st
import html
import json
import os
import sys
import math
import re
import platform
import sqlite3
import auth
from utils import render_html, safe_text, unescape_text, truncate_title_word_boundary
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

def get_chart_layout_dict(theme):
    """Generates a theme-consistent Plotly layout dictionary."""
    return {
        "paper_bgcolor": theme.get("chart_bg", "#111827"),
        "plot_bgcolor": theme.get("chart_plot_bg", "#111827"),
        "font": {"color": theme.get("chart_font", "#E2E8F0"), "family": "Inter, sans-serif"},
        "xaxis": {
            "gridcolor": theme.get("chart_grid", "#1F2937"),
            "linecolor": theme.get("chart_line", "#374151"),
            "tickcolor": theme.get("chart_tick", "#94A3B8"),
            "tickfont": {"color": theme.get("chart_font", "#E2E8F0")},
        },
        "yaxis": {
            "gridcolor": theme.get("chart_grid", "#1F2937"),
            "linecolor": theme.get("chart_line", "#374151"),
            "tickcolor": theme.get("chart_tick", "#94A3B8"),
            "tickfont": {"color": theme.get("chart_font", "#E2E8F0")},
        },
        "legend": {
            "bgcolor": theme.get("chart_bg", "#111827"),
            "bordercolor": theme.get("chart_line", "#374151"),
            "font": {"color": theme.get("chart_font", "#E2E8F0")},
        },
        "margin": {"l": 35, "r": 20, "t": 35, "b": 35}
    }

# ===========================================================================
# 1. ADMIN DASHBOARD
# ===========================================================================
def render_admin_dashboard(theme, navigate_to):
    """Renders the Administrator Overview & Governance Dashboard."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 28px;">🛡️</span>
                <div>
                    <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Administrator Control Center</h1>
                    <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                        PaperIQ System Administration, User Governance, Audit Logging, and Institutional Repository Management.
                    </p>
                </div>
            </div>
        </div>
        """)

    # Navigation Shortcuts
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.button("👥 Users", type="primary", use_container_width=True, key="adm_btn_users", on_click=navigate_to, args=("👥 User Management",))
    with c2:
        st.button("🕒 Audit Logs", use_container_width=True, key="adm_btn_logins", on_click=navigate_to, args=("🕒 Login & Audit Logs",))
    with c3:
        st.button("📁 Repository", use_container_width=True, key="adm_btn_saved", on_click=navigate_to, args=("📁 Saved Papers",))
    with c4:
        st.button("📈 Analytics", use_container_width=True, key="adm_btn_analytics", on_click=navigate_to, args=("📈 Analytics & Reports",))
    with c5:
        st.button("🩺 Health", use_container_width=True, key="adm_btn_health", on_click=navigate_to, args=("🩺 System Health",))
    with c6:
        st.button("💾 Storage", use_container_width=True, key="adm_btn_storage", on_click=navigate_to, args=("💾 Storage & Data Management",))

    render_html("<br>")

    # Real Database Metrics (Calculated 100% from SQLite)
    stats = auth.get_system_stats()

    # Metric Row 1: Users & Curated Repository
    m_r1_1, m_r1_2, m_r1_3, m_r1_4 = st.columns(4)
    m_r1_1.metric("Registered Users", stats["total_users"])
    m_r1_2.metric("Student Accounts", stats["student_count"])
    m_r1_3.metric("Researcher Accounts", stats["researcher_count"])
    m_r1_4.metric("Repository Papers", stats["saved_papers_count"])

    st.write("")
    # Metric Row 2: Analyses, Audit Logs & Database Storage
    m_r2_1, m_r2_2, m_r2_3 = st.columns(3)
    m_r2_1.metric("Analysis Records", stats["analysis_count"])
    m_r2_2.metric("Audit Log Entries", stats["audit_count"])
    m_r2_3.metric("Storage", stats["db_size_formatted"])

    render_html("<br>")

    # Database Activity Trend Chart (Real Data, Continuous Timeline)
    all_users = auth.get_all_users()
    login_events = auth.get_login_history(limit=500)

    # Group events by date for trend visualization
    date_counts = {}
    for ev in login_events:
        d = ev.get("login_time", "")[:10]
        if d:
            date_counts[d] = date_counts.get(d, 0) + 1

    today = datetime.now().date()
    # Continuous 7-day rolling window
    date_window = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    display_labels = [(today - timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    counts_7d = [date_counts.get(d, 0) for d in date_window]

    # Hourly counts for today
    today_str = today.strftime("%Y-%m-%d")
    today_events = [ev for ev in login_events if ev.get("login_time", "").startswith(today_str)]
    hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
    for ev in today_events:
        t_part = ev.get("login_time", "")
        if len(t_part) >= 13:
            h_str = t_part[11:13] + ":00"
            hour_counts[h_str] = hour_counts.get(h_str, 0) + 1

    col_chart_hdr, col_chart_mode = st.columns([4, 2])
    with col_chart_hdr:
        render_html(f"""
            <div style="font-weight: 700; color: {theme['text_primary']}; font-size: 15px; margin-bottom: 4px;">
                📊 Live System Activity & Authentication Trend (Real Database Records)
            </div>
            """)
    with col_chart_mode:
        t_mode = st.radio("Chart View", ["7-Day Daily Trend", "Today's Hourly Activity"], horizontal=True, label_visibility="collapsed", key="adm_chart_mode_toggle")

    fig_trend = go.Figure()
    layout_dict = get_chart_layout_dict(theme)
    layout_dict["height"] = 250
    layout_dict["margin"] = dict(l=40, r=20, t=10, b=40)

    if "Hourly" in t_mode:
        h_x = list(hour_counts.keys())
        h_y = list(hour_counts.values())
        fig_trend.add_trace(go.Bar(
            x=h_x,
            y=h_y,
            marker_color=theme.get("accent_primary", "#7C3AED"),
            hovertemplate="<b>Hour:</b> %{x}<br><b>Recorded Events:</b> %{y}<extra></extra>",
            name="Hourly Events"
        ))
        layout_dict["xaxis"]["title"] = "Hour of Day (Local)"
        layout_dict["yaxis"]["title"] = "Recorded Events"
    else:
        fig_trend.add_trace(go.Bar(
            x=display_labels,
            y=counts_7d,
            marker_color=theme.get("accent_primary", "#7C3AED"),
            hovertemplate="<b>Date:</b> %{x}<br><b>Recorded Events:</b> %{y}<extra></extra>",
            name="Daily Events"
        ))
        layout_dict["xaxis"]["title"] = "Date (Past 7 Days)"
        layout_dict["yaxis"]["title"] = "Recorded Events"

    fig_trend.update_layout(**layout_dict)
    st.plotly_chart(fig_trend, use_container_width=True)

    render_html("<br>")

    # Side-by-Side Activity Overview
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            head_col1, head_col2 = st.columns([3, 1.5])
            with head_col1:
                render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0;'>👥 Recent User Registrations</h4>")
            with head_col2:
                if st.button("View All Users →", key="adm_link_view_all_users", use_container_width=True):
                    navigate_to("👥 User Management")
                    st.rerun()

            st.write("")
            if all_users:
                recent_users = all_users[:5]
                for u in recent_users:
                    r_badge_color = theme['info_text'] if u['role'] == 'Student' else (theme['accent_purple'] if u['role'] == 'Researcher' else theme['warning_text'])
                    r_badge_bg = theme['info_bg'] if u['role'] == 'Student' else (theme['accent_primary_subtle'] if u['role'] == 'Researcher' else theme['warning_bg'])
                    is_active = u.get("status", "Active") != "Disabled"
                    stat_color = theme['success_text'] if is_active else theme['error_text']
                    stat_bg = theme['success_bg'] if is_active else theme['error_bg']
                    created_date = u.get("created_at", "")[:16]

                    render_html(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid {theme['border_color']};">
                            <div>
                                <b style="color: {theme['text_primary']}; font-size: 13.5px;">{safe_text(u['username'])}</b>
                                <div style="font-size: 11.5px; color: {theme['text_muted']};">Joined: {created_date} &nbsp;•&nbsp; Analyses: {u.get('analysis_count', 0)}</div>
                            </div>
                            <div style="display: flex; gap: 6px; align-items: center;">
                                <span style="font-size: 10.5px; font-weight: 700; color: {stat_color}; background: {stat_bg}; padding: 2px 7px; border-radius: 6px;">
                                    {safe_text(u.get('status', 'Active'))}
                                </span>
                                <span style="font-size: 10.5px; font-weight: 700; color: {r_badge_color}; background: {r_badge_bg}; padding: 2px 7px; border-radius: 6px;">
                                    {safe_text(u['role'])}
                                </span>
                            </div>
                        </div>
                        """)
            else:
                st.caption("No registered users recorded.")

    with col_right:
        with st.container(border=True):
            ahead_col1, ahead_col2 = st.columns([3, 1.5])
            with ahead_col1:
                render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0;'>🕒 Recent Audit & Security Events</h4>")
            with ahead_col2:
                if st.button("View Audit Logs →", key="adm_link_view_all_audits", use_container_width=True):
                    navigate_to("🕒 Login & Audit Logs")
                    st.rerun()

            st.write("")
            if login_events:
                for ev in login_events[:5]:
                    is_success = "Success" in ev.get('status', '') or "Registered" in ev.get('status', '') or "Provisioned" in ev.get('status', '')
                    s_color = theme['success_text'] if is_success else theme['error_text']
                    s_bg = theme['success_bg'] if is_success else theme['error_bg']
                    action_tag = ev.get('action_type', 'AUTH')

                    render_html(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid {theme['border_color']};">
                            <div>
                                <b style="color: {theme['text_primary']}; font-size: 13.5px;">{safe_text(ev.get('username', 'Unknown'))}</b>
                                <div style="font-size: 11.5px; color: {theme['text_muted']};">
                                    <span style="font-family: monospace;">{ev.get('login_time', '')}</span> &nbsp;•&nbsp; 
                                    <span style="color: {theme['accent_purple']}; font-weight: 600;">{safe_text(action_tag)}</span>
                                </div>
                            </div>
                            <span style="font-size: 10.5px; font-weight: 700; color: {s_color}; background: {s_bg}; padding: 2px 7px; border-radius: 6px;">
                                {safe_text(ev.get('status', ''))}
                            </span>
                        </div>
                        """)
            else:
                st.caption("No authentication audit logs found.")

# ===========================================================================
# 2. USER MANAGEMENT & ROLE GOVERNANCE
# ===========================================================================
def render_all_users_view(theme, current_admin_user):
    """Renders the comprehensive User Management page."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">All Users — System User Governance & Role Management</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Inspect registered user accounts, manage permission roles, toggle account status, and perform authorized administrative account actions.
            </p>
        </div>
        """)

    all_users = auth.get_all_users()
    students = [u for u in all_users if u["role"] == "Student"]
    researchers = [u for u in all_users if u["role"] == "Researcher"]
    admins = [u for u in all_users if u["role"] == "Administrator"]
    legacies = [u for u in all_users if u["role"] not in ["Student", "Researcher", "Administrator"]]
    actives = [u for u in all_users if u.get("status") != "Disabled"]
    disabled = [u for u in all_users if u.get("status") == "Disabled"]

    # Filter & Search Bar
    f_c1, f_c2, f_c3 = st.columns([3, 1.5, 1.5])
    with f_c1:
        search_query = st.text_input("🔍 Search user accounts by username, role, or status", "", key="adm_user_search")
    with f_c2:
        page_size_choice = st.selectbox("Page Size", [15, 30, 50, "All"], index=0, key="adm_users_page_size")
    with f_c3:
        st.write("")
        st.write("")
        st.download_button(
            "📥 Export Users CSV",
            data=auth.export_users_csv(),
            file_name=f"PaperIQ_Users_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_users"
        )

    # User Category Tabs
    tab_all, tab_stu, tab_res, tab_adm, tab_leg, tab_act, tab_dis = st.tabs([
        f"All Users ({len(all_users)})",
        f"Students ({len(students)})",
        f"Researchers ({len(researchers)})",
        f"Administrators ({len(admins)})",
        f"Legacy Accounts ({len(legacies)})",
        f"Active ({len(actives)})",
        f"Disabled ({len(disabled)})"
    ])

    def display_users_table(user_list, key_prefix):
        filtered = [
            u for u in user_list
            if not search_query or (
                search_query.lower() in u["username"].lower() or
                search_query.lower() in u["role"].lower() or
                search_query.lower() in u.get("status", "").lower()
            )
        ]
        if not filtered:
            st.info("No user accounts match the current filter.")
            return

        # Pagination calculation
        total_items = len(filtered)
        if page_size_choice != "All":
            limit_n = int(page_size_choice)
            total_pages = max(1, math.ceil(total_items / limit_n))
            page_key = f"adm_user_page_{key_prefix}"
            if page_key not in st.session_state:
                st.session_state[page_key] = 1
            if st.session_state[page_key] > total_pages:
                st.session_state[page_key] = total_pages
            if st.session_state[page_key] < 1:
                st.session_state[page_key] = 1

            curr_p = st.session_state[page_key]
            start_idx = (curr_p - 1) * limit_n
            end_idx = min(start_idx + limit_n, total_items)
            display_slice = filtered[start_idx:end_idx]
            st.caption(f"Showing accounts {start_idx + 1}–{end_idx} of {total_items} (Page {curr_p} of {total_pages})")
        else:
            display_slice = filtered
            total_pages = 1
            curr_p = 1
            start_idx = 0
            st.caption(f"Showing all {total_items} matching accounts.")

        # Render Table Header
        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.4fr 2fr 1.4fr 1.2fr 1.6fr 1fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 12.5px; color: {theme['text_muted']}; text-transform: uppercase;">
                <div>#</div>
                <div>Username</div>
                <div>Academic Role</div>
                <div>Status</div>
                <div>Registered Date</div>
                <div>Analyses</div>
            </div>
            """)

        for i, u in enumerate(display_slice):
            r_color = theme['info_text'] if u['role'] == 'Student' else (theme['accent_purple'] if u['role'] == 'Researcher' else (theme['error_text'] if u['role'] == 'Administrator' else theme['warning_text']))
            r_bg = theme['info_bg'] if u['role'] == 'Student' else (theme['accent_primary_subtle'] if u['role'] == 'Researcher' else (theme['error_bg'] if u['role'] == 'Administrator' else theme['warning_bg']))
            is_active = u.get("status", "Active") != "Disabled"
            s_color = theme['success_text'] if is_active else theme['error_text']
            s_bg = theme['success_bg'] if is_active else theme['error_bg']
            created_str = u.get("created_at", "")[:16]

            render_html(f"""
                <div style="display: grid; grid-template-columns: 0.4fr 2fr 1.4fr 1.2fr 1.6fr 1fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 13.5px; align-items: center;">
                    <div style="color: {theme['text_muted']};">{start_idx + i + 1}</div>
                    <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(u['username'])}</div>
                    <div><span style="font-size: 11px; font-weight: 700; color: {r_color}; background: {r_bg}; padding: 2px 8px; border-radius: 6px;">{safe_text(u['role'])}</span></div>
                    <div><span style="font-size: 11px; font-weight: 700; color: {s_color}; background: {s_bg}; padding: 2px 8px; border-radius: 6px;">{safe_text(u.get('status', 'Active'))}</span></div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; font-family: monospace;">{created_str}</div>
                    <div style="color: {theme['text_primary']}; font-weight: 600;">{u.get('analysis_count', 0)}</div>
                </div>
                """)

        if page_size_choice != "All" and total_pages > 1:
            p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
            with p_col1:
                if st.button("← Previous", key=f"btn_prev_{key_prefix}", disabled=(curr_p <= 1), use_container_width=True):
                    st.session_state[page_key] -= 1
                    st.rerun()
            with p_col2:
                render_html(f"<div style='text-align: center; padding-top: 8px; font-size: 13px; color: {theme['text_muted']};'>Page <b>{curr_p}</b> of <b>{total_pages}</b></div>")
            with p_col3:
                if st.button("Next →", key=f"btn_next_{key_prefix}", disabled=(curr_p >= total_pages), use_container_width=True):
                    st.session_state[page_key] += 1
                    st.rerun()

    with tab_all:
        display_users_table(all_users, "all")
    with tab_stu:
        display_users_table(students, "stu")
    with tab_res:
        display_users_table(researchers, "res")
    with tab_adm:
        display_users_table(admins, "adm")
    with tab_leg:
        display_users_table(legacies, "leg")
    with tab_act:
        display_users_table(actives, "act")
    with tab_dis:
        display_users_table(disabled, "dis")

    render_html("<br>")

    # Authorized Account Management Actions Panel
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>⚙️ Authorized Account Actions & Security Controls</h3>")
        user_names = [u["username"] for u in all_users]
        if not user_names:
            st.caption("No users to manage.")
            return

        sel_target_user = st.selectbox("Select Account to Inspect & Manage", user_names, key="adm_sel_manage_user")
        target_info = next((u for u in all_users if u["username"] == sel_target_user), None)

        if target_info:
            c_det1, c_det2, c_det3, c_det4 = st.columns(4)
            c_det1.metric("Username", target_info["username"])
            c_det2.metric("Role", target_info["role"])
            c_det3.metric("Status", target_info.get("status", "Active"))
            c_det4.metric("Analyses Stored", target_info.get("analysis_count", 0))

            act_col1, act_col2, act_col3, act_col4 = st.tabs(["Assign Role", "Toggle Status", "Reset Password", "Delete Account"])

            with act_col1:
                st.write("")
                role_opts = ["Student", "Researcher", "Administrator"]
                curr_idx = 0 if target_info["role"] == "Student" else (1 if target_info["role"] == "Researcher" else (2 if target_info["role"] == "Administrator" else 0))
                new_role_choice = st.selectbox("Assign New Academic Role", role_opts, index=curr_idx, key="adm_new_role_select")
                conf_role = st.checkbox(f"Confirm changing role of '{sel_target_user}' to '{new_role_choice}'", key="adm_chk_role")
                if st.button("Update Role", type="primary", key="adm_btn_apply_role"):
                    if conf_role:
                        success, msg = auth.update_user_role(sel_target_user, new_role_choice, current_admin_user=current_admin_user)
                        if success:
                            st.success(f"✓ {msg}")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please check the confirmation box before updating role.")

            with act_col2:
                st.write("")
                current_st = target_info.get("status", "Active")
                target_new_st = "Disabled" if current_st == "Active" else "Active"
                action_verb = "Deactivate / Disable" if current_st == "Active" else "Reactivate / Enable"
                st.info(f"Current account status is **{current_st}**. You can {action_verb} this account.")

                if sel_target_user == current_admin_user and target_new_st == "Disabled":
                    st.error("⚠️ Self-Lockout Safeguard: You cannot deactivate your own currently active Administrator account.")
                else:
                    conf_status = st.checkbox(f"Confirm changing account status of '{sel_target_user}' to '{target_new_st}'", key="adm_chk_status")
                    if st.button(f"{action_verb} Account", type="primary", key="adm_btn_apply_status"):
                        if conf_status:
                            success, msg = auth.toggle_user_status(sel_target_user, target_new_st, current_admin_user=current_admin_user)
                            if success:
                                st.success(f"✓ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Please check the confirmation box before toggling account status.")

            with act_col3:
                st.write("")
                new_temp_pass = st.text_input("New Temporary Password (min 4 chars)", type="password", key="adm_new_pass_input")
                conf_pass = st.checkbox(f"Confirm resetting password for '{sel_target_user}'", key="adm_chk_pass")
                if st.button("Reset Password", type="primary", key="adm_btn_apply_pass"):
                    if conf_pass:
                        if len(new_temp_pass) >= 4:
                            success, msg = auth.admin_reset_password(sel_target_user, new_temp_pass, current_admin_user=current_admin_user)
                            if success:
                                st.success(f"✓ {msg}")
                            else:
                                st.error(msg)
                        else:
                            st.warning("Password must be at least 4 characters.")
                    else:
                        st.warning("Please check the confirmation box before resetting password.")

            with act_col4:
                st.write("")
                if sel_target_user == current_admin_user:
                    st.error("⚠️ Self-Lockout Safeguard: You cannot delete your own currently active Administrator account.")
                else:
                    st.warning(f"⚠️ Warning: Deleting user '{sel_target_user}' will permanently remove their credentials and all associated analysis records.")
                    conf_del = st.checkbox(f"I confirm permanent deletion of account '{sel_target_user}' and all its stored data", key="adm_chk_del")
                    if st.button("Delete User Permanently", type="primary", key="adm_btn_apply_del"):
                        if conf_del:
                            success, msg = auth.delete_user_account(sel_target_user, current_admin_user=current_admin_user)
                            if success:
                                st.success(f"✓ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Please check the confirmation box before deleting an account.")

# ===========================================================================
# 3. LOGIN & AUDIT LOGS
# ===========================================================================
def render_login_history_view(theme, current_admin_user="admin"):
    """Renders the comprehensive Login History & Audit Logs page."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Login History & Security Audit Logs</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Comprehensive security audit trail tracking authentication, role updates, account lifecycle events, and repository modifications. Sensitive credentials and passwords are never logged.
            </p>
        </div>
        """)

    history = auth.get_login_history(limit=500)

    f_col1, f_col2, f_col3, f_col4 = st.columns([2.5, 1.8, 1.8, 1.5])
    with f_col1:
        search_user = st.text_input("🔍 Filter by username or keyword", "", key="adm_log_search_user")
    with f_col2:
        action_types = ["All Action Types"] + sorted(list(set(h.get("action_type", "AUTH") for h in history if h.get("action_type"))))
        sel_action = st.selectbox("Action Type", action_types, key="adm_log_action_filter")
    with f_col3:
        status_opts = ["All Statuses"] + sorted(list(set(h.get("status", "") for h in history if h.get("status"))))
        sel_status = st.selectbox("Status / Outcome", status_opts, key="adm_log_status_filter")
    with f_col4:
        st.write("")
        st.write("")
        st.download_button(
            "📥 Export Audit CSV",
            data=auth.export_audit_csv(limit=1000),
            file_name=f"PaperIQ_Audit_Logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_audit"
        )

    # Filtered logs
    filtered_logs = [
        h for h in history
        if (not search_user or (
            search_user.lower() in h.get("username", "").lower() or
            search_user.lower() in h.get("details", "").lower() or
            search_user.lower() in h.get("target", "").lower()
        ))
        and (sel_action == "All Action Types" or h.get("action_type") == sel_action)
        and (sel_status == "All Statuses" or h.get("status") == sel_status)
    ]

    count_col, clear_col = st.columns([4, 2])
    with count_col:
        render_html(f"<p style='color: {theme['text_muted']}; font-size: 13px; margin: 8px 0;'>Showing <b>{len(filtered_logs)}</b> of <b>{len(history)}</b> audit events</p>")
    with clear_col:
        with st.expander("🛡️ Audit Log Maintenance"):
            st.caption("Audit logs are sensitive records. Purging will clear existing records and log a self-contained purge event.")
            conf_clear = st.checkbox("Confirm authorized audit purge", key="adm_chk_clear_log")
            if st.button("Clear Audit History", type="primary", use_container_width=True, key="adm_btn_clear_log"):
                if conf_clear:
                    auth.clear_login_history(current_admin_user=current_admin_user)
                    st.success("✓ Login audit history cleared.")
                    st.rerun()
                else:
                    st.warning("Please check the confirmation box.")

    if not filtered_logs:
        st.info("No login audit events recorded or matched by current filters.")
        return

    # Table Header
    render_html(f"""
        <div style="display: grid; grid-template-columns: 0.4fr 1.6fr 1.4fr 1.2fr 1.4fr 1.6fr 1.8fr 1fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 11.5px; color: {theme['text_muted']}; text-transform: uppercase;">
            <div>#</div>
            <div>Timestamp</div>
            <div>Actor</div>
            <div>Action</div>
            <div>Outcome</div>
            <div>Target</div>
            <div>Details</div>
            <div>IP Address</div>
        </div>
        """)

    for idx, log in enumerate(filtered_logs[:100]):
        is_success = "Success" in log.get("status", "") or "Registered" in log.get("status", "") or "Provisioned" in log.get("status", "")
        stat_color = theme['success_text'] if is_success else theme['error_text']
        stat_bg = theme['success_bg'] if is_success else theme['error_bg']
        act_tag = log.get("action_type", "AUTH")

        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.4fr 1.6fr 1.4fr 1.2fr 1.4fr 1.6fr 1.8fr 1fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12.5px; align-items: center;">
                <div style="color: {theme['text_muted']};">{idx+1}</div>
                <div style="color: {theme['text_secondary']}; font-family: monospace; font-size: 11.5px;">{log.get('login_time', '')}</div>
                <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(log.get('username', ''))}</div>
                <div><span style="font-size: 10.5px; font-weight: 700; color: {theme['accent_purple']}; background: {theme['accent_primary_subtle']}; padding: 2px 6px; border-radius: 4px;">{safe_text(act_tag)}</span></div>
                <div><span style="font-size: 10.5px; font-weight: 700; color: {stat_color}; background: {stat_bg}; padding: 2px 6px; border-radius: 4px;">{safe_text(log.get('status', ''))}</span></div>
                <div style="color: {theme['text_secondary']}; font-size: 11.5px;">{safe_text(str(log.get('target', ''))[:22])}</div>
                <div style="color: {theme['text_muted']}; font-size: 11.5px;">{safe_text(str(log.get('details', ''))[:30])}</div>
                <div style="color: {theme['text_muted']}; font-size: 11px; font-family: monospace;">{safe_text(log.get('ip_address', '127.0.0.1'))}</div>
            </div>
            """)

# ===========================================================================
# 4. INSTITUTIONAL SAVED PAPERS REPOSITORY
# ===========================================================================
def render_saved_papers_view(theme, navigate_to, load_analysis_into_session, current_admin_user="admin"):
    """Renders the Institutional Saved Papers Library."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Institutional Saved Papers Library</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Centrally stored academic research papers and reference manuscripts curated for institutional analysis.
            </p>
        </div>
        """)

    papers = auth.get_saved_papers()

    c_s1, c_s2, c_s3, c_s4 = st.columns([3, 1.8, 1.5, 1.8])
    with c_s1:
        q = st.text_input("🔍 Search repository by title, author, or domain", "", key="adm_saved_search")
    with c_s2:
        domains_list = ["All Disciplines"] + sorted(list(set(p.get("domain", "") for p in papers if p.get("domain"))))
        sel_dom = st.selectbox("Filter Discipline", domains_list, key="adm_saved_domain_filter")
    with c_s3:
        st.write("")
        st.write("")
        st.download_button(
            "📥 Export CSV",
            data=auth.export_repository_csv(),
            file_name=f"PaperIQ_Repository_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_repo"
        )
    with c_s4:
        st.write("")
        st.write("")
        if st.button("+ Upload Paper", type="primary", use_container_width=True, key="adm_btn_goto_upload_paper"):
            navigate_to("📤 Upload Research Paper")
            st.rerun()

    filtered = [
        p for p in papers
        if (not q or q.lower() in f"{p.get('title','')} {p.get('authors','')} {p.get('domain','')}".lower())
        and (sel_dom == "All Disciplines" or p.get("domain") == sel_dom)
    ]

    render_html(f"<p style='color: {theme['text_muted']}; font-size: 13px; margin: 6px 0 14px 0;'>Showing <b>{len(filtered)}</b> of <b>{len(papers)}</b> repository papers</p>")

    if not filtered:
        render_html(f"""
            <div class="iq-card" style="text-align: center; padding: 40px !important;">
                <div style="font-size: 32px; margin-bottom: 8px;">📁</div>
                <h4 style="color: {theme['text_primary']}; margin: 0;">No Saved Papers in Repository</h4>
                <p style="color: {theme['text_muted']}; margin-top: 4px;">Upload benchmark papers in <b>Upload Research Paper</b> to populate the institutional library.</p>
            </div>
            """)
        return

    for idx, p in enumerate(filtered):
        with st.container(border=True):
            col_info, col_score, col_act1, col_act2, col_del = st.columns([4, 1.8, 1.5, 1.5, 1.2])
            with col_info:
                render_html(f"""
                    <div style="font-weight: 700; color: {theme['text_primary']}; font-size: 15px;">📄 {safe_text(p.get('title', 'Research Paper'))}</div>
                    <div style="color: {theme['text_muted']}; font-size: 12px; margin-top: 3px;">
                        Authors: <b style="color: {theme['text_secondary']};">{safe_text(p.get('authors', 'Institutional Authors'))}</b> &nbsp;•&nbsp; 
                        Domain: <b style="color: {theme['info_text']};">{safe_text(p.get('domain', 'General Academic'))}</b> &nbsp;•&nbsp; 
                        Uploaded: {p.get('uploaded_at', '')} by <i>{safe_text(p.get('uploaded_by', 'admin'))}</i>
                    </div>
                    """)
            with col_score:
                render_html(f"""
                    <div style="font-size: 14.5px; font-weight: 800; color: {theme['accent_purple']}; margin-top: 6px;">
                        Score: {p.get('score', 0.0):.1f} / 100 &nbsp;
                        <span style="background: {theme['badge_role_bg']}; color: {theme['badge_role_text']}; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 8px; border: 1px solid {theme['badge_role_border']};">Grade {p.get('grade', 'C')}</span>
                    </div>
                    """)
            with col_act1:
                if st.button("View Analysis", key=f"adm_saved_view_{p.get('id', idx)}", use_container_width=True):
                    item_dict = {
                        "id": p.get("id"),
                        "analysis_id": p.get("paper_id"),
                        "filename": p.get("filename", "Paper.pdf"),
                        "display_title": p.get("title"),
                        "domain": p.get("domain"),
                        "score": p.get("score"),
                        "grade": p.get("grade"),
                        "pdf": bytes(p["pdf_report_bytes"]) if p.get("pdf_report_bytes") else b"",
                        "results_json": p.get("results_json")
                    }
                    load_analysis_into_session(item_dict)
                    navigate_to("📊 Analysis")
                    st.rerun()
            with col_act2:
                if p.get("pdf_report_bytes"):
                    fn_base = p.get("filename") or p.get("title") or "Paper"
                    for ext in [".pdf", ".docx", ".txt", ".doc"]:
                        if fn_base.lower().endswith(ext):
                            fn_base = fn_base[:-len(ext)]
                    clean_down_fn = f"PaperIQ_Report_{fn_base}.pdf"
                    st.download_button(
                        "Download Report",
                        data=bytes(p["pdf_report_bytes"]),
                        file_name=clean_down_fn,
                        mime="application/pdf",
                        key=f"adm_saved_down_{p.get('id', idx)}",
                        use_container_width=True
                    )
                elif p.get("file_bytes"):
                    st.download_button(
                        "Download Paper",
                        data=bytes(p["file_bytes"]),
                        file_name=p.get("filename", "Paper.pdf"),
                        mime="application/octet-stream",
                        key=f"adm_saved_down_orig_{p.get('id', idx)}",
                        use_container_width=True
                    )
            with col_del:
                if st.button("Delete", key=f"adm_saved_del_{p.get('id', idx)}", use_container_width=True):
                    st.session_state[f"confirm_del_saved_{p.get('paper_id')}"] = True
                    st.rerun()

            if st.session_state.get(f"confirm_del_saved_{p.get('paper_id')}", False):
                st.warning(f"Delete paper '{p.get('title')}' from institutional repository?")
                c_c1, c_c2 = st.columns([1, 1])
                with c_c1:
                    if st.button("Confirm Delete", type="primary", key=f"btn_conf_del_saved_{p.get('paper_id')}"):
                        auth.delete_saved_paper(p.get("paper_id"), current_admin_user=current_admin_user)
                        st.session_state[f"confirm_del_saved_{p.get('paper_id')}"] = False
                        st.success("✓ Paper deleted from repository.")
                        st.rerun()
                with c_c2:
                    if st.button("Cancel", key=f"btn_canc_del_saved_{p.get('paper_id')}"):
                        st.session_state[f"confirm_del_saved_{p.get('paper_id')}"] = False
                        st.rerun()

# ===========================================================================
# 5. UPLOAD HISTORY VIEW
# ===========================================================================
def render_upload_history_view(theme):
    """Renders the Document Upload Audit History page."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Document Upload Audit History</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Comprehensive audit trail of uploaded manuscripts, processed files, and repository additions.
            </p>
        </div>
        """)

    uploads = auth.get_upload_history(limit=250)

    c_u1, c_u2 = st.columns([3, 2])
    with c_u1:
        search_f = st.text_input("🔍 Search upload history by filename or username", "", key="adm_upl_search")
    with c_u2:
        target_opts = ["All Destinations", "Personal", "Repository"]
        sel_target = st.selectbox("Filter by Destination", target_opts, key="adm_upl_target_filter")

    filtered = [
        u for u in uploads
        if (not search_f or search_f.lower() in f"{u.get('filename','')} {u.get('username','')}".lower())
        and (sel_target == "All Destinations" or u.get("target") == sel_target)
    ]

    render_html(f"<p style='color: {theme['text_muted']}; font-size: 13px; margin: 6px 0 14px 0;'>Showing <b>{len(filtered)}</b> of <b>{len(uploads)}</b> upload records</p>")

    if not filtered:
        st.info("No document upload history records found.")
        return

    # Table Header
    render_html(f"""
        <div style="display: grid; grid-template-columns: 0.5fr 2fr 1.5fr 2.5fr 1fr 1fr 1fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 12px; color: {theme['text_muted']}; text-transform: uppercase;">
            <div>#</div>
            <div>Timestamp</div>
            <div>Uploader</div>
            <div>Filename</div>
            <div>Format</div>
            <div>Size (KB)</div>
            <div>Target</div>
        </div>
        """)

    for idx, u in enumerate(filtered):
        t_color = theme['accent_purple'] if u.get('target') == 'Repository' else theme['info_text']
        t_bg = theme['accent_primary_subtle'] if u.get('target') == 'Repository' else theme['info_bg']
        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.5fr 2fr 1.5fr 2.5fr 1fr 1fr 1fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 13px; align-items: center;">
                <div style="color: {theme['text_muted']};">{idx+1}</div>
                <div style="color: {theme['text_secondary']}; font-family: monospace;">{u.get('upload_time', '')}</div>
                <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(u.get('username', ''))}</div>
                <div style="color: {theme['text_primary']}; font-weight: 600;">📄 {safe_text(u.get('filename', ''))}</div>
                <div style="color: {theme['text_muted']}; font-weight: 600;">{u.get('file_type', '').upper()}</div>
                <div style="color: {theme['text_secondary']};">{u.get('file_size_kb', 0.0):.1f} KB</div>
                <div><span style="font-size: 11px; font-weight: 700; color: {t_color}; background: {t_bg}; padding: 2px 7px; border-radius: 6px;">{safe_text(u.get('target', 'Personal'))}</span></div>
            </div>
            """)

# ===========================================================================
# 6. UPLOAD RESEARCH PAPER TO INSTITUTIONAL REPOSITORY
# ===========================================================================
def render_upload_research_paper_view(theme, navigate_to, current_admin_user, extract_text_fn, evaluate_fn, summarize_fn, report_fn):
    """Renders the Administrator paper upload interface for the institutional repository."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Upload Paper to Institutional Repository</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Add benchmark research papers and reference manuscripts to the shared institutional library.
            </p>
        </div>
        """)

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>Manuscript Details</h3>")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            paper_title = st.text_input("Manuscript Display Title", placeholder="e.g. Deep Residual Learning for Image Recognition", key="adm_up_title")
            paper_authors = st.text_input("Authors / Institutional Affiliation", placeholder="e.g. K. He, X. Zhang, S. Ren, J. Sun", key="adm_up_authors")
        with col_m2:
            domain_options = [
                "Computer Science & Artificial Intelligence",
                "Biomedical & Health Sciences",
                "Physical Sciences & Mathematics",
                "Engineering & Robotics",
                "Social Sciences & Psychology",
                "Economics & Business",
                "Environmental & Earth Sciences",
                "Humanities & Literature",
                "Law & Public Policy",
                "Education & Pedagogy",
                "Chemistry & Materials",
                "Interdisciplinary"
            ]
            paper_domain = st.selectbox("Academic Discipline / Domain", domain_options, key="adm_up_domain")
            is_public_flag = st.checkbox("Make Available in Institutional Shared Library", value=True, key="adm_up_public")

        render_html("<hr style='margin: 14px 0;'>")
        upload_mode = st.radio("Ingestion Mode", ["📁 File Upload (PDF, DOCX, TXT)", "📝 Paste Manuscript Text"], horizontal=True, key="adm_up_mode")

        extracted_text = ""
        orig_filename = ""
        file_bytes_data = b""
        file_size_kb = 0.0
        file_ext = "TXT"

        if "File Upload" in upload_mode:
            uploaded_file = st.file_uploader("Select Academic Document", type=["pdf", "docx", "txt"], key="adm_file_uploader")
            if uploaded_file is not None:
                orig_filename = uploaded_file.name
                file_bytes_data = uploaded_file.getvalue()
                file_size_kb = len(file_bytes_data) / 1024.0
                file_ext = orig_filename.split(".")[-1].upper() if "." in orig_filename else "TXT"

                if len(file_bytes_data) > 30 * 1024 * 1024:
                    st.error("Error: Document exceeds maximum allowable size (30MB).")
                else:
                    raw_extracted = extract_text_fn(uploaded_file)
                    if isinstance(raw_extracted, str) and raw_extracted.startswith("__ERROR_"):
                        if raw_extracted == "__ERROR_SCANNED_PDF__":
                            st.error("⚠️ Scanned Image Document Detected: This PDF appears to be a scanned image without an embedded selectable text layer. Please upload an academic document containing digital text.")
                        elif raw_extracted == "__ERROR_PASSWORD_PROTECTED__":
                            st.error("🔒 Password Protected: The uploaded PDF is encrypted. Please provide an unencrypted version.")
                        elif raw_extracted == "__ERROR_FILE_TOO_LARGE__":
                            st.error("⚠️ Document Exceeds Size Limit: The file is larger than the maximum allowable size.")
                        elif raw_extracted == "__ERROR_CORRUPTED_PDF__":
                            st.error("⚠️ Corrupted PDF: The uploaded PDF file is damaged or corrupted and could not be parsed.")
                        elif raw_extracted == "__ERROR_CORRUPTED_DOCX__":
                            st.error("⚠️ Corrupted DOCX: The uploaded Word document could not be read.")
                        elif raw_extracted == "__ERROR_EMPTY_DOCUMENT__":
                            st.error("⚠️ Empty Document: The uploaded file contains no extractable text.")
                        else:
                            st.error(f"⚠️ Document Extraction Error: {raw_extracted}")
                        extracted_text = ""
                    else:
                        extracted_text = raw_extracted
                        word_count = len(extracted_text.split())
                        if word_count < 30:
                            st.warning(f"⚠️ Document text is very short ({word_count} words). Academic analysis requires at least 30 words.")
                        else:
                            st.success(f"✓ Document loaded successfully: '{orig_filename}' ({file_size_kb:.1f} KB, ~{word_count:,} words)")
        else:
            pasted_text = st.text_area("Manuscript Text Content", height=240, placeholder="Paste the complete text or abstract of the manuscript here...", key="adm_pasted_text")
            if pasted_text:
                extracted_text = pasted_text.strip()
                orig_filename = (paper_title.strip() or "Pasted_Manuscript") + ".txt"
                file_bytes_data = extracted_text.encode("utf-8")
                file_size_kb = len(file_bytes_data) / 1024.0
                file_ext = "TXT"

        st.write("")
        if st.button("Process & Save to Institutional Repository", type="primary", use_container_width=True, key="adm_btn_process_paper"):
            if not extracted_text:
                st.warning("Please upload or paste a research document with valid extractable text.")
            elif len(extracted_text.split()) < 30:
                st.warning(f"Please provide a research manuscript containing at least 30 words (currently {len(extracted_text.split())} words).")
            else:
                with st.spinner("Analyzing manuscript and compiling institutional report..."):
                    try:
                        # 1. Run Academic Evaluation
                        eval_res = evaluate_fn(extracted_text, filename=orig_filename, domain_override=paper_domain)
                        eval_res["title"] = paper_title.strip() if paper_title else orig_filename
                        comp_score = eval_res.get("overall_score", 70.0)
                        comp_grade = eval_res.get("grade", "B")

                        # 2. Run Executive Summary
                        sum_res = summarize_fn(extracted_text, summary_type="Medium", filename=orig_filename, doc_title=paper_title or orig_filename)

                        # 3. Generate PDF Report
                        pdf_report = report_fn(eval_res, sum_res, original_filename=orig_filename, title=paper_title or orig_filename)

                        # 4. Save to Repository
                        paper_id = auth.save_repository_paper(
                            title=paper_title or orig_filename,
                            authors=paper_authors or "Institutional Authors",
                            domain=paper_domain,
                            uploaded_by=current_admin_user,
                            filename=orig_filename,
                            file_bytes=file_bytes_data,
                            pdf_report_bytes=pdf_report,
                            score=comp_score,
                            grade=comp_grade,
                            results_json=json.dumps(eval_res),
                            is_public=1 if is_public_flag else 0
                        )

                        # 5. Log Upload
                        auth.record_upload(
                            username=current_admin_user,
                            filename=orig_filename,
                            file_type=file_ext,
                            file_size_kb=file_size_kb,
                            status="Repository Ingested",
                            target="Repository"
                        )

                        st.success(f"✓ Manuscript successfully analyzed and added to the Institutional Repository! (Paper ID: {paper_id})")
                        if st.button("📁 View in Institutional Saved Papers →", key="adm_btn_goto_view_saved"):
                            navigate_to("📁 Saved Papers")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Failed to process manuscript: {str(e)}")

# ===========================================================================
# 7. ANALYTICS & INSTITUTIONAL REPORTING
# ===========================================================================
def render_analytics_view(theme):
    """Renders comprehensive institutional intelligence and database analytics."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Administration Analytics & Intelligence Reports</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Visual analytics, academic quality distributions, role allocations, and export center driven 100% by live SQLite records.
            </p>
        </div>
        """)

    stats = auth.get_system_stats()
    all_users = auth.get_all_users()
    saved_papers = auth.get_saved_papers()
    platform_analyses = auth.get_all_analyses_summary()
    login_events = auth.get_login_history(limit=500)

    # Summary Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registered Users", stats["total_users"])
    m2.metric("Analyses Executed", stats["analysis_count"])
    m3.metric("Repository Manuscripts", stats["saved_papers_count"])
    m4.metric("Audit & Security Events", stats["audit_count"])

    render_html("<br>")

    # Chart Row 1: Role Distribution & Security Events
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>👥 User Role Distribution</h4>")
            roles_data = {
                "Student": stats["student_count"],
                "Researcher": stats["researcher_count"],
                "Administrator": stats["admin_count"]
            }
            if stats["legacy_count"] > 0:
                roles_data["Legacy Accounts"] = stats["legacy_count"]

            labels = list(roles_data.keys())
            values = list(roles_data.values())

            fig_roles = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=.45,
                marker=dict(colors=[theme['info_text'], theme['accent_primary'], theme['error_text'], theme['warning_text']])
            )])
            layout_r = get_chart_layout_dict(theme)
            layout_r["height"] = 280
            fig_roles.update_layout(**layout_r)
            st.plotly_chart(fig_roles, use_container_width=True)

    with c_chart2:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>🛡️ Authentication & Audit Outcomes</h4>")
            success_count = sum(1 for e in login_events if "Success" in e.get("status", "") or "Registered" in e.get("status", "") or "Provisioned" in e.get("status", ""))
            failed_count = sum(1 for e in login_events if "Failed" in e.get("status", "") or "Denied" in e.get("status", ""))
            other_count = max(0, len(login_events) - (success_count + failed_count))

            fig_auth = go.Figure(data=[go.Pie(
                labels=["Successful / Normal", "Failed / Denied", "System / Admin Actions"],
                values=[success_count, failed_count, other_count],
                hole=.45,
                marker=dict(colors=[theme['success_text'], theme['error_text'], theme['accent_purple']])
            )])
            layout_a = get_chart_layout_dict(theme)
            layout_a["height"] = 280
            fig_auth.update_layout(**layout_a)
            st.plotly_chart(fig_auth, use_container_width=True)

    render_html("<br>")

    # Dataset Scope Selector for Academic Domain & Quality Scoring
    render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>🔬 Academic Intelligence Dataset Scope</h4>")
    scope_choice = st.radio(
        "Select Dataset Scope for Discipline Breakdown & Quality Distributions",
        [
            f"🌐 Platform-Wide User Analyses ({len(platform_analyses)} records across all users)",
            f"🏛️ Institutional Saved Repository ({len(saved_papers)} benchmark manuscripts)"
        ],
        horizontal=True,
        key="adm_anl_dataset_scope"
    )

    is_platform_scope = "Platform-Wide" in scope_choice
    active_dataset = platform_analyses if is_platform_scope else saved_papers

    # Chart Row 2: Academic Disciplines & Quality Scores
    c_chart3, c_chart4 = st.columns(2)

    with c_chart3:
        with st.container(border=True):
            header_txt = "📚 Research Disciplines (Platform-Wide)" if is_platform_scope else "📚 Research Disciplines (Repository)"
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>{header_txt}</h4>")
            domain_counts = {}
            for item in active_dataset:
                d = item.get("domain") or "General Academic"
                domain_counts[d] = domain_counts.get(d, 0) + 1

            if domain_counts:
                fig_dom = go.Figure(data=[go.Bar(
                    x=list(domain_counts.keys()),
                    y=list(domain_counts.values()),
                    marker_color=theme.get("accent_purple", "#A78BFA"),
                    text=list(domain_counts.values()),
                    textposition="auto"
                )])
                layout_d = get_chart_layout_dict(theme)
                layout_d["height"] = 280
                layout_d["yaxis"]["title"] = "Documents"
                fig_dom.update_layout(**layout_d)
                st.plotly_chart(fig_dom, use_container_width=True)
            else:
                st.info("No documents found for selected scope.")

    with c_chart4:
        with st.container(border=True):
            header_txt = "📊 Quality Score Distribution (Platform-Wide)" if is_platform_scope else "📊 Quality Score Overview (Repository)"
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>{header_txt}</h4>")
            scores = [float(item["score"]) for item in active_dataset if item.get("score") is not None]
            if scores:
                avg_sc = sum(scores) / len(scores)
                fig_sc = go.Figure(data=[go.Histogram(
                    x=scores,
                    xbins=dict(start=0, end=100, size=10),
                    marker_color=theme.get("info_text", "#38BDF8"),
                    opacity=0.85
                )])
                layout_s = get_chart_layout_dict(theme)
                layout_s["height"] = 280
                layout_s["xaxis"]["title"] = f"Overall Score (0-100) — Avg: {avg_sc:.1f}"
                layout_s["xaxis"]["range"] = [0, 100]
                layout_s["yaxis"]["title"] = "Frequency"
                fig_sc.update_layout(**layout_s)
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("No scored documents available for histogram.")

    render_html("<br>")

    # Export Center
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>📥 Institutional Data Export Hub</h3>")
        st.caption("Generate sanitized, formula-injection protected CSV spreadsheets of system data. Passwords, hashes, and secrets are strictly excluded.")

        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            st.download_button(
                "Export All Users CSV",
                data=auth.export_users_csv(),
                file_name=f"PaperIQ_Users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_users"
            )
        with ex2:
            st.download_button(
                "Export Audit Logs CSV",
                data=auth.export_audit_csv(limit=1000),
                file_name=f"PaperIQ_Audit_Logs_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_audits"
            )
        with ex3:
            st.download_button(
                "Export Repository Metadata CSV",
                data=auth.export_repository_csv(),
                file_name=f"PaperIQ_Repository_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_repo"
            )

# ===========================================================================
# 8. SYSTEM HEALTH & DIAGNOSTICS
# ===========================================================================
def render_system_health_view(theme, current_admin_user="admin"):
    """Renders real-time SQLite health, latency, and system diagnostics."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">System Health & Diagnostics</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Live database connectivity, SQLite integrity checks, ping latency, and environment diagnostics.
            </p>
        </div>
        """)

    health = auth.get_system_health()
    status_str = health["status"]
    s_col = theme["success_text"] if status_str == "Healthy" else theme["error_text"]
    s_bg = theme["success_bg"] if status_str == "Healthy" else theme["error_bg"]

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        render_html(f"""
            <div style="padding: 14px; background: {theme['bg_card']}; border: 1px solid {theme['border_color']}; border-radius: 8px;">
                <div style="font-size: 12px; color: {theme['text_muted']}; text-transform: uppercase; font-weight: 700;">System Status</div>
                <div style="font-size: 20px; font-weight: 800; color: {s_col}; margin-top: 4px;">
                    <span style="background: {s_bg}; padding: 3px 10px; border-radius: 6px;">● {status_str}</span>
                </div>
            </div>
            """)
    with h2:
        st.metric("DB Ping Latency", f"{health['latency_ms']} ms")
    with h3:
        st.metric("Integrity Check", health["integrity"].upper())
    with h4:
        db_mb = health["db_size_bytes"] / (1024 * 1024)
        st.metric("Database File Size", f"{db_mb:.2f} MB")

    render_html("<br>")

    # Database Table Records Breakdown
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>🗄️ Database Table Counts & Storage Allocation</h4>")
        tbl_cols = st.columns(5)
        names = ["users", "analysis_history", "login_history", "saved_papers", "upload_history"]
        labels = ["Users", "Analyses", "Audit Logs", "Saved Papers", "Upload Trail"]
        for i, (name, lbl) in enumerate(zip(names, labels)):
            with tbl_cols[i]:
                st.metric(lbl, health["table_counts"].get(name, 0))

    render_html("<br>")

    # Environment Specifications
    os_detail = f"{platform.system()} {platform.release()} ({platform.machine()})"
    sqlite_ver = sqlite3.sqlite_version
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 12px 0;'>⚙️ Runtime Environment Specifications</h4>")
        env_c1, env_c2 = st.columns(2)
        with env_c1:
            render_html(f"""
                <div style="font-size: 13.5px; line-height: 1.8; color: {theme['text_secondary']};">
                    • <b>Python Runtime:</b> <code>v{sys.version.split()[0]}</code><br>
                    • <b>Streamlit Framework:</b> <code>v{st.__version__}</code><br>
                    • <b>Database Engine:</b> SQLite <code>v{sqlite_ver}</code> (WAL & UTF-8)<br>
                    • <b>SQLite Page Size:</b> <code>{health['page_size']:,} bytes</code><br>
                </div>
                """)
        with env_c2:
            render_html(f"""
                <div style="font-size: 13.5px; line-height: 1.8; color: {theme['text_secondary']};">
                    • <b>Host Operating System:</b> <code>{os_detail}</code><br>
                    • <b>Architecture:</b> <code>{platform.architecture()[0]}</code><br>
                    • <b>Allocated DB Pages:</b> <code>{health['page_count']:,} pages</code><br>
                    • <b>Security Architecture:</b> SHA-256 (Zero Plaintext Secrets)<br>
                </div>
                """)

        st.write("")
        if st.button("🔄 Refresh System Diagnostics", key="adm_btn_refresh_health"):
            st.rerun()

# ===========================================================================
# 9. STORAGE & DATA MANAGEMENT
# ===========================================================================
def render_storage_management_view(theme, current_admin_user="admin"):
    """Renders database maintenance and storage optimization tools."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Storage & Data Management</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Inspect database disk usage, defragment SQLite storage, and run authorized maintenance procedures.
            </p>
        </div>
        """)

    stats = auth.get_system_stats()
    health = auth.get_system_health()

    s1, s2, s3 = st.columns(3)
    s1.metric("Database Storage", stats["db_size_formatted"])
    s2.metric("Total Records Across Tables", sum(health["table_counts"].values()))
    s3.metric("SQLite Integrity", health["integrity"].upper())

    render_html("<br>")

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>🧹 Compact Database & Reclaim Space (VACUUM)</h3>")
        st.write("Over time, deleting analysis records or papers leaves fragmented unused pages in SQLite. Running **VACUUM** rebuilds the database file, defragments pages, and shrinks file size on disk.")

        conf_vac = st.checkbox("I confirm running SQLite VACUUM optimization", key="adm_chk_vacuum")
        if st.button("Run VACUUM Optimization", type="primary", key="adm_btn_run_vacuum"):
            if conf_vac:
                with st.spinner("Compacting database pages..."):
                    success, msg = auth.vacuum_database(current_admin_user=current_admin_user)
                    if success:
                        st.success(f"✓ {msg}")
                        st.rerun()
                    else:
                        st.error(f"Failed to compact database: {msg}")
            else:
                st.warning("Please check the confirmation box before running VACUUM.")

    render_html("<br>")

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>🛡️ Audit Trail Retention Policy</h3>")
        st.write("PaperIQ retains authentication and security events in `login_history`. As an authorized administrator, you can clear older logs when compliance policies allow.")

        conf_purge = st.checkbox("Confirm authorized audit log purge (creates a tamper-evident purge record)", key="adm_chk_purge_retention")
        if st.button("Purge Audit History", key="adm_btn_purge_retention"):
            if conf_purge:
                success, msg = auth.clear_login_history(current_admin_user=current_admin_user)
                if success:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("Please check the confirmation box.")
