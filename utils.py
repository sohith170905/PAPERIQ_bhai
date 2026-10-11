"""Shared HTML rendering, text escaping/unescaping, and formatting utilities for PaperIQ."""
from __future__ import annotations

import html
import re
import textwrap
from typing import Any, Iterable

import streamlit as st

_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);")
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def unescape_text(val: Any) -> str:
    """Unescape HTML entities (including double-escaped sequences like &amp;#x005F; or &#x005F;)
    into clean plain Unicode text."""
    if val is None:
        return ""
    text = str(val)
    # Up to 3 passes to resolve any pre-existing double-escaped entities (e.g., &amp;#x005F; -> &#x005F; -> _)
    for _ in range(3):
        if "&" not in text:
            break
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def clean_plain_text(val: Any) -> str:
    """Convert a value to clean plain text with HTML entities decoded and any stray HTML tags removed.
    Ideal for PDF export, TXT export, and database storage."""
    if val is None:
        return ""
    text = unescape_text(val)
    # Replace <br> / <br/> / </li> / </p> with spaces or newlines as appropriate before stripping tags
    text = re.sub(r"(?i)<br\s*/?>", " ", text)
    text = _HTML_TAG_RE.sub("", text)
    # Second unescape pass in case stripping tags revealed entities
    text = unescape_text(text)
    return text


def safe_text(val: Any) -> str:
    """Safely escape user/paper text ONCE for insertion into HTML.
    Always unescapes first so already-escaped text is never double-escaped,
    and ensures underscores remain plain '_' rather than '&#x005F;'."""
    if val is None:
        return ""
    plain = unescape_text(val)
    return html.escape(plain, quote=True)


def normalize_html(html_input: str | Iterable[str]) -> str:
    """Normalize an HTML string (or iterable of HTML fragments) so Markdown never treats it as a code block:
    1. Joins iterable fragments if needed
    2. Applies textwrap.dedent
    3. Strips leading and trailing whitespace from every line
    4. Removes all blank lines
    5. Collapses non-style HTML onto a single line (and keeps 0-indented lines with no blank lines)
    """
    if html_input is None:
        return ""
    if not isinstance(html_input, str):
        raw = "".join(str(part) for part in html_input if part is not None)
    else:
        raw = html_input

    dedented = textwrap.dedent(raw)
    lines = [line.strip() for line in dedented.splitlines() if line.strip()]
    if not lines:
        return ""
    # Join with a single space so the output is a single line with zero blank lines and zero leading spaces
    return " ".join(lines)


def render_html(html_input: str | Iterable[str]) -> str:
    """Normalize HTML via normalize_html() and render it with st.markdown(..., unsafe_allow_html=True)."""
    normalized = normalize_html(html_input)
    if normalized:
        st.markdown(normalized, unsafe_allow_html=True)
    return normalized


def truncate_title_word_boundary(title: Any, max_chars: int = 58) -> str:
    """Return the clean plain-text title, or truncate cleanly at a word boundary with an ellipsis ('…')
    if it exceeds max_chars. Never truncates mid-word or leaves a trailing hyphen or dangling fragment like 'pp'."""
    clean = re.sub(r"\s+", " ", unescape_text(title)).strip()
    if not clean or len(clean) <= max_chars:
        return clean

    # Find last space at or before max_chars - 1
    cutoff = max_chars - 1
    space_idx = clean.rfind(" ", 0, cutoff + 1)
    if space_idx > max(10, cutoff // 2):
        truncated = clean[:space_idx]
    else:
        # If first word is very long, break at word boundary after it if possible
        next_space = clean.find(" ")
        if 0 < next_space <= max_chars + 10:
            truncated = clean[:next_space]
        else:
            truncated = clean[:cutoff]

    truncated = truncated.rstrip(" -–—,:;./\\|(")
    # Remove dangling short citation/preposition fragments at the very end (e.g. "pp", "vol", "no")
    truncated = re.sub(r"\s+\b(?:pp|vol|no|vs|cf|al|ed)\.?$", "", truncated, flags=re.I).rstrip(" -–—,:;./\\|(")
    return f"{truncated}…"


def format_title_with_tooltip_html(title: Any, max_chars: int = 65, style: str = "") -> str:
    """Return an HTML <span> with a word-boundary truncated title and a tooltip containing the full canonical title."""
    full_clean = re.sub(r"\s+", " ", unescape_text(title)).strip() or "Untitled Manuscript"
    disp = truncate_title_word_boundary(full_clean, max_chars=max_chars)
    style_attr = f' style="{style}"' if style else ""
    return f'<span title="{safe_text(full_clean)}"{style_attr}>{safe_text(disp)}</span>'

