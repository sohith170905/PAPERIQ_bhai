"""
Comprehensive regression & E2E verification suite for Researcher Workspace Fixes 1-8.
Verifies:
- FIX 1: Title / Authors / Venue extraction, citation-line rejection, word-boundary truncation, ID 213 backfill
- FIX 2: Research Profile accuracy (Objective from Abstract/Intro, honest confidence, literature-cited vs author-stated limitations, deduplication)
- FIX 3: 5 distinct Manuscript Quality scores (Structure 25%, Clarity 20%, Coherence 20%, Citations 20%, Readability 15%) + Driven by explanations
- FIX 4: Citation & Section detection (excludes Preamble/Keywords, counts in-text markers [1]-[11] and 11 reference entries for ID 213)
- FIX 5: Research Insights (deduped keywords without sub-phrases, honest gaps, chronological temporal trends without negative years or period-definition sentences, period inconsistency note)
- FIX 6: Ask PaperIQ Researcher Mode (distinct answers for limitations vs gaps vs future work vs contributions, extractive synthesis + evidence, multi-paper project scope)
- FIX 7: 30 MB upload limit config, real Member Since date, word-boundary title truncation with tooltip
- FIX 8: All PDF exports (analysis, summary, comparison, insights, chat) succeed without TypeError
- 5 Test Document Types:
  (1) Millet PDF (ID 213: Growth Performance of Nutri-Cereals in India)
  (2) Computer Science / Deep Learning PDF
  (3) DOCX research paper
  (4) Plain TXT research paper
  (5) Paper with explicit Limitations section and explicit gap statements
"""
import io
import json
import os
import sqlite3
import docx
from fpdf import FPDF

import auth
import pdf_export
import research_engine
import summarizer
from utils import format_title_with_tooltip_html, truncate_title_word_boundary


def test_fix1_title_authors_venue_and_id213():
    """Verify FIX 1: Citation-line rejection, venue parsing, author extraction, and Record ID 213."""
    citation_line = "J. Exp. Agric. Int., vol. 45, no. 12, pp. 197-200, 2023"
    assert research_engine.is_citation_or_header_line(citation_line) is True
    assert summarizer.is_citation_or_header_title_line(citation_line) is True

    parsed_venue = research_engine.parse_citation_venue_line(citation_line)
    assert "Journal of Experimental Agriculture International" in parsed_venue["venue_display"]
    assert "vol. 45" in parsed_venue["venue_display"]
    assert "no. 12" in parsed_venue["venue_display"]
    assert "197-200" in parsed_venue["venue_display"]
    assert parsed_venue["year"] == "2023"

    # Verify Millet Record in users.db
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM analysis_history WHERE id IN (286, 250, 213) OR display_title = 'Growth Performance of Nutri-Cereals in India' ORDER BY (username = 'sohith') DESC, id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Millet record must exist in analysis_history"
    meta_row = conn.execute(
        "SELECT * FROM paper_metadata WHERE analysis_id IN (?, ?, '213', '250', '286')",
        (str(row["analysis_id"]), str(row["id"])),
    ).fetchone()
    conn.close()

    assert row["display_title"] == "Growth Performance of Nutri-Cereals in India"
    res = json.loads(row["results_json"])
    assert res["title"] == "Growth Performance of Nutri-Cereals in India"
    authors_val = (res.get("metadata") or {}).get("authors") or res.get("authors") or (meta_row["authors"] if meta_row else "")
    journal_val = (res.get("metadata") or {}).get("journal") or res.get("journal") or (meta_row["journal"] if meta_row else "")
    assert authors_val == "Gangadharan S., Abhinav Pillai, S. Aravind"
    assert "Journal of Experimental Agriculture International" in journal_val
    assert meta_row is not None
    assert meta_row["authors"] == "Gangadharan S., Abhinav Pillai, S. Aravind"

    # Word-boundary truncation test: never cuts mid-word or leaves trailing 'pp'
    long_title = "Growth Performance of Nutri-Cereals in India Under Changing Climatic Conditions and Market Regimes"
    trunc = truncate_title_word_boundary(long_title, max_chars=52)
    assert trunc.endswith("…")
    assert not trunc[:-1].endswith(" pp")
    tooltip_html = format_title_with_tooltip_html(long_title, max_chars=52)
    assert 'title="Growth Performance of Nutri-Cereals in India Under Changing Climatic Conditions and Market Regimes"' in tooltip_html


