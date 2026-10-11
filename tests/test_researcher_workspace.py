"""
Regression & Feature Test Suite for the PaperIQ Researcher Workspace Overhaul
=============================================================================
Covers:
- Part B: Idempotent DB migration (safe when run twice) + ownership enforcement
- Part C: Research Profile extraction, honest Research Insights, Comparison Matrix (2 & 3 papers),
          Ask PaperIQ (single & multi-paper scope), and Researcher PDF/TXT exports
- Part D: Sentence splitter on decimals ('growth rate of 4.41 per cent'), abbreviations ('et al.', 'Fig.'),
          merged heading prefix stripping ('1 Growth Performance of Millets in India A compound...'),
          unified word/sentence counts, and zero raw HTML / entity leaks.
- Part E5: 3-account isolation (Student A, Researcher B, Researcher C) + ID tampering protection.
"""

from __future__ import annotations

import sqlite3
import uuid
import pytest

import auth
import pdf_export
import research_engine
import summarizer
from core import registry


def test_idempotent_researcher_migration():
    """Part B: Migration must run twice safely without raising errors or losing data."""
    auth.create_users_table()
    conn = auth.get_db_connection()
    try:
        auth.run_researcher_migrations(conn)
        auth.run_researcher_migrations(conn)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        required = {
            "projects",
            "project_papers",
            "paper_metadata",
            "tags",
            "paper_tags",
            "research_notes",
            "activity_log",
            "saved_comparisons",
            "paper_chats",
        }
        assert required.issubset(tables), f"Missing tables: {required - tables}"
    finally:
        conn.close()


def test_sentence_splitter_decimals_abbreviations_and_headings():
    """Part D1 & D2: 'growth rate of 4.41 per cent', 'et al.', 'Fig.', and merged section headers."""
    sample = (
        "1 Growth Performance of Millets in India A compound annual growth rate of 4.41 per cent "
        "was recorded during Period III as shown in Fig. 2 and reported by Sharma et al. (2022). "
        "Furthermore, e.g. pearl millet and sorghum exhibited p < 0.05 significance across 12.85 million hectares."
    )
    sents = summarizer.split_into_sentences(sample)
    assert len(sents) == 2, f"Expected 2 clean sentences, got {sents}"
    assert "4.41 per cent" in sents[0], f"Decimal was broken: {sents[0]}"
    assert not sents[0].startswith("1 Growth Performance"), f"Merged heading was not stripped: {sents[0]}"
    assert sents[0].startswith("A compound annual growth rate of 4.41 per cent"), f"Unexpected start: {sents[0]}"
    assert "Fig. 2" in sents[0]
    assert "et al." in sents[0]
    assert "12.85 million" in sents[1]

    counts = summarizer.compute_text_counts(sample)
    assert counts["sentence_count"] == 2
    assert counts["word_count"] > 25


