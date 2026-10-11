import io
import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import app
from summarizer import summarize_research_paper


class MockUploadedFile(io.BytesIO):
    def __init__(self, data: bytes, name: str, size: int = None):
        super().__init__(data)
        self.name = name
        self.size = len(data) if size is None else size


def test_4_1_empty_file_rejected_gracefully():
    """Verify empty files return a clear error sentinel without crashing."""
    empty_pdf = MockUploadedFile(b"", "empty_paper.pdf")
    res = app.extract_text_from_file(empty_pdf)
    assert res == "__ERROR_EMPTY_DOCUMENT__"


def test_4_2_oversized_file_over_30mb_rejected():
    """Verify files larger than 30 MB are rejected with the size limit sentinel."""
    oversized = MockUploadedFile(b"sample content", "huge_paper.pdf", size=35 * 1024 * 1024)
    res = app.extract_text_from_file(oversized)
    assert res == "__ERROR_FILE_TOO_LARGE__"


def test_4_3_unsupported_file_extension_rejected():
    """Verify unsupported file types (.exe, .csv, .zip) return the unsupported format sentinel."""
    unsupported = MockUploadedFile(b"col1,col2\n1,2", "dataset.csv")
    res = app.extract_text_from_file(unsupported)
    assert res == "__ERROR_UNSUPPORTED_FORMAT__"


def test_4_4_corrupted_pdf_handled_gracefully():
    """Verify corrupted PDF bytes return a clean error sentinel instead of an unhandled exception."""
    corrupted = MockUploadedFile(b"%PDF-1.4\ncorrupted_garbage_bytes_not_a_valid_xref", "corrupted.pdf")
    res = app.extract_text_from_file(corrupted)
    assert res == "__ERROR_CORRUPTED_PDF__"


def test_4_5_scanned_image_only_pdf_handled_gracefully():
    """Verify a valid PDF page with zero extractable text reports a scanned/image-only PDF sentinel."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin1")
    blank_pdf = MockUploadedFile(bytes(pdf_bytes), "scanned_blank.pdf")
    res = app.extract_text_from_file(blank_pdf)
    assert res in ("__ERROR_SCANNED_PDF__", "__ERROR_EMPTY_DOCUMENT__")


def test_4_6_very_short_document_summarizer_and_metrics_do_not_crash():
    """Verify a very short document (<300 words) can be summarized and scored without crashing."""
    short_text = (
        "Abstract\n"
        "This short research note evaluates soil moisture retention under millet cultivation in arid regions. "
        "Field measurements across twelve experimental plots demonstrate a 14% improvement in water use efficiency "
        "compared with conventional monoculture baselines during seasonal drought stress.\n"
        "Methodology\n"
        "Soil moisture sensors recorded volumetric water content at root-zone depths over three consecutive growing cycles.\n"
        "Conclusion\n"
        "Millet cultivation offers sustainable drought resilience and stable grain yields for smallholder dryland farmers."
    )
    txt_file = MockUploadedFile(short_text.encode("utf-8"), "short_note.txt")
    extracted = app.extract_text_from_file(txt_file)
    assert not extracted.startswith("__ERROR_")
    counts = app.compute_text_counts(extracted)
    assert 45 <= counts["word_count"] < 300
    assert counts["sentence_count"] >= 3

    for level in ("Short", "Medium", "Long"):
        sum_res = summarize_research_paper(extracted, summary_type=level)
        assert sum_res["word_count"] > 0

    doc_res = app.analyze_full_document(extracted)
    assert doc_res is not None
    assert doc_res["stats"]["word_count"] == counts["word_count"]