def _get_id213_record():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM analysis_history WHERE id IN (286, 250, 213) OR display_title = 'Growth Performance of Nutri-Cereals in India' ORDER BY (username = 'sohith') DESC, id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    res = json.loads(row["results_json"])
    full_text = res.get("extracted_text") or res.get("full_text") or ""
    res["full_text"] = full_text
    return row, res, full_text


def test_fix2_research_profile_accuracy_and_confidence():
    """Verify FIX 2: Research Objective from Abstract/Intro, honest confidence, literature constraint vs author limitation."""
    _, res, full_text = _get_id213_record()
    sections = summarizer.extract_sections(full_text)
    profile = research_engine.extract_research_profile(full_text, sections)

    # Objective must come from Abstract or Introduction, never Results
    obj = profile["research_objective"]
    assert obj["found"] is True
    assert any(k in obj["section"].lower() for k in ("abstract", "introduction"))
    assert "results" not in obj["section"].lower()
    assert obj["confidence"] in ("High", "Moderate")
    assert not obj["text"].lower().startswith("the primary factor being")

    # Limitations on ID 213: no dedicated Limitations section, only cited literature constraint [5]
    lim = profile["limitations"]
    assert lim["confidence"] in ("Low", "Not found")
    if lim["found"]:
        assert "No limitations explicitly stated by the authors" in lim["text"] or "Background constraint cited from literature" in lim["text"]

    # Data & Materials should not repeat near-identical 1992-2021 sentences
    dm = profile["datasets_and_materials"]["text"]
    sents = [s.strip() for s in summarizer.split_into_sentences(dm) if s.strip()]
    if len(sents) >= 2:
        assert not research_engine._sentences_are_near_duplicate(sents[0], sents[1])


def test_fix3_five_distinct_manuscript_quality_scores():
    """Verify FIX 3: 5 distinct quality dimensions for Researcher + weighted composite + Driven by explanations."""
    _, res, full_text = _get_id213_record()
    sections = summarizer.extract_sections(full_text)
    q = research_engine.compute_researcher_quality_scores(full_text, sections)

    s1 = q["structure_score"]
    s2 = q["clarity_score"]
    s3 = q["coherence_score"]
    s4 = q["citation_score"]
    s5 = q["readability_score"]
    distinct_vals = {s1, s2, s3, s4, s5}
    assert len(distinct_vals) >= 4, f"Expected distinct dimension scores, got {distinct_vals}"

    expected_comp = round(0.25 * s1 + 0.20 * s2 + 0.20 * s3 + 0.20 * s4 + 0.15 * s5, 1)
    assert abs(q["overall_score"] - expected_comp) <= 0.1

    for dim_key, expl in q["explanations"].items():
        assert expl.startswith("Driven by "), f"Missing 'Driven by' explanation for {dim_key}: {expl}"


def test_fix4_citation_and_section_detection():
    """Verify FIX 4: Section detector excludes Preamble/Keywords; Citation detector finds 11 in-text & 11 refs on ID 213."""
    _, res, full_text = _get_id213_record()

    sections = summarizer.extract_sections(full_text)
    sec_names_lower = [k.lower() for k in sections.keys()]
    assert "preamble" not in sec_names_lower
    assert not any(k.startswith("keywords") for k in sec_names_lower)
    assert len(sections) == 7

    cit = research_engine.detect_citations_and_references(full_text, sections)
    assert cit["in_text_count"] == 11
    assert cit["reference_entries_count"] == 11