def test_honesty_rule_and_research_profile_extraction():
    """Part C2 & C6: Honest extraction returns 'Not found in this manuscript' when absent, and extracts real data when present."""
    # 1. Empirical agriculture paper with decimals, trends, gaps, future work
    agri_text = (
        "Growth Performance of Nutri-Cereals in India\n"
        "R. K. Sharma, A. Patel\n"
        "Journal of Agricultural Economics, 2023\n"
        "Keywords: millets, compound annual growth rate, instability index, food security\n\n"
        "Abstract\n"
        "The objective of this study is to examine the growth performance and instability of millets in India from 1966-67 to 2021-22.\n\n"
        "Methodology\n"
        "Secondary time-series data on area, production, and yield were collected from the Ministry of Agriculture and Farmers Welfare. "
        "We employ the compound annual growth rate (CAGR) and Cuddy-Della Valle instability index to evaluate decadal performance.\n\n"
        "Results and Discussion\n"
        "Results show that pearl millet productivity registered a compound annual growth rate of 4.41 per cent during 2000-01 to 2021-22. "
        "However, this study is limited by the lack of district-level disaggregated farm cost data across rainfed regions. "
        "Future research should focus on climate-resilient cultivar adoption and minimum support price procurement.\n"
    )
    meta = research_engine.extract_paper_metadata(agri_text)
    assert "Nutri-Cereals" in meta["title"]
    assert meta["year"] == "2023"
    assert "Agriculture" in meta["domain"] or "Economics" in meta["domain"]
    assert len(meta["keywords"]) >= 3

    prof = research_engine.extract_research_profile(agri_text)
    assert prof["objective"]["found"] is True
    assert prof["methodology"]["found"] is True
    assert prof["data_materials"]["found"] is True
    assert prof["key_results"]["found"] is True
    assert "4.41 per cent" in prof["key_results"]["value"]
    assert prof["limitations"]["found"] is True

    ins = research_engine.extract_honest_research_insights(agri_text)
    assert len(ins["gaps"]) >= 1
    assert "Conduct a comprehensive empirical evaluation" not in ins["gaps"][0]["opportunity"]
    assert len(ins["trends"]) >= 1
    assert "4.41" in ins["trends"][0]["statement"]
    assert len(ins["future_directions"]) >= 1

    # 2. Minimal theoretical note with NO datasets, NO trends, NO limitations, NO future work
    minimal_text = (
        "A Note on Purely Algebraic Ring Homomorphisms\n"
        "Introduction\n"
        "This paper investigates the abstract properties of commutative ring homomorphisms under identity mappings. "
        "We prove that every surjective morphism preserves the ideal lattice structure."
    )
    min_prof = research_engine.extract_research_profile(minimal_text)
    assert min_prof["limitations"]["found"] is False
    assert min_prof["limitations"]["value"] in ("Not found in this manuscript", "No limitations explicitly stated by the authors")
    assert min_prof["data_materials"]["found"] is False
    assert min_prof["data_materials"]["value"] == "Not found in this manuscript"

    min_ins = research_engine.extract_honest_research_insights(minimal_text)
    assert min_ins["gaps"] == []
    assert min_ins["trends"] == []
    assert min_ins["future_directions"] == []


def test_three_account_isolation_and_project_deletion_semantics():
    """Part B & E5: Student A, Researcher B, and Researcher C strict ownership isolation + project delete modes."""
    sfx = uuid.uuid4().hex[:6]
    stu_a = f"stu_a_{sfx}"
    res_b = f"res_b_{sfx}"
    res_c = f"res_c_{sfx}"

    auth.register_user(stu_a, f"{stu_a}@test.edu", "Pass123!@#", role="Student")
    auth.register_user(res_b, f"{res_b}@test.edu", "Pass123!@#", role="Researcher")
    auth.register_user(res_c, f"{res_c}@test.edu", "Pass123!@#", role="Researcher")

    # Researcher B saves 2 papers and 2 projects
    aid_b1 = auth.save_user_analysis(
        username=res_b,
        filename="millet_growth.pdf",
        paper_title="Growth Performance of Millets in India",
        overall_score=84.5,
        structure_score=86.0,
        clarity_score=83.0,
        coherence_score=85.0,
        citation_score=82.0,
        readability_score=86.5,
        summary="Study of millet growth rate of 4.41 per cent.",
        feedback=[],
        extracted_text="The study examines millet growth rate of 4.41 per cent from 1966-67 to 2021-22.",
        sections={"Abstract": "The study examines millet growth rate of 4.41 per cent."},
        metrics={},
        domain="Agriculture & Food Science",
    )
    aid_b2 = auth.save_user_analysis(
        username=res_b,
        filename="granet_deep_learning.pdf",
        paper_title="GRA_Net: A Deep Learning Architecture for Crop Segmentation",
        overall_score=88.0,
        structure_score=90.0,
        clarity_score=87.0,
        coherence_score=88.0,
        citation_score=89.0,
        readability_score=86.0,
        summary="Deep learning model for segmentation.",
        feedback=[],
        extracted_text="We propose a convolutional neural network transformer for image segmentation achieving 94.2% accuracy.",
        sections={"Methodology": "We propose a convolutional neural network transformer."},
        metrics={},
        domain="Computer Science & AI",
    )

    ok_p1, _, pid_b1 = auth.create_project(res_b, "Agri Economics Review", "Millet studies")
    ok_p2, _, pid_b2 = auth.create_project(res_b, "AI Vision Benchmarks", "Deep learning papers")
    assert ok_p1 and pid_b1
    assert ok_p2 and pid_b2

    assert auth.assign_paper_to_project(res_b, pid_b1, aid_b1) is True
    assert auth.assign_paper_to_project(res_b, pid_b2, aid_b2) is True
    assert auth.set_paper_tags(res_b, aid_b1, ["millets", "cagr"]) is True
    ok_note, _, note_id_b = auth.add_research_note(res_b, aid_b1, "Verify 4.41% CAGR in Period III.")
    assert ok_note and note_id_b

    # Researcher C must see ZERO papers, ZERO projects, ZERO notes from Researcher B
    assert auth.get_researcher_library(res_c) == []
    assert auth.get_user_projects(res_c) == []
    assert auth.get_single_analysis_for_user(res_c, aid_b1) is None
    assert auth.get_project_by_id(res_c, pid_b1) is None

    # ID Tampering attempts by Researcher C or Student A must be rejected
    assert auth.assign_paper_to_project(res_c, pid_b1, aid_b1) is False
    assert auth.rename_project(res_c, pid_b1, "Hacked Name")[0] is False
    assert auth.delete_project(res_c, pid_b1, delete_papers=True)[0] is False
    assert auth.update_research_note(res_c, note_id_b, "Tampered note") is False
    assert auth.delete_research_note(res_c, note_id_b) is False
    assert auth.set_paper_tags(stu_a, aid_b1, ["hacked"]) is False

    # Deleting project pid_b1 with delete_papers=False keeps aid_b1 in Researcher B's library
    ok_del, _ = auth.delete_project(res_b, pid_b1, delete_papers=False)
    assert ok_del is True
    lib_b_after = auth.get_researcher_library(res_b)
    assert any(p["id"] == aid_b1 for p in lib_b_after), "Paper should remain in library when project is deleted with delete_papers=False"


