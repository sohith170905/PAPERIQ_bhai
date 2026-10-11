import io
import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import app
import summarizer
from summarizer import clean_extracted_text, compute_text_counts, summarize_research_paper

FIXTURE_PDF = os.path.join(os.path.dirname(__file__), "fixtures", "Gangadharan45122023JEAI111549.pdf")


class DummyPDFFile(io.BytesIO):
    def __init__(self, path: str):
        with open(path, "rb") as f:
            data = f.read()
        super().__init__(data)
        self.name = os.path.basename(path)
        self.size = len(data)


# =====================================================================
# 1.1 Text Extraction Cleanup Tests
# =====================================================================
def test_1_1_clean_extracted_text_garbled_sample():
    """Verify the exact garbled equation/variable sample from Phase 1.1 is cleaned into normal prose."""
    garbled = (
        "a= Intercept cultivation area of millet was high in Rajasthan "
        "b= Regression coefficient (4.36 M ha) followed by Maharashtra (2.11 M ha). "
        "Y= abtU (1) t t millet\n"
        "Where,\n"
        "Y= Growth rate of area/production/yield\n"
        "a= Intercept\n"
        "b= Regression coefficient\n"
        "t = Time period\n"
        "U= Disturbance term\n"
        "ln Y= ln a + t ln b + u (2)\n"
        "CAGR (r)= [Antilog (log b) - 1] x 100 (3)\n"
        "t=bi/Se (bi) (4)\n"
        "Table 1. Compound growth rate of area, production and productivity of millets\n"
        "Period I 1966-67 0.25 1.12 0.85 -0.45 2.15 1.88\n"
        "The cultivation of nutri-cereals contributes significantly to nutritional security in dryland regions."
    )
    cleaned = clean_extracted_text(garbled)
    assert "a= Intercept" not in cleaned
    assert "b= Regression coefficient" not in cleaned
    assert "Y= abtU" not in cleaned
    assert "ln Y=" not in cleaned
    assert "CAGR (r)=" not in cleaned
    assert "t=bi/Se" not in cleaned
    assert "Table 1." not in cleaned
    assert "cultivation area of millet was high in Rajasthan" in cleaned
    assert "nutritional security in dryland regions" in cleaned


def test_1_1_real_pdf_extraction_removes_equation_debris():
    """Verify real PDF extraction on Gangadharan et al. removes 2-column equation merge artifacts."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)
    assert not extracted.startswith("__ERROR_")
    assert len(extracted) > 1000
    assert "a= Intercept" not in extracted
    assert "b= Regression coefficient" not in extracted
    assert "Y= abtU" not in extracted
    assert "ln Y= ln a" not in extracted
    assert "CAGR (r)=" not in extracted


def test_1_1_hyphenation_and_line_wrap_cleanup():
    """Verify hyphenation across line breaks is rejoined and broken wraps are collapsed."""
    raw = (
        "The experi-\n"
        "mental evaluation of nutri-\n"
        "cereals demonstrates strong resilience across semi-arid agro-climatic zones.\n"
        "Page 4 of 12\n"
        "Figure 2: Trend of millet cultivation area across states."
    )
    cleaned = clean_extracted_text(raw)
    assert "experimental evaluation" in cleaned
    assert "nutri-cereals" in cleaned or "nutricereals" in cleaned
    assert "Page 4 of 12" not in cleaned
    assert "Figure 2:" not in cleaned


# =====================================================================
# 1.2 Single Source of Truth for Word and Sentence Counts
# =====================================================================
def test_1_2_single_source_of_truth_word_and_sentence_counts():
    """Verify compute_text_counts produces identical word and sentence counts across all modules."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)

    # 1. Direct helper in app
    counts_app = app.compute_text_counts(extracted)
    w_direct = counts_app["word_count"]
    s_direct = counts_app["sentence_count"]
    assert w_direct > 1500
    assert s_direct > 50

    # 2. Summarizer helper
    counts_sum = summarizer.compute_text_counts(extracted)
    assert w_direct == counts_sum["word_count"]
    assert s_direct == counts_sum["sentence_count"]

    # 3. Summarizer output metadata
    sum_res = summarize_research_paper(extracted, summary_type="Medium")
    assert sum_res["document_info"]["total_words"] == w_direct

    # 4. Full document analysis stats (used in Document Statistics & Evaluation)
    doc_res = app.analyze_full_document(extracted)
    assert doc_res["stats"]["word_count"] == w_direct
    assert doc_res["stats"]["sentence_count"] == s_direct


