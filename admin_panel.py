"""
PaperIQ Administrator Control Center Module
Provides comprehensive, production-conscious administration interfaces:
1. Admin Dashboard with System Status badge, 10 real database/operational stat cards, activity chart, and recent activity panels
2. User Management & Role Governance with search, filters, pagination, bulk actions, guarded role/password/delete actions, test account cleanup, and legacy role migration
3. Login & Security Audit Logs with tamper-evident SHA-256 hash-chain verification, date-range filtering, and retention-guarded purge with automatic CSV archiving
4. Institutional Saved Papers Repository with search, canonical discipline filtering, duplicate detection/cleanup, and inline analysis viewer
5. Document Upload Audit History with aggregate telemetry and privacy-preserving masked filenames (abc….pdf)
6. Upload Research Paper to Institutional Repository with SHA-256 duplicate warning and processing telemetry logging
7. Research Activity Overview (Analytics & Intelligence Reports) with date-range selector, test-account exclusion toggle, processing metrics, and readable discipline charts
8. System Health & Diagnostics with Recent Application Errors, Processing Failures, Dependency Status, and SQLite diagnostics
9. Storage & Data Management with database backups (sqlite3.Connection.backup), per-table breakdown, orphan cleanup, report cleanup, and VACUUM
10. Platform Settings (app_settings) with input validation and audit logging
11. About & System Information with deployment specs, role overview, known limitations, and responsible-use notice
"""

import streamlit as st
import html
import json
import os
import sys
import math
import re
import time
import platform
import sqlite3
import auth
from utils import render_html, safe_text, unescape_text, truncate_title_word_boundary
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
import plotly.express as px


def get_chart_layout_dict(theme):
    """Generates a theme-consistent Plotly layout dictionary with solid readable backgrounds."""
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
        "margin": {"l": 40, "r": 24, "t": 35, "b": 40},
    }


def _status_badge_colors(status_str, theme):
    """Maps Healthy / Degraded / Error to theme colors."""
    s = str(status_str or "Healthy").strip().lower()
    if s == "healthy":
        return theme.get("success_text", "#34D399"), theme.get("success_bg", "rgba(16,185,129,0.15)")
    elif s == "degraded":
        return theme.get("warning_text", "#FBBF24"), theme.get("warning_bg", "rgba(245,158,11,0.15)")
    return theme.get("error_text", "#F87171"), theme.get("error_bg", "rgba(239,68,68,0.15)")


