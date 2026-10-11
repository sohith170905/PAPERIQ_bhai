"""
Regression tests for Task 2:
- All 4 PDF builders in pdf_export.py (build_summary_pdf, build_analysis_pdf, build_comparison_pdf, build_chat_pdf)
- Filename sanitizer get_pdf_filename
- Unicode safety (±, Δ, %, accented letters, Greek letters, em-dash)
- Entity unescaping and HTML stripping (no '&#x005F;' or '<div>' in PDF text)
- Page numbering ("Page X of Y") and embedded chart verification
"""

import io
import pdfplumber
import pytest

from pdf_export import (
    build_summary_pdf,
    build_analysis_pdf,
    build_comparison_pdf,
    build_chat_pdf,
    get_pdf_filename,
)


SPECIAL_TITLE = 'GRA&#x005F;Net: α/β &amp; Δ ± 5% — Café "Study" [2026]'


def extract_pdf_text_and_images(pdf_bytes: bytes):
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF"), "Output is not a valid PDF header"
    assert len(pdf_bytes) > 1200, f"PDF size unexpectedly small: {len(pdf_bytes)} bytes"

    full_text = []
    total_images = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 1
        for page in pdf.pages:
            txt = page.extract_text() or ""
            full_text.append(txt)
            total_images += len(page.images)

    joined = "\n".join(full_text)
    assert "&#x" not in joined, f"Found unescaped hex entity in PDF text: {joined!r}"
    assert "&amp;" not in joined, f"Found unescaped &amp; entity in PDF text: {joined!r}"
    assert "<div" not in joined and "<ul" not in joined and "<li" not in joined
    assert "Page 1 of" in joined, "Missing 'Page X of Y' footer in PDF"
    return joined, total_images


@pytest.mark.parametrize("mode", ["Short", "Medium", "Long"])
def test_build_summary_pdf_modes(mode):
    summary_data = {
        "executive_overview": "GRA&#x005F;Net achieves 94.2% ± 1.1% accuracy with Δ = +4.5% over baseline in Café settings.",
        "takeaways": [
            "Introduces graph-relational attention (α = 0.05) for layout analysis.",
            "Reduces inference latency by 32% &amp; improves F1 score.",
        ],
        "section_breakdown": {
            "Abstract": "Presents GRA&#x005F;Net for document representation learning.",
            "Methodology": "Uses multi-head graph attention with residual connections.",
            "Results and Discussion": "Outperforms prior benchmarks by Δ = 4.5% ± 0.3%.",
            "Conclusion": "Demonstrates scalable performance across 3 datasets.",
        },
        "keywords": ["GRA_Net", "Graph Attention", "Document AI", "Δ-Metrics"],
    }
    metadata = {
        "domain": "Computer Science & AI",
        "overall": 86.4,
        "grade": "A",
        "word_count": 5420,
        "sentence_count": 240,
        "reading_time_min": 27.1,
    }
    pdf_bytes = build_summary_pdf(SPECIAL_TITLE, mode, summary_data, metadata)
    text, _ = extract_pdf_text_and_images(pdf_bytes)
    assert "GRA_Net" in text
    assert mode in text
    assert "Executive Overview" in text or "Key Takeaways" in text


def test_build_analysis_pdf_includes_charts_and_all_sections():
    record = {
        "filename": SPECIAL_TITLE,
        "domain": "Computer Science &amp; AI",
        "overall": 85.2,
        "grade": "A",
        "word_count": 6120,
        "sentence_count": 285,
        "vocab_diversity": 42.8,
        "Dimensions": {
            "Readability": 88.0,
            "Methodology": 90.5,
            "Originality": 82.0,
            "Completeness": 81.5,
            "Impact": 84.0,
        },
        "Feedback": {
            "strengths": [
                "Rigorous ablation study across α and β hyperparameters.",
                "Clear mathematical formulation with ±95% confidence intervals.",
            ],
            "weaknesses": [
                "Limited evaluation on low-resource handwritten manuscripts — Why: dataset bias; Action: evaluate on IAM & RIMES datasets.",
            ],
        },
        "Summary": {
            "Abstract": "This paper introduces GRA&#x005F;Net for structured document understanding.",
            "Introduction": "Addresses layout variability in multi-column academic manuscripts.",
            "Methodology": "Combines spatial graph convolutions with transformer encoders.",
            "Results and Discussion": "Achieves 94.2% ± 0.8% accuracy (Δ = +3.9%).",
            "Conclusion": "Future work will extend GRA_Net to multilingual corpora.",
        },
    }
    pdf_bytes = build_analysis_pdf(record)
    text, total_images = extract_pdf_text_and_images(pdf_bytes)
    assert "GRA_Net" in text
    assert "85.2" in text
    assert "Readability" in text
    assert "Methodology" in text
    assert total_images >= 1, "Expected embedded Plotly radar/bar chart PNG images in Analysis PDF"


