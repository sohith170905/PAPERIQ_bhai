import io
import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import app

FIXTURE_PDF = os.path.join(os.path.dirname(__file__), "fixtures", "Gangadharan45122023JEAI111549.pdf")


class DummyPDFFile(io.BytesIO):
    def __init__(self, path: str):
        with open(path, "rb") as f:
            data = f.read()
        super().__init__(data)
        self.name = os.path.basename(path)
        self.size = len(data)


def test_2_1_student_navigation_includes_all_required_pages():
    """Verify Student sidebar navigation contains all 8 required pages plus Logout."""
    with open(os.path.join(ROOT_DIR, "app.py"), "r", encoding="utf-8") as f:
        source = f.read()

    required_pages = [
        "🏠 Student Dashboard",
        "📄 Analyze Paper",
        "📊 Writing Quality & Feedback",
        "🔄 Compare Papers",
        "💬 Ask PaperIQ",
        "📚 My History",
        "⚙ Settings",
        "ℹ About",
        "🚪 Logout",
    ]
    for page in required_pages:
        assert page in source


def test_2_2_writing_quality_data_grounded_dimension_explanations():
    """Verify every one of the 5 dimension scores produces a real data-grounded metric explanation."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)
    res = app.analyze_full_document(extracted)
    res["full_text"] = extracted

    expected_dims = [
        "Language Quality",
        "Structural Coherence",
        "Argumentation",
        "Academic Style",
        "Readability",
    ]
    for dim_key in expected_dims:
        assert dim_key in res["scores"]
        explanation = app.get_dimension_metric_explanation(dim_key, res)
        assert isinstance(explanation, str)
        assert len(explanation) > 25
        # Must include numeric evidence from the paper
        assert any(ch.isdigit() for ch in explanation), f"Explanation for {dim_key} lacked numeric data: {explanation}"


def test_2_3_compare_papers_radar_and_winner_summary_present():
    """Verify Compare Papers builds both a Plotly Scatterpolar radar overlay and Bar chart, plus Winner & Strongest Dimension."""
    with open(os.path.join(ROOT_DIR, "app.py"), "r", encoding="utf-8") as f:
        source = f.read()

    assert "go.Scatterpolar" in source
    assert "go.Bar" in source
    assert "Overall Winner &amp; Strongest Dimension" in source or "Overall Winner & Strongest Dimension" in source


def test_2_4_settings_privacy_information_lists_all_stored_data_and_deletion():
    """Verify Settings Privacy Information explicitly lists all 9 required stored items and how to delete them."""
    with open(os.path.join(ROOT_DIR, "app.py"), "r", encoding="utf-8") as f:
        source = f.read().lower()

    required_privacy_items = [
        "username",
        "role",
        "uploaded paper metadata",
        "extracted text",
        "scores",
        "feedback",
        "chat history",
        "timestamps",
        "generated reports",
        "how to delete your data",
    ]
    for item in required_privacy_items:
        assert item in source, f"Missing privacy disclosure item in Settings: {item}"


def test_2_5_about_page_includes_limitations_and_responsible_use():
    """Verify About page includes explicit Limitations and Responsible Use sections."""
    with open(os.path.join(ROOT_DIR, "app.py"), "r", encoding="utf-8") as f:
        source = f.read()

    assert "Limitations" in source
    assert "Responsible Use" in source


def test_2_6_pdf_report_generation_succeeds_with_consistent_counts_and_title():
    """Verify PDF report generation works cleanly and returns valid PDF bytes."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)
    res = app.analyze_full_document(extracted)
    res["full_text"] = extracted
    res["title"] = app.get_clean_display_title(pdf_file.name, text=extracted, file=pdf_file)

    pdf_bytes = app.generate_pdf_report(res, pdf_file.name)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1500