def test_comparison_matrix_and_pdf_exports():
    """Part C4 & C7: 2- and 3-paper comparison matrix, cross-domain notice, and all 4 Researcher PDF/TXT exports."""
    papers = [
        {
            "id": 1,
            "title": "Growth Performance of Nutri-Cereals in India",
            "text": (
                "The objective of this study is to examine the growth performance of millets in India. "
                "Secondary time-series data from 1966-67 to 2021-22 were analyzed using compound annual growth rate (CAGR). "
                "Results show a growth rate of 4.41 per cent in pearl millet yield. "
                "However, the study is limited by reliance on aggregated state-level secondary data."
            ),
            "scores": {"overall_score": 84.0, "structure_score": 85.0, "clarity_score": 82.0, "coherence_score": 84.0, "citation_score": 83.0, "readability_score": 86.0},
            "overall_score": 84.0,
        },
        {
            "id": 2,
            "title": "GRA_Net: Deep Learning for Autonomous Crop Segmentation",
            "text": (
                "This paper aims to address real-time weed and crop segmentation under variable field lighting. "
                "We propose a convolutional neural network with multi-head attention trained on 15,000 UAV multispectral images. "
                "Experimental results demonstrate an accuracy of 96.4% and F1-score of 94.8%. "
                "A key limitation is computational latency on edge microcontroller hardware."
            ),
            "scores": {"overall_score": 89.0, "structure_score": 91.0, "clarity_score": 88.0, "coherence_score": 89.0, "citation_score": 90.0, "readability_score": 87.0},
            "overall_score": 89.0,
        },
    ]
    comp = research_engine.build_comparison_matrix_and_synthesis(papers)
    assert comp["is_cross_domain"] is True
    assert "Cross-Domain Comparison Detected" in comp["cross_domain_notice"]
    assert len(comp["matrix_rows"]) >= 8
    assert len(comp["similarities"]) >= 1
    assert len(comp["differences"]) >= 2

    # Verify all 4 Researcher PDF builders return valid non-empty PDFs
    p0_prof = research_engine.extract_research_profile(papers[0]["text"])
    p0_ins = research_engine.extract_honest_research_insights(papers[0]["text"])

    paper_pdf = pdf_export.build_researcher_paper_pdf({
        "title": papers[0]["title"],
        "metadata": {"authors": "R. Sharma", "year": "2023", "domain": "Agriculture & Food Science", "keywords": ["millets", "cagr"]},
        "profile": p0_prof,
        "summary": "Executive summary of millet growth.",
        "overall_score": 84.0,
    })
    assert paper_pdf.startswith(b"%PDF") and len(paper_pdf) > 1200

    cmp_pdf = pdf_export.build_comparison_pdf(papers, comp)
    assert cmp_pdf.startswith(b"%PDF") and len(cmp_pdf) > 1200

    ins_pdf = pdf_export.build_insights_pdf(papers[0]["title"], p0_ins, {"domain": "Agriculture & Food Science"})
    assert ins_pdf.startswith(b"%PDF") and len(ins_pdf) > 1200

    proj_pdf = pdf_export.build_project_report_pdf(
        {"name": "Food Security Benchmark", "description": "Cross-paper review"},
        [{"title": p["title"], "profile": p0_prof, "overall_score": p["overall_score"]} for p in papers],
        comp,
        [{"paper_title": papers[0]["title"], "note_text": "Key baseline paper.", "created_at": "2026-10-11"}],
    )
    assert proj_pdf.startswith(b"%PDF") and len(proj_pdf) > 1200