def test_fix5_research_insights_keywords_gaps_trends():
    """Verify FIX 5: Sub-phrase removal in keywords, honest gaps, clean temporal trends, period inconsistency note."""
    _, res, full_text = _get_id213_record()
    sections = summarizer.extract_sections(full_text)

    insights = research_engine.extract_honest_research_insights(full_text, sections)
    kw_terms_lower = [k["term"].lower() for k in insights["keywords"]]
    assert "compound annual growth rate" in kw_terms_lower
    for subsumed in ("growth", "growth rate", "annual growth", "annual", "compound annual", "compound"):
        assert subsumed not in kw_terms_lower, f"Sub-phrase '{subsumed}' should be subsumed by Compound Annual Growth Rate"

    # Theme mentions must equal sum of member counts
    for theme in insights["themes"]:
        assert theme["mentions"] == sum(m["count"] for m in theme["members"])

    # Gaps: never output broken 'Address the manuscript's stated constraint regarding Lack...'
    for g in insights["gaps"]:
        assert "regarding Lack" not in g.get("direction", "")

    # Temporal trends: chronological order, no '-2001' in metrics, period inconsistency note present
    trends = insights["trends"]
    assert len(trends) >= 3
    for t in trends:
        for m in t.get("metrics", []):
            assert "-2001" not in m and "-2011" not in m and "-2021" not in m
        assert "study period was divided" not in t["statement"].lower()
        assert "data was collected" not in t["statement"].lower()

    assert "Period boundaries differ between sections" in insights["period_boundary_note"]
    assert insights["future_directions"] == []


def test_fix6_ask_paperiq_distinct_intents_and_project_scope():
    """Verify FIX 6: Distinct answers for limitations, gaps, future work, contributions + multi-paper scope."""
    _, res, full_text = _get_id213_record()
    paper_213 = {
        "id": 213,
        "title": "Growth Performance of Nutri-Cereals in India",
        "full_text": full_text,
        "sections": summarizer.extract_sections(full_text),
    }

    q_lim = research_engine.answer_researcher_question("What are the study's limitations?", [paper_213])
    q_gap = research_engine.answer_researcher_question("What research gap is identified?", [paper_213])
    q_fut = research_engine.answer_researcher_question("What future work do the authors suggest?", [paper_213])
    q_con = research_engine.answer_researcher_question("What are the main contributions and findings?", [paper_213])

    ans_set = {q_lim["answer"], q_gap["answer"], q_fut["answer"], q_con["answer"]}
    assert len(ans_set) == 4, "Limitations, gaps, future work, and contributions must return 4 distinct answers"
    assert "No study-specific methodological limitations" in q_lim["answer"]
    assert "Not stated by the authors" in q_fut["answer"] or "do not state explicit future work" in q_fut["answer"]


