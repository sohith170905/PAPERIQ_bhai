"""
PaperIQ — Role-Based Page Registry (`pages/registry.py`)
========================================================
Centralized registry mapping roles (Student vs Researcher) to their distinct navigation
structures and page modules, ensuring strict role isolation while sharing core engines.

PART A — Exact Researcher Navigation (9 sections):
1. Researcher Dashboard
2. Analyze Research Paper
3. Research Library            <- NEW
4. Advanced Paper Comparison   <- REBUILD
5. Ask PaperIQ                 <- researcher version
6. Research Insights           <- REBUILD
7. Research History & Reports  <- extend
8. Settings & Privacy
9. About & Methodology
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from core.student.workspace_pages import STUDENT_NAV_SECTIONS, STUDENT_ALLOWED_PAGES
from core.researcher import (
    dashboard as res_dashboard,
    analyze as res_analyze,
    library as res_library,
    comparison as res_comparison,
    ask_paperiq as res_ask,
    insights as res_insights,
    history_reports as res_history,
    settings_privacy as res_settings,
    about_methodology as res_about,
)

# Exact 9 Researcher navigation items (Part A)
RESEARCHER_NAV_ITEMS: List[tuple[str, str]] = [
    ("🏠 Researcher Dashboard", "nav_res_dashboard"),
    ("📄 Analyze Research Paper", "nav_res_analyze"),
    ("📚 Research Library", "nav_res_library"),
    ("🔄 Advanced Paper Comparison", "nav_res_compare"),
    ("💬 Ask PaperIQ", "nav_res_ask"),
    ("💡 Research Insights", "nav_res_insights"),
    ("🗂️ Research History & Reports", "nav_res_history"),
    ("⚙️ Settings & Privacy", "nav_res_settings"),
    ("ℹ️ About & Methodology", "nav_res_about"),
]

# Map aliases / legacy route names for Researcher to canonical Part A route names
RESEARCHER_ROUTE_ALIASES: Dict[str, str] = {
    "🏠 Dashboard": "🏠 Researcher Dashboard",
    "🏠 Researcher Dashboard": "🏠 Researcher Dashboard",
    "Researcher Dashboard": "🏠 Researcher Dashboard",
    "📄 Analyze Paper": "📄 Analyze Research Paper",
    "📄 Analyze Manuscript": "📄 Analyze Research Paper",
    "📄 Analyze Research Paper": "📄 Analyze Research Paper",
    "Analyze Research Paper": "📄 Analyze Research Paper",
    "📊 Analysis": "📄 Analyze Research Paper",
    "📊 Manuscript Evaluation": "📄 Analyze Research Paper",
    "📚 Research Library": "📚 Research Library",
    "Research Library": "📚 Research Library",
    "🔄 Compare Papers": "🔄 Advanced Paper Comparison",
    "🔄 Compare Manuscripts": "🔄 Advanced Paper Comparison",
    "🔄 Advanced Paper Comparison": "🔄 Advanced Paper Comparison",
    "Advanced Paper Comparison": "🔄 Advanced Paper Comparison",
    "💬 Ask PaperIQ": "💬 Ask PaperIQ",
    "💬 Ask PaperIQ Chat": "💬 Ask PaperIQ",
    "Ask PaperIQ": "💬 Ask PaperIQ",
    "💡 Insights": "💡 Research Insights",
    "💡 Research Insights": "💡 Research Insights",
    "Research Insights": "💡 Research Insights",
    "📚 History": "🗂️ Research History & Reports",
    "📚 Research History": "🗂️ Research History & Reports",
    "🗂️ Research History & Reports": "🗂️ Research History & Reports",
    "Research History & Reports": "🗂️ Research History & Reports",
    "⚙ Settings": "⚙️ Settings & Privacy",
    "⚙️ Settings": "⚙️ Settings & Privacy",
    "⚙️ Settings & Privacy": "⚙️ Settings & Privacy",
    "Settings & Privacy": "⚙️ Settings & Privacy",
    "ℹ About": "ℹ️ About & Methodology",
    "ℹ️ About": "ℹ️ About & Methodology",
    "ℹ️ About & Methodology": "ℹ️ About & Methodology",
    "About & Methodology": "ℹ️ About & Methodology",
}


def resolve_researcher_page(raw_page: str) -> str:
    """Resolve any page string to one of the 9 canonical Researcher pages."""
    return RESEARCHER_ROUTE_ALIASES.get(raw_page, "🏠 Researcher Dashboard")


def is_researcher_only_page(raw_page: str) -> bool:
    """Return True if `raw_page` is exclusively a Researcher page that Students must not access."""
    return raw_page in {
        "🏠 Researcher Dashboard",
        "📄 Analyze Research Paper",
        "📚 Research Library",
        "🔄 Advanced Paper Comparison",
        "💡 Research Insights",
        "🗂️ Research History & Reports",
        "⚙️ Settings & Privacy",
        "ℹ️ About & Methodology",
    }


from utils import render_html


def inject_researcher_workspace_css(theme: Dict[str, str]) -> None:
    """
    Inject CSS rules strictly scoped to the Researcher Workspace (#res-workspace-scope).
    Student and Admin workspaces never call this function and are never affected.
    """
    bg_card = theme.get("bg_card", "#111827")
    bg_card_inner = theme.get("bg_card_inner", "#0B0F19")
    bg_elevated = theme.get("bg_card_elevated", "#1F2937")
    border_col = theme.get("border_color", "#1F2937")
    border_sub = theme.get("border_subtle", "#374151")
    text_pri = theme.get("text_primary", "#F9FAFB")
    text_sec = theme.get("text_secondary", "#D1D5DB")
    text_mut = theme.get("text_muted", "#9CA3AF")
    input_bg = theme.get("input_bg", "#1F2937")
    input_bd = theme.get("input_border", "#374151")
    accent_p = theme.get("accent_purple", "#A78BFA")

    render_html('<div id="res-workspace-scope" style="display:none;"></div>')

    css_rules = f"""
        div[data-testid="stElementContainer"]:has(#res-workspace-scope),
        div[data-testid="stElementContainer"]:has(.res-card-scope):not(:has(div[data-testid="stMarkdownContainer"] div)),
        div[data-testid="stElementContainer"]:has(.res-item-scope):not(:has(div[data-testid="stMarkdownContainer"] div)),
        div[data-testid="stElementContainer"]:has(.res-suggested-q-scope):not(:has(div[data-testid="stMarkdownContainer"] div)) {{
            display: none !important;
            margin: 0 !important;
            padding: 0 !important;
            height: 0 !important;
        }}

        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-card-scope) {{
            background-color: {bg_card} !important;
            border: 1px solid {border_col} !important;
            border-radius: 12px !important;
            padding: 22px 24px !important;
            margin-bottom: 18px !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.24) !important;
            gap: 0.85rem !important;
        }}

        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-item-scope) {{
            background-color: {bg_card} !important;
            border: 1px solid {border_col} !important;
            border-radius: 12px !important;
            padding: 18px 22px !important;
            margin-bottom: 12px !important;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2) !important;
            gap: 0.7rem !important;
            transition: border-color 0.18s ease !important;
        }}
        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-item-scope):hover {{
            border-color: {border_sub} !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stForm"] {{
            background-color: {bg_card} !important;
            border: 1px solid {border_col} !important;
            border-radius: 12px !important;
            padding: 18px 22px !important;
            margin-bottom: 16px !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22) !important;
        }}
        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-card-scope) [data-testid="stForm"] {{
            background-color: transparent !important;
            border: none !important;
            padding: 0 !important;
            margin-bottom: 0 !important;
            box-shadow: none !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stFormSubmitButton"] > button {{
            background: linear-gradient(135deg, #7C3AED, #4F46E5) !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(139, 92, 246, 0.4) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            min-height: 40px !important;
            padding: 0.45rem 1rem !important;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3) !important;
            width: 100% !important;
            transition: all 0.2s ease !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stFormSubmitButton"] > button * {{
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stFormSubmitButton"] > button:hover {{
            background: linear-gradient(135deg, #6D28D9, #4338CA) !important;
            box-shadow: 0 6px 16px rgba(124, 58, 237, 0.42) !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stTextInputRootElement"],
        .stApp:has(#res-workspace-scope) [data-testid="stTextAreaRootElement"],
        .stApp:has(#res-workspace-scope) div[data-baseweb="input"],
        .stApp:has(#res-workspace-scope) div[data-baseweb="base-input"],
        .stApp:has(#res-workspace-scope) div[data-baseweb="textarea"] {{
            background-color: {input_bg} !important;
            border: 1px solid {input_bd} !important;
            border-radius: 8px !important;
            color: {text_pri} !important;
            box-shadow: none !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stTextInputRootElement"]:focus-within,
        .stApp:has(#res-workspace-scope) [data-testid="stTextAreaRootElement"]:focus-within,
        .stApp:has(#res-workspace-scope) div[data-baseweb="select"] > div:focus-within {{
            border-color: #8B5CF6 !important;
            box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.25) !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stTextInputRootElement"] input,
        .stApp:has(#res-workspace-scope) [data-testid="stTextAreaRootElement"] textarea {{
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: {text_pri} !important;
        }}
        .stApp:has(#res-workspace-scope) div[data-baseweb="select"] > div {{
            border-radius: 8px !important;
            min-height: 40px !important;
        }}

        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-card-scope) [data-testid="stFileUploader"] {{
            background-color: transparent !important;
            border: none !important;
            padding: 2px 0 4px 0 !important;
            box-shadow: none !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stFileUploaderDropzone"] {{
            background-color: {bg_card_inner} !important;
            border: 1.5px dashed {border_sub} !important;
            border-radius: 10px !important;
            padding: 20px 24px !important;
            transition: border-color 0.2s ease, background-color 0.2s ease !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stFileUploaderDropzone"]:hover {{
            border-color: #8B5CF6 !important;
            background-color: rgba(139, 92, 246, 0.05) !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stButton button[kind="primary"] {{
            background: linear-gradient(135deg, #7C3AED, #4F46E5) !important;
            color: #FFFFFF !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35) !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stButton button[kind="primary"] * {{
            color: #FFFFFF !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stButton button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #6D28D9, #4338CA) !important;
            box-shadow: 0 6px 18px rgba(124, 58, 237, 0.45) !important;
        }}

        .stApp:has(#res-workspace-scope) .stButton button[kind="primary"]:disabled,
        .stApp:has(#res-workspace-scope) .stButton button[kind="primary"][disabled],
        .stApp:has(#res-workspace-scope) .stButton button[data-testid="stBaseButton-primary"]:disabled,
        .stApp:has(#res-workspace-scope) .stButton button:disabled,
        .stApp:has(#res-workspace-scope) .stButton button[disabled] {{
            background: {bg_elevated} !important;
            background-image: none !important;
            background-color: {bg_elevated} !important;
            border: 1px solid {border_sub} !important;
            color: {text_mut} !important;
            box-shadow: none !important;
            opacity: 0.88 !important;
            cursor: not-allowed !important;
        }}
        .stApp:has(#res-workspace-scope) .stButton button[kind="primary"]:disabled *,
        .stApp:has(#res-workspace-scope) .stButton button:disabled * {{
            color: {text_mut} !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stButton button,
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stDownloadButton button,
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] [data-testid="stPopoverButton"],
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] [data-testid="stPopover"] button {{
            min-height: 40px !important;
            padding: 0.42rem 0.85rem !important;
            font-size: 13px !important;
            line-height: 1.25 !important;
            border-radius: 8px !important;
            width: 100% !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stButton button p,
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stDownloadButton button p,
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] [data-testid="stPopover"] button p {{
            font-size: 13px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            margin: 0 !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stDownloadButton button {{
            background: linear-gradient(135deg, #4F46E5, #3730A3) !important;
            border: 1px solid rgba(129, 140, 248, 0.35) !important;
            box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25) !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] .stDownloadButton button:hover {{
            background: linear-gradient(135deg, #6366F1, #4338CA) !important;
            border-color: {accent_p} !important;
        }}

        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-suggested-q-scope) .stButton button {{
            min-height: 48px !important;
            padding: 0.5rem 0.9rem !important;
        }}
        .stApp:has(#res-workspace-scope) div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .res-suggested-q-scope) .stButton button p {{
            white-space: normal !important;
            line-height: 1.3 !important;
            text-align: center !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stRadio"] div[role="radiogroup"] {{
            gap: 16px !important;
            align-items: center !important;
            flex-wrap: wrap !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stRadio"] label[data-baseweb="radio"] {{
            align-items: center !important;
            margin-right: 4px !important;
        }}
        .stApp:has(#res-workspace-scope) [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:first-child {{
            background-color: #8B5CF6 !important;
            border-color: #8B5CF6 !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] code {{
            background-color: rgba(139, 92, 246, 0.14) !important;
            color: #DDD6FE !important;
            border: 1px solid rgba(139, 92, 246, 0.28) !important;
            padding: 2px 6px !important;
            border-radius: 5px !important;
            font-size: 0.88em !important;
        }}

        .stApp:has(#res-workspace-scope) [data-testid="stMainBlockContainer"] {{
            max-width: 1400px !important;
            padding-top: 2.2rem !important;
            padding-bottom: 3rem !important;
            overflow-x: hidden !important;
        }}
        @media (max-width: 1100px) {{
            .stApp:has(#res-workspace-scope) [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap !important;
            }}
        }}
    """
    render_html(f"<style>{css_rules}</style>")


def dispatch_researcher_page(
    canonical_page: str,
    theme: Dict[str, str],
    username: str,
    user_data: Dict[str, Any],
    navigate_to: Callable[[str], None],
    load_analysis_into_session: Callable[[Dict[str, Any]], None],
    extract_text_from_file: Callable[[Any], str],
    clean_text: Callable[[str], str],
    analyze_full_document: Callable[[str], Dict[str, Any]],
    get_clean_display_title: Callable[..., str],
) -> bool:
    """
    Dispatch and render the requested Researcher page module.
    Returns True if handled by the Researcher page registry.
    """
    page = resolve_researcher_page(canonical_page)
    inject_researcher_workspace_css(theme)

    if page == "🏠 Researcher Dashboard":
        res_dashboard.render_researcher_dashboard(
            theme=theme,
            username=username,
            navigate_to=navigate_to,
            load_analysis_into_session=load_analysis_into_session,
        )
        return True

    if page == "📄 Analyze Research Paper":
        res_analyze.render_analyze_research_paper(
            theme=theme,
            username=username,
            navigate_to=navigate_to,
            extract_text_from_file=extract_text_from_file,
            clean_text=clean_text,
            analyze_full_document=analyze_full_document,
            get_clean_display_title=get_clean_display_title,
        )
        return True

    if page == "📚 Research Library":
        res_library.render_research_library(
            theme=theme,
            username=username,
            navigate_to=navigate_to,
            load_analysis_into_session=load_analysis_into_session,
        )
        return True

    if page == "🔄 Advanced Paper Comparison":
        res_comparison.render_advanced_paper_comparison(
            theme=theme,
            username=username,
            extract_text_from_file=extract_text_from_file,
            clean_text=clean_text,
            analyze_full_document=analyze_full_document,
        )
        return True

    if page == "💬 Ask PaperIQ":
        res_ask.render_researcher_ask_paperiq(
            theme=theme,
            username=username,
        )
        return True

    if page == "💡 Research Insights":
        res_insights.render_research_insights(
            theme=theme,
            username=username,
        )
        return True

    if page == "🗂️ Research History & Reports":
        res_history.render_research_history_and_reports(
            theme=theme,
            username=username,
            navigate_to=navigate_to,
            load_analysis_into_session=load_analysis_into_session,
        )
        return True

    if page == "⚙️ Settings & Privacy":
        res_settings.render_researcher_settings_and_privacy(
            theme=theme,
            username=username,
            user_data=user_data,
        )
        return True

    if page == "ℹ️ About & Methodology":
        res_about.render_researcher_about_and_methodology(
            theme=theme,
        )
        return True

    return False