def test_researcher_navigation_registry_exact_9_sections():
    """Part A: Verify exact 9 Researcher navigation sections are registered."""
    labels = [lbl for lbl, _ in registry.RESEARCHER_NAV_ITEMS]
    expected = [
        "🏠 Researcher Dashboard",
        "📄 Analyze Research Paper",
        "📚 Research Library",
        "🔄 Advanced Paper Comparison",
        "💬 Ask PaperIQ",
        "💡 Research Insights",
        "🗂️ Research History & Reports",
        "⚙️ Settings & Privacy",
        "ℹ️ About & Methodology",
    ]
    assert labels == expected


def test_student_unchanged_and_researcher_all_9_pages_render_cleanly(monkeypatch):
    """Verify Student workspace navigation/behavior is unchanged and all 9 Researcher pages render cleanly with valid HTML."""
    import logging
    import streamlit as st
    import utils
    for name in list(logging.root.manager.loggerDict):
        if "streamlit" in name:
            logging.getLogger(name).setLevel(logging.ERROR)
    from core.researcher import (
        dashboard,
        analyze,
        library,
        comparison,
        ask_paperiq,
        insights,
        history_reports,
        settings_privacy,
        about_methodology,
    )

    # 1. Verify Student navigation remains unchanged and separate from Researcher
    student_labels = [lbl for sec in registry.STUDENT_NAV_SECTIONS for lbl, _ in sec["items"]]
    assert "🏠 Student Dashboard" in student_labels
    assert "📊 Writing Quality & Feedback" in student_labels
    assert "📚 Research Library" not in student_labels
    assert "🗂️ Research History & Reports" not in student_labels

    # 2. Seed a Researcher account with 2 diverse papers and a project
    sfx = uuid.uuid4().hex[:6]
    res_user = f"res_ui_{sfx}"
    auth.create_users_table()
    auth.register_user(res_user, f"{res_user}@test.edu", "Pass123!@#", role="Researcher")

    p1_text = (
        "Growth Performance of Nutri-Cereals in India\n"
        "R. K. Sharma, A. Patel\n"
        "Journal of Agricultural Economics, 2023\n"
        "Keywords: millets, compound annual growth rate, instability index\n\n"
        "Abstract\n"
        "The objective of this study is to examine the growth performance of millets in India from 1966-67 to 2021-22.\n\n"
        "Methodology\n"
        "Secondary time-series data were analyzed using compound annual growth rate (CAGR).\n\n"
        "Results and Discussion\n"
        "Results show that pearl millet productivity registered a compound annual growth rate of 4.41 per cent during 2000-01 to 2021-22. "
        "However, this study is limited by the lack of district-level disaggregated farm cost data. "
        "Future research should focus on climate-resilient cultivar adoption.\n"
    )
    p2_text = (
        "GRA_Net: A Deep Learning Architecture for Crop Segmentation\n"
        "M. Chen, L. Zhang\n"
        "IEEE Transactions, 2024\n"
        "Keywords: deep learning, convolutional neural network, crop segmentation\n\n"
        "Abstract\n"
        "The objective of this paper is to address real-time crop segmentation in UAV imagery.\n\n"
        "Methodology\n"
        "We propose GRA_Net, a hybrid convolutional neural network trained on 12,500 field images.\n\n"
        "Results\n"
        "Experimental results show that GRA_Net achieved an accuracy of 96.4 per cent. "
        "However, inference latency is limited by edge hardware constraints.\n"
    )

    aid1 = auth.save_user_analysis(
        username=res_user,
        filename="millets_2023.pdf",
        paper_title="Growth Performance of Nutri-Cereals in India",
        overall_score=84.5,
        structure_score=86.0,
        clarity_score=83.0,
        coherence_score=85.0,
        citation_score=84.0,
        readability_score=84.5,
        summary="Empirical study of millets in India.",
        feedback=[],
        extracted_text=p1_text,
        sections=summarizer.segment_paper_sections(p1_text),
    )
    aid2 = auth.save_user_analysis(
        username=res_user,
        filename="granet_2024.pdf",
        paper_title="GRA_Net: A Deep Learning Architecture for Crop Segmentation",
        overall_score=89.0,
        structure_score=90.0,
        clarity_score=88.0,
        coherence_score=89.0,
        citation_score=90.0,
        readability_score=88.0,
        summary="Deep learning architecture for crop segmentation.",
        feedback=[],
        extracted_text=p2_text,
        sections=summarizer.segment_paper_sections(p2_text),
    )
    _, _, pid = auth.create_project(res_user, "Cross-Domain Benchmark", "Agri + AI review")
    auth.assign_paper_to_project(res_user, pid, aid1)
    auth.assign_paper_to_project(res_user, pid, aid2)

    captured_html = []

    def spy_markdown(body, unsafe_allow_html=False, **kwargs):
        s = str(body or "")
        if unsafe_allow_html:
            assert "\n\n" not in s
            for line in s.split("\n"):
                assert not line.startswith("    "), f"4+ leading spaces found in HTML: {line[:80]}"
            assert "&amp;#x" not in s, f"Double-escaped entity found in HTML: {s[:120]}"
        captured_html.append(s)

    class _SessionDict(dict):
        def __getattr__(self, item):
            return self.get(item)

        def __setattr__(self, key, value):
            self[key] = value

    mock_state = _SessionDict({
        "username": res_user,
        "role": "Researcher",
        "logged_in": True,
        "analyzed": True,
        "paper_text": p1_text,
        "filename": "millets_2023.pdf",
        "paper_title": "Growth Performance of Nutri-Cereals in India",
        "sections": summarizer.segment_paper_sections(p1_text),
        "scores": {
            "overall_score": 84.5,
            "structure_score": 86.0,
            "clarity_score": 83.0,
            "coherence_score": 85.0,
            "citation_score": 84.0,
            "readability_score": 84.5,
        },
        "current_analysis_id": aid1,
    })

    monkeypatch.setattr(st, "markdown", spy_markdown)
    monkeypatch.setattr(st, "plotly_chart", lambda *a, **kw: None)
    monkeypatch.setattr(st, "session_state", mock_state)

    from collections import defaultdict
    test_theme = defaultdict(lambda: "#1e293b")

    # Render all 9 Researcher pages via registry.dispatch_researcher_page and verify output
    for nav_label, _ in registry.RESEARCHER_NAV_ITEMS:
        handled = registry.dispatch_researcher_page(
            canonical_page=nav_label,
            theme=test_theme,
            username=res_user,
            user_data={"username": res_user, "role": "Researcher", "email": f"{res_user}@test.edu"},
            navigate_to=lambda p: None,
            load_analysis_into_session=lambda d: None,
            extract_text_from_file=lambda f: p1_text,
            clean_text=lambda t: t,
            analyze_full_document=lambda t: {"overall_score": 85.0},
            get_clean_display_title=lambda t, f="": t or f,
        )
        assert handled is True

    joined_html = "\n".join(captured_html)
    assert "Researcher Dashboard" in joined_html
    assert "Research Library" in joined_html
    assert "Advanced Paper Comparison" in joined_html
    assert "Structured Research Content Matrix" in joined_html
    assert "Cross-Domain" in joined_html
    assert "Research Insights" in joined_html
    assert "Writing Improvements" not in joined_html
    assert "Researchers can only access their own uploaded papers" in joined_html