# =====================================================================
# 1.3 Title Detection
# =====================================================================
def test_1_3_title_detection_excludes_journal_headers():
    """Verify largest-font PDF title detection extracts the true title and excludes journal headers."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)

    detected_title = app.get_clean_display_title(
        filename=pdf_file.name,
        text=extracted,
        file=pdf_file,
    )
    assert detected_title == "Growth Performance of Nutri-Cereals in India"
    assert "Journal of Experimental Agriculture" not in detected_title
    assert "Original Research Article" not in detected_title
    assert "Gangadharan45122023" not in detected_title


# =====================================================================
# 1.4 Section Detection & References Panel
# =====================================================================
def test_1_4_section_detection_and_references_extraction():
    """Verify Results and Discussion is detected, References lists reference entries, and missing sections are noted."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)

    sections = app.extract_sections(extracted)
    reliable = app.get_reliable_academic_sections(sections)
    assert "Abstract" in reliable
    assert "Introduction" in reliable
    assert "Methodology" in reliable
    assert "Results and Discussion" in reliable or "Results" in reliable
    assert "Conclusion" in reliable
    assert "References" in reliable

    # References must extract actual numbered reference entries, never an Executive Summary
    ref_entries = app.extract_reference_entries(reliable["References"])
    assert len(ref_entries) >= 8
    assert any("1." in entry for entry in ref_entries)

    # Missing standard sections note
    missing = app.get_missing_standard_sections(reliable)
    assert "Limitations" in missing


# =====================================================================
# 1.5 Ask PaperIQ Retrieval Quality
# =====================================================================
def test_1_5_ask_paperiq_retrieval_quality_and_fallbacks():
    """Verify Ask PaperIQ returns clean prose, section-labeled supporting evidence, and fallback on out-of-scope."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)
    sections = app.extract_sections(extracted)

    prompts = [
        "What is the main contribution of this paper?",
        "What methodology was used?",
        "What dataset or experimental setup was used?",
        "What are the key findings?",
        "What limitations are mentioned?",
    ]
    for q in prompts:
        ans, sources = app.grounded_paper_qa(q, extracted, sections)
        assert "a= Intercept" not in ans
        assert "b= Regression coefficient" not in ans
        assert "Y= abtU" not in ans
        assert "Supporting evidence (from " in ans or "Limitations" in ans

    # Free-text question grounded in paper
    free_ans, _ = app.grounded_paper_qa("Which state had high cultivation area of millet?", extracted, sections)
    assert "Rajasthan" in free_ans
    assert "Supporting evidence (from " in free_ans

    # Unrelated question must return the exact fallback
    unrel_ans, _ = app.grounded_paper_qa(
        "How do quantum superconducting qubits behave at millikelvin temperatures?",
        extracted,
        sections,
    )
    assert "I could not find this information in the paper." in unrel_ans


# =====================================================================
# 1.6 Summary Quality (Short, Medium, Long)
# =====================================================================
def test_1_6_summary_quality_and_word_counts():
    """Verify Short (~100-150w), Medium (~250-400w), and Long (~600-900w) summaries have clean text and accurate counts."""
    pdf_file = DummyPDFFile(FIXTURE_PDF)
    extracted = app.extract_text_from_file(pdf_file)

    short_res = summarize_research_paper(extracted, summary_type="Short", doc_title="Growth Performance of Nutri-Cereals in India")
    med_res = summarize_research_paper(extracted, summary_type="Medium", doc_title="Growth Performance of Nutri-Cereals in India")
    long_res = summarize_research_paper(extracted, summary_type="Long", doc_title="Growth Performance of Nutri-Cereals in India")

    # Word count ranges
    assert 95 <= short_res["word_count"] <= 165
    assert 240 <= med_res["word_count"] <= 420
    assert 580 <= long_res["word_count"] <= 920

    # Verify reported badge word count matches compute_text_counts on summary text
    for res in (short_res, med_res, long_res):
        recomputed_w = compute_text_counts(res["summary"])["word_count"]
        assert res["word_count"] == recomputed_w
        assert "a= Intercept" not in res["summary"]
        assert "b= Regression coefficient" not in res["summary"]
        assert "Y= abtU" not in res["summary"]

    # Medium summary must have neutral missing-Limitations note AND limitation/background constraint line
    assert "does not explicitly present an isolated limitations section" in med_res["summary"]
    assert ("Possible limitations mentioned" in med_res["summary"] or "Background constraint cited from literature" in med_res["summary"])