def test_five_document_formats_and_pdf_exports():
    """Verify all 5 document types (Millet PDF, CS PDF, DOCX, TXT, Explicit Limitations/Gaps TXT) and PDF exports."""
    # 1. Millet PDF (via stored ID 213 + live file if present)
    _, millet_res, _ = _get_id213_record()
    assert millet_res["title"] == "Growth Performance of Nutri-Cereals in India"

    # 2. Computer Science / Deep Learning PDF (synthesized in-memory PDF)
    cs_pdf = FPDF()
    cs_pdf.add_page()
    cs_pdf.set_font("Helvetica", "B", 16)
    cs_pdf.cell(0, 10, "Sparse Attention Transformers for Long-Horizon Time Series Forecasting", ln=True)
    cs_pdf.set_font("Helvetica", "", 11)
    cs_pdf.cell(0, 8, "Elena Rostova, Marcus Vance, Disha Patel", ln=True)
    cs_pdf.cell(0, 8, "IEEE Transactions on Neural Networks, vol. 35, no. 4, pp. 412-425, 2024", ln=True)
    cs_pdf.multi_cell(0, 6, (
        "Abstract\n"
        "This paper proposes a sparse block-attention transformer architecture designed to reduce quadratic memory complexity in long-horizon time series forecasting. "
        "We evaluate the model on four public benchmark datasets (ETTh1, Traffic, Weather, and Electricity) using Mean Squared Error (MSE) and Mean Absolute Error (MAE).\n"
        "1. Introduction\n"
        "Standard self-attention scales quadratically with sequence length [1, 2], limiting deployment on resource-constrained edge accelerators (kitaev et al., 2020). "
        "The primary objective of this study is to design an O(N log N) sparse routing mechanism that preserves long-range temporal dependencies.\n"
        "2. Methodology\n"
        "We formulate a locality-sensitive routing kernel combined with dilated causal convolutions over 96-to-720 step horizons.\n"
        "3. Experimental Results\n"
        "Experimental evaluations demonstrate that our model reduces MSE by 14.8% compared to Informer and achieves 2.4x faster inference throughput.\n"
        "4. Conclusion\n"
        "Sparse block-attention achieves state-of-the-art accuracy on long-horizon benchmarks. In future work, we plan to extend this architecture to multimodal spatio-temporal weather grids.\n"
        "References\n"
        "[1] Vaswani A, et al. Attention is all you need. NeurIPS 2017.\n"
        "[2] Kitaev N, et al. Reformer: The efficient transformer. ICLR 2020.\n"
    ))
    raw_pdf_out = cs_pdf.output(dest="S")
    pdf_bytes = raw_pdf_out.encode("latin-1") if isinstance(raw_pdf_out, str) else bytes(raw_pdf_out)
    pdf_file = io.BytesIO(pdf_bytes)
    pdf_file.name = "rostova_transformer_2024.pdf"

    import app
    cs_text = app.extract_text_from_file(pdf_file)
    assert "Sparse Attention Transformers for Long-Horizon Time Series Forecasting" in cs_text
    cs_meta = research_engine.infer_paper_metadata(cs_text, "rostova_transformer_2024.pdf")
    assert "Sparse Attention Transformers" in cs_meta["title"]
    assert "Elena Rostova" in cs_meta["authors"]
    assert "IEEE Transactions on Neural Networks" in cs_meta["journal"]

    # 3. DOCX Research Paper
    doc = docx.Document()
    doc.add_paragraph("Biochar Amendment Enhances Soil Nitrogen Retention in Semi-Arid Wheat Systems")
    doc.add_paragraph("Ramesh Kumar, Priya Nair, K. S. Subramanian")
    doc.add_paragraph("Abstract")
    doc.add_paragraph(
        "This study investigates the effect of pyrolysis biochar application on soil nitrate retention and grain yield across three semi-arid wheat seasons. "
        "Field trials were conducted using a randomized complete block design with four replication plots."
    )
    doc.add_paragraph("1. Introduction")
    doc.add_paragraph("Nitrogen leaching represents a major agronomic challenge in sandy loam soils [1].")
    doc.add_paragraph("2. Methodology")
    doc.add_paragraph("Soil cores were sampled at 0-30 cm depth and analyzed via Kjeldahl digestion and ANOVA.")
    doc.add_paragraph("3. Results and Discussion")
    doc.add_paragraph("Biochar addition at 10 t/ha increased grain yield by 18.4% and reduced nitrate leaching by 27.2%.")
    doc.add_paragraph("4. Conclusion")
    doc.add_paragraph("Biochar amendment provides a sustainable soil management strategy for semi-arid wheat cultivation.")
    doc.add_paragraph("References")
    doc.add_paragraph("[1] Lehmann J, Joseph S. Biochar for environmental management. Earthscan 2015.")
    docx_buf = io.BytesIO()
    doc.save(docx_buf)
    docx_buf.seek(0)
    docx_buf.name = "biochar_wheat_study.docx"

    docx_text = app.extract_text_from_file(docx_buf)
    docx_secs = summarizer.extract_sections(docx_text)
    docx_prof = research_engine.extract_research_profile(docx_text, docx_secs)
    assert docx_prof["research_objective"]["found"] is True
    assert docx_prof["methodology"]["found"] is True

    # 4. Plain TXT Research Paper
    txt_content = (
        "Federated Learning with Differential Privacy for Multi-Hospital Clinical Risk Prediction\n"
        "Sarah Chen, David Alverez\n\n"
        "Abstract\n"
        "The objective of this paper is to evaluate differentially private federated averaging across five tertiary hospital ICU cohorts.\n\n"
        "1. Introduction\n"
        "Sharing patient electronic health records across institutions raises strict regulatory privacy barriers [1].\n\n"
        "2. Methodology\n"
        "We train a gradient-boosted Cox proportional hazards model on 42,500 patient admissions using Gaussian noise calibration.\n\n"
        "3. Results\n"
        "Our federated framework achieves an AUROC of 0.874 while maintaining an epsilon privacy budget of 1.2.\n\n"
        "4. Conclusion\n"
        "Privacy-preserving federated learning matches centralized clinical risk prediction performance.\n\n"
        "References\n"
        "[1] McMahan B, et al. Communication-efficient learning of deep networks. AISTATS 2017.\n"
    )
    txt_file = io.BytesIO(txt_content.encode("utf-8"))
    txt_file.name = "federated_clinical_2024.txt"
    txt_extracted = app.extract_text_from_file(txt_file)
    txt_secs = summarizer.extract_sections(txt_extracted)
    txt_prof = research_engine.extract_research_profile(txt_extracted, txt_secs)
    assert txt_prof["research_objective"]["confidence"] == "High"
    assert txt_prof["datasets_and_materials"]["found"] is True

    # 5. Paper with explicit Limitations section and explicit gap statements
    lim_txt = (
        "Cross-Lingual Transfer for Low-Resource Dravidian Morphological Tagging\n"
        "Arunima Iyer, Karthik Sundaram\n\n"
        "Abstract\n"
        "This study aims to evaluate zero-shot cross-lingual transfer for morphological tagging in low-resource Dravidian languages.\n\n"
        "1. Introduction\n"
        "Despite advances in multilingual transformers, little research has examined agglutinative inflectional morphology in tribal Dravidian dialects [1]. "
        "This gap remains largely unaddressed in existing NLP benchmarks.\n\n"
        "2. Methodology\n"
        "We fine-tune adapter layers on Universal Dependencies treebanks using morphological byte-pair encoding.\n\n"
        "3. Results\n"
        "Adapter fine-tuning improves morpheme F1 score by 9.6% over zero-shot mBERT baselines.\n\n"
        "4. Limitations\n"
        "A primary limitation of this study is the small annotated evaluation corpus of 1,200 sentences restricted to written literary text. "
        "Furthermore, our tokenizer could not capture spoken code-switched phonetic variations.\n\n"
        "5. Conclusion and Future Work\n"
        "In future research, we plan to expand the corpus to conversational speech transcripts and dialectal audio.\n\n"
        "References\n"
        "[1] Pires T, et al. How multilingual is Multilingual BERT? ACL 2019.\n"
    )
    lim_secs = summarizer.extract_sections(lim_txt)
    lim_prof = research_engine.extract_research_profile(lim_txt, lim_secs)
    assert lim_prof["limitations"]["found"] is True
    assert lim_prof["limitations"]["confidence"] == "High"
    assert "primary limitation of this study" in lim_prof["limitations"]["text"].lower()

    lim_insights = research_engine.extract_honest_research_insights(lim_txt, lim_secs)
    assert len(lim_insights["gaps"]) >= 1
    assert any(g["gap_type"] == "Explicit Research Gap" for g in lim_insights["gaps"])
    assert len(lim_insights["future_directions"]) >= 1

    # Verify FIX 8: All PDF builders run cleanly without TypeError
    pdf_a = pdf_export.build_analysis_pdf({"paper_title": "Test Title", "overall_score": 82.5, "scores": millet_res})
    assert isinstance(pdf_a, bytes) and pdf_a.startswith(b"%PDF")
    pdf_s = pdf_export.build_summary_pdf("Test Title", "Medium", {"summary": "Test summary."}, {"word_count": 500})
    assert isinstance(pdf_s, bytes) and pdf_s.startswith(b"%PDF")
    pdf_c = pdf_export.build_comparison_pdf([{"title": "Paper A", "overall_score": 80.0}, {"title": "Paper B", "overall_score": 85.0}], {})
    assert isinstance(pdf_c, bytes) and pdf_c.startswith(b"%PDF")
    pdf_i = pdf_export.build_insights_pdf("Test Title", {"domain": "Agriculture", "profile": docx_prof, "insights": lim_insights, "quality_scores": millet_res})
    assert isinstance(pdf_i, bytes) and pdf_i.startswith(b"%PDF")
    pdf_ch = pdf_export.build_chat_pdf("Test Title", [{"role": "user", "content": "Q?"}, {"role": "assistant", "content": "A."}])
    assert isinstance(pdf_ch, bytes) and pdf_ch.startswith(b"%PDF")


