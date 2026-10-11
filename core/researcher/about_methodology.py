"""
PaperIQ — Researcher Page 9: About & Methodology (C9)
=====================================================
Requirements:
- How PaperIQ works
- Scoring dimensions & weights
- How research-profile extraction works
- Supported formats (PDF, DOCX, TXT)
- Honest limitations & responsible AI use
- Explicit statement that researchers can only access their own papers (single-user ownership).
"""

from __future__ import annotations

from typing import Dict
import streamlit as st
from utils import render_html, safe_text


def render_researcher_about_and_methodology(theme: Dict[str, str]) -> None:
    """Render Researcher Page 9: About & Methodology (C9)."""
    render_html([
        '<div style="margin-bottom: 18px;">',
        f'<span style="background: {theme["badge_role_bg"]}; border: 1px solid {theme["badge_role_border"]}; color: {theme["badge_role_text"]}; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em;">ℹ️ System Architecture &amp; Extraction Methodology</span>',
        f'<h1 style="margin: 6px 0 4px 0; font-size: 27px; font-weight: 800; color: {theme["text_primary"]};">About &amp; Methodology</h1>',
        f'<p style="margin: 0; color: {theme["text_muted"]}; font-size: 14px;">Transparent documentation of PaperIQ\'s Research Profile extraction pipeline, secondary writing quality weights, supported manuscript formats, and strict honesty &amp; privacy guarantees.</p>',
        '</div>',
    ])

    # 1. How Research-Profile Extraction Works (Primary Researcher Engine)
    render_html([
        f'<div class="iq-card" style="padding: 20px 24px !important; margin-bottom: 16px; border-top: 3px solid {theme["accent_purple"]};">',
        f'<h3 style="margin: 0 0 10px 0; font-size: 18px; font-weight: 800; color: {theme["text_primary"]};">1. How Structured Research-Profile Extraction Works</h3>',
        f'<p style="font-size: 13.5px; color: {theme["text_secondary"]}; line-height: 1.6; margin-bottom: 10px;">In the Researcher Workspace, PaperIQ prioritizes <b>manuscript content synthesis</b> over surface-level writing drills. Each uploaded manuscript undergoes a 4-stage deterministic NLP pipeline:</p>',
        f'<ol style="margin: 0; padding-left: 20px; font-size: 13px; color: {theme["text_primary"]}; line-height: 1.7;">',
        '<li><b>Unicode Normalization &amp; Section Segmentation:</b> Equations, running headers/footers, and broken hyphenations are cleaned while IMRaD and domain-specific headings (<i>Abstract, Introduction, Methodology, Datasets, Results &amp; Discussion, Limitations, Conclusion</i>) are segmented.</li>',
        '<li><b>Decimal- &amp; Abbreviation-Safe Sentence Splitting:</b> Sentences are tokenized while preserving decimal figures (e.g., <code>4.41 per cent</code>, <code>p &lt; 0.05</code>), scholarly abbreviations (<code>et al.</code>, <code>Fig.</code>, <code>e.g.</code>, <code>i.e.</code>), and stripping merged section numbers.</li>',
        '<li><b>6-Dimension Research Profile Extraction:</b> Candidate sentences are scored using discourse markers, section priors, and quantitative density across <b>Research Objective</b>, <b>Methodology &amp; Design</b>, <b>Data / Sample / Materials</b>, <b>Key Results</b>, <b>Main Contributions</b>, and <b>Limitations</b>.</li>',
        '<li><b>Strict Zero-Boilerplate Honesty Rule:</b> If a manuscript does not contain explicit textual evidence for a profile field, literature gap, temporal trend, or future direction, PaperIQ reports <i>"Not found in this manuscript"</i> (or <i>"No trend data found"</i> / <i>"Not stated by the authors"</i>) rather than fabricating template text.</li>',
        '</ol>',
        '</div>',
    ])

    # 2. Secondary Manuscript Quality Dimensions & Weights
    render_html([
        f'<div class="iq-card" style="padding: 20px 24px !important; margin-bottom: 16px; border-top: 3px solid #06B6D4;">',
        f'<h3 style="margin: 0 0 10px 0; font-size: 18px; font-weight: 800; color: {theme["text_primary"]};">2. Secondary Manuscript Quality Dimensions &amp; Weights</h3>',
        f'<p style="font-size: 13.5px; color: {theme["text_secondary"]}; line-height: 1.55; margin-bottom: 12px;">While research content is primary for researchers, PaperIQ also computes a secondary 5-dimension composite writing quality score (0–100):</p>',
        f'<table style="width: 100%; border-collapse: collapse; font-size: 13px; color: {theme["text_primary"]};">',
        f'<tr style="background: {theme["bg_card_inner"]}; border-bottom: 1px solid {theme["border_color"]};">',
        '<th style="padding: 8px 12px; text-align: left;">Dimension</th>',
        '<th style="padding: 8px 12px; text-align: left;">Weight</th>',
        '<th style="padding: 8px 12px; text-align: left;">Analytical Signals</th>',
        '</tr>',
        f'<tr style="border-bottom: 1px solid {theme["border_divider"]};"><td style="padding: 8px 12px; font-weight: 700;">Structure &amp; Organization</td><td style="padding: 8px 12px;">25%</td><td style="padding: 8px 12px; color: {theme["text_secondary"]};">Canonical section coverage (Abstract, Introduction, Methods, Results, Conclusion), heading hierarchy, and section balance.</td></tr>',
        f'<tr style="border-bottom: 1px solid {theme["border_divider"]};"><td style="padding: 8px 12px; font-weight: 700;">Clarity &amp; Academic Style</td><td style="padding: 8px 12px;">20%</td><td style="padding: 8px 12px; color: {theme["text_secondary"]};">Sentence length distribution, passive/hedging balance, academic vocabulary precision, and conciseness.</td></tr>',
        f'<tr style="border-bottom: 1px solid {theme["border_divider"]};"><td style="padding: 8px 12px; font-weight: 700;">Coherence &amp; Flow</td><td style="padding: 8px 12px;">20%</td><td style="padding: 8px 12px; color: {theme["text_secondary"]};">Discourse transition markers, logical progression across paragraphs, and argument continuity.</td></tr>',
        f'<tr style="border-bottom: 1px solid {theme["border_divider"]};"><td style="padding: 8px 12px; font-weight: 700;">Citations &amp; Evidence Grounding</td><td style="padding: 8px 12px;">20%</td><td style="padding: 8px 12px; color: {theme["text_secondary"]};">In-text citation markers (APA/IEEE/numbered), reference list presence, and quantitative evidence density.</td></tr>',
        f'<tr><td style="padding: 8px 12px; font-weight: 700;">Readability</td><td style="padding: 8px 12px;">15%</td><td style="padding: 8px 12px; color: {theme["text_secondary"]};">Calibrated Flesch Reading Ease and syllable complexity suited for scholarly prose.</td></tr>',
        '</table>',
        '</div>',
    ])

    # 3. Supported Formats, Honest Limitations & Single-User Privacy
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        render_html([
            f'<div class="iq-card" style="padding: 18px 20px !important; border-top: 3px solid #10B981; min-height: 220px;">',
            f'<h3 style="margin: 0 0 8px 0; font-size: 16.5px; font-weight: 700; color: {theme["text_primary"]};">📄 Supported Formats &amp; Scope</h3>',
            f'<ul style="margin: 0; padding-left: 18px; font-size: 13px; color: {theme["text_secondary"]}; line-height: 1.65;">',
            '<li><b>Formats:</b> Text-based <code>PDF</code>, Microsoft Word (<code>DOCX</code>), and plain text (<code>TXT</code>) up to 30 MB.</li>',
            '<li><b>Multi-Paper Comparison:</b> Supports comparing 2 or 3 manuscripts simultaneously from either direct file uploads or your personal Research Library.</li>',
            '<li><b>Single-Researcher Isolation:</b> Researchers can only view, query, compare, and export their own papers, projects, tags, and notes. No cross-account sharing is permitted.</li>',
            '</ul>',
            '</div>',
        ])
    with c2:
        render_html([
            f'<div class="iq-card" style="padding: 18px 20px !important; border-top: 3px solid #F59E0B; min-height: 220px;">',
            f'<h3 style="margin: 0 0 8px 0; font-size: 16.5px; font-weight: 700; color: {theme["text_primary"]};">⚖️ Honest Limitations &amp; Responsible AI</h3>',
            f'<ul style="margin: 0; padding-left: 18px; font-size: 13px; color: {theme["text_secondary"]}; line-height: 1.65;">',
            '<li><b>Scanned PDFs:</b> Image-only PDFs without an embedded text layer require external OCR prior to upload.</li>',
            '<li><b>Heuristic &amp; Extractive Grounding:</b> PaperIQ extracts verbatim sentences and statistical figures from the manuscript; it does not verify external factual accuracy or peer-review validity.</li>',
            '<li><b>English Calibration:</b> Discourse markers and readability metrics are calibrated for English-language academic manuscripts.</li>',
            '</ul>',
            '</div>',
        ])
