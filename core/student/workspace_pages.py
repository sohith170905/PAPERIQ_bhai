"""
PaperIQ — Student Workspace Page Module
=======================================
Preserves the exact Student Workspace navigation, look, and behavior (100% regression-protected).
Writing scores (5 dimensions) and actionable writing feedback are PRIMARY for the Student role.
"""

from typing import Any, Callable, Dict, List

STUDENT_NAV_SECTIONS: List[Dict[str, Any]] = [
    {
        "group": "Workspace",
        "items": [
            ("🏠 Student Dashboard", "nav_dashboard"),
            ("📄 Analyze Paper", "nav_analyze"),
        ],
    },
    {
        "group": "Research Tools",
        "items": [
            ("📊 Writing Quality & Feedback", "nav_analysis"),
            ("🔄 Compare Papers", "nav_compare"),
            ("💬 Ask PaperIQ", "nav_ask"),
            ("📚 My History", "nav_history"),
        ],
    },
    {
        "group": "Account",
        "items": [
            ("⚙ Settings", "nav_settings"),
            ("ℹ About", "nav_about"),
        ],
    },
]

STUDENT_ALLOWED_PAGES = {
    "🏠 Dashboard",
    "🏠 Student Dashboard",
    "📄 Analyze Paper",
    "📊 Analysis",
    "📊 Writing Quality & Feedback",
    "🔄 Compare Papers",
    "💬 Ask PaperIQ",
    "💬 Ask PaperIQ Chat",
    "📚 History",
    "📚 My History",
    "🕘 History",
    "⚙ Settings",
    "⚙️ Settings",
    "ℹ About",
    "ℹ️ About",
}