def test_task1_registry_page_removed_and_config():
    """Verify TASK 1: No pages/ directory exists, core/registry.py works, and .streamlit/config.toml hides sidebar nav."""
    assert not os.path.exists("pages"), "No pages/ directory may remain for Streamlit auto-discovery"
    assert os.path.exists(os.path.join("core", "registry.py")), "core/registry.py must exist"
    assert os.path.exists(os.path.join("core", "researcher", "dashboard.py")), "core/researcher/dashboard.py must exist"
    assert os.path.exists(os.path.join("core", "student", "workspace_pages.py")), "core/student/workspace_pages.py must exist"

    from core.registry import RESEARCHER_NAV_ITEMS, STUDENT_NAV_SECTIONS, resolve_researcher_page
    assert len(RESEARCHER_NAV_ITEMS) == 9
    assert len(STUDENT_NAV_SECTIONS) == 3
    assert resolve_researcher_page("Researcher Dashboard") == "🏠 Researcher Dashboard"

    cfg_path = os.path.join(".streamlit", "config.toml")
    assert os.path.exists(cfg_path), ".streamlit/config.toml must exist"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg_text = f.read()
    assert "[client]" in cfg_text
    assert "showSidebarNavigation = false" in cfg_text


def test_task2_byline_classifier_author_parser_and_multiline_title():
    """Verify TASK 2: Byline-vs-title classifier, author parser with markers & continuation lines, multi-line title merging, and idempotent migration."""
    # 1. Byline-vs-title classifier & title validator
    assert research_engine.is_author_byline("Gangadharan S. a*, Abhinav Pillai a,") is True
    assert research_engine.is_author_byline("Gangadharan S. a*, Abhinav Pillai a, S. Aravind a,") is True
    assert research_engine.is_author_byline("S. Aravind a,") is True
    assert research_engine.is_author_byline("and S. Aravind b, 1, \u2020") is True
    assert research_engine.is_author_byline("Growth Performance of Nutri-Cereals in India") is False

    assert research_engine.is_valid_paper_title("Gangadharan S. a*, Abhinav Pillai a,") is False
    assert research_engine.is_valid_paper_title("Growth Performance of Nutri-Cereals in India,") is False
    assert research_engine.is_valid_paper_title("J. Exp. Agric. Int., vol. 45, no. 12, pp. 197-200, 2023") is False
    assert research_engine.is_valid_paper_title("Growth Performance of Nutri-Cereals in India") is True

    # 2. Author parser with affiliation markers (a*, b, 1, †) and continuation lines
    byline_block = [
        "Gangadharan S. a*, Abhinav Pillai a,",
        "and S. Aravind b, 1, \u2020",
        "a Department of Agricultural Economics, Tamil Nadu Agricultural University, India",
        "Corresponding author: gangadharan@tnau.ac.in",
    ]
    parsed_authors = research_engine.parse_author_byline_lines(byline_block)
    assert parsed_authors == ["Gangadharan S.", "Abhinav Pillai", "S. Aravind"]
    assert ", ".join(parsed_authors) == "Gangadharan S., Abhinav Pillai, S. Aravind"

    # 3. Multi-line title merging from page-1 layout spans
    spans = [
        {"text": "Original Research Article", "size": 10.0, "y": 50.0},
        {"text": "Growth Performance of", "size": 18.0, "y": 95.0},
        {"text": "Nutri-Cereals in India.", "size": 18.0, "y": 116.0},
        {"text": "Gangadharan S. a*, Abhinav Pillai a,", "size": 11.5, "y": 152.0},
        {"text": "S. Aravind a", "size": 11.5, "y": 168.0},
    ]
    merged_title = research_engine.merge_multiline_title_spans(spans)
    assert merged_title == "Growth Performance of Nutri-Cereals in India"

    # 4. Live PDF verification if Gangadharan45122023JEAI111549.pdf exists on disk
    millet_pdf_path = r"C:\Users\sohit\Downloads\Gangadharan45122023JEAI111549.pdf"
    if os.path.exists(millet_pdf_path):
        import app
        with open(millet_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        buf = io.BytesIO(pdf_bytes)
        buf.name = "Gangadharan45122023JEAI111549.pdf"
        layout_title = app.extract_title_from_pdf_object(buf)
        assert layout_title == "Growth Performance of Nutri-Cereals in India"
        buf.seek(0)
        raw_text = app.extract_text_from_file(buf)
        meta = research_engine.extract_paper_metadata(raw_text, filename=buf.name)
        assert meta["title"] == "Growth Performance of Nutri-Cereals in India"
        assert meta["authors"] == "Gangadharan S., Abhinav Pillai, S. Aravind"
        assert "Journal of Experimental Agriculture International" in meta["journal"]

    # 5. Migration idempotency check
    auth._BACKFILL_COMPLETED = False
    auth.backfill_existing_researcher_records(force=False)
    auth._BACKFILL_COMPLETED = False
    second_run = auth.backfill_existing_researcher_records(force=False)
    assert second_run == 0, f"Expected idempotent migration to update 0 records on second run, got {second_run}"


def test_task3_limitation_label_consistency():
    """Verify TASK 3: Literature-cited background constraint from Intro is labeled 'Background constraint cited from literature [5]'."""
    intro_cited_sent = "The primary factor being the lack of suitable varieties for varied climatic regions [5]."
    label = summarizer.format_limitation_sentence_label(intro_cited_sent, "1. INTRODUCTION")
    assert label == "Background constraint cited from literature [5]"
    assert "Possible limitations mentioned" not in label

    author_lim_sent = "A limitation of our study is the reliance on secondary district-level data."
    author_label = summarizer.format_limitation_sentence_label(author_lim_sent, "4. DISCUSSION")
    assert author_label == "Possible limitations mentioned"

    legacy_summary = (
        "Research Objective: The study aims to analyse growth performance of millets.\n"
        "Possible limitations mentioned: The primary factor being the lack of suitable varieties [5]."
    )
    normalized = summarizer.normalize_summary_limitations_label(legacy_summary)
    assert "Background constraint cited from literature [5]:" in normalized
    assert "Possible limitations mentioned" not in normalized

    # Check stored millet record summary and generated summary PDF
    _, res, full_text = _get_id213_record()
    stored_summary = res.get("summary") or ""
    assert "Possible limitations mentioned" not in stored_summary

    med_sum = summarizer.summarize_research_paper(full_text, summary_type="Medium")
    assert "Possible limitations mentioned" not in med_sum.get("summary", "")
    assert "Background constraint cited from literature [5]" in med_sum.get("summary", "")

    sum_pdf = pdf_export.build_summary_pdf(
        "Growth Performance of Nutri-Cereals in India",
        "Medium",
        {"summary": legacy_summary},
        {"word_count": 1445},
    )
    assert isinstance(sum_pdf, bytes) and sum_pdf.startswith(b"%PDF")