def test_build_comparison_pdf_with_3_papers_and_charts():
    papers = [
        {
            "filename": SPECIAL_TITLE,
            "domain": "Computer Science & AI",
            "overall": 86.5,
            "grade": "A",
            "word_count": 5800,
            "sentence_count": 260,
            "vocab_diversity": 44.1,
            "Dimensions": {
                "Readability": 88.2,
                "Methodology": 91.0,
                "Originality": 84.5,
                "Completeness": 83.0,
                "Impact": 85.8,
            },
        },
        {
            "filename": "Growth Performance of Nutri-Cereals Under Varying Agronomic Conditions in Semi-Arid Regions",
            "domain": "Agriculture & Food Science",
            "overall": 78.4,
            "grade": "B",
            "word_count": 4900,
            "sentence_count": 215,
            "vocab_diversity": 39.5,
            "Dimensions": {
                "Readability": 86.8,
                "Methodology": 76.0,
                "Originality": 74.2,
                "Completeness": 79.0,
                "Impact": 76.0,
            },
        },
        {
            "filename": "Quantum_Annealing &amp; Optimization in Supply Chains",
            "domain": "Operations Research",
            "overall": 81.2,
            "grade": "A-",
            "word_count": 5300,
            "sentence_count": 240,
            "vocab_diversity": 41.0,
            "Dimensions": {
                "Readability": 82.0,
                "Methodology": 84.5,
                "Originality": 83.0,
                "Completeness": 78.5,
                "Impact": 78.0,
            },
        },
    ]
    comparison_data = {
        "similarities": [
            "All three papers employ quantitative empirical validation with statistical significance testing.",
            "Each manuscript maintains high Readability (>82/100) and structured methodology sections.",
        ],
        "differences": [
            "GRA_Net focuses on deep graph architectures whereas Paper 2 investigates agronomic field trials.",
            "Methodology scores span a 15.0-point range across the three manuscripts.",
        ],
    }
    pdf_bytes = build_comparison_pdf(papers, comparison_data)
    text, total_images = extract_pdf_text_and_images(pdf_bytes)
    assert "GRA_Net" in text
    assert "Growth Performance of Nutri-Cereals" in text
    assert "Quantum_Annealing" in text
    assert "Strengths" in text
    assert total_images >= 1, "Expected embedded Plotly comparison chart PNG images in Comparison PDF"


def test_build_chat_pdf_renders_qa_and_evidence():
    chat_history = [
        {
            "question": "What is the main contribution of GRA&#x005F;Net?",
            "answer": "GRA_Net introduces a graph-relational attention mechanism achieving 94.2% ± 0.8% accuracy.",
            "confidence": "High",
            "timestamp": "2026-10-11 02:00:00",
            "evidence": [
                {
                    "section": "Methodology",
                    "text": "We formulate document layout analysis as a relational graph attention problem with Δ = +4.5% gain.",
                    "score": 0.89,
                }
            ],
        }
    ]
    pdf_bytes = build_chat_pdf(SPECIAL_TITLE, chat_history)
    text, _ = extract_pdf_text_and_images(pdf_bytes)
    assert "GRA_Net" in text
    assert "What is the main contribution of GRA_Net?" in text
    assert "Methodology" in text


def test_get_pdf_filename_sanitizes_special_characters():
    fn = get_pdf_filename(SPECIAL_TITLE, "Analysis_Report", "20261011")
    assert fn.startswith("PaperIQ_")
    assert fn.endswith("_Analysis_Report_20261011.pdf")
    assert "GRA_Net" in fn
    for illegal in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '&', ';']:
        assert illegal not in fn