# ===========================================================================
# 1. ADMIN DASHBOARD (Part 1.3)
# ===========================================================================
def render_admin_dashboard(theme, navigate_to):
    """Renders the Administrator Overview & Governance Dashboard."""
    stats = auth.get_system_stats()
    sys_status = stats.get("system_status", "Healthy")
    sys_reason = stats.get("system_status_reason", "All core subsystems nominal.")
    badge_col, badge_bg = _status_badge_colors(sys_status, theme)

    render_html(f"""
        <div style="margin-bottom: 18px; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 28px;">🛡️</span>
                <div>
                    <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Administrator Control Center</h1>
                    <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                        PaperIQ Platform Governance, Security Operations, Aggregate Telemetry, and System Health.
                    </p>
                </div>
            </div>
            <div style="background: {theme['bg_card']}; border: 1px solid {theme['border_color']}; border-radius: 10px; padding: 10px 16px; min-width: 280px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                    <span style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: {theme['text_muted']};">System Status</span>
                    <span style="font-size: 12.5px; font-weight: 800; color: {badge_col}; background: {badge_bg}; padding: 3px 10px; border-radius: 999px;">● {safe_text(sys_status)}</span>
                </div>
                <div style="font-size: 12px; color: {theme['text_secondary']}; margin-top: 5px;">
                    {safe_text(sys_reason)}
                </div>
            </div>
        </div>
        """)

    # Navigation Shortcuts (8 core admin sections)
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
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
    with c7:
        st.button("⚙️ Settings", use_container_width=True, key="adm_btn_settings", on_click=navigate_to, args=("⚙️ Platform Settings",))
    with c8:
        st.button("ℹ️ About", use_container_width=True, key="adm_btn_about", on_click=navigate_to, args=("ℹ️ About & System Info",))

    render_html("<br>")

    # Metric Row 1: Users & Curated Repository (4 cards)
    m_r1_1, m_r1_2, m_r1_3, m_r1_4 = st.columns(4)
    m_r1_1.metric("Registered Users", stats["total_users"])
    m_r1_2.metric("Student Accounts", stats["student_count"])
    m_r1_3.metric("Researcher Accounts", stats["researcher_count"])
    m_r1_4.metric("Repository Papers", stats["saved_papers_count"])

    st.write("")
    # Metric Row 2: Analyses, Audit Logs & Database Storage (3 cards)
    m_r2_1, m_r2_2, m_r2_3 = st.columns(3)
    m_r2_1.metric("Analysis Records", stats["analysis_count"])
    m_r2_2.metric("Audit Log Entries", stats["audit_count"])
    m_r2_3.metric("Storage", stats["db_size_formatted"])

    st.write("")
    # Metric Row 3 (Part 1.3 New Cards): Errors in last 24h, Processing Success Rate (7d), Last Backup Time
    m_r3_1, m_r3_2, m_r3_3 = st.columns(3)
    m_r3_1.metric("Errors in Last 24h", stats.get("errors_24h", 0))
    m_r3_2.metric("Processing Success Rate (7d)", f"{stats.get('processing_success_rate_7d', 100.0):.1f}%")
    m_r3_3.metric("Last Backup Time", stats.get("last_backup_time", "Never"))

    render_html("<br>")

    # Database Activity Trend Chart (Real Data, Continuous Timeline)
    all_users = auth.get_all_users()
    login_events = auth.get_login_history(limit=500)

    date_counts = {}
    for ev in login_events:
        d = ev.get("login_time", "")[:10]
        if d:
            date_counts[d] = date_counts.get(d, 0) + 1

    today = datetime.now().date()
    date_window = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    display_labels = [(today - timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    counts_7d = [date_counts.get(d, 0) for d in date_window]

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
        t_mode = st.radio(
            "Chart View",
            ["7-Day Daily Trend", "Today's Hourly Activity"],
            horizontal=True,
            label_visibility="collapsed",
            key="adm_chart_mode_toggle",
        )

    fig_trend = go.Figure()
    layout_dict = get_chart_layout_dict(theme)
    layout_dict["height"] = 250
    layout_dict["margin"] = dict(l=40, r=20, t=15, b=40)

    if "Hourly" in t_mode:
        h_x = list(hour_counts.keys())
        h_y = list(hour_counts.values())
        fig_trend.add_trace(go.Bar(
            x=h_x,
            y=h_y,
            marker_color=theme.get("accent_primary", "#7C3AED"),
            hovertemplate="<b>Hour:</b> %{x}<br><b>Recorded Events:</b> %{y}<extra></extra>",
            name="Hourly Events",
        ))
        layout_dict["xaxis"]["title"] = "Hour of Day (Local)"
        layout_dict["yaxis"]["title"] = "Recorded Events"
    else:
        fig_trend.add_trace(go.Bar(
            x=display_labels,
            y=counts_7d,
            marker_color=theme.get("accent_primary", "#7C3AED"),
            text=counts_7d,
            textposition="auto",
            hovertemplate="<b>Date:</b> %{x}<br><b>Recorded Events:</b> %{y}<extra></extra>",
            name="Daily Events",
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
                for u in all_users[:5]:
                    r_badge_color = theme["info_text"] if u["role"] == "Student" else (theme["accent_purple"] if u["role"] == "Researcher" else theme["warning_text"])
                    r_badge_bg = theme["info_bg"] if u["role"] == "Student" else (theme["accent_primary_subtle"] if u["role"] == "Researcher" else theme["warning_bg"])
                    is_active = u.get("status", "Active") != "Disabled"
                    stat_color = theme["success_text"] if is_active else theme["error_text"]
                    stat_bg = theme["success_bg"] if is_active else theme["error_bg"]
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
                    is_success = "Success" in ev.get("status", "") or "Registered" in ev.get("status", "") or "Provisioned" in ev.get("status", "")
                    s_color = theme["success_text"] if is_success else theme["error_text"]
                    s_bg = theme["success_bg"] if is_success else theme["error_bg"]
                    action_tag = ev.get("action_type", "AUTH")

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
# 2. USER MANAGEMENT & ROLE GOVERNANCE (Parts 2.1, 2.2, 2.3, 4.1, 4.2, 4.5)
# ===========================================================================
def render_all_users_view(theme, current_admin_user):
    """Renders the comprehensive User Management page with guardrails, bulk ops, test cleanup, and legacy migration."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">All Users — System User Governance & Role Management</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Inspect registered user accounts, manage permission roles, execute bulk status governance, and perform audited account lifecycle actions.
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
    f_c1, f_c2, f_c3, f_c4 = st.columns([2.6, 1.2, 1.4, 1.4])
    with f_c1:
        search_query = st.text_input("🔍 Search user accounts by username, role, or status", "", key="adm_user_search")
    with f_c2:
        page_size_choice = st.selectbox("Page Size", [15, 30, 50, "All"], index=0, key="adm_users_page_size")
    with f_c3:
        hide_test_in_table = st.checkbox("Hide test/demo accounts", value=False, key="adm_users_hide_test")
    with f_c4:
        st.write("")
        st.download_button(
            "📥 Export Users CSV",
            data=auth.export_users_csv(current_admin_user=current_admin_user),
            file_name=f"PaperIQ_Users_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_users",
        )

    # Part 4.2: Hide "Legacy Accounts" tab once 0 legacy accounts remain
    tab_labels = [
        f"All Users ({len(all_users)})",
        f"Students ({len(students)})",
        f"Researchers ({len(researchers)})",
        f"Administrators ({len(admins)})",
    ]
    if legacies:
        tab_labels.append(f"Legacy Accounts ({len(legacies)})")
    tab_labels.extend([
        f"Active ({len(actives)})",
        f"Disabled ({len(disabled)})",
    ])
    tabs_objs = st.tabs(tab_labels)

    def display_users_table(user_list, key_prefix):
        filtered = [
            u for u in user_list
            if (not hide_test_in_table or not auth.is_test_account(u["username"]) or u["role"] == "Administrator")
            and (
                not search_query
                or search_query.lower() in u["username"].lower()
                or search_query.lower() in u["role"].lower()
                or search_query.lower() in u.get("status", "").lower()
            )
        ]
        if not filtered:
            st.info("No user accounts match the current filter.")
            return []

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

        # Render Table Header (includes Last Login column per Part 4.5)
        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.4fr 1.8fr 1.3fr 1.0fr 1.5fr 1.5fr 0.8fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 12px; color: {theme['text_muted']}; text-transform: uppercase;">
                <div>#</div>
                <div>Username</div>
                <div>Academic Role</div>
                <div>Status</div>
                <div>Registered Date</div>
                <div>Last Login</div>
                <div>Analyses</div>
            </div>
            """)

        for i, u in enumerate(display_slice):
            r_color = theme["info_text"] if u["role"] == "Student" else (theme["accent_purple"] if u["role"] == "Researcher" else (theme["error_text"] if u["role"] == "Administrator" else theme["warning_text"]))
            r_bg = theme["info_bg"] if u["role"] == "Student" else (theme["accent_primary_subtle"] if u["role"] == "Researcher" else (theme["error_bg"] if u["role"] == "Administrator" else theme["warning_bg"]))
            is_active = u.get("status", "Active") != "Disabled"
            s_color = theme["success_text"] if is_active else theme["error_text"]
            s_bg = theme["success_bg"] if is_active else theme["error_bg"]
            created_str = u.get("created_at", "")[:16] or "—"
            last_login_str = (u.get("last_login") or "")[:16] or "Never"

            render_html(f"""
                <div style="display: grid; grid-template-columns: 0.4fr 1.8fr 1.3fr 1.0fr 1.5fr 1.5fr 0.8fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 13px; align-items: center;">
                    <div style="color: {theme['text_muted']};">{start_idx + i + 1}</div>
                    <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(u['username'])}</div>
                    <div><span style="font-size: 11px; font-weight: 700; color: {r_color}; background: {r_bg}; padding: 2px 8px; border-radius: 6px;">{safe_text(u['role'])}</span></div>
                    <div><span style="font-size: 11px; font-weight: 700; color: {s_color}; background: {s_bg}; padding: 2px 8px; border-radius: 6px;">{safe_text(u.get('status', 'Active'))}</span></div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; font-family: monospace;">{safe_text(created_str)}</div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; font-family: monospace;">{safe_text(last_login_str)}</div>
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
        return filtered

    t_idx = 0
    with tabs_objs[t_idx]:
        filtered_all = display_users_table(all_users, "all")
    t_idx += 1
    with tabs_objs[t_idx]:
        display_users_table(students, "stu")
    t_idx += 1
    with tabs_objs[t_idx]:
        display_users_table(researchers, "res")
    t_idx += 1
    with tabs_objs[t_idx]:
        display_users_table(admins, "adm")
    t_idx += 1
    if legacies:
        with tabs_objs[t_idx]:
            display_users_table(legacies, "leg")
        t_idx += 1
    with tabs_objs[t_idx]:
        display_users_table(actives, "act")
    t_idx += 1
    with tabs_objs[t_idx]:
        display_users_table(disabled, "dis")

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 4.5: Authorized Account Inspection & Management (Only shown when selected)
    # -----------------------------------------------------------------------
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>⚙️ Inspect & Manage Individual User Account</h3>")
        st.caption("Select an account from the current filtered list to inspect its governance history or perform role, status, password, or deletion actions.")

        candidate_users = filtered_all if filtered_all else all_users
        placeholder_opt = "— Select a user account to inspect & manage —"
        select_options = [placeholder_opt] + [u["username"] for u in candidate_users]

        sel_target_user = st.selectbox(
            "Select Account to Inspect & Manage",
            select_options,
            index=0,
            key="adm_sel_manage_user",
        )

        # Display one-time generated temporary password banner if one was just issued
        last_reset_info = st.session_state.get("adm_last_temp_password_info")
        if last_reset_info:
            st.info(
                f"🔑 **One-Time Temporary Password for `{last_reset_info['username']}`:** "
                f"`{last_reset_info['temp_password']}`\n\n"
                "Copy and share this temporary credential with the user now. It is stored only as a PBKDF2 hash and will not be shown again. "
                "The user will be required to set a new password upon next login."
            )
            if st.button("Dismiss One-Time Password Notice", key="adm_btn_dismiss_temp_pw"):
                st.session_state.pop("adm_last_temp_password_info", None)
                st.rerun()

        if sel_target_user != placeholder_opt:
            target_info = next((u for u in all_users if u["username"] == sel_target_user), None)
            if target_info:
                c_det1, c_det2, c_det3, c_det4, c_det5 = st.columns(5)
                c_det1.metric("Username", target_info["username"])
                c_det2.metric("Role", target_info["role"])
                c_det3.metric("Status", target_info.get("status", "Active"))
                c_det4.metric("Last Login", (target_info.get("last_login") or "Never")[:16])
                c_det5.metric("Analyses Stored", target_info.get("analysis_count", 0))

                act_col1, act_col2, act_col3, act_col4, act_col5 = st.tabs([
                    "Assign Role",
                    "Toggle Status",
                    "Reset Password",
                    "Delete Account",
                    "Role & Governance History",
                ])

                with act_col1:
                    st.write("")
                    if sel_target_user == current_admin_user:
                        st.info("🛡️ **Self-Demotion Safeguard:** You cannot demote your own currently active Administrator account.")
                    role_opts = ["Student", "Researcher", "Administrator"]
                    curr_idx = 0 if target_info["role"] == "Student" else (1 if target_info["role"] == "Researcher" else (2 if target_info["role"] == "Administrator" else 0))
                    new_role_choice = st.selectbox("Assign New Academic Role", role_opts, index=curr_idx, key="adm_new_role_select")

                    confirm_admin_typed = None
                    if new_role_choice == "Administrator" and target_info["role"] != "Administrator":
                        st.warning(
                            f"⚠️ **Elevated Privilege Warning:** Granting `Administrator` gives `{sel_target_user}` full platform governance permissions. "
                            f"Please type `{sel_target_user}` below as a second explicit confirmation."
                        )
                        confirm_admin_typed = st.text_input(
                            f"Type '{sel_target_user}' to confirm granting Administrator role",
                            "",
                            key="adm_confirm_grant_admin_input",
                        )

                    conf_role = st.checkbox(f"Confirm changing role of '{sel_target_user}' to '{new_role_choice}'", key="adm_chk_role")
                    if st.button("Update Role", type="primary", key="adm_btn_apply_role"):
                        if not conf_role:
                            st.warning("Please check the confirmation box before updating role.")
                        else:
                            success, msg = auth.update_user_role(
                                sel_target_user,
                                new_role_choice,
                                current_admin_user=current_admin_user,
                                confirm_username=confirm_admin_typed if (new_role_choice == "Administrator" and target_info["role"] != "Administrator") else sel_target_user,
                            )
                            if success:
                                st.success(f"✓ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)

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
                    st.write(
                        "Generates a cryptographically random 14-character temporary password via `secrets`, stores **only** its PBKDF2-HMAC-SHA256 hash, "
                        "and sets `must_change_password = 1` so the user is forced to choose a new password on next login."
                    )
                    conf_pass = st.checkbox(f"Confirm issuing a one-time temporary password for '{sel_target_user}'", key="adm_chk_pass")
                    if st.button("Generate One-Time Temporary Password", type="primary", key="adm_btn_apply_pass"):
                        if conf_pass:
                            res = auth.admin_reset_password(sel_target_user, current_admin_user=current_admin_user)
                            if res[0]:
                                st.session_state["adm_last_temp_password_info"] = {
                                    "username": sel_target_user,
                                    "temp_password": res.temp_password,
                                }
                                st.success(f"✓ {res[1]}")
                                st.rerun()
                            else:
                                st.error(res[1])
                        else:
                            st.warning("Please check the confirmation box before resetting password.")

                with act_col4:
                    st.write("")
                    if sel_target_user == current_admin_user:
                        st.error("⚠️ Self-Lockout Safeguard: You cannot delete your own currently active Administrator account.")
                    else:
                        st.warning(
                            f"⚠️ **Data Impact Summary for `{sel_target_user}`:**\n"
                            f"- Stored Analyses: **{target_info.get('analysis_count', 0)}** record(s)\n"
                            f"- Security Audit Trail (`login_history`): **Preserved** as immutable historical text for compliance."
                        )
                        del_mode_label = st.radio(
                            "Account Data Handling Policy",
                            [
                                "Delete All Associated Data (papers, analyses, projects, notes, chats) & Credentials",
                                "Anonymize Associated Analyses/Projects (`anon_<hash>`) & Delete Credentials",
                            ],
                            key="adm_del_mode_radio",
                        )
                        del_mode = "anonymize" if "Anonymize" in del_mode_label else "delete_all"
                        typed_del_user = st.text_input(
                            f"Type the exact username '{sel_target_user}' to confirm permanent deletion",
                            "",
                            key="adm_del_confirm_username_input",
                        )
                        if st.button("Delete User Account Permanently", type="primary", key="adm_btn_apply_del"):
                            success, msg = auth.delete_user_account(
                                sel_target_user,
                                current_admin_user=current_admin_user,
                                confirm_username=typed_del_user,
                                mode=del_mode,
                            )
                            if success:
                                st.success(f"✓ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)

                with act_col5:
                    st.write("")
                    role_hist = auth.get_user_role_history(sel_target_user, current_admin_user=current_admin_user)
                    if role_hist:
                        for rh in role_hist:
                            render_html(f"""
                                <div style="padding: 8px 12px; border-bottom: 1px solid {theme['border_color']}; font-size: 12.5px;">
                                    <span style="font-family: monospace; color: {theme['text_muted']};">{safe_text(rh.get('login_time', ''))}</span>
                                    &nbsp;•&nbsp; <b style="color: {theme['accent_purple']};">{safe_text(rh.get('action_type', ''))}</b>
                                    &nbsp;•&nbsp; Actor: <b>{safe_text(rh.get('actor', ''))}</b>
                                    &nbsp;—&nbsp; <span style="color: {theme['text_secondary']};">{safe_text(rh.get('details', ''))}</span>
                                </div>
                                """)
                    else:
                        st.caption("No role or governance history recorded for this account yet.")

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 4.5: Bulk User Governance Actions
    # -----------------------------------------------------------------------
    with st.expander("📦 Bulk User Status Governance & Selected Export", expanded=False):
        st.caption("Select multiple non-admin accounts to disable/enable in bulk or export a targeted CSV subset.")
        bulk_candidates = [u["username"] for u in all_users if u["username"] != current_admin_user]
        selected_bulk_users = st.multiselect("Select Accounts for Bulk Action", bulk_candidates, key="adm_bulk_users_select")
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            if st.button("Disable Selected Accounts", use_container_width=True, key="adm_btn_bulk_disable"):
                ok, msg, _ = auth.bulk_update_user_status(selected_bulk_users, "Disabled", current_admin_user=current_admin_user)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.warning(msg)
        with b_col2:
            if st.button("Enable Selected Accounts", use_container_width=True, key="adm_btn_bulk_enable"):
                ok, msg, _ = auth.bulk_update_user_status(selected_bulk_users, "Active", current_admin_user=current_admin_user)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.warning(msg)
        with b_col3:
            st.download_button(
                "📥 Export Selected CSV",
                data=auth.export_users_csv(usernames=selected_bulk_users if selected_bulk_users else None, current_admin_user=current_admin_user),
                file_name=f"PaperIQ_Selected_Users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=(len(selected_bulk_users) == 0),
                key="adm_btn_bulk_export_csv",
            )

    # -----------------------------------------------------------------------
    # Part 4.1: Test & Demo Account Detection & Cleanup Tool
    # -----------------------------------------------------------------------
    test_accounts = auth.detect_test_accounts(current_admin_user=current_admin_user)
    with st.expander(f"🧹 Test & Demo Account Cleanup Tool ({len(test_accounts)} detected)", expanded=False):
        st.write(
            "Detects accounts matching automated test and demo patterns (`audit_user_*`, `qa_user_*`, `reg_tester_*`, "
            "`test_cleanup_user`, `testuser`, `e2e_*`, `stu_a_*`, `res_b_*`, `res_c_*`, `res_ui_*`, `Student_Demo`, `Teacher_Demo`). "
            "No accounts are ever disabled or deleted automatically."
        )
        if test_accounts:
            test_names = [u["username"] for u in test_accounts]
            sel_test_to_clean = st.multiselect(
                "Select Detected Test/Demo Accounts",
                test_names,
                default=test_names,
                key="adm_sel_test_accounts_cleanup",
            )
            tc_col1, tc_col2, tc_col3 = st.columns([2, 2, 1.5])
            with tc_col1:
                tc_action_lbl = st.radio(
                    "Cleanup Action",
                    ["Disable Selected Test Accounts", "Permanently Delete Selected Test Accounts"],
                    horizontal=True,
                    key="adm_test_cleanup_action",
                )
            with tc_col2:
                tc_confirm = st.text_input("Type 'CONFIRM' to execute cleanup", "", key="adm_test_cleanup_confirm")
            with tc_col3:
                st.write("")
                st.write("")
                if st.button("Execute Test Cleanup", type="primary", use_container_width=True, key="adm_btn_exec_test_cleanup"):
                    act_code = "delete" if "Delete" in tc_action_lbl else "disable"
                    ok, msg, _ = auth.cleanup_test_accounts(
                        sel_test_to_clean,
                        action=act_code,
                        confirm_text=tc_confirm,
                        current_admin_user=current_admin_user,
                    )
                    if ok:
                        st.success(f"✓ {msg}")
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.success("✓ No test or demo accounts detected.")

    # -----------------------------------------------------------------------
    # Part 4.2: Legacy Role Migration Tool
    # -----------------------------------------------------------------------
    if legacies:
        with st.expander(f"🔄 Legacy Role Migration Tool ({len(legacies)} legacy account(s) found)", expanded=True):
            st.write(
                "The following accounts have legacy role labels outside the canonical (`Student`, `Researcher`, `Administrator`) taxonomy. "
                "Choose the target role for each account and confirm to migrate them."
            )
            role_map = {}
            for leg_u in legacies:
                uname = leg_u["username"]
                old_r = leg_u["role"]
                default_idx = 1 if str(old_r).lower() in ("evaluator", "faculty", "reviewer") else 0
                mc1, mc2, mc3 = st.columns([2, 1.5, 2])
                with mc1:
                    st.markdown(f"**Account:** `{uname}`")
                with mc2:
                    st.markdown(f"**Legacy Role:** `{old_r}`")
                with mc3:
                    role_map[uname] = st.selectbox(
                        f"Target Role for {uname}",
                        ["Student", "Researcher"],
                        index=default_idx,
                        key=f"adm_leg_mig_{uname}",
                    )
            conf_mig = st.checkbox("Confirm migrating legacy accounts to canonical roles (logs each change in audit trail)", key="adm_chk_mig_legacy")
            if st.button("Migrate Legacy Roles Now", type="primary", key="adm_btn_mig_legacy"):
                ok, msg, _ = auth.migrate_legacy_roles(
                    role_mapping=role_map,
                    current_admin_user=current_admin_user,
                    confirm=conf_mig,
                )
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.error(msg)


# ===========================================================================
# 3. LOGIN & SECURITY AUDIT LOGS (Parts 2.4 & 4.7)
# ===========================================================================
def render_login_history_view(theme, current_admin_user="admin"):
    """Renders the Login History & Security Audit Logs page with hash-chain integrity check, date-range filter, and guarded retention purge."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Login History & Security Audit Logs</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Tamper-evident SHA-256 hash-chained security audit trail tracking logins, lockouts, role updates, settings changes, backups, and access events. Passwords and hashes are never logged.
            </p>
        </div>
        """)

    # Part 2.4: Tamper-Evident Audit Log Integrity Verification Bar
    integrity_info = auth.verify_audit_log_integrity()
    total_recs = integrity_info.get("total_rows", 0)
    ver_count = integrity_info.get("verified_count", 0)
    n_tamper = integrity_info.get("tamper_count", 0)
    n_breaks = integrity_info.get("link_break_count", 0)
    first_break_id = integrity_info.get("first_broken_row_id")
    is_ok = integrity_info.get("ok", False)
    content_valid = integrity_info.get("content_valid", False)
    chain_valid = integrity_info.get("chain_valid", False)

    # 1. Dual Status Badges: Content-Hash Validity & Chain-Link Continuity
    st_col_cont, st_col_link, st_col_btn = st.columns([2.5, 2.5, 1.3])
    with st_col_cont:
        if content_valid:
            render_html(f"""
                <div style="padding: 10px 14px; background: {theme['success_bg']}; border: 1px solid {theme['success_text']}; border-radius: 8px; font-size: 13px; line-height: 1.4;">
                    <div style="color: {theme['success_text']}; font-weight: 700;">✅ Record Content Hashes: Valid</div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; margin-top: 2px;">{ver_count} / {total_recs} records match cryptographic content hashes (0 modified)</div>
                </div>
            """)
        else:
            render_html(f"""
                <div style="padding: 10px 14px; background: {theme['error_bg']}; border: 1px solid {theme['error_text']}; border-radius: 8px; font-size: 13px; line-height: 1.4;">
                    <div style="color: {theme['error_text']}; font-weight: 700;">🚨 Record Content Hashes: Tamper Detected</div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; margin-top: 2px;">{n_tamper} record(s) fail content verification (stored hash mismatch)</div>
                </div>
            """)

    with st_col_link:
        if chain_valid:
            render_html(f"""
                <div style="padding: 10px 14px; background: {theme['success_bg']}; border: 1px solid {theme['success_text']}; border-radius: 8px; font-size: 13px; line-height: 1.4;">
                    <div style="color: {theme['success_text']}; font-weight: 700;">✅ Chain-Link Continuity: Valid</div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; margin-top: 2px;">Unbroken sequence across {total_recs} records (0 link discontinuities)</div>
                </div>
            """)
        else:
            render_html(f"""
                <div style="padding: 10px 14px; background: {theme['warning_bg']}; border: 1px solid {theme['warning_text']}; border-radius: 8px; font-size: 13px; line-height: 1.4;">
                    <div style="color: {theme['warning_text']}; font-weight: 700;">⚠️ Chain-Link Continuity: Discontinuity Detected</div>
                    <div style="color: {theme['text_secondary']}; font-size: 12px; margin-top: 2px;">{n_breaks} record(s) reference non-consecutive ancestors (first: row ID {first_break_id})</div>
                </div>
            """)

    with st_col_btn:
        st.write("")
        if st.button("🔐 Verify Audit Trail", use_container_width=True, key="adm_btn_verify_audit_chain"):
            st.toast(integrity_info["message"])

    # 2. Overall Status Summary Banner
    if is_ok:
        rec_msg = ""
        if integrity_info.get("has_recovery_history"):
            last_rec = integrity_info.get("last_recovery") or {}
            rec_msg = f" &nbsp;•&nbsp; <span style='font-weight:400; font-size:12px;'>Continuity realigned under authorized recovery batch '{last_rec.get('recovery_batch_id')}' ({last_rec.get('row_count')} records archived)</span>"
        render_html(f"""
            <div style="margin-top: 10px; padding: 9px 14px; background: {theme['success_bg']}; border: 1px solid rgba(16,185,129,0.3); border-radius: 8px; font-size: 12.5px; color: {theme['success_text']}; font-weight: 600;">
                🔐 <b>Audit Hash-Chain Integrity: Fully Verified</b> — All {ver_count} records passed both record-content verification and chain-link continuity checks.{rec_msg}
            </div>
        """)
    elif n_tamper > 0:
        render_html(f"""
            <div style="margin-top: 10px; padding: 9px 14px; background: {theme['error_bg']}; border: 1px solid {theme['error_text']}; border-radius: 8px; font-size: 12.5px; color: {theme['error_text']}; font-weight: 600;">
                🚨 <b>Audit Integrity Alert — Content Tampering Detected:</b> {safe_text(integrity_info['message'])}
            </div>
        """)
    else:
        render_html(f"""
            <div style="margin-top: 10px; padding: 10px 14px; background: {theme['warning_bg']}; border: 1px solid rgba(180,83,9,0.3); border-radius: 8px; font-size: 12.5px; color: {theme['warning_text']}; line-height: 1.55;">
                <b>⚠️ Audit Trail Status:</b> Record content hashes are verified for all {ver_count} records. However, {n_breaks} records reference non-consecutive predecessors (first affected: row ID {first_break_id}).
                Discontinuities originated during concurrent multi-row write operations where predecessor pointers diverged before write serialization was enforced.
            </div>
        """)

    # 3. Forensic Inspection & Authorized Recovery Expanders (When Discontinuities Exist)
    if n_breaks > 0 and n_tamper == 0:
        forensics = auth.get_audit_discontinuity_forensics(current_admin_user=current_admin_user)
        with st.expander(f"🔍 Inspect Discontinuity Forensics ({n_breaks} affected records)"):
            render_html(f"""
                <div style="margin-bottom: 10px; font-size: 12.5px; color: {theme['text_muted']}; line-height: 1.5;">
                    The table below details every record whose <code>prev_hash</code> references an earlier ancestor rather than its immediate chronological predecessor in the sequence.
                    All row content hashes have been verified against stored signatures.
                </div>
            """)
            if forensics:
                table_rows = []
                for f in forensics:
                    table_rows.append(f"""
                        <tr style="border-bottom: 1px solid {theme['border_color']};">
                            <td style="padding: 6px 8px; font-weight: 700; color: {theme['text_primary']};">#{f['row_id']}</td>
                            <td style="padding: 6px 8px; color: {theme['text_secondary']};">{safe_text(f['timestamp'])}</td>
                            <td style="padding: 6px 8px; color: {theme['accent_purple']};">{safe_text(f['action_type'])}</td>
                            <td style="padding: 6px 8px; color: {theme['text_muted']};">{safe_text(f['target'])}</td>
                            <td style="padding: 6px 8px; color: {theme['warning_text']};">Row #{f['referenced_row_id']}</td>
                            <td style="padding: 6px 8px; color: {theme['text_secondary']};">Row #{f['expected_prev_id']}</td>
                            <td style="padding: 6px 8px; color: {theme['success_text']}; font-weight: 600;">{'✓ Valid' if f['content_hash_valid'] else '✗ Mismatch'}</td>
                        </tr>
                    """)
                render_html(f"""
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid {theme['border_color']}; color: {theme['text_muted']};">
                                <th style="padding: 6px 8px;">Row ID</th>
                                <th style="padding: 6px 8px;">Timestamp</th>
                                <th style="padding: 6px 8px;">Action</th>
                                <th style="padding: 6px 8px;">Target</th>
                                <th style="padding: 6px 8px;">Points To</th>
                                <th style="padding: 6px 8px;">Sequence Predecessor</th>
                                <th style="padding: 6px 8px;">Content Hash</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(table_rows)}
                        </tbody>
                    </table>
                """)

        with st.expander(f"🛠️ Authorized Audit Chain Continuity Recovery (Administrator Action)"):
            render_html(f"""
                <div style="padding: 10px 14px; background: {theme['warning_bg']}; border: 1px solid rgba(180,83,9,0.3); border-radius: 8px; margin-bottom: 12px; font-size: 12.5px; color: {theme['warning_text']}; line-height: 1.55;">
                    <b>🛡️ Governance Policy & Evidence Preservation:</b><br/>
                    • All original hashes, predecessor pointers, timestamps, and row metadata will be archived to <code>audit_evidence_archive</code> before any updates.<br/>
                    • A full database backup snapshot will be saved in <code>backups/</code>.<br/>
                    • Predecessor pointers will be sequentially realigned to restore full cryptographic continuity.<br/>
                    • An immutable <code>AUDIT_CHAIN_RECOVERY</code> audit event will be recorded documenting this authorized operation.<br/>
                    • A downloadable Cryptographic Repair Manifest CSV will be generated.
                </div>
            """)
            rc_col1, rc_col2 = st.columns([1.5, 1])
            with rc_col1:
                rec_reason = st.text_input(
                    "Compliance Justification (Required, >= 10 chars)",
                    placeholder="e.g., Realigning legacy concurrent write discontinuities after concurrency fix",
                    key="adm_recovery_reason_input"
                )
            with rc_col2:
                rec_conf = st.text_input(
                    "Type 'AUTHORIZE_AUDIT_REPAIR' to confirm",
                    placeholder="AUTHORIZE_AUDIT_REPAIR",
                    key="adm_recovery_conf_input"
                )

            if st.button("🔧 Execute Authorized Chain Recovery", type="primary", use_container_width=True, key="adm_btn_exec_recovery"):
                rec_ok, rec_msg, rec_csv = auth.recover_audit_chain_continuity(
                    current_admin_user=current_admin_user,
                    compliance_reason=rec_reason,
                    confirmation_phrase=rec_conf
                )
                if rec_ok:
                    st.session_state["adm_last_recovery_csv"] = rec_csv
                    st.success(f"✓ {rec_msg}")
                    st.rerun()
                else:
                    st.error(rec_msg)

            if st.session_state.get("adm_last_recovery_csv"):
                st.download_button(
                    "📥 Download Cryptographic Repair Manifest CSV",
                    data=st.session_state["adm_last_recovery_csv"],
                    file_name=f"PaperIQ_Audit_Recovery_Manifest_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="adm_dl_recovery_manifest_csv"
                )

    if integrity_info.get("has_recovery_history") and not st.session_state.get("adm_last_recovery_csv"):
        last_rec = integrity_info.get("last_recovery") or {}
        with st.expander("📜 Historical Audit Chain Continuity Recovery Manifest"):
            st.caption(
                f"An authorized continuity recovery was performed on {last_rec.get('recovery_timestamp')} "
                f"by {last_rec.get('authorized_by')} (Batch: {last_rec.get('recovery_batch_id')}, {last_rec.get('row_count')} records realigned). "
                f"Reason: {last_rec.get('compliance_reason')}"
            )
            hist_csv = auth.export_audit_recovery_manifest_csv(batch_id=last_rec.get("recovery_batch_id"))
            st.download_button(
                "📥 Download Historical Recovery Manifest CSV",
                data=hist_csv,
                file_name=f"PaperIQ_Audit_Recovery_Manifest_{last_rec.get('recovery_batch_id')}.csv",
                mime="text/csv",
                key="adm_dl_hist_recovery_csv"
            )

    st.write("")


    # Filters: Username/Keyword, Action Type, Status, Date Range (Part 4.7)
    all_recent = auth.get_login_history(limit=1000)
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2.2, 1.5, 1.5, 1.5, 1.3])
    with f_col1:
        search_user = st.text_input("🔍 Filter by username, target, or details", "", key="adm_log_search_user")
    with f_col2:
        action_types = ["All Action Types"] + sorted(list(set(h.get("action_type", "AUTH") for h in all_recent if h.get("action_type"))))
        sel_action = st.selectbox("Action Type", action_types, key="adm_log_action_filter")
    with f_col3:
        status_opts = ["All Statuses"] + sorted(list(set(h.get("status", "") for h in all_recent if h.get("status"))))
        sel_status = st.selectbox("Status / Outcome", status_opts, key="adm_log_status_filter")
    with f_col4:
        date_preset = st.selectbox(
            "Date Range",
            ["All Dates", "Today", "Last 7 Days", "Last 30 Days", "Custom Range"],
            key="adm_log_date_preset",
        )
    with f_col5:
        st.write("")
        st.write("")
        st.download_button(
            "📥 Export Audit CSV",
            data=auth.export_audit_csv(limit=1000, current_admin_user=current_admin_user),
            file_name=f"PaperIQ_Audit_Logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_audit",
        )

    start_date_str = None
    end_date_str = None
    today_d = datetime.now().date()
    if date_preset == "Today":
        start_date_str = today_d.strftime("%Y-%m-%d")
        end_date_str = today_d.strftime("%Y-%m-%d")
    elif date_preset == "Last 7 Days":
        start_date_str = (today_d - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date_str = today_d.strftime("%Y-%m-%d")
    elif date_preset == "Last 30 Days":
        start_date_str = (today_d - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date_str = today_d.strftime("%Y-%m-%d")
    elif date_preset == "Custom Range":
        dc1, dc2 = st.columns(2)
        with dc1:
            sd = st.date_input("Start Date", value=today_d - timedelta(days=30), key="adm_log_custom_start")
            start_date_str = sd.strftime("%Y-%m-%d")
        with dc2:
            ed = st.date_input("End Date", value=today_d, key="adm_log_custom_end")
            end_date_str = ed.strftime("%Y-%m-%d")

    history = auth.get_login_history(
        limit=500,
        start_date=start_date_str,
        end_date=end_date_str,
    )

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

    count_col, _ = st.columns([3.5, 2.5])
    with count_col:
        render_html(f"<p style='color: {theme['text_muted']}; font-size: 13px; margin: 8px 0;'>Showing <b>{len(filtered_logs)}</b> matching audit events</p>")

    # Guarded Audit Retention Purge — full width, styled expander
    min_ret = int(auth.get_platform_setting("audit_retention_days", 90))

    # Inject scoped CSS to give the purge expander a subtle amber border instead of Streamlit's default red.
    render_html("""
        <style>
        div[data-testid="stExpander"] details,
        .stExpander details {
            border-color: rgba(180, 83, 9, 0.30) !important;
            border-width: 1px !important;
            border-radius: 10px !important;
        }
        div[data-testid="stExpander"] summary,
        .stExpander summary {
            border-radius: 10px !important;
        }
        div[data-testid="stExpander"] details[open],
        .stExpander details[open] {
            border-color: rgba(180, 83, 9, 0.35) !important;
        }
        </style>
    """)

    with st.expander(f"🛡️ Guarded Audit Retention Purge  ·  Minimum retention window: {min_ret} days"):
        render_html(f"""
            <div style="padding: 10px 14px 6px 14px; background: {theme['warning_bg']}; border: 1px solid rgba(180,83,9,0.3); border-radius: 8px; margin-bottom: 12px; font-size: 13px; color: {theme['warning_text']}; line-height: 1.55;">
                <b>🛡️ Policy Safeguard:</b> Bulk "Purge All" is blocked.
                Only non-immutable entries older than the retention window (&ge;&nbsp;{min_ret}&nbsp;days) can be purged,
                and only after automatic CSV archiving and a typed compliance reason.
                Immutable events (logins, role changes, purge records) are always preserved.
            </div>
        """)
        p_col1, p_col2 = st.columns([1, 2])
        with p_col1:
            purge_days = st.number_input(
                "Purge entries older than (days)",
                min_value=min_ret,
                max_value=3650,
                value=min_ret,
                step=15,
                key="adm_log_purge_days_input",
            )
        with p_col2:
            purge_reason = st.text_input("Compliance Reason for Purge (required)", "", key="adm_log_purge_reason_input")
        conf_clear = st.checkbox("✅ Confirm archive & retention purge", key="adm_chk_clear_log")
        if st.button("🗑️ Archive & Purge Old Audit Entries", type="primary", use_container_width=True, key="adm_btn_clear_log"):
            if conf_clear:
                res = auth.purge_audit_history(
                    older_than_days=purge_days,
                    reason=purge_reason,
                    current_admin_user=current_admin_user,
                )
                if res[0]:
                    st.session_state["adm_last_purge_csv"] = res.csv_data
                    st.success(f"✓ {res[1]}")
                    st.rerun()
                else:
                    st.error(res[1])
            else:
                st.warning("Please check the confirmation box before proceeding.")
        if st.session_state.get("adm_last_purge_csv"):
            st.download_button(
                "📥 Download Pre-Purge Archive CSV",
                data=st.session_state["adm_last_purge_csv"],
                file_name=f"PaperIQ_PrePurge_Archive_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_dl_pre_purge_csv",
            )

    if not filtered_logs:
        st.info("No login audit events recorded or matched by current filters.")
        return

    # Table Header
    render_html(f"""
        <div style="display: grid; grid-template-columns: 0.4fr 1.5fr 1.2fr 1.3fr 1.3fr 1.3fr 2.0fr 0.9fr 0.9fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 11px; color: {theme['text_muted']}; text-transform: uppercase;">
            <div>#</div>
            <div>Timestamp</div>
            <div>Actor</div>
            <div>Action</div>
            <div>Outcome</div>
            <div>Target</div>
            <div>Details</div>
            <div>IP</div>
            <div>Chain Hash</div>
        </div>
        """)

    for idx, log in enumerate(filtered_logs[:100]):
        is_success = "Success" in log.get("status", "") or "Registered" in log.get("status", "") or "Provisioned" in log.get("status", "") or "Purge" in log.get("status", "")
        stat_color = theme["success_text"] if is_success else theme["error_text"]
        stat_bg = theme["success_bg"] if is_success else theme["error_bg"]
        act_tag = log.get("action_type", "AUTH")
        rhash = str(log.get("row_hash") or "")[:10]

        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.4fr 1.5fr 1.2fr 1.3fr 1.3fr 1.3fr 2.0fr 0.9fr 0.9fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12px; align-items: center;">
                <div style="color: {theme['text_muted']};">{idx+1}</div>
                <div style="color: {theme['text_secondary']}; font-family: monospace; font-size: 11px;">{safe_text(log.get('login_time', ''))}</div>
                <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(log.get('username', ''))}</div>
                <div><span style="font-size: 10px; font-weight: 700; color: {theme['accent_purple']}; background: {theme['accent_primary_subtle']}; padding: 2px 6px; border-radius: 4px;">{safe_text(act_tag)}</span></div>
                <div><span style="font-size: 10px; font-weight: 700; color: {stat_color}; background: {stat_bg}; padding: 2px 6px; border-radius: 4px;">{safe_text(log.get('status', ''))}</span></div>
                <div style="color: {theme['text_secondary']}; font-size: 11px;">{safe_text(str(log.get('target', ''))[:22])}</div>
                <div style="color: {theme['text_muted']}; font-size: 11px;">{safe_text(str(log.get('details', ''))[:48])}</div>
                <div style="color: {theme['text_muted']}; font-size: 10.5px; font-family: monospace;">{safe_text(log.get('ip_address', '127.0.0.1'))}</div>
                <div style="color: {theme['text_muted']}; font-size: 10.5px; font-family: monospace;">{safe_text(rhash)}…</div>
            </div>
            """)


# ===========================================================================
# 4. INSTITUTIONAL SAVED PAPERS REPOSITORY (Parts 3, 4.3, 4.4)
# ===========================================================================
def render_saved_papers_view(theme, navigate_to, load_analysis_into_session=None, current_admin_user="admin"):
    """Renders the Institutional Saved Papers Library with duplicate cleanup and self-contained inspection."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Institutional Saved Papers Library</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Centrally curated public reference manuscripts and benchmark papers (distinct from private user analyses).
            </p>
        </div>
        """)

    papers = auth.get_saved_papers()
    dup_groups = auth.find_repository_duplicates()

    # Part 4.3: Duplicate Detection & Cleanup Banner
    if dup_groups:
        total_dup_extra = sum(len(g["duplicates"]) for g in dup_groups)
        with st.expander(f"🔍 Duplicate Repository Papers Detected ({len(dup_groups)} group(s), {total_dup_extra} redundant copy/copies)", expanded=True):
            st.write("The following repository manuscripts have multiple identical or same-title entries. Cleaning duplicates keeps the **newest** entry and removes older copies.")
            for g in dup_groups:
                keep_p = g["keep"]
                rem_ids = ", ".join(f"{d['paper_id']} ({d.get('uploaded_at', '')[:16]})" for d in g["duplicates"])
                st.markdown(
                    f"- **{safe_text(g['title'])}** — **{g['count']} copies** "
                    f"(Keep newest: `{keep_p['paper_id']}` uploaded `{keep_p.get('uploaded_at', '')[:16]}`; "
                    f"Remove older: `{rem_ids}`)"
                )
            conf_dedup = st.checkbox("Confirm removing older duplicate repository entries (keeps newest copy of each)", key="adm_chk_repo_dedup")
            if st.button("Remove Older Duplicates Now", type="primary", key="adm_btn_repo_dedup"):
                ok, msg, _ = auth.remove_duplicate_repository_papers(
                    current_admin_user=current_admin_user,
                    confirm=conf_dedup,
                )
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.error(msg)

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
            data=auth.export_repository_csv(current_admin_user=current_admin_user),
            file_name=f"PaperIQ_Repository_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_repo",
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
        pid_key = p.get("paper_id") or p.get("id", idx)
        with st.container(border=True):
            col_info, col_score, col_act1, col_act2, col_del = st.columns([4, 1.8, 1.5, 1.5, 1.2])
            with col_info:
                render_html(f"""
                    <div style="font-weight: 700; color: {theme['text_primary']}; font-size: 15px;">📄 {safe_text(p.get('title', 'Research Paper'))}</div>
                    <div style="color: {theme['text_muted']}; font-size: 12px; margin-top: 3px;">
                        ID: <code>{safe_text(pid_key)}</code> &nbsp;•&nbsp;
                        Authors: <b style="color: {theme['text_secondary']};">{safe_text(p.get('authors', 'Institutional Authors'))}</b> &nbsp;•&nbsp;
                        Domain: <b style="color: {theme['info_text']};">{safe_text(p.get('domain', 'Interdisciplinary & General Research'))}</b> &nbsp;•&nbsp;
                        Uploaded: {safe_text(p.get('uploaded_at', ''))} by <i>{safe_text(p.get('uploaded_by', 'admin'))}</i>
                    </div>
                    """)
            with col_score:
                render_html(f"""
                    <div style="font-size: 14.5px; font-weight: 800; color: {theme['accent_purple']}; margin-top: 6px;">
                        Score: {float(p.get('score', 0.0)):.1f} / 100 &nbsp;
                        <span style="background: {theme['badge_role_bg']}; color: {theme['badge_role_text']}; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 8px; border: 1px solid {theme['badge_role_border']};">Grade {safe_text(p.get('grade', 'B'))}</span>
                    </div>
                    """)
            with col_act1:
                inspect_key = f"adm_inspect_repo_{pid_key}"
                is_open = st.session_state.get(inspect_key, False)
                btn_lbl = "Hide Details" if is_open else "Inspect Summary"
                if st.button(btn_lbl, key=f"adm_saved_view_{p.get('id', idx)}", use_container_width=True):
                    st.session_state[inspect_key] = not is_open
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
                        use_container_width=True,
                    )
                elif p.get("file_bytes"):
                    st.download_button(
                        "Download Paper",
                        data=bytes(p["file_bytes"]),
                        file_name=p.get("filename", "Paper.pdf"),
                        mime="application/octet-stream",
                        key=f"adm_saved_down_orig_{p.get('id', idx)}",
                        use_container_width=True,
                    )
            with col_del:
                if st.button("Delete", key=f"adm_saved_del_{p.get('id', idx)}", use_container_width=True):
                    st.session_state[f"confirm_del_saved_{pid_key}"] = True
                    st.rerun()

            if st.session_state.get(f"adm_inspect_repo_{pid_key}", False):
                res_dict = {}
                if p.get("results_json"):
                    try:
                        res_dict = json.loads(p["results_json"])
                    except Exception:
                        res_dict = {}
                exec_sum = res_dict.get("summary") or res_dict.get("executive_summary") or "Curated institutional benchmark manuscript."
                render_html(f"""
                    <div style="margin-top: 10px; padding: 12px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px; font-size: 13px; color: {theme['text_secondary']};">
                        <b>Institutional Repository Record Metadata:</b><br>
                        • <b>Filename:</b> <code>{safe_text(p.get('filename', 'N/A'))}</code> &nbsp;|&nbsp;
                        <b>SHA-256 Content Hash:</b> <code>{safe_text((p.get('content_hash') or 'N/A')[:24])}…</code><br>
                        • <b>Overview:</b> {safe_text(str(exec_sum)[:500])}
                    </div>
                    """)

            if st.session_state.get(f"confirm_del_saved_{pid_key}", False):
                st.warning(f"Delete paper '{p.get('title')}' from institutional repository?")
                c_c1, c_c2 = st.columns([1, 1])
                with c_c1:
                    if st.button("Confirm Delete", type="primary", key=f"btn_conf_del_saved_{pid_key}"):
                        auth.delete_saved_paper(pid_key, current_admin_user=current_admin_user)
                        st.session_state[f"confirm_del_saved_{pid_key}"] = False
                        st.success("✓ Paper deleted from repository.")
                        st.rerun()
                with c_c2:
                    if st.button("Cancel", key=f"btn_canc_del_saved_{pid_key}"):
                        st.session_state[f"confirm_del_saved_{pid_key}"] = False
                        st.rerun()


