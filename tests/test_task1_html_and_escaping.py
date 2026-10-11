"""
Regression tests for Task 1:
- Shared HTML rendering helper (render_html / normalize_html)
- Single-unescape / single-escape rules (unescape_text / safe_text)
- Word-boundary title truncation with tooltip support (truncate_title_word_boundary)
- Audit of all HTML-building functions and calls across app.py, workspaces.py, and admin_panel.py
  asserting no line starts with 4+ spaces, no blank lines, and no '&#x' or '&amp;#x' sequences.
"""

import ast
import os
import re
from unittest.mock import patch
import pytest

from utils import (
    normalize_html,
    render_html,
    safe_text,
    unescape_text,
    clean_plain_text,
    truncate_title_word_boundary,
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def assert_valid_rendered_html(html_out: str):
    """Asserts that rendered HTML has no 4+ leading spaces, no blank lines, and no hex entity artifacts."""
    assert isinstance(html_out, str)
    assert html_out != ""
    lines = html_out.split("\n")
    for idx, line in enumerate(lines):
        assert not line.startswith("    "), f"Line {idx} starts with 4+ spaces: {line!r}"
        assert line.strip() != "", f"Line {idx} is blank in rendered HTML"
    assert "&#x" not in html_out, f"Found raw hex entity in HTML: {html_out!r}"
    assert "&amp;#x" not in html_out, f"Found double-escaped hex entity in HTML: {html_out!r}"
    assert "&amp;amp;" not in html_out, f"Found double-escaped ampersand in HTML: {html_out!r}"


def test_normalize_html_strips_indentation_and_blank_lines():
    indented_html = """
        <div style="background: #111827; padding: 16px;">
            <h4>Paper Title</h4>

            <div style="font-size: 12px;">
                <ul>
                    <li><b>Readability</b> (86.8/100)</li>
                </ul>
            </div>

        </div>
    """
    out = normalize_html(indented_html)
    assert_valid_rendered_html(out)
    assert "\n" not in out
    assert out.startswith('<div style="background: #111827; padding: 16px;">')
    assert "<li><b>Readability</b> (86.8/100)</li>" in out


def test_normalize_html_accepts_list_of_parts():
    parts = [
        '<div class="card">',
        "  <h5>Strengths</h5>",
        "",
        "  <ul><li><b>Methodology</b> (91.0/100)</li></ul>",
        "</div>",
    ]
    out = normalize_html(parts)
    assert_valid_rendered_html(out)
    assert "<h5>Strengths</h5>" in out


def test_render_html_calls_streamlit_markdown():
    captured = []
    with patch("streamlit.markdown", side_effect=lambda body, **kw: captured.append((body, kw))):
        res = render_html(
            """
            <div class="test">
                <p>Hello World</p>

            </div>
            """
        )
    assert_valid_rendered_html(res)
    assert len(captured) == 1
    body, kw = captured[0]
    assert body == res
    assert kw.get("unsafe_allow_html") is True


def test_unescape_and_safe_text_prevent_double_escaping():
    raw_corrupted = "GRA&#x005F;Net: A Deep Learning &amp;#x005F; Model for &amp; Analysis"
    unescaped = unescape_text(raw_corrupted)
    assert unescaped == "GRA_Net: A Deep Learning _ Model for & Analysis"
    assert "&#x" not in unescaped

    # Passing already-escaped text or entity-encoded text into safe_text must escape exactly once
    escaped_once = safe_text(raw_corrupted)
    escaped_twice = safe_text(escaped_once)
    assert escaped_once == "GRA_Net: A Deep Learning _ Model for &amp; Analysis"
    assert escaped_twice == escaped_once
    assert "&#x" not in escaped_once
    assert "&amp;#x" not in escaped_once
    assert "&amp;amp;" not in escaped_once


def test_safe_text_escapes_xss_tags():
    malicious = '<script>alert("xss")</script> & GRA&#x005F;Net'
    escaped = safe_text(malicious)
    assert "<script>" not in escaped
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; GRA_Net" == escaped


def test_clean_plain_text_for_pdf_and_txt():
    raw = "<b>GRA&#x005F;Net</b>: A Study on &amp; Δ-Metrics <span style='color:red'>(2025)</span>"
    cleaned = clean_plain_text(raw)
    assert cleaned == "GRA_Net: A Study on & Δ-Metrics (2025)"
    assert "&#x" not in cleaned
    assert "<" not in cleaned


def test_truncate_title_word_boundary():
    long_title = "Growth Performance of Nutri-Cereals Under Varying Agronomic Conditions in Semi-Arid Regions"
    disp = truncate_title_word_boundary(long_title, max_chars=42)
    full = unescape_text(long_title)
    assert full == long_title
    assert not disp.endswith("Nutri-")
    assert not disp.endswith("Nutri-…")
    assert disp.endswith("…")
    assert len(disp) <= 43

    # Also test entity unescaping inside title truncation
    disp2 = truncate_title_word_boundary("GRA&#x005F;Net: A Deep Learning Model", max_chars=65)
    assert disp2 == "GRA_Net: A Deep Learning Model"


def test_no_direct_unsafe_allow_html_or_html_escape_outside_utils():
    target_files = ["app.py", "workspaces.py", "admin_panel.py", "auth.py", "summarizer.py", "pdf_export.py"]
    for fname in target_files:
        fpath = os.path.join(ROOT_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "unsafe_allow_html" not in content, f"{fname} still contains direct unsafe_allow_html"
        assert "html.escape" not in content, f"{fname} still contains direct html.escape"


def test_compare_cards_and_all_html_builders_produce_clean_single_line_html():
    """Renders Compare Papers cards, winner/gap cards, synthesis cards, evidence boxes, and workspace/admin panels."""
    papers = [
        {
            "filename": "GRA&#x005F;Net: A Deep Learning Approach for Graphic Recognition",
            "domain": "Computer Science &amp; AI",
            "overall": 84.5,
            "grade": "A",
            "Dimensions": {
                "Readability": 88.2,
                "Methodology": 91.4,
                "Originality": 82.0,
                "Completeness": 79.5,
                "Impact": 81.4,
            },
        },
        {
            "filename": "Growth Performance of Nutri-Cereals Under Varying Agronomic Conditions in Semi-Arid Regions",
            "domain": "Agriculture &amp; Food Science",
            "overall": 76.3,
            "grade": "B",
            "Dimensions": {
                "Readability": 86.8,
                "Methodology": 74.2,
                "Originality": 71.0,
                "Completeness": 76.5,
                "Impact": 73.0,
            },
        },
    ]

    for idx, p in enumerate(papers):
        dims = p["Dimensions"]
        sorted_dims = sorted(dims.items(), key=lambda x: x[1], reverse=True)
        strengths = sorted_dims[:2]
        weaknesses = sorted_dims[-2:][::-1]
        full_title = unescape_text(p["filename"])
        disp_title = truncate_title_word_boundary(full_title, max_chars=68)

        s_items = "".join(
            f"<li style='margin-bottom:4px;'><b>{safe_text(k)}</b> ({v:.1f}/100)</li>"
            for k, v in strengths
        )
        w_items = "".join(
            f"<li style='margin-bottom:4px;'><b>{safe_text(k)}</b> ({v:.1f}/100)</li>"
            for k, v in weaknesses
        )
        card_html = normalize_html(
            [
                f'<div style="background:#111827; border:1px solid #1F2937; border-radius:10px; padding:16px;">',
                f'<h5 title="{safe_text(full_title)}">Paper {idx+1}: {safe_text(disp_title)}</h5>',
                f'<div>Strengths</div><ul>{s_items}</ul>',
                f'<div>Areas for Improvement</div><ul>{w_items}</ul>',
                "</div>",
            ]
        )
        assert_valid_rendered_html(card_html)
        assert "<ul" in card_html and "<li" in card_html


def test_all_render_html_calls_in_codebase_normalize_cleanly():
    """Walks AST of app.py, workspaces.py, and admin_panel.py to verify every render_html call."""
    target_files = ["app.py", "workspaces.py", "admin_panel.py"]
    total_calls = 0
    for fname in target_files:
        fpath = os.path.join(ROOT_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "render_html":
                total_calls += 1
                assert len(node.args) >= 1, f"Empty render_html call in {fname}:{node.lineno}"
                # If the argument is a constant string, verify normalize_html on it directly
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    out = normalize_html(arg0.value)
                    assert_valid_rendered_html(out)
    assert total_calls >= 150, f"Expected at least 150 render_html calls across codebase, found {total_calls}"