# ===========================================================================
# 5. UPLOAD HISTORY VIEW (Part 3 Privacy — Aggregate Counts & Masked Filenames)
# ===========================================================================
def render_upload_history_view(theme, current_admin_user="admin"):
    """
    Renders the Document Upload Audit History page.
    Part 3 Privacy: Shows aggregate counts by default and masks user filenames as 'abc….pdf'.
    """
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Document Upload Telemetry & Masked Audit History</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Aggregate document ingestion telemetry. To protect Student and Researcher document privacy, private filenames are masked (<code>abc….pdf</code>) in the Administrator workspace and CSV exports.
            </p>
        </div>
        """)

    uploads = auth.get_upload_history(username=None, limit=500, mask_filenames=True)

    # Aggregate Summary Cards (Part 3: show aggregate counts by default)
    total_upl = len(uploads)
    personal_upl = sum(1 for u in uploads if u.get("target", "Personal") == "Personal")
    repo_upl = sum(1 for u in uploads if u.get("target") == "Repository")
    total_kb = sum(float(u.get("file_size_kb") or 0.0) for u in uploads)

    u_m1, u_m2, u_m3, u_m4 = st.columns(4)
    u_m1.metric("Total Upload Events", total_upl)
    u_m2.metric("User Workspace Uploads", personal_upl)
    u_m3.metric("Institutional Repository Uploads", repo_upl)
    u_m4.metric("Total Volume Processed", f"{total_kb / 1024.0:.2f} MB" if total_kb >= 1024 else f"{total_kb:.1f} KB")

    st.write("")

    c_u1, c_u2, c_u3 = st.columns([2.8, 1.6, 1.6])
    with c_u1:
        search_f = st.text_input("🔍 Filter by username or file format", "", key="adm_upl_search")
    with c_u2:
        target_opts = ["All Destinations", "Personal", "Repository"]
        sel_target = st.selectbox("Filter by Destination", target_opts, key="adm_upl_target_filter")
    with c_u3:
        st.write("")
        st.write("")
        st.download_button(
            "📥 Export Masked CSV",
            data=auth.export_upload_history_csv(limit=500, current_admin_user=current_admin_user),
            file_name=f"PaperIQ_Upload_Telemetry_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="adm_btn_export_uploads_masked",
        )

    filtered = [
        u for u in uploads
        if (not search_f or search_f.lower() in f"{u.get('masked_filename','')} {u.get('username','')} {u.get('file_type','')}".lower())
        and (sel_target == "All Destinations" or u.get("target") == sel_target)
    ]

    render_html(f"<p style='color: {theme['text_muted']}; font-size: 13px; margin: 6px 0 14px 0;'>Showing <b>{len(filtered)}</b> of <b>{len(uploads)}</b> masked upload records</p>")

    if not filtered:
        st.info("No document upload history records found.")
        return

    # Table Header
    render_html(f"""
        <div style="display: grid; grid-template-columns: 0.5fr 2fr 1.5fr 2.2fr 1fr 1.2fr 1.2fr; padding: 10px 14px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 12px; color: {theme['text_muted']}; text-transform: uppercase;">
            <div>#</div>
            <div>Timestamp</div>
            <div>Uploader</div>
            <div>Masked Filename</div>
            <div>Format</div>
            <div>Size (KB)</div>
            <div>Scope</div>
        </div>
        """)

    for idx, u in enumerate(filtered):
        t_color = theme["accent_purple"] if u.get("target") == "Repository" else theme["info_text"]
        t_bg = theme["accent_primary_subtle"] if u.get("target") == "Repository" else theme["info_bg"]
        masked_fn = u.get("masked_filename") or auth.mask_filename(u.get("filename", ""))
        render_html(f"""
            <div style="display: grid; grid-template-columns: 0.5fr 2fr 1.5fr 2.2fr 1fr 1.2fr 1.2fr; padding: 10px 14px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 13px; align-items: center;">
                <div style="color: {theme['text_muted']};">{idx+1}</div>
                <div style="color: {theme['text_secondary']}; font-family: monospace;">{safe_text(u.get('upload_time', ''))}</div>
                <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(u.get('username', ''))}</div>
                <div style="color: {theme['text_primary']}; font-weight: 600; font-family: monospace;">📄 {safe_text(masked_fn)}</div>
                <div style="color: {theme['text_muted']}; font-weight: 600;">{safe_text(str(u.get('file_type', '')).upper())}</div>
                <div style="color: {theme['text_secondary']};">{float(u.get('file_size_kb', 0.0)):.1f} KB</div>
                <div><span style="font-size: 11px; font-weight: 700; color: {t_color}; background: {t_bg}; padding: 2px 7px; border-radius: 6px;">{safe_text(u.get('target', 'Personal'))}</span></div>
            </div>
            """)


# ===========================================================================
# 6. UPLOAD RESEARCH PAPER TO INSTITUTIONAL REPOSITORY (Part 4.3 & 1.6)
# ===========================================================================
def render_upload_research_paper_view(theme, navigate_to, current_admin_user, extract_text_fn, evaluate_fn, summarize_fn, report_fn):
    """Renders the Administrator paper upload interface for the institutional repository with duplicate detection."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Upload Paper to Institutional Repository</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Add curated benchmark research papers and public reference manuscripts to the shared institutional library.
            </p>
        </div>
        """)

    max_mb = int(auth.get_platform_setting("max_upload_size_mb", 30))
    allowed_raw = str(auth.get_platform_setting("allowed_formats", "PDF,DOCX,TXT"))
    allowed_exts = [x.strip().lower() for x in allowed_raw.split(",") if x.strip()]

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>Manuscript Details</h3>")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            paper_title = st.text_input("Manuscript Display Title", placeholder="e.g. Deep Residual Learning for Image Recognition", key="adm_up_title")
            paper_authors = st.text_input("Authors / Institutional Affiliation", placeholder="e.g. K. He, X. Zhang, S. Ren, J. Sun", key="adm_up_authors")
        with col_m2:
            paper_domain = st.selectbox("Academic Discipline / Domain", auth.CANONICAL_DISCIPLINES, key="adm_up_domain")
            is_public_flag = st.checkbox("Make Available in Institutional Shared Library", value=True, key="adm_up_public")

        render_html("<hr style='margin: 14px 0;'>")
        upload_mode = st.radio("Ingestion Mode", [f"📁 File Upload ({', '.join(e.upper() for e in allowed_exts)})", "📝 Paste Manuscript Text"], horizontal=True, key="adm_up_mode")

        extracted_text = ""
        orig_filename = ""
        file_bytes_data = b""
        file_size_kb = 0.0
        file_ext = "TXT"

        if "File Upload" in upload_mode:
            uploaded_file = st.file_uploader(
                f"Select Academic Document (Max {max_mb} MB | Allowed: {', '.join(e.upper() for e in allowed_exts)})",
                type=allowed_exts if allowed_exts else ["pdf", "docx", "txt"],
                key="adm_file_uploader",
            )
            if uploaded_file is not None:
                orig_filename = uploaded_file.name
                file_bytes_data = uploaded_file.getvalue()
                file_size_kb = len(file_bytes_data) / 1024.0
                file_ext = orig_filename.split(".")[-1].upper() if "." in orig_filename else "TXT"

                if file_ext.lower() not in allowed_exts:
                    st.error(f"Error: File format '.{file_ext.lower()}' is currently disabled in Platform Settings.")
                    auth.log_processing_event(current_admin_user, file_ext, file_size_kb, stage="extraction", status="failed", failure_reason="unsupported type")
                elif len(file_bytes_data) > max_mb * 1024 * 1024:
                    st.error(f"Error: Document exceeds maximum allowable size ({max_mb} MB).")
                    auth.log_processing_event(current_admin_user, file_ext, file_size_kb, stage="extraction", status="failed", failure_reason="too large")
                else:
                    t0 = time.perf_counter()
                    raw_extracted = extract_text_fn(uploaded_file)
                    dur_ms = (time.perf_counter() - t0) * 1000.0
                    if isinstance(raw_extracted, str) and raw_extracted.startswith("__ERROR_"):
                        reason_map = {
                            "__ERROR_SCANNED_PDF__": "scanned PDF, no text layer",
                            "__ERROR_PASSWORD_PROTECTED__": "password-protected",
                            "__ERROR_FILE_TOO_LARGE__": "too large",
                            "__ERROR_CORRUPTED_PDF__": "corrupted file",
                            "__ERROR_CORRUPTED_DOCX__": "corrupted file",
                            "__ERROR_EMPTY_DOCUMENT__": "empty document",
                        }
                        f_reason = reason_map.get(raw_extracted, "extraction error")
                        auth.log_processing_event(current_admin_user, file_ext, file_size_kb, stage="extraction", status="failed", failure_reason=f_reason, duration_ms=dur_ms)
                        st.error(f"⚠️ Document Extraction Failed ({f_reason}).")
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

        # Part 4.3: Check for duplicate title or SHA-256 content hash before saving
        candidate_title = (paper_title.strip() if paper_title else orig_filename).strip()
        existing_dups = auth.check_repository_duplicate(title=candidate_title, file_bytes=file_bytes_data) if (candidate_title or file_bytes_data) else []
        allow_dup_override = True
        if existing_dups:
            dup_first = existing_dups[0]
            st.warning(
                f"⚠️ **Duplicate Repository Paper Detected:** `{dup_first.get('title')}` "
                f"(ID: `{dup_first.get('paper_id')}`, uploaded `{dup_first.get('uploaded_at')}`) "
                "already has the same title or SHA-256 content hash."
            )
            allow_dup_override = st.checkbox(
                "Override duplicate warning and save a new copy to the repository anyway",
                value=False,
                key="adm_up_dup_override_chk",
            )

        st.write("")
        if st.button("Process & Save to Institutional Repository", type="primary", use_container_width=True, key="adm_btn_process_paper"):
            if not extracted_text:
                st.warning("Please upload or paste a research document with valid extractable text.")
            elif len(extracted_text.split()) < 30:
                st.warning(f"Please provide a research manuscript containing at least 30 words (currently {len(extracted_text.split())} words).")
            elif existing_dups and not allow_dup_override:
                st.error("Duplicate safeguard active: Please check the duplicate override box above if you intend to save a duplicate manuscript.")
            else:
                with st.spinner("Analyzing manuscript and compiling institutional report..."):
                    t_start = time.perf_counter()
                    try:
                        eval_res = evaluate_fn(extracted_text, filename=orig_filename, domain_override=paper_domain)
                        eval_res["title"] = paper_title.strip() if paper_title else orig_filename
                        comp_score = eval_res.get("overall_score", 70.0)
                        comp_grade = eval_res.get("grade", "B")

                        sum_res = summarize_fn(extracted_text, summary_type="Medium", filename=orig_filename, doc_title=paper_title or orig_filename)
                        pdf_report = report_fn(eval_res, sum_res, original_filename=orig_filename, title=paper_title or orig_filename)

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
                            is_public=1 if is_public_flag else 0,
                            allow_duplicate=True,
                        )

                        auth.record_upload(
                            username=current_admin_user,
                            filename=orig_filename,
                            file_type=file_ext,
                            file_size_kb=file_size_kb,
                            status="Repository Ingested",
                            target="Repository",
                        )
                        dur_ms = (time.perf_counter() - t_start) * 1000.0
                        auth.log_processing_event(
                            user_id=current_admin_user,
                            file_type=file_ext,
                            file_size_kb=file_size_kb,
                            stage="repository_analysis",
                            status="success",
                            duration_ms=dur_ms,
                        )

                        st.success(f"✓ Manuscript successfully analyzed and added to the Institutional Repository! (Paper ID: {paper_id})")
                        if st.button("📁 View in Institutional Saved Papers →", key="adm_btn_goto_view_saved"):
                            navigate_to("📁 Saved Papers")
                            st.rerun()

                    except Exception as e:
                        dur_ms = (time.perf_counter() - t_start) * 1000.0
                        auth.log_app_error(type(e).__name__, str(e), page="Upload Research Paper", role="Administrator", user_id=current_admin_user)
                        auth.log_processing_event(
                            user_id=current_admin_user,
                            file_type=file_ext,
                            file_size_kb=file_size_kb,
                            stage="repository_analysis",
                            status="failed",
                            failure_reason=str(e),
                            duration_ms=dur_ms,
                        )
                        st.error("Failed to process manuscript due to an internal processing error. The incident has been logged in System Health.")


# ===========================================================================
# 7. RESEARCH ACTIVITY OVERVIEW — ANALYTICS & REPORTS (Parts 1.4, 3, 4.4, 4.6)
# ===========================================================================
def render_analytics_view(theme, current_admin_user="admin"):
    """Renders aggregate institutional intelligence, processing metrics, date-range filters, and readable charts."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Research Activity Overview — Analytics & Intelligence</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Aggregate platform telemetry, processing performance, discipline distributions, and export hub (privacy-safe aggregate statistics only).
            </p>
        </div>
        """)

    # Part 1.4(b) & (c): Date-Range Selector & Exclude Test Accounts Toggle
    ctrl_col1, ctrl_col2 = st.columns([3.5, 2.5])
    with ctrl_col1:
        date_range_opt = st.radio(
            "Telemetry Date Range",
            ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom"],
            horizontal=True,
            key="adm_anl_date_range_radio",
        )
    with ctrl_col2:
        st.write("")
        exclude_test = st.checkbox(
            "Exclude test/demo accounts from analytics",
            value=False,
            key="adm_anl_exclude_test_toggle",
        )

    start_date_str = None
    end_date_str = None
    today_d = datetime.now().date()
    if date_range_opt == "Last 7 Days":
        start_date_str = (today_d - timedelta(days=7)).strftime("%Y-%m-%d")
    elif date_range_opt == "Last 30 Days":
        start_date_str = (today_d - timedelta(days=30)).strftime("%Y-%m-%d")
    elif date_range_opt == "Last 90 Days":
        start_date_str = (today_d - timedelta(days=90)).strftime("%Y-%m-%d")
    elif date_range_opt == "Custom":
        cc1, cc2 = st.columns(2)
        with cc1:
            sd = st.date_input("Start Date", value=today_d - timedelta(days=30), key="adm_anl_cust_start")
            start_date_str = sd.strftime("%Y-%m-%d")
        with cc2:
            ed = st.date_input("End Date", value=today_d, key="adm_anl_cust_end")
            end_date_str = ed.strftime("%Y-%m-%d")

    stats = auth.get_system_stats(exclude_test_accounts=exclude_test)
    saved_papers = auth.get_saved_papers()
    platform_analyses = auth.get_all_analyses_summary(
        exclude_test_accounts=exclude_test,
        start_date=start_date_str,
        end_date=end_date_str,
    )
    login_events = auth.get_login_history(
        limit=1000,
        start_date=start_date_str,
        end_date=end_date_str,
        exclude_test_accounts=exclude_test,
    )
    proc_stats = auth.get_processing_stats(
        start_date=start_date_str,
        end_date=end_date_str,
        exclude_test_accounts=exclude_test,
    )

    # Summary Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registered Users", stats["total_users"])
    m2.metric("Analyses in Range", len(platform_analyses))
    m3.metric("Repository Manuscripts", len(saved_papers))
    m4.metric("Audit Events in Range", len(login_events))

    st.write("")
    # Part 1.4(a): Processing Telemetry Summary Row
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Processing Runs (Succeeded / Failed)", f"{proc_stats['succeeded']} / {proc_stats['failed']}")
    p2.metric("Processing Success Rate", f"{proc_stats['success_rate']:.1f}%")
    p3.metric("Avg Processing Duration", f"{proc_stats['avg_duration_ms']:.0f} ms")
    by_ft = proc_stats.get("by_file_type", {})
    p4.metric("By Format (PDF / DOCX / TXT)", f"{by_ft.get('PDF', 0)} / {by_ft.get('DOCX', 0)} / {by_ft.get('TXT', 0)}")

    render_html("<br>")

    # Chart Row 1: Role Distribution & Security Events
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>👥 User Role Distribution</h4>")
            roles_data = {
                "Student": stats["student_count"],
                "Researcher": stats["researcher_count"],
                "Administrator": stats["admin_count"],
            }
            if stats["legacy_count"] > 0:
                roles_data["Legacy Accounts"] = stats["legacy_count"]

            fig_roles = go.Figure(data=[go.Pie(
                labels=list(roles_data.keys()),
                values=list(roles_data.values()),
                hole=0.45,
                marker=dict(colors=[theme["info_text"], theme["accent_primary"], theme["error_text"], theme["warning_text"]]),
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
                hole=0.45,
                marker=dict(colors=[theme["success_text"], theme["error_text"], theme["accent_purple"]]),
            )])
            layout_a = get_chart_layout_dict(theme)
            layout_a["height"] = 280
            fig_auth.update_layout(**layout_a)
            st.plotly_chart(fig_auth, use_container_width=True)

    render_html("<br>")

    # Part 1.4(a): Processing Runs by Day & Uploads per Role
    c_proc1, c_proc2 = st.columns(2)
    with c_proc1:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>⚙️ Processing Runs by Day (Succeeded vs Failed)</h4>")
            by_day = proc_stats.get("by_day", {})
            if by_day:
                days_x = list(by_day.keys())
                succ_y = [by_day[d]["success"] for d in days_x]
                fail_y = [by_day[d]["failed"] for d in days_x]
                fig_pday = go.Figure()
                fig_pday.add_trace(go.Bar(name="Succeeded", x=days_x, y=succ_y, marker_color=theme.get("success_text", "#34D399"), text=succ_y, textposition="auto"))
                fig_pday.add_trace(go.Bar(name="Failed", x=days_x, y=fail_y, marker_color=theme.get("error_text", "#F87171"), text=fail_y, textposition="auto"))
                layout_pd = get_chart_layout_dict(theme)
                layout_pd["barmode"] = "stack"
                layout_pd["height"] = 270
                layout_pd["xaxis"]["title"] = "Date"
                layout_pd["yaxis"]["title"] = "Processing Events"
                max_day_v = max([by_day[d]["total"] for d in days_x] or [1])
                layout_pd["yaxis"]["dtick"] = max(1, math.ceil(max_day_v / 5))
                fig_pday.update_layout(**layout_pd)
                st.plotly_chart(fig_pday, use_container_width=True)
            else:
                st.info("No processing events recorded in the selected date range.")

    with c_proc2:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>📤 Uploads & Processing Activity by Role</h4>")
            by_role = proc_stats.get("by_role", {})
            # Supplement with analysis counts per role if greater
            for a in platform_analyses:
                rname = a.get("role", "Student")
                by_role[rname] = max(by_role.get(rname, 0), sum(1 for x in platform_analyses if x.get("role", "Student") == rname))
            r_x = list(by_role.keys())
            r_y = list(by_role.values())
            fig_urole = go.Figure(data=[go.Bar(
                x=r_x,
                y=r_y,
                marker_color=[theme.get("info_text", "#38BDF8"), theme.get("accent_purple", "#A78BFA"), theme.get("warning_text", "#FBBF24")][:len(r_x)],
                text=r_y,
                textposition="outside",
                cliponaxis=False,
            )])
            layout_ur = get_chart_layout_dict(theme)
            layout_ur["height"] = 270
            layout_ur["xaxis"]["title"] = "Academic Role"
            layout_ur["yaxis"]["title"] = "Processed Documents"
            max_ur = max(r_y or [1])
            layout_ur["yaxis"]["dtick"] = max(1, math.ceil(max_ur / 5))
            fig_urole.update_layout(**layout_ur)
            st.plotly_chart(fig_urole, use_container_width=True)

    render_html("<br>")

    # Dataset Scope Selector for Academic Domain & Quality Scoring
    render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>🔬 Academic Intelligence Dataset Scope</h4>")
    scope_choice = st.radio(
        "Select Dataset Scope for Discipline Breakdown & Quality Distributions",
        [
            f"🌐 Platform-Wide User Analyses ({len(platform_analyses)} records)",
            f"🏛️ Institutional Saved Repository ({len(saved_papers)} benchmark manuscripts)",
        ],
        horizontal=True,
        key="adm_anl_dataset_scope",
    )

    is_platform_scope = "Platform-Wide" in scope_choice
    active_dataset = platform_analyses if is_platform_scope else saved_papers

    # Chart Row 2: Academic Disciplines (Part 4.4 & 4.6) & Quality Scores
    c_chart3, c_chart4 = st.columns(2)

    with c_chart3:
        with st.container(border=True):
            header_txt = "📚 Research Disciplines (Platform-Wide)" if is_platform_scope else "📚 Research Disciplines (Repository)"
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>{header_txt}</h4>")
            domain_counts = {}
            for item in active_dataset:
                d = auth.normalize_discipline(item.get("domain"))
                domain_counts[d] = domain_counts.get(d, 0) + 1

            if domain_counts:
                sorted_doms = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
                dom_labels = [k for k, _ in sorted_doms]
                dom_vals = [v for _, v in sorted_doms]
                max_dom_v = max(dom_vals or [1])

                fig_dom = go.Figure(data=[go.Bar(
                    x=dom_labels,
                    y=dom_vals,
                    marker_color=theme.get("accent_purple", "#A78BFA"),
                    text=dom_vals,
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(color=theme.get("chart_font", "#E2E8F0"), size=12),
                )])
                layout_d = get_chart_layout_dict(theme)
                layout_d["height"] = 320
                layout_d["margin"] = dict(l=45, r=20, t=35, b=85)
                layout_d["xaxis"]["title"] = "Canonical Academic Discipline"
                layout_d["xaxis"]["tickangle"] = -20
                layout_d["yaxis"]["title"] = "Document Count"
                layout_d["yaxis"]["dtick"] = max(1, math.ceil(max_dom_v / 6))
                layout_d["yaxis"]["range"] = [0, max_dom_v * 1.22]
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
                    opacity=0.88,
                )])
                layout_s = get_chart_layout_dict(theme)
                layout_s["height"] = 320
                layout_s["xaxis"]["title"] = f"Overall Score (0-100) — Mean: {avg_sc:.1f}"
                layout_s["xaxis"]["range"] = [0, 100]
                layout_s["yaxis"]["title"] = "Document Frequency"
                layout_s["yaxis"]["dtick"] = 1 if len(scores) <= 15 else None
                fig_sc.update_layout(**layout_s)
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("No scored documents available for histogram.")

    render_html("<br>")

    # Export Center
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>📥 Institutional Data Export Hub</h3>")
        st.caption("Generate sanitized, formula-injection protected CSV spreadsheets of system data. Passwords, hashes, secrets, and private user filenames are strictly excluded.")

        ex1, ex2, ex3, ex4 = st.columns(4)
        with ex1:
            st.download_button(
                "Export All Users CSV",
                data=auth.export_users_csv(current_admin_user=current_admin_user),
                file_name=f"PaperIQ_Users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_users",
            )
        with ex2:
            st.download_button(
                "Export Audit Logs CSV",
                data=auth.export_audit_csv(limit=1000, current_admin_user=current_admin_user),
                file_name=f"PaperIQ_Audit_Logs_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_audits",
            )
        with ex3:
            st.download_button(
                "Export Repository CSV",
                data=auth.export_repository_csv(current_admin_user=current_admin_user),
                file_name=f"PaperIQ_Repository_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_repo",
            )
        with ex4:
            st.download_button(
                "Export Masked Uploads CSV",
                data=auth.export_upload_history_csv(limit=500, exclude_test_accounts=exclude_test, current_admin_user=current_admin_user),
                file_name=f"PaperIQ_Uploads_Masked_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_anl_exp_uploads",
            )


# ===========================================================================
# 8. SYSTEM HEALTH & DIAGNOSTICS (Part 1.2)
# ===========================================================================
def render_system_health_view(theme, current_admin_user="admin"):
    """Renders real-time SQLite health, Recent Application Errors, Processing Failures, and Dependency Status."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">System Health & Diagnostics</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Live database connectivity, application error telemetry, document processing failure diagnostics, and runtime dependency verification.
            </p>
        </div>
        """)

    health = auth.get_system_health()
    status_str = health["status"]
    s_col, s_bg = _status_badge_colors(status_str, theme)
    err_counts = health.get("error_counts", {"errors_24h": 0, "errors_7d": 0, "total_errors": 0})

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        render_html(f"""
            <div style="padding: 14px; background: {theme['bg_card']}; border: 1px solid {theme['border_color']}; border-radius: 8px;">
                <div style="font-size: 12px; color: {theme['text_muted']}; text-transform: uppercase; font-weight: 700;">System Status</div>
                <div style="font-size: 20px; font-weight: 800; color: {s_col}; margin-top: 4px;">
                    <span style="background: {s_bg}; padding: 3px 10px; border-radius: 6px;">● {safe_text(status_str)}</span>
                </div>
                <div style="font-size: 11.5px; color: {theme['text_secondary']}; margin-top: 4px;">{safe_text(health.get('status_reason', ''))}</div>
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
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 10px 0;'>🗄️ Database Table Counts</h4>")
        tbl_cols = st.columns(7)
        names = ["users", "analysis_history", "login_history", "saved_papers", "upload_history", "app_errors", "processing_events"]
        labels = ["Users", "Analyses", "Audit Logs", "Saved Papers", "Upload Trail", "App Errors", "Proc Events"]
        for i, (name, lbl) in enumerate(zip(names, labels)):
            with tbl_cols[i]:
                st.metric(lbl, health["table_counts"].get(name, 0))

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.2(a): Recent Application Errors Table
    # -----------------------------------------------------------------------
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>🚨 Recent Application Errors (`app_errors`)</h4>")
        st.caption("Sanitized runtime exception log (truncated to 300 chars; file paths, usernames, passwords, and document contents are stripped).")

        ec1, ec2, ec3, ec4 = st.columns([1.4, 1.4, 1.4, 2.2])
        ec1.metric("Errors (Last 24h)", err_counts.get("errors_24h", 0))
        ec2.metric("Errors (Last 7d)", err_counts.get("errors_7d", 0))
        ec3.metric("Total Logged Errors", err_counts.get("total_errors", 0))
        with ec4:
            err_date_filter = st.selectbox(
                "Filter Error Log by Date Range",
                ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"],
                key="adm_health_err_date_filter",
            )

        err_start = None
        now_dt = datetime.now()
        if err_date_filter == "Last 24 Hours":
            err_start = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        elif err_date_filter == "Last 7 Days":
            err_start = (now_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        elif err_date_filter == "Last 30 Days":
            err_start = (now_dt - timedelta(days=30)).strftime("%Y-%m-%d")

        app_errors_list = auth.get_app_errors(limit=100, start_date=err_start)
        if app_errors_list:
            render_html(f"""
                <div style="display: grid; grid-template-columns: 0.5fr 1.6fr 1.4fr 1.2fr 1.4fr 3.2fr 1.0fr; padding: 9px 12px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 11.5px; color: {theme['text_muted']}; text-transform: uppercase;">
                    <div>ID</div>
                    <div>Timestamp</div>
                    <div>Page / Module</div>
                    <div>Role</div>
                    <div>Error Type</div>
                    <div>Short Message (Sanitized)</div>
                    <div>Stack Hash</div>
                </div>
                """)
            for er in app_errors_list[:50]:
                render_html(f"""
                    <div style="display: grid; grid-template-columns: 0.5fr 1.6fr 1.4fr 1.2fr 1.4fr 3.2fr 1.0fr; padding: 9px 12px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12px; align-items: center;">
                        <div style="color: {theme['text_muted']};">#{er.get('id')}</div>
                        <div style="font-family: monospace; color: {theme['text_secondary']};">{safe_text(er.get('timestamp', ''))}</div>
                        <div style="font-weight: 600; color: {theme['text_primary']};">{safe_text(er.get('page', 'Unknown'))}</div>
                        <div style="color: {theme['text_secondary']};">{safe_text(er.get('role', 'Unknown'))}</div>
                        <div><span style="font-size: 11px; font-weight: 700; color: {theme['error_text']}; background: {theme['error_bg']}; padding: 2px 7px; border-radius: 5px;">{safe_text(er.get('error_type', 'Error'))}</span></div>
                        <div style="color: {theme['text_secondary']}; font-family: monospace; font-size: 11.5px;">{safe_text(er.get('message_short', ''))}</div>
                        <div style="color: {theme['text_muted']}; font-family: monospace; font-size: 11px;">{safe_text(er.get('stack_hash', ''))}</div>
                    </div>
                    """)
        else:
            st.success("✓ Zero application errors recorded for the selected time window.")

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.2(b): Processing Failures Table & Aggregate Counts by Reason
    # -----------------------------------------------------------------------
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>⚠️ Document Processing Failures (`processing_events`)</h4>")
        st.caption("Tracks failed extraction, validation, or analysis runs by file format, stage, and canonical failure reason (without storing private filenames or paper text).")

        all_proc_stats = auth.get_processing_stats()
        failed_events = auth.get_processing_events(limit=100, status_filter="failed")
        by_reason = all_proc_stats.get("by_reason", {})

        if by_reason:
            render_html(f"<div style='font-size: 12.5px; font-weight: 700; color: {theme['text_secondary']}; margin-bottom: 6px;'>Aggregate Failure Counts by Reason:</div>")
            reason_badges = " &nbsp; ".join(
                f"<span style='display:inline-block; margin: 2px 4px 6px 0; padding: 4px 10px; border-radius: 6px; background: {theme['warning_bg']}; color: {theme['warning_text']}; font-size: 12px; font-weight: 700;'>{safe_text(r_name)}: {r_cnt}</span>"
                for r_name, r_cnt in by_reason.items()
            )
            render_html(f"<div>{reason_badges}</div>")

        if failed_events:
            render_html(f"""
                <div style="display: grid; grid-template-columns: 0.5fr 1.8fr 1.0fr 1.2fr 1.4fr 3.0fr 1.0fr; padding: 9px 12px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 11.5px; color: {theme['text_muted']}; text-transform: uppercase;">
                    <div>ID</div>
                    <div>Timestamp</div>
                    <div>Format</div>
                    <div>Size (KB)</div>
                    <div>Stage</div>
                    <div>Failure Reason</div>
                    <div>Duration</div>
                </div>
                """)
            for fe in failed_events[:50]:
                render_html(f"""
                    <div style="display: grid; grid-template-columns: 0.5fr 1.8fr 1.0fr 1.2fr 1.4fr 3.0fr 1.0fr; padding: 9px 12px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12px; align-items: center;">
                        <div style="color: {theme['text_muted']};">#{fe.get('id')}</div>
                        <div style="font-family: monospace; color: {theme['text_secondary']};">{safe_text(fe.get('timestamp', ''))}</div>
                        <div style="font-weight: 700; color: {theme['text_primary']};">{safe_text(fe.get('file_type', ''))}</div>
                        <div style="color: {theme['text_secondary']};">{float(fe.get('file_size_kb') or 0.0):.1f} KB</div>
                        <div style="color: {theme['accent_purple']}; font-weight: 600;">{safe_text(fe.get('stage', 'analysis'))}</div>
                        <div><span style="font-size: 11px; font-weight: 700; color: {theme['error_text']}; background: {theme['error_bg']}; padding: 2px 7px; border-radius: 5px;">{safe_text(fe.get('failure_reason', 'Unspecified failure'))}</span></div>
                        <div style="color: {theme['text_muted']}; font-family: monospace;">{float(fe.get('duration_ms') or 0.0):.0f} ms</div>
                    </div>
                    """)
        else:
            st.success("✓ Zero document processing failures recorded.")

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.2(c): Dependency Status Table
    # -----------------------------------------------------------------------
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>📦 Runtime Dependency Status (`requirements.txt` & Core Stack)</h4>")
        deps = auth.check_dependencies()
        render_html(f"""
            <div style="display: grid; grid-template-columns: 1.6fr 1.2fr 1.0fr 1.1fr 3.2fr; padding: 9px 12px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 8px 8px 0 0; font-weight: 700; font-size: 11.5px; color: {theme['text_muted']}; text-transform: uppercase;">
                <div>Package</div>
                <div>Installed Version</div>
                <div>Status</div>
                <div>Requirement</div>
                <div>Subsystem Purpose</div>
            </div>
            """)
        for d in deps:
            is_ok = d["status"] == "OK"
            d_col = theme["success_text"] if is_ok else (theme["error_text"] if d["required"] else theme["warning_text"])
            d_bg = theme["success_bg"] if is_ok else (theme["error_bg"] if d["required"] else theme["warning_bg"])
            req_col = theme["info_text"] if d["required"] else theme["text_muted"]
            render_html(f"""
                <div style="display: grid; grid-template-columns: 1.6fr 1.2fr 1.0fr 1.1fr 3.2fr; padding: 9px 12px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12.5px; align-items: center;">
                    <div style="font-weight: 700; color: {theme['text_primary']}; font-family: monospace;">{safe_text(d['package'])}</div>
                    <div style="font-family: monospace; color: {theme['text_secondary']};">{safe_text(d['version'])}</div>
                    <div><span style="font-size: 11px; font-weight: 700; color: {d_col}; background: {d_bg}; padding: 2px 8px; border-radius: 5px;">{safe_text(d['status'])}</span></div>
                    <div style="font-size: 11.5px; font-weight: 600; color: {req_col};">{safe_text(d['type_label'])}</div>
                    <div style="color: {theme['text_muted']}; font-size: 12px;">{safe_text(d['purpose'])}</div>
                </div>
                """)

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
                    • <b>Host Operating System:</b> <code>{safe_text(os_detail)}</code><br>
                    • <b>Architecture:</b> <code>{safe_text(platform.architecture()[0])}</code><br>
                    • <b>Allocated DB Pages:</b> <code>{health['page_count']:,} pages</code><br>
                    • <b>Password Security Scheme:</b> <code>{safe_text(health.get('password_scheme', auth.PASSWORD_SCHEME_LABEL))}</code><br>
                </div>
                """)

        st.write("")
        if st.button("🔄 Refresh System Diagnostics", key="adm_btn_refresh_health"):
            st.rerun()


# ===========================================================================
# 9. STORAGE & DATA MANAGEMENT (Part 1.5)
# ===========================================================================
def render_storage_management_view(theme, current_admin_user="admin"):
    """Renders database backups, per-table storage breakdown, orphan cleanup, report cleanup, VACUUM, and audit retention."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Storage & Data Management</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Inspect SQLite storage allocation, manage online database backups, clean orphaned or aged report blobs, and compact database pages.
            </p>
        </div>
        """)

    stats = auth.get_system_stats()
    health = auth.get_system_health()
    s_stats = auth.get_storage_detailed_stats()
    b_info = auth.get_last_backup_info()

    # Warning if no backup in last 7 days
    if b_info["overdue_7d"]:
        st.warning("⚠️ **Backup Notice:** No database backup has been created in the last 7 days. Use **Create Backup Now** below to snapshot `users.db`.")

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Database Storage", stats["db_size_formatted"])
    s2.metric("Total DB Records", sum(health["table_counts"].values()))
    s3.metric("Generated Reports Stored", f"{s_stats['report_count']} ({s_stats['report_size_formatted']})")
    s4.metric("Orphaned Records", s_stats["total_orphans"])
    s5.metric("SQLite Integrity", health["integrity"].upper())

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.5(b): Database Backup Manager (sqlite3.Connection.backup)
    # -----------------------------------------------------------------------
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>💾 Database Backup & Recovery Manager (`backups/`)</h3>")
        st.write(
            "Creates consistent online snapshots of `users.db` using `sqlite3.Connection.backup` and verifies `PRAGMA integrity_check` on each backup file."
        )

        bk_c1, bk_c2, bk_c3, bk_c4 = st.columns([2.2, 1.5, 1.5, 1.5])
        with bk_c1:
            bk_label = st.text_input("Optional Backup Label", placeholder="e.g. pre_semester_audit", key="adm_bk_label_input")
        with bk_c2:
            st.write("")
            st.write("")
            if st.button("📸 Create Backup Now", type="primary", use_container_width=True, key="adm_btn_create_backup"):
                ok, msg, _ = auth.create_db_backup(current_admin_user=current_admin_user, label=bk_label)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.error(msg)
        with bk_c3:
            keep_n_cur = int(auth.get_platform_setting("backup_retention_count", 10))
            keep_n_val = st.number_input("Keep Last N Backups", min_value=1, max_value=100, value=keep_n_cur, key="adm_bk_keep_n")
        with bk_c4:
            st.write("")
            st.write("")
            if st.button("Apply Retention Policy", use_container_width=True, key="adm_btn_apply_bk_retention"):
                auth.update_platform_setting("backup_retention_count", keep_n_val, current_admin_user=current_admin_user)
                ok, msg, _ = auth.apply_backup_retention(keep_last_n=keep_n_val, current_admin_user=current_admin_user)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.error(msg)

        backups_list = auth.list_db_backups()
        if backups_list:
            st.write("")
            for idx, bk in enumerate(backups_list):
                bfn = bk["filename"]
                bc1, bc2, bc3, bc4, bc5 = st.columns([3.0, 1.6, 1.2, 1.4, 1.2])
                with bc1:
                    st.markdown(f"**`{bfn}`**")
                with bc2:
                    st.caption(f"Created: `{bk['created_at']}`")
                with bc3:
                    st.caption(f"Size: **{bk['size_formatted']}** | `{bk['integrity'].upper()}`")
                with bc4:
                    bk_bytes = auth.get_backup_bytes(bfn, current_admin_user=current_admin_user)
                    if bk_bytes:
                        st.download_button(
                            "⬇ Download",
                            data=bk_bytes,
                            file_name=bfn,
                            mime="application/octet-stream",
                            use_container_width=True,
                            key=f"adm_dl_bk_{idx}_{bfn}",
                        )
                with bc5:
                    if st.button("Delete", key=f"adm_del_bk_btn_{idx}_{bfn}", use_container_width=True):
                        st.session_state[f"adm_conf_del_bk_{bfn}"] = True
                        st.rerun()

                if st.session_state.get(f"adm_conf_del_bk_{bfn}", False):
                    dc1, dc2, dc3 = st.columns([3, 1.2, 1.2])
                    with dc1:
                        typed_bk = st.text_input(f"Type '{bfn}' to confirm deleting backup", "", key=f"adm_inp_del_bk_{bfn}")
                    with dc2:
                        st.write("")
                        if st.button("Confirm Delete", type="primary", key=f"adm_yes_del_bk_{bfn}"):
                            ok, msg = auth.delete_db_backup(bfn, confirm_filename=typed_bk, current_admin_user=current_admin_user)
                            if ok:
                                st.session_state[f"adm_conf_del_bk_{bfn}"] = False
                                st.success(f"✓ {msg}")
                                st.rerun()
                            else:
                                st.error(msg)
                    with dc3:
                        st.write("")
                        if st.button("Cancel", key=f"adm_no_del_bk_{bfn}"):
                            st.session_state[f"adm_conf_del_bk_{bfn}"] = False
                            st.rerun()
        else:
            st.info("No database backups stored in `backups/` yet.")

        with st.expander("📖 Manual Database Restore Instructions (Safe Offline Procedure)"):
            st.markdown(
                "To prevent SQLite file-lock corruption on Windows, live in-app database overwrite is intentionally disabled while Streamlit holds `users.db` open. "
                "To restore from a backup snapshot:\n"
                "1. Stop the running Streamlit server process.\n"
                "2. Copy your current `users.db` to `users.db.pre_restore.bak`.\n"
                "3. Copy the verified backup file from `backups/<backup_filename>.db` over `users.db`.\n"
                "4. Run `python -c \"import sqlite3; print(sqlite3.connect('users.db').execute('PRAGMA integrity_check').fetchone())\"` to confirm `'ok'`.\n"
                "5. Restart the Streamlit server."
            )

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.5(a): Per-Table Row Counts & Approximate Storage Breakdown + Orphan Cleanup
    # -----------------------------------------------------------------------
    col_tbl_brk, col_orph = st.columns([3, 2])
    with col_tbl_brk:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>📊 Per-Table Row Counts & Approximate Storage</h4>")
            render_html(f"""
                <div style="display: grid; grid-template-columns: 2fr 1fr 1.2fr; padding: 8px 12px; background: {theme['bg_card_inner']}; border: 1px solid {theme['border_color']}; border-radius: 6px 6px 0 0; font-weight: 700; font-size: 11.5px; color: {theme['text_muted']}; text-transform: uppercase;">
                    <div>Table Name</div>
                    <div>Row Count</div>
                    <div>Approx Payload</div>
                </div>
                """)
            for tb in s_stats["table_breakdown"]:
                render_html(f"""
                    <div style="display: grid; grid-template-columns: 2fr 1fr 1.2fr; padding: 7px 12px; border-bottom: 1px solid {theme['border_color']}; background: {theme['bg_card']}; font-size: 12.5px;">
                        <div style="font-family: monospace; font-weight: 600; color: {theme['text_primary']};">{safe_text(tb['table'])}</div>
                        <div style="color: {theme['text_secondary']}; font-weight: 600;">{tb['rows']:,}</div>
                        <div style="color: {theme['text_muted']}; font-family: monospace;">{safe_text(tb['approx_size'])}</div>
                    </div>
                    """)

    with col_orph:
        with st.container(border=True):
            render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>🔍 Orphaned-Record Integrity Check</h4>")
            st.caption("Checks child tables for records referencing deleted user accounts or deleted projects.")
            for k_orph, v_orph in s_stats["orphans"].items():
                st.markdown(f"- `{k_orph}`: **{v_orph}** orphaned row(s)")
            st.write("")
            conf_orph = st.checkbox("Confirm cleaning orphaned child records", key="adm_chk_clean_orphans")
            if st.button("Clean Orphaned Records", type="primary", use_container_width=True, key="adm_btn_clean_orphans"):
                ok, msg, _ = auth.clean_orphaned_records(current_admin_user=current_admin_user, confirm=conf_orph)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.warning(msg)

    render_html("<br>")

    # -----------------------------------------------------------------------
    # Part 1.5(c): Report Storage Cleanup & SQLite VACUUM & Audit Retention
    # -----------------------------------------------------------------------
    c_clean1, c_clean2 = st.columns(2)
    with c_clean1:
        with st.container(border=True):
            render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>📄 Generated Report Storage Cleanup</h3>")
            st.write("Reclaim SQLite blob storage by clearing generated PDF report blobs (`pdf_data`) older than N days while preserving user score summaries.")
            rep_days = st.number_input("Clean generated report files older than (days)", min_value=7, max_value=3650, value=90, step=15, key="adm_rep_cleanup_days")
            prev_rep = auth.preview_old_reports(rep_days)
            st.info(f"Preview: **{prev_rep['count']}** report blob(s) older than {rep_days} days (**{prev_rep['size_formatted']}** reclaimable).")
            conf_rep_clean = st.checkbox(f"Confirm cleaning {prev_rep['count']} report blob(s) older than {rep_days} days", key="adm_chk_rep_cleanup")
            if st.button("Clean Old Report Blobs", type="primary", key="adm_btn_rep_cleanup"):
                ok, msg, _ = auth.cleanup_old_reports(older_than_days=rep_days, current_admin_user=current_admin_user, confirm=conf_rep_clean)
                if ok:
                    st.success(f"✓ {msg}")
                    st.rerun()
                else:
                    st.warning(msg)

    with c_clean2:
        with st.container(border=True):
            render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>🧹 Compact Database & Reclaim Space (VACUUM)</h3>")
            st.write("Running **VACUUM** rebuilds the SQLite database file, defragments pages, and shrinks file size on disk after deletions or blob cleanup.")
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

    # Guarded Audit Trail Retention Policy (Part 2.4)
    min_ret = int(auth.get_platform_setting("audit_retention_days", 90))
    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 8px 0;'>🛡️ Audit Trail Retention Policy (Minimum {min_ret} Days)</h3>")
        st.write(
            f"PaperIQ protects `login_history` with tamper-evident SHA-256 hash chaining. 'Purge All' is strictly blocked. "
            f"You may archive and purge non-immutable entries older than the configured retention period (**>= {min_ret} days**) with a mandatory compliance reason."
        )
        p_c1, p_c2 = st.columns([1.5, 3])
        with p_c1:
            st_purge_days = st.number_input("Retention Cutoff (Days)", min_value=min_ret, max_value=3650, value=min_ret, step=15, key="adm_stor_purge_days")
        with p_c2:
            st_purge_reason = st.text_input("Compliance Reason for Audit Purge (min 5 chars)", "", key="adm_stor_purge_reason")
        conf_purge = st.checkbox("Confirm authorized audit log retention purge (auto-archives CSV & writes immutable LOG_PURGE record)", key="adm_chk_purge_retention")
        if st.button("Execute Guarded Audit Retention Purge", key="adm_btn_purge_retention"):
            if conf_purge:
                res = auth.purge_audit_history(
                    older_than_days=st_purge_days,
                    reason=st_purge_reason,
                    current_admin_user=current_admin_user,
                )
                if res[0]:
                    st.success(f"✓ {res[1]}")
                    st.rerun()
                else:
                    st.error(res[1])
            else:
                st.warning("Please check the confirmation box.")


# ===========================================================================
# 10. PLATFORM SETTINGS PAGE (Part 1.6)
# ===========================================================================
def render_platform_settings_view(theme, current_admin_user="admin"):
    """Renders the operational Platform Settings page backed by app_settings."""
    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">Platform Operational Settings</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Configure upload limits, allowed formats, self-registration controls, session timeouts, audit retention, failed-login lockouts, and maintenance announcements. Every change is validated and audit-logged.
            </p>
        </div>
        """)

    meta = auth.get_platform_settings_with_meta()

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 12px 0;'>⚙️ Ingestion, Registration & Security Policies</h3>")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            cur_max_mb = int(meta["max_upload_size_mb"]["value"] or 30)
            new_max_mb = st.number_input(
                "1. Max Upload File Size (MB)",
                min_value=1,
                max_value=200,
                value=cur_max_mb,
                help=meta["max_upload_size_mb"]["spec"].get("description", ""),
                key="adm_set_max_mb",
            )

            cur_fmts = [x.strip().upper() for x in str(meta["allowed_formats"]["value"] or "PDF,DOCX,TXT").split(",") if x.strip()]
            st.markdown("**2. Allowed File Formats (Enforced on Upload)**")
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                fmt_pdf = st.checkbox("PDF (.pdf)", value=("PDF" in cur_fmts), key="adm_set_fmt_pdf")
            with fc2:
                fmt_docx = st.checkbox("DOCX (.docx)", value=("DOCX" in cur_fmts), key="adm_set_fmt_docx")
            with fc3:
                fmt_txt = st.checkbox("TXT (.txt)", value=("TXT" in cur_fmts), key="adm_set_fmt_txt")

            cur_reg = str(meta["registration_enabled"]["value"]).lower() in ("true", "1", "yes")
            new_reg = st.toggle(
                "3. Enable New User Self-Registration",
                value=cur_reg,
                help=meta["registration_enabled"]["spec"].get("description", ""),
                key="adm_set_reg_enabled",
            )

            cur_def_role = meta["default_role"]["value"] if meta["default_role"]["value"] in ("Student", "Researcher") else "Student"
            new_def_role = st.selectbox(
                "4. Default Role for Self-Registered Users (Never Administrator)",
                ["Student", "Researcher"],
                index=0 if cur_def_role == "Student" else 1,
                key="adm_set_default_role",
            )

        with col_s2:
            cur_timeout = int(meta["session_timeout_minutes"]["value"] or 60)
            new_timeout = st.number_input(
                "5. Session Inactivity Timeout (Minutes)",
                min_value=5,
                max_value=1440,
                value=cur_timeout,
                key="adm_set_session_timeout",
            )

            cur_ret = int(meta["audit_retention_days"]["value"] or 90)
            new_ret = st.number_input(
                "6. Audit Log Minimum Retention (Days)",
                min_value=7,
                max_value=3650,
                value=cur_ret,
                key="adm_set_audit_retention",
            )

            lc1, lc2 = st.columns(2)
            with lc1:
                cur_lock_thresh = int(meta["lockout_threshold"]["value"] or 5)
                new_lock_thresh = st.number_input(
                    "7a. Lockout Threshold (Attempts)",
                    min_value=2,
                    max_value=50,
                    value=cur_lock_thresh,
                    key="adm_set_lock_thresh",
                )
            with lc2:
                cur_lock_dur = int(meta["lockout_duration_minutes"]["value"] or 15)
                new_lock_dur = st.number_input(
                    "7b. Lockout Duration (Minutes)",
                    min_value=1,
                    max_value=1440,
                    value=cur_lock_dur,
                    key="adm_set_lock_dur",
                )

        st.write("")
        cur_banner = str(meta["maintenance_banner"]["value"] or "")
        new_banner = st.text_input(
            "8. Maintenance / Platform Announcement Banner (Shown across all workspaces when non-empty)",
            value=cur_banner,
            max_chars=280,
            placeholder="Leave empty for normal operation, or enter an announcement (e.g., Scheduled maintenance tonight at 23:00 UTC).",
            key="adm_set_maint_banner",
        )

        st.write("")
        if st.button("💾 Save Platform Settings", type="primary", use_container_width=True, key="adm_btn_save_platform_settings"):
            chosen_fmts = []
            if fmt_pdf:
                chosen_fmts.append("PDF")
            if fmt_docx:
                chosen_fmts.append("DOCX")
            if fmt_txt:
                chosen_fmts.append("TXT")

            payload = {
                "max_upload_size_mb": new_max_mb,
                "allowed_formats": ",".join(chosen_fmts),
                "registration_enabled": "true" if new_reg else "false",
                "default_role": new_def_role,
                "session_timeout_minutes": new_timeout,
                "audit_retention_days": new_ret,
                "lockout_threshold": new_lock_thresh,
                "lockout_duration_minutes": new_lock_dur,
                "maintenance_banner": new_banner,
            }
            ok, msg = auth.update_platform_settings_bulk(payload, current_admin_user=current_admin_user)
            if ok:
                st.success(f"✓ {msg}")
                st.rerun()
            else:
                st.error(msg)

    render_html("<br>")

    # Settings Metadata Table
    with st.container(border=True):
        render_html(f"<h4 style='color: {theme['text_primary']}; margin: 0 0 8px 0;'>📋 Current Active Configuration & Audit Provenance</h4>")
        display_keys = [
            "max_upload_size_mb",
            "allowed_formats",
            "registration_enabled",
            "default_role",
            "session_timeout_minutes",
            "audit_retention_days",
            "lockout_threshold",
            "lockout_duration_minutes",
            "maintenance_banner",
        ]
        for k in display_keys:
            m = meta.get(k, {})
            lbl = m.get("spec", {}).get("label", k)
            val_disp = m.get("value", "") or "(empty)"
            upd_by = m.get("updated_by", "system")
            upd_at = m.get("updated_at", "")
            render_html(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 10px; border-bottom: 1px solid {theme['border_color']}; font-size: 12.5px;">
                    <div><b>{safe_text(lbl)}</b> (<code>{safe_text(k)}</code>)</div>
                    <div>
                        <code style="color: {theme['accent_purple']}; font-weight: 700;">{safe_text(str(val_disp))}</code>
                        <span style="color: {theme['text_muted']}; font-size: 11px; margin-left: 10px;">Updated by {safe_text(upd_by)} at {safe_text(upd_at)}</span>
                    </div>
                </div>
                """)


# ===========================================================================
# 11. ABOUT & SYSTEM INFORMATION PAGE (Part 1.7)
# ===========================================================================
def render_admin_about_view(theme, current_admin_user="admin"):
    """Renders the About & System Information page for Administrators."""
    uptime_sec = max(0, int(time.time() - auth.APP_START_TIME))
    up_h, rem = divmod(uptime_sec, 3600)
    up_m, up_s = divmod(rem, 60)
    uptime_str = f"{up_h}h {up_m}m {up_s}s"
    db_basename = os.path.basename(auth.DB_PATH)  # Only basename 'users.db', never full host path

    render_html(f"""
        <div style="margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 28px; color: {theme['text_primary']};">About PaperIQ & System Information</h1>
            <p style="margin: 3px 0 0 0; color: {theme['text_muted']}; font-size: 14.5px;">
                Platform build metadata, runtime environment specifications, role governance overview, known operational boundaries, and academic integrity notice.
            </p>
        </div>
        """)

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Application Version", f"v{auth.APP_VERSION}")
    a2.metric("Build Date", auth.APP_BUILD_DATE)
    a3.metric("Supported Formats", auth.get_platform_setting("allowed_formats", "PDF,DOCX,TXT"))
    a4.metric("Current Session Uptime", uptime_str)

    render_html("<br>")

    col_ab1, col_ab2 = st.columns(2)
    with col_ab1:
        with st.container(border=True):
            render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 10px 0;'>🖥️ Deployment & Environment Details</h3>")
            render_html(f"""
                <div style="font-size: 13.5px; line-height: 1.85; color: {theme['text_secondary']};">
                    • <b>Application Name:</b> PaperIQ Academic Research Intelligence Platform<br>
                    • <b>Release Version & Build:</b> <code>v{safe_text(auth.APP_VERSION)}</code> (Build <code>{safe_text(auth.APP_BUILD_DATE)}</code>)<br>
                    • <b>Operating System:</b> <code>{safe_text(platform.system())} {safe_text(platform.release())} ({safe_text(platform.machine())})</code><br>
                    • <b>Python Runtime:</b> <code>v{safe_text(sys.version.split()[0])}</code><br>
                    • <b>Streamlit Framework:</b> <code>v{safe_text(st.__version__)}</code><br>
                    • <b>Database Engine:</b> SQLite <code>v{safe_text(sqlite3.sqlite_version)}</code> (Database file: <code>{safe_text(db_basename)}</code>)<br>
                    • <b>Server Start Time:</b> <code>{safe_text(auth.APP_START_ISO)}</code> (Uptime: <code>{safe_text(uptime_str)}</code>)<br>
                    • <b>Credential Security:</b> <code>{safe_text(auth.PASSWORD_SCHEME_LABEL)}</code>
                </div>
                """)

    with col_ab2:
        with st.container(border=True):
            render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 10px 0;'>🛡️ Workspace Role & Privacy Architecture</h3>")
            render_html(f"""
                <div style="font-size: 13.5px; line-height: 1.75; color: {theme['text_secondary']};">
                    <p style="margin: 0 0 8px 0;">
                        <b>Student Workspace:</b> Provides manuscript evaluation, structural rubric scoring, grammar/style feedback, executive summarization, side-by-side comparison, and personal analysis history strictly isolated to the student's own account.
                    </p>
                    <p style="margin: 0 0 8px 0;">
                        <b>Researcher Workspace:</b> Provides deep section-aware manuscript profiling, multi-paper structured synthesis matrices, evidence-grounded Ask PaperIQ Q&A, project/tag organization, and personal research library management.
                    </p>
                    <p style="margin: 0;">
                        <b>Administrator Workspace:</b> Restricted to user governance, security audit verification, system health, storage/backup operations, and aggregate platform telemetry. By strict privacy design, Administrators <b>cannot</b> open or read any Student's or Researcher's private uploaded documents, extracted text, chats, or personal analysis reports.
                    </p>
                </div>
                """)

    render_html("<br>")

    with st.container(border=True):
        render_html(f"<h3 style='font-size: 18px; color: {theme['text_primary']}; margin: 0 0 10px 0;'>⚠️ Known Technical Limitations & Responsible-Use Notice</h3>")
        render_html(f"""
            <div style="font-size: 13.5px; line-height: 1.75; color: {theme['text_secondary']};">
                • <b>Digital Text Extraction Requirement:</b> PDF ingestion relies on embedded digital text layers (<code>pdfplumber</code>). Scanned raster-image PDFs without OCR text layers are automatically rejected with a clear diagnostic message.<br>
                • <b>Automated Heuristic & Statistical NLP Evaluation:</b> Quality scores, readability indices, and extracted methodology profiles are deterministic computational indicators designed to assist academic review—not a substitute for peer review or faculty grading.<br>
                • <b>Local SQLite Storage Scope:</b> PaperIQ uses a single-node SQLite database (<code>users.db</code>). Administrators should create regular backups in <b>Storage & Data Management</b> prior to bulk maintenance.<br>
                • <b>Academic Integrity & Responsible Use:</b> Users remain solely responsible for verifying citations, statistical claims, and institutional originality standards in submitted manuscripts.
            </div>
            """)
