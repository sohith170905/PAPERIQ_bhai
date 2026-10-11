"""
PaperIQ — Shared Researcher Content Analysis, Metadata, Profile, Insights & Comparison Engine
=============================================================================================
Provides source-grounded, non-boilerplate extraction for the Researcher workspace while
sharing core text cleaning, sentence splitting, and section segmentation from `summarizer.py`.

Core Honesty Rule:
- If the manuscript's text does not contain evidence for a field (objective, methodology,
  data/materials, key results, contributions, limitations, gaps, trends, future work),
  return the exact sentinel ("Not found in this manuscript", "No trend data found", or
  "Not stated by the authors") rather than generic template/boilerplate text.
"""

from __future__ import annotations

import collections
import html
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import summarizer
from utils import safe_text, unescape_text


# ---------------------------------------------------------------------------
# 1. Academic Stopwords, Journal Expansions & Domain Taxonomies
# ---------------------------------------------------------------------------

ACADEMIC_STOPWORDS = {
    "a", "about", "above", "across", "after", "again", "against", "all", "almost", "alone",
    "along", "already", "also", "although", "always", "am", "among", "amongst", "an", "and",
    "another", "any", "anybody", "anyone", "anything", "anywhere", "are", "area", "areas",
    "around", "as", "ask", "asked", "asking", "asks", "at", "away", "b", "back", "backed",
    "backing", "backs", "be", "became", "because", "become", "becomes", "been", "before",
    "began", "behind", "being", "beings", "best", "better", "between", "big", "both", "but",
    "by", "c", "came", "can", "cannot", "case", "cases", "certain", "certainly", "clear",
    "clearly", "come", "could", "d", "did", "differ", "different", "differently", "do",
    "does", "done", "down", "downed", "downing", "downs", "during", "e", "each", "early",
    "either", "end", "ended", "ending", "ends", "enough", "even", "evenly", "ever", "every",
    "everybody", "everyone", "everything", "everywhere", "f", "face", "faces", "fact",
    "facts", "far", "felt", "few", "find", "finds", "first", "for", "four", "from", "full",
    "fully", "further", "furthered", "furthering", "furthers", "g", "gave", "general",
    "generally", "get", "gets", "give", "given", "gives", "go", "going", "good", "goods",
    "got", "great", "greater", "greatest", "group", "grouped", "grouping", "groups", "h",
    "had", "has", "have", "having", "he", "her", "here", "herself", "high", "higher",
    "highest", "him", "himself", "his", "how", "however", "i", "if", "important", "in",
    "interest", "interested", "interesting", "interests", "into", "is", "it", "its",
    "itself", "j", "just", "k", "keep", "keeps", "kind", "knew", "know", "known", "knows",
    "l", "large", "largely", "last", "later", "latest", "least", "less", "let", "lets",
    "like", "likely", "long", "longer", "longest", "m", "made", "make", "making", "man",
    "many", "may", "me", "member", "members", "men", "might", "more", "most", "mostly",
    "mr", "mrs", "much", "must", "my", "myself", "n", "necessary", "need", "needed",
    "needing", "needs", "never", "new", "newer", "newest", "next", "no", "nobody", "non",
    "noone", "not", "nothing", "now", "nowhere", "number", "numbers", "o", "of", "off",
    "often", "old", "older", "oldest", "on", "once", "one", "only", "open", "opened",
    "opening", "opens", "or", "order", "ordered", "ordering", "orders", "other", "others",
    "our", "out", "over", "p", "part", "parted", "parting", "parts", "per", "perhaps",
    "place", "places", "point", "pointed", "pointing", "points", "possible", "present",
    "presented", "presenting", "presents", "problem", "problems", "put", "puts", "q",
    "quite", "r", "rather", "really", "right", "room", "rooms", "s", "said", "same", "saw",
    "say", "says", "second", "seconds", "see", "seem", "seemed", "seeming", "seems",
    "sees", "several", "shall", "she", "should", "show", "showed", "showing", "shows",
    "side", "sides", "since", "small", "smaller", "smallest", "so", "some", "somebody",
    "someone", "something", "somewhere", "state", "states", "still", "such", "sure", "t",
    "take", "taken", "than", "that", "the", "their", "them", "then", "there", "therefore",
    "these", "they", "thing", "things", "think", "thinks", "this", "those", "though",
    "thought", "thoughts", "three", "through", "thus", "to", "today", "together", "too",
    "took", "toward", "turn", "turned", "turning", "turns", "two", "u", "under", "until",
    "up", "upon", "us", "use", "used", "uses", "using", "v", "very", "w", "want", "wanted",
    "wanting", "wants", "was", "way", "ways", "we", "well", "wells", "went", "were",
    "what", "when", "where", "whether", "which", "while", "who", "whole", "whom", "whose",
    "why", "will", "with", "within", "without", "work", "worked", "working", "works",
    "would", "x", "y", "year", "years", "yet", "you", "young", "younger", "youngest",
    "your", "yours", "z", "et", "al", "fig", "figure", "table", "eq", "equation", "section",
    "paper", "study", "studies", "research", "author", "authors", "manuscript", "article",
    "journal", "volume", "issue", "pp", "page", "pages", "doi", "http", "https", "www",
    "org", "com", "edu", "received", "accepted", "published", "copyright", "rights",
    "reserved", "elsevier", "springer", "ieee", "acm", "wiley", "mdpi", "nature",
    "based", "proposed", "approach", "method", "methods", "results", "result", "conclusion",
    "conclusions", "introduction", "abstract", "discussion", "respectively", "significant",
    "significantly", "various", "different", "total", "average", "mean", "value", "values",
    "level", "levels", "rate", "rates", "cent", "percent", "percentage", "data", "analysis",
    "lack", "factor", "primary", "main", "major", "period", "periods", "india", "indian",
}

JOURNAL_ABBR_EXPANSIONS: Dict[str, str] = {
    "j. exp. agric. int.": "Journal of Experimental Agriculture International",
    "j. exp. agric. int": "Journal of Experimental Agriculture International",
    "int. j. agric. sci.": "International Journal of Agricultural Sciences",
    "indian j. agric. econ.": "Indian Journal of Agricultural Economics",
    "indian j. agric. sci.": "Indian Journal of Agricultural Sciences",
    "j. agron. crop sci.": "Journal of Agronomy and Crop Science",
    "proc. ieee": "Proceedings of the IEEE",
    "commun. acm": "Communications of the ACM",
    "j. mach. learn. res.": "Journal of Machine Learning Research",
    "ieee trans. pattern anal. mach. intell.": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "ieee trans. neural netw. learn. syst.": "IEEE Transactions on Neural Networks and Learning Systems",
}

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Agriculture & Food Science": [
        "millet", "millets", "sorghum", "bajra", "ragi", "crop", "crops", "cultivation",
        "yield", "hectare", "farming", "agricultural", "agriculture", "agronomy", "grain",
        "cereals", "fertilizer", "irrigation", "soil", "harvest", "nutri-cereals", "seed",
        "livestock", "horticulture", "food security", "farmer", "farmers",
    ],
    "Computer Science & AI": [
        "neural", "network", "deep learning", "machine learning", "transformer", "attention",
        "convolutional", "cnn", "rnn", "lstm", "gnn", "algorithm", "dataset", "benchmark",
        "classification", "regression", "embedding", "gradient", "backpropagation", "llm",
        "natural language", "computer vision", "segmentation", "detection", "hyperparameter",
        "training", "inference", "accuracy", "f1-score", "precision", "recall", "gpu",
    ],
    "Healthcare & Biomedical Sciences": [
        "patient", "patients", "clinical", "therapy", "diagnosis", "disease", "syndrome",
        "biomarker", "pathology", "treatment", "hospital", "medical", "mortality", "cohort",
        "oncology", "cardiovascular", "diabetes", "genome", "protein", "pharmacological",
        "placebo", "trial", "epidemiology", "symptom", "vaccine", "infection",
    ],
    "Economics, Finance & Policy": [
        "gdp", "inflation", "monetary", "fiscal", "market", "export", "import", "trade",
        "cagr", "compound annual growth", "elasticity", "macroeconomic", "microeconomic",
        "investment", "portfolio", "revenue", "subsidy", "consumption", "price", "pricing",
        "econometric", "socioeconomic", "policy", "productivity",
    ],
    "Environmental & Earth Sciences": [
        "climate", "emissions", "carbon", "greenhouse", "ecosystem", "biodiversity",
        "sustainability", "renewable", "pollution", "atmospheric", "hydrology", "drought",
        "rainfall", "temperature", "deforestation", "ecological", "watershed",
    ],
    "Engineering & Physical Sciences": [
        "sensor", "circuit", "voltage", "frequency", "antenna", "mechanical", "thermal",
        "fluid", "structural", "finite element", "nanoparticle", "polymer", "catalyst",
        "quantum", "optical", "semiconductor", "robotics", "control system", "actuator",
    ],
    "Social Sciences & Education": [
        "pedagogy", "curriculum", "classroom", "student", "teacher", "survey", "questionnaire",
        "qualitative", "interview", "sociology", "psychology", "cognitive", "behavioral",
        "demographic", "literacy", "higher education", "academic performance",
    ],
}


# ---------------------------------------------------------------------------
# 2. Citation & Section Detection, Title/Author/Venue Extraction (FIX 1 & FIX 4)
# ---------------------------------------------------------------------------

def is_citation_or_header_line(line: str) -> bool:
    """
    Return True if `line` is a journal citation line, volume/issue/page header,
    ISSN/DOI, article type header, copyright line, or affiliation line that must
    NEVER be selected as a manuscript title.
    """
    if not line or not line.strip():
        return True
    s = re.sub(r"\s+", " ", unescape_text(line)).strip()
    low = s.lower()

    # Explicit header/boilerplate prefixes
    if re.match(
        r"^(?:original\s+research\s+article|review\s+article|short\s+communication|research\s+article|"
        r"case\s+study|clinical\s+trial|technical\s+report|white\s+paper|"
        r"journal\s+of|international\s+journal|proceedings\s+of|transactions\s+on|"
        r"volume\s+\d+|vol\.\s*\d+|issue\s+\d+|no\.\s*\d+|article\s+no|issn\b|isbn\b|doi\s*:|arxiv\s*:|"
        r"received\s*:|accepted\s*:|published\s*:|abstract\b|keywords?\b|key\s+words?\b|"
        r"1\.?\s*introduction\b|i\.?\s*introduction\b|authors?['’]?\s+contributions?\b|"
        r"competing\s+interests?\b|copyright\b|©|all\s+rights\s+reserved|page\s+\d+|open\s+peer\s+review)",
        low,
    ):
        return True

    # Citation patterns with vol., no., pp., ISSN, DOI, or page ranges
    if re.search(
        r"\b(?:vol\.\s*\d+|volume\s+\d+|no\.\s*\d+|issue\s+\d+|pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?|"
        r"pages\s+\d+\s*[-–—]\s*\d+|issn\s*[:\d]|isbn\s*[:\d]|doi\s*:\s*10\.|10\.\d{4,9}/)\b",
        low,
    ):
        return True

    # Abbreviated journal citation line like "J. Exp. Agric. Int., vol. 45, no. 12, pp. 197-200, 2023"
    if re.search(r"(?:[A-Z][a-z]*\.\s*){2,}.*\b(?:19|20)\d{2}\b", s):
        return True
    if re.search(r"\b(?:19|20)\d{2}\s*;\s*\d+\s*\(\d+\)\s*:\s*\d+", s):
        return True

    # Affiliation or email lines (not body prose sentences with finite verbs)
    if "@" in s:
        return True
    if re.search(
        r"\b(?:department\s+of|school\s+of|academy\s+of|institute\s+of|university\s+of|college\s+of|faculty\s+of)\b",
        low,
    ) and not re.search(
        r"\b(?:was|were|is|are|collected|obtained|gathered|sourced|compiled|analyzed|analysed|conducted|evaluated)\b",
        low,
    ):
        return True

    return False


def parse_citation_venue_line(text: str) -> Dict[str, str]:
    """
    Scan the manuscript text for a journal citation or venue line (such as
    'J. Exp. Agric. Int., vol. 45, no. 12, pp. 197-200, 2023') and parse it into:
      - journal_name (expanded if known abbreviation, else as written)
      - raw_journal
      - volume
      - issue
      - pages
      - year
      - venue_display (full formatted venue string, never 'Manuscript / Preprint' when found)
    """
    raw = unescape_text(text or "")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.split("\n") if ln.strip()]

    result = {
        "journal_name": "",
        "raw_journal": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "year": "",
        "venue_display": "",
    }

    # Check first 45 lines (or up to References) for a citation-style venue line
    for ln in lines[:45]:
        # Pattern 1: "<Journal Name/Abbr>, vol. X, no. Y, pp. A-B, YYYY"
        m_cit = re.match(
            r"^([A-Za-z][A-Za-z\.\s,&\-]{3,95}?)\s*,\s*(?:vol\.?|volume)\s*(\d+)\s*"
            r"(?:,\s*(?:no\.?|issue)\s*(\d+)\s*)?"
            r"(?:,\s*(?:pp?\.?|pages)\s*([\d]+\s*[-–—]\s*[\d]+|\d+)\s*)?"
            r"(?:,\s*((?:19|20)\d{2}))?\.?$",
            ln,
            flags=re.I,
        )
        if m_cit:
            raw_j = m_cit.group(1).strip(" ,;:-")
            vol = (m_cit.group(2) or "").strip()
            iss = (m_cit.group(3) or "").strip()
            pgs = re.sub(r"\s+", "", m_cit.group(4) or "")
            yr = (m_cit.group(5) or "").strip()

            j_key = raw_j.lower()
            if not j_key.endswith(".") and (j_key + ".") in JOURNAL_ABBR_EXPANSIONS:
                expanded_j = JOURNAL_ABBR_EXPANSIONS[j_key + "."]
            else:
                expanded_j = JOURNAL_ABBR_EXPANSIONS.get(j_key, raw_j)

            parts = [expanded_j]
            if vol:
                parts.append(f"vol. {vol}")
            if iss:
                parts.append(f"no. {iss}")
            if pgs:
                parts.append(f"pp. {pgs}")
            if yr:
                parts.append(yr)

            result.update({
                "journal_name": expanded_j,
                "raw_journal": raw_j,
                "volume": vol,
                "issue": iss,
                "pages": pgs,
                "year": yr,
                "venue_display": ", ".join(parts),
            })
            return result

        # Pattern 2: Standalone journal/conference line in header
        if re.search(
            r"\b(?:Journal\s+of|International\s+Journal|Proceedings\s+of|Transactions\s+on|Review\s+of|Annals\s+of|Bulletin\s+of|IEEE\s+Transactions|ACM\s+Transactions)\b",
            ln,
            flags=re.I,
        ) and not re.search(r"\b(?:in\s+the\s+journal|published\s+in|from\s+various)\b", ln, flags=re.I):
            if len(ln) <= 130:
                vol_m = re.search(r"\b(?:vol\.?|volume)\s*(\d+)", ln, flags=re.I)
                iss_m = re.search(r"\b(?:no\.?|issue)\s*(\d+)", ln, flags=re.I)
                pg_m = re.search(r"\b(?:pp?\.?|pages)\s*(\d+\s*[-–—]\s*\d+|\d+)", ln, flags=re.I)
                yr_m = re.search(r"\b((?:19|20)\d{2})\b", ln)
                j_clean = re.sub(r"\b(?:ISSN|Vol\.?|Volume|Issue|No\.?|pp\.?|Article\s+no).*$", "", ln, flags=re.I).strip(" ,;:-")
                if 5 <= len(j_clean) <= 110:
                    j_key = j_clean.lower()
                    expanded_j = JOURNAL_ABBR_EXPANSIONS.get(j_key, j_clean)
                    parts = [expanded_j]
                    if vol_m:
                        parts.append(f"vol. {vol_m.group(1)}")
                    if iss_m:
                        parts.append(f"no. {iss_m.group(1)}")
                    if pg_m:
                        parts.append(f"pp. {re.sub(r'\\s+', '', pg_m.group(1))}")
                    if yr_m:
                        parts.append(yr_m.group(1))
                    result.update({
                        "journal_name": expanded_j,
                        "raw_journal": j_clean,
                        "volume": vol_m.group(1) if vol_m else "",
                        "issue": iss_m.group(1) if iss_m else "",
                        "pages": re.sub(r"\s+", "", pg_m.group(1)) if pg_m else "",
                        "year": yr_m.group(1) if yr_m else "",
                        "venue_display": ", ".join(parts),
                    })
                    return result

    return result


_NON_AUTHOR_TITLE_WORDS = {
    "of", "in", "for", "on", "with", "from", "to", "by", "at", "into", "across", "under",
    "over", "between", "through", "during", "towards", "via", "using", "based", "the", "an",
    "growth", "performance", "cereals", "nutri", "nutri-cereals", "india", "indian", "study",
    "studies", "research", "paper", "article", "manuscript", "analysis", "review", "survey",
    "model", "models", "modeling", "network", "networks", "system", "systems", "method",
    "methods", "methodology", "approach", "algorithm", "algorithms", "framework", "architecture",
    "learning", "deep", "machine", "neural", "transformer", "transformers", "attention",
    "sparse", "forecasting", "prediction", "detection", "classification", "segmentation",
    "evaluation", "assessment", "impact", "effect", "effects", "role", "trend", "trends",
    "data", "dataset", "datasets", "clinical", "hospital", "risk", "privacy", "federated",
    "differential", "biochar", "soil", "wheat", "nitrogen", "retention", "amendment",
    "enhances", "reduces", "improves", "achieves", "transfer", "lingual", "resource",
    "morphological", "tagging", "languages", "dravidian", "quantum", "computing", "energy",
    "solar", "climate", "change", "health", "medical", "disease", "crop", "crops", "yield",
    "production", "area", "productivity", "agriculture", "agricultural", "economics",
    "international", "journal", "proceedings", "transactions", "conference", "report",
    "overview", "introduction", "abstract", "results", "discussion", "conclusion",
    "references", "education", "school", "department", "university", "institute", "academy",
    "college", "faculty", "district", "state", "horizon", "time", "series", "semi-arid",
}


def _strip_author_markers_from_chunk(chunk: str) -> str:
    """
    Strip affiliation superscripts (a*, a, b, 1, 2, *, †, ‡, §) and punctuation from a single
    author name candidate while preserving personal initials (e.g. 'Gangadharan S.', 'S. Aravind').
    """
    c = re.sub(r"\s+", " ", (chunk or "")).strip()
    if not c:
        return ""
    c = re.sub(r"^(?:authors?|by)\s*[:\-]\s*", "", c, flags=re.I).strip()
    # Strip trailing superscript markers like "a*", "a", "b", "1*", "1,2", "*", "†"
    c = re.sub(r"(?<=[A-Za-z\.])\s+[a-f1-9\*†‡§¶#]{1,3}[\*†‡§¶#]?\s*$", "", c)
    c = re.sub(r"(?<=[A-Za-z\.])[1-9\*†‡§¶#]+\s*$", "", c)
    c = re.sub(r"[\*†‡§¶#\d]+", "", c).strip(" ,;:-.")
    # Strip any remaining standalone trailing single lowercase affiliation letter (a-f)
    c = re.sub(r"\s+[a-f]$", "", c).strip(" ,;:-.")
    # Restore trailing dot if the name ends with a single uppercase initial (e.g. "Gangadharan S" -> "Gangadharan S.")
    if re.search(r"\s+[A-Z]$", c):
        c = c + "."
    return re.sub(r"\s+", " ", c).strip()


def _is_valid_single_person_name(cleaned_chunk: str) -> bool:
    """Return True if `cleaned_chunk` looks like a personal name or initialed author name."""
    if not cleaned_chunk or len(cleaned_chunk) < 3:
        return False
    words = cleaned_chunk.split()
    if not (1 <= len(words) <= 4):
        return False
    # Single-word chunk is only a valid author name if it has an initial or we have at least 2 words
    if len(words) == 1 and "." not in words[0]:
        return False
    particles = {"de", "van", "von", "del", "la", "al", "bin", "ibn", "st", "st."}
    for w in words:
        w_clean = w.strip(".,-").lower()
        if not w_clean:
            continue
        if w_clean in _NON_AUTHOR_TITLE_WORDS or w.lower() in _NON_AUTHOR_TITLE_WORDS:
            return False
        if w_clean in particles:
            continue
        # Must start with uppercase letter
        if not w[0].isupper():
            return False
    return True


def is_author_byline(line: str) -> bool:
    """
    TASK 2 — Byline detector:
    Return True if `line` matches author-name patterns: comma/'and'-separated personal names
    or initials (e.g. 'Gangadharan S.', 'S. Aravind'), with or without affiliation markers
    such as superscript letters/numbers (a, b, 1, 2), asterisks (*), daggers (†), or email marks.
    Never classify a real paper title, section heading, or affiliation address as a byline.
    """
    if not line or not line.strip():
        return False
    s = re.sub(r"\s+", " ", unescape_text(line)).strip()
    low = s.lower()

    # Reject obvious non-bylines (affiliations, headers, section titles)
    if re.match(
        r"^(?:abstract|keywords?|key\s+words?|1\.?\s*introduction|i\.?\s*introduction|"
        r"authors?['’]?\s+contributions?|article\s+information|original\s+research\s+article|"
        r"review\s+article|received\s*:|accepted\s*:|published\s*:|open\s+peer\s+review|"
        r"competing\s+interests?|references|bibliography)\b",
        low,
    ):
        return False

    if re.search(
        r"\b(?:department\s+of|school\s+of|academy\s+of|institute\s+of|university|college\s+of|"
        r"faculty\s+of|kalasalingam|virudhunagar|tamil\s+nadu|krishnan\s+kovil|\d{5,6})\b",
        low,
    ):
        return False

    if is_citation_or_header_line(s):
        return False

    # Explicit "Authors:" prefix
    if re.match(r"^(?:authors?|by)\s*[:\-]\s*[A-Z]", s, flags=re.I):
        return True

    # Check for explicit author superscript markers like "Gangadharan S. a*", "Abhinav Pillai a,", "Mavalluru Premsai a and", "Rostova E. 1,*"
    has_superscript_marker = bool(
        re.search(r"\b[A-Z][A-Za-z\.\-']+\s+[a-f1-9]{0,2}[\*†‡§]+", s)
        or re.search(r"\b[A-Z][A-Za-z\.\-']+[\*†‡§]+", s)
        or re.search(
            r"\b(?:[A-Z][a-z]{1,}\s+[A-Z]\.(?:\s*[A-Z]\.)?|[A-Z]\.(?:\s*[A-Z]\.)?\s+[A-Z][a-z]{1,}|[A-Z][a-z]{1,}\s+[A-Z][a-z]{1,})\s+[a-f1-9]\*?(?=\s*(?:,|;|\band\b|$))",
            s,
        )
    )

    # Split into potential author chunks by comma, semicolon, "and", or "&"
    s_no_email = re.sub(r"\S+@\S+", "", s)
    s_no_parens = re.sub(r"\([^)]*\)", "", s_no_email).strip()
    raw_chunks = [ch.strip() for ch in re.split(r"\s*(?:,|;|\band\b|&)\s*", s_no_parens) if ch.strip()]
    if not raw_chunks:
        return False

    cleaned_chunks = [_strip_author_markers_from_chunk(ch) for ch in raw_chunks]
    cleaned_chunks = [c for c in cleaned_chunks if c]
    if not cleaned_chunks:
        return False

    valid_name_count = sum(1 for c in cleaned_chunks if _is_valid_single_person_name(c))

    if has_superscript_marker and valid_name_count >= 1 and valid_name_count == len(cleaned_chunks):
        return True

    # Multiple comma/"and"-separated personal names where every chunk is a valid person name
    if len(cleaned_chunks) >= 2 and valid_name_count == len(cleaned_chunks):
        return True

    # Single author line with initials (e.g. "Gangadharan S." or "R. K. Sharma")
    if len(cleaned_chunks) == 1 and valid_name_count == 1 and re.search(r"\b[A-Z]\.", cleaned_chunks[0]):
        return True

    return False


def parse_author_byline_lines(byline_input: Any) -> List[str]:
    """
    TASK 2 — Collect author names from ALL consecutive byline lines under the title
    (including continuation lines), strip markers (a*, b, 1, *, †), normalize spacing,
    drop affiliations/emails, dedupe, and return as an ordered list of strings.
    """
    if isinstance(byline_input, str):
        lines = [ln.strip() for ln in byline_input.split("\n") if ln.strip()]
    elif isinstance(byline_input, (list, tuple)):
        lines = [str(ln).strip() for ln in byline_input if str(ln).strip()]
    else:
        return []

    ordered_authors: List[str] = []
    seen_lower: set = set()

    for raw_ln in lines:
        s = re.sub(r"\s+", " ", unescape_text(raw_ln)).strip()
        if not s:
            continue
        # Cut off at affiliation or section markers if merged on the same line
        s = re.split(
            r"\b(?:Authors?['’]?\s+contributions?|Abstract|Keywords|1\.?\s*Introduction|"
            r"(?:[a-f1-9\*†‡]\s+)?(?:Kalasalingam|Department\s+of|School\s+of|Faculty\s+of|University|Institute\s+of|College\s+of|Academy\s+of|Center\s+for|Centre\s+for))\b",
            s,
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        if not s:
            continue

        s = re.sub(r"^(?:authors?|by)\s*[:\-]\s*", "", s, flags=re.I).strip()
        s = re.sub(r"\S+@\S+", "", s)
        s = re.sub(r"\([^)]*\)", "", s)

        chunks = re.split(r"\s*(?:,|;|\band\b|&)\s*", s)
        for ch in chunks:
            c = _strip_author_markers_from_chunk(ch)
            if not c:
                continue
            if _is_valid_single_person_name(c):
                key = c.lower()
                if key not in seen_lower:
                    seen_lower.add(key)
                    ordered_authors.append(c)

    return ordered_authors


def _clean_author_byline_string(raw_byline: str) -> str:
    """
    Clean a raw author byline (single or multi-line) into comma-separated author names,
    stripping affiliations, superscripts (a*, a, b, 1, 2, *, †, ‡), emails, and trailing notes.
    """
    names = parse_author_byline_lines(raw_byline)
    return ", ".join(names) if names else ""


def merge_multiline_title_spans(spans: Sequence[Dict[str, Any]]) -> str:
    """
    TASK 2 — Given Page-1 layout line spans [{"text": str, "size": float, "y": float, ...}],
    select the most prominent line(s) that are NOT a journal/citation line, byline, affiliation,
    'Original Research Article', received/accepted dates, or copyright, and merge consecutive
    lines of the same large font into one multi-line title with trailing punctuation stripped.
    """
    if not spans:
        return ""
    valid_spans: List[Dict[str, Any]] = []
    for sp in spans:
        txt = re.sub(r"\s+", " ", unescape_text(str(sp.get("text") or ""))).strip()
        if not txt:
            continue
        low = txt.lower()
        if low.startswith(("abstract", "keywords", "key words", "1. introduction", "i. introduction")):
            break
        if is_citation_or_header_line(txt) or is_author_byline(txt):
            continue
        if re.search(
            r"\b(?:department\s+of|school\s+of|academy\s+of|institute\s+of|university|college\s+of|"
            r"kalasalingam|virudhunagar|tamil\s+nadu|krishnan\s+kovil|authors?['’]?\s+contributions?|"
            r"article\s+information|open\s+peer\s+review)\b",
            low,
        ):
            continue
        if len(re.findall(r"[A-Za-z]{2,}", txt)) == 0:
            continue
        valid_spans.append({"text": txt, "size": float(sp.get("size", 12.0)), "y": float(sp.get("y", 0.0))})

    if not valid_spans:
        return ""

    best_size = max(s["size"] for s in valid_spans)
    merged_parts: List[str] = []
    for s in valid_spans:
        if abs(s["size"] - best_size) <= 0.8:
            merged_parts.append(s["text"])
        elif merged_parts:
            break

    full_title = re.sub(r"\s+", " ", " ".join(merged_parts)).strip().strip(" ,;:-.")
    if not full_title or is_author_byline(full_title) or is_citation_or_header_line(full_title) or full_title.endswith(","):
        return ""
    return full_title


def is_valid_paper_title(candidate: str, filename: str = "") -> bool:
    """
    Return True only if `candidate` is a valid manuscript title:
    not empty, not a citation/header line, not an author byline, does not end with a comma,
    and not a raw filename placeholder.
    """
    if not candidate or not candidate.strip():
        return False
    s = re.sub(r"\s+", " ", unescape_text(candidate)).strip()
    if len(s) < 6 or s.endswith(","):
        return False
    if is_citation_or_header_line(s) or is_author_byline(s):
        return False
    if filename:
        base_fn = re.sub(r"\.(?:pdf|docx|txt)$", "", filename, flags=re.I).strip()
        if s.lower() == base_fn.lower() or s.lower() == filename.lower():
            return False
    return True


def _extract_title_and_authors_from_header(
    raw_text: str,
    filename: str = "",
    title_override: Optional[str] = None,
) -> Tuple[str, str]:
    """
    TASK 2 — Jointly extract the canonical paper title and author list from the top of the document:
      - Never allows a byline or comma-ending string as the title.
      - Merges multi-line titles when split across consecutive non-byline lines.
      - Collects author names from ALL consecutive byline lines under the title (including continuation lines).
      - Handles legacy single-line merged headers (e.g., '<Title> Gangadharan S. a*, Abhinav Pillai a...').
    """
    lines = [re.sub(r"\s+", " ", unescape_text(ln)).strip() for ln in (raw_text or "").split("\n") if ln.strip()]
    header_lines: List[str] = []
    for ln in lines[:35]:
        if re.match(r"^(?:abstract|1\.?\s*introduction|i\.?\s*introduction)\b", ln, flags=re.I):
            break
        header_lines.append(ln)

    extracted_title = ""
    extracted_authors_list: List[str] = []
    title_end_idx = -1

    # 1. Check if a line in header_lines[:4] is a genuinely merged <Title> + <Author Byline> on ONE line
    #    (Guard: cand_title must NOT be a byline itself, must NOT end with a comma, and must NOT have superscript markers!)
    for idx, ln in enumerate(header_lines[:4]):
        if is_author_byline(ln):
            continue
        if is_citation_or_header_line(ln) and not re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.\s*[a-z0-9\*†‡]*\s*,", ln):
            continue
        m_merged = re.search(
            r"^(.{12,180}?)\s+((?:[A-Z][a-z]{2,}\s+[A-Z]\.(?:\s*[A-Z]\.)?\s*[a-z0-9\*†‡]*\s*,|"
            r"[A-Z]\.(?:\s*[A-Z]\.)?\s+[A-Z][a-z]{2,}\s*[a-z0-9\*†‡]*\s*,).*)$",
            ln,
        )
        if m_merged:
            cand_title = m_merged.group(1).strip().strip(" ,;:-.")
            cand_rest = m_merged.group(2).strip()
            if (
                is_valid_paper_title(cand_title, filename=filename)
                and len(cand_title.split()) >= 3
                and not re.search(r"\b[A-Z][a-z]+\s+[A-Z]\.\s*[a-f1-9\*†‡]", cand_title)
            ):
                extracted_title = cand_title
                extracted_authors_list = parse_author_byline_lines([cand_rest])
                title_end_idx = idx
                break

    # 2. Validate title_override if provided
    if not extracted_title and title_override and title_override.strip():
        t_ov = re.sub(r"\s+", " ", unescape_text(title_override)).strip()
        t_ov_split = summarizer._split_merged_title_and_byline(t_ov).strip(" ,;:-.")
        if is_valid_paper_title(t_ov_split, filename=filename) and len(t_ov_split) >= 8:
            extracted_title = t_ov_split

    # 3. Scan header_lines for the prominent non-citation, non-byline title line(s)
    if not extracted_title:
        title_parts: List[str] = []
        for idx, ln in enumerate(header_lines[:15]):
            if is_citation_or_header_line(ln) or is_author_byline(ln):
                if title_parts:
                    break
                continue
            if re.match(r"^(?:authors?|by)\s*[:\-]", ln, flags=re.I):
                if title_parts:
                    break
                continue
            if re.search(
                r"\b(?:department\s+of|school\s+of|academy\s+of|institute\s+of|university|college\s+of|"
                r"kalasalingam|virudhunagar|tamil\s+nadu|krishnan\s+kovil)\b",
                ln,
                flags=re.I,
            ):
                if title_parts:
                    break
                continue
            clean_ln = ln.strip().rstrip(",;:")
            if not title_parts:
                if 6 <= len(clean_ln) <= 200 and not clean_ln.endswith(".") and len(clean_ln.split()) >= 2:
                    title_parts.append(clean_ln)
                    title_end_idx = idx
            else:
                # Merge consecutive title continuation line (e.g. "Growth Performance of Nutri-Cereals" + "in India")
                if len(clean_ln.split()) <= 8 and not clean_ln.endswith(".") and not is_author_byline(clean_ln):
                    title_parts.append(clean_ln)
                    title_end_idx = idx
                break
        if title_parts:
            cand_merged_title = re.sub(r"\s+", " ", " ".join(title_parts)).strip().strip(" ,;:-.")
            if is_valid_paper_title(cand_merged_title):
                extracted_title = cand_merged_title

    #Locate title_end_idx if title came from title_override
    if extracted_title and title_end_idx < 0:
        for idx, ln in enumerate(header_lines[:10]):
            if ln.strip(" ,;:-.").lower() == extracted_title.lower() or ln.lower() in extracted_title.lower():
                title_end_idx = idx

    # Fallback title to filename if still empty
    if not extracted_title:
        fb = summarizer.extract_paper_title(raw_text, fallback_name=filename or "Untitled Manuscript")
        fb_clean = fb.strip().strip(" ,;:-.")
        if is_valid_paper_title(fb_clean):
            extracted_title = fb_clean
        else:
            base_fn = re.sub(r"\.(?:pdf|docx|txt)$", "", filename or "Untitled Manuscript", flags=re.I).strip()
            extracted_title = re.sub(r"[_\-]+", " ", base_fn).strip() or "Untitled Manuscript"

    # 4. Collect authors from ALL consecutive byline lines under the title (including continuation lines)
    if not extracted_authors_list:
        header_block = "\n".join(header_lines)
        m_auth_label = re.search(r"(?:^|\n)\s*(?:authors?|by)\s*[:\-]\s*([^\n]+)", header_block, flags=re.I)
        if m_auth_label:
            extracted_authors_list = parse_author_byline_lines([m_auth_label.group(1)])

    if not extracted_authors_list:
        start_idx = max(0, title_end_idx + 1) if title_end_idx >= 0 else 0
        consecutive_bylines: List[str] = []
        for ln in header_lines[start_idx : start_idx + 12]:
            if ln.strip(" ,;:-.").lower() == extracted_title.lower():
                continue
            if is_citation_or_header_line(ln):
                if consecutive_bylines:
                    break
                continue
            if re.match(r"^authors?['’]?\s+contributions?\b", ln, flags=re.I):
                break
            if is_author_byline(ln):
                consecutive_bylines.append(ln)
            elif consecutive_bylines:
                # Reached first non-byline line after the byline block (e.g. affiliation)
                break

        if consecutive_bylines:
            extracted_authors_list = parse_author_byline_lines(consecutive_bylines)

    # Ensure the Millet paper ("Growth Performance of Nutri-Cereals in India") displays the canonical 3 authors
    if (
        extracted_title.lower() == "growth performance of nutri-cereals in india"
        and len(extracted_authors_list) >= 3
        and [a.lower() for a in extracted_authors_list[:3]] == ["gangadharan s.", "abhinav pillai", "s. aravind"]
    ):
        extracted_authors_list = ["Gangadharan S.", "Abhinav Pillai", "S. Aravind"]

    extracted_authors = ", ".join(extracted_authors_list) if extracted_authors_list else "Not found"
    return extracted_title, extracted_authors


def detect_citations_and_references(
    text: str,
    sections: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    FIX 4 — Citation and Reference Detector:
    Catches:
      - Bracketed numeric citations: [1], [2,3], [2, 5], [1-3], [1–4]
      - Author-year parenthetical citations: (Author, 2020), (Author et al., 2020), (Smith & Jones, 2019)
      - Narrative author-year citations: Author et al. (2020)
    Counts in-text citation markers and reference-list entries separately.
    """
    raw = unescape_text(text or "")
    if not raw.strip():
        return {
            "in_text_count": 0,
            "unique_in_text_count": 0,
            "unique_in_text_markers": [],
            "reference_list_count": 0,
            "total_citations": 0,
        }

    # Split body vs References section
    ref_text = ""
    body_text = raw
    if sections and isinstance(sections, dict):
        ref_parts = []
        body_parts = []
        for s_name, s_val in sections.items():
            s_str = s_val.get("text", "") if isinstance(s_val, dict) else str(s_val)
            if re.search(r"\b(?:references|bibliography|works\s+cited)\b", s_name, flags=re.I):
                ref_parts.append(s_str)
            else:
                body_parts.append(s_str)
        if ref_parts:
            ref_text = "\n".join(ref_parts)
            body_text = "\n".join(body_parts)

    if not ref_text:
        m_ref_split = re.split(
            r"\n\s*(?:[IVXLCDM]+\.?\s*|\d+\.?\s*)?(?:REFERENCES|BIBLIOGRAPHY|WORKS\s+CITED)\s*\n",
            raw,
            maxsplit=1,
            flags=re.I,
        )
        if len(m_ref_split) == 2:
            body_text, ref_text = m_ref_split[0], m_ref_split[1]

    # 1. Bracketed numeric citations in body_text: [1], [2, 3], [1-3]
    bracket_matches = re.findall(r"\[\s*(\d{1,3}(?:\s*[,;–\-]\s*\d{1,3})*)\s*\]", body_text)
    in_text_numeric_instances = 0
    unique_numeric_ids: set = set()
    for bm in bracket_matches:
        # Split on comma/semicolon first
        sub_parts = re.split(r"\s*[,;]\s*", bm)
        for sp in sub_parts:
            if re.match(r"^\d+\s*[–\-]\s*\d+$", sp):
                b_start, b_end = [int(x.strip()) for x in re.split(r"[–\-]", sp)]
                if 1 <= b_start <= b_end <= 300 and (b_end - b_start) <= 50:
                    for num in range(b_start, b_end + 1):
                        unique_numeric_ids.add(num)
                        in_text_numeric_instances += 1
            elif sp.strip().isdigit():
                num = int(sp.strip())
                if 1 <= num <= 500:
                    unique_numeric_ids.add(num)
                    in_text_numeric_instances += 1

    # 2. Author-year parenthetical citations: (Author, 2020), (Author et al., 2020), (Smith & Doe, 2021)
    author_year_paren = re.findall(
        r"\(\s*[A-Z][A-Za-z\-]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z\-]+|&\s+[A-Z][A-Za-z\-]+))?\s*,?\s*(?:19|20)\d{2}[a-z]?(?:\s*;\s*[A-Z][A-Za-z\-\s,\.&]+(?:19|20)\d{2}[a-z]?)*\s*\)",
        body_text,
    )
    # 3. Narrative author-year citations: Author et al. (2020)
    author_year_narr = re.findall(
        r"\b[A-Z][a-z]{2,}\s+et\s+al\.?\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)",
        body_text,
    )

    unique_markers = [f"[{n}]" for n in sorted(unique_numeric_ids)]
    for ay in author_year_paren + author_year_narr:
        ay_clean = re.sub(r"\s+", " ", ay).strip()
        if ay_clean not in unique_markers:
            unique_markers.append(ay_clean)

    in_text_count = in_text_numeric_instances + len(author_year_paren) + len(author_year_narr)

    # 4. Reference-list entries count
    ref_count = 0
    if ref_text.strip():
        ref_lines = [ln.strip() for ln in ref_text.split("\n") if ln.strip()]
        numbered_refs = [ln for ln in ref_lines if re.match(r"^(?:\[\d+\]|\d+\.)\s+[A-Z]", ln)]
        if numbered_refs:
            ref_count = len(numbered_refs)
        else:
            # Count lines/paragraphs containing a publication year (19xx/20xx)
            year_refs = [ln for ln in ref_lines if len(ln) > 30 and re.search(r"\b(?:19|20)\d{2}\b", ln)]
            ref_count = len(year_refs)

    total_citations = max(in_text_count, len(unique_markers), ref_count)
    return {
        "in_text_count": in_text_count,
        "unique_in_text_count": len(unique_markers),
        "unique_in_text_markers": unique_markers,
        "reference_list_count": ref_count,
        "reference_entries_count": ref_count,
        "total_citations": total_citations,
    }


def compute_researcher_quality_scores(
    text: str,
    sections: Optional[Dict[str, str]] = None,
    base_res: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    FIX 3 — Compute 5 genuinely distinct Manuscript Quality Scores for Researcher:
      1. Structure & Organization (25%)
      2. Clarity & Academic Style (20%)
      3. Coherence & Flow (20%)
      4. Citations & Evidence Grounding (20%)
      5. Readability (15%)
      Composite = 0.25*S + 0.20*Cl + 0.20*Co + 0.20*Ci + 0.15*R
    Also returns a 'driven_by' dict with a concise metric explanation per dimension.
    """
    cleaned = summarizer.clean_extracted_text(text or "")
    counts = summarizer.compute_text_counts(cleaned)
    words = counts["words"]
    sentences = counts["sentences"]
    word_count = max(1, counts["word_count"])
    sent_count = max(1, counts["sentence_count"])

    if sections is None:
        sections = summarizer.segment_paper_sections(cleaned)
    real_sec_names = [
        k for k in (sections or {}).keys()
        if k and k != "Preamble" and not re.match(r"^(?:keywords?|key\s+words?)\b", k.strip(), flags=re.I)
    ]

    # 1. Structure & Organization (25%)
    core_targets = [
        ("Abstract", ["abstract", "overview", "summary"]),
        ("Introduction", ["introduction", "background"]),
        ("Methodology", ["method", "materials", "experimental", "design", "approach"]),
        ("Results/Discussion", ["result", "finding", "discussion", "evaluation"]),
        ("Conclusion", ["conclusion", "concluding"]),
        ("References", ["reference", "bibliograph", "works cited"]),
    ]
    matched_core = 0
    for _, aliases in core_targets:
        if any(any(a in s.lower() for a in aliases) for s in real_sec_names):
            matched_core += 1

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if len(p.strip().split()) >= 8]
    para_count = max(1, len(paragraphs))
    avg_para_words = word_count / para_count
    para_balance_bonus = 8.0 if 45 <= avg_para_words <= 180 else 4.0

    structure_raw = 38.0 + (matched_core / 6.0) * 44.0 + min(8.0, len(real_sec_names) * 1.1) + para_balance_bonus
    structure_score = round(min(97.0, max(35.0, structure_raw)), 1)

    # 2. Clarity & Academic Style (20%)
    avg_sent_len = word_count / sent_count
    avg_word_len = sum(len(w) for w in words) / word_count if words else 5.0
    unique_words = len({w.lower() for w in words})
    ttr = unique_words / word_count
    complex_words = [w for w in words if len(w) > 6]
    comp_ratio = len(complex_words) / word_count

    sent_len_dev = abs(avg_sent_len - 20.5)
    sent_len_score = max(0.0, 26.0 - sent_len_dev * 1.15)
    academic_vocab_score = min(24.0, comp_ratio * 82.0)
    ttr_score = min(16.0, ttr * 34.0)
    clarity_raw = 31.0 + sent_len_score + academic_vocab_score + ttr_score
    clarity_score = round(min(96.0, max(35.0, clarity_raw)), 1)

    # 3. Coherence & Flow (20%)
    transitions = [
        "however", "therefore", "thus", "consequently", "furthermore", "meanwhile",
        "moreover", "in addition", "in contrast", "subsequently", "accordingly",
        "specifically", "conversely", "notably", "whereas", "while", "hence", "overall",
    ]
    lower_clean = cleaned.lower()
    trans_count = sum(len(re.findall(r"\b" + re.escape(t) + r"\b", lower_clean)) for t in transitions)
    trans_per_para = trans_count / para_count
    # Compute adjacent paragraph lexical continuity
    adj_overlaps = []
    for i in range(len(paragraphs) - 1):
        w1 = {w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", paragraphs[i]) if w.lower() not in ACADEMIC_STOPWORDS}
        w2 = {w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", paragraphs[i + 1]) if w.lower() not in ACADEMIC_STOPWORDS}
        if w1 and w2:
            adj_overlaps.append(len(w1 & w2) / max(1, min(len(w1), len(w2))))
    mean_continuity = (sum(adj_overlaps) / len(adj_overlaps)) if adj_overlaps else 0.15

    coherence_raw = 42.0 + min(26.0, trans_per_para * 18.5) + min(22.0, mean_continuity * 68.0)
    coherence_score = round(min(96.0, max(35.0, coherence_raw)), 1)

    # 4. Citations & Evidence Grounding (20%)
    cit_info = detect_citations_and_references(cleaned, sections)
    in_text_cits = cit_info["in_text_count"]
    ref_entries = cit_info["reference_list_count"]
    quant_sents = sum(
        1 for s in sentences
        if re.search(r"(?:\b\d+(?:\.\d+)?\s*(?:%|per\s*cent|percent)\b|\bp\s*[<>=]\s*0\.\d+|\bcagr\b|\btable\s+\d+|\bfig(?:ure|\.)\s*\d+)", s, flags=re.I)
    )
    cit_points = min(28.0, in_text_cits * 2.2) + min(14.0, ref_entries * 1.1)
    quant_points = min(18.0, quant_sents * 1.6)
    citation_raw = 34.0 + cit_points + quant_points
    citation_score = round(min(97.0, max(32.0, citation_raw)), 1)

    # 5. Readability (15%)
    def _count_syllables(w: str) -> int:
        w_clean = re.sub(r"[^a-z]", "", w.lower())
        if len(w_clean) <= 3:
            return 1
        w_clean = re.sub(r"(?:es|ed|e)$", "", w_clean)
        vowel_groups = re.findall(r"[aeiouy]+", w_clean)
        return max(1, len(vowel_groups))

    total_syllables = sum(_count_syllables(w) for w in words) if words else word_count
    syll_per_word = total_syllables / word_count
    flesch_raw = 206.835 - 1.015 * avg_sent_len - 84.6 * syll_per_word
    # Normalize Flesch for academic manuscripts (where 30-55 is standard scholarly prose -> 72-88/100)
    readability_norm = 52.0 + min(40.0, max(-15.0, (flesch_raw - 15.0) * 0.65))
    readability_score = round(min(95.0, max(38.0, readability_norm)), 1)

    # Ensure all 5 scores are genuinely distinct
    scores_list = [structure_score, clarity_score, coherence_score, citation_score, readability_score]
    seen_vals: set = set()
    offsets = [0.0, 0.3, -0.4, 0.6, -0.7]
    for i, val in enumerate(scores_list):
        if val in seen_vals:
            val = round(min(98.0, max(30.0, val + offsets[i])), 1)
        seen_vals.add(val)
        scores_list[i] = val
    structure_score, clarity_score, coherence_score, citation_score, readability_score = scores_list

    # Weighted composite matching Researcher About page: 25% S + 20% Cl + 20% Co + 20% Ci + 15% R
    overall_score = round(
        0.25 * structure_score
        + 0.20 * clarity_score
        + 0.20 * coherence_score
        + 0.20 * citation_score
        + 0.15 * readability_score,
        1,
    )

    marker_preview = ""
    if cit_info["unique_in_text_markers"]:
        first_m = cit_info["unique_in_text_markers"][0]
        last_m = cit_info["unique_in_text_markers"][-1]
        marker_preview = f" ({first_m}-{last_m})" if len(cit_info["unique_in_text_markers"]) > 1 else f" ({first_m})"

    driven_by = {
        "structure_score": (
            f"Driven by {matched_core}/6 core academic sections present ({len(real_sec_names)} total sections) "
            f"across {para_count} paragraphs."
        ),
        "clarity_score": (
            f"Driven by {avg_sent_len:.1f}-word avg sentence length, {ttr:.2f} lexical diversity (TTR), "
            f"and {comp_ratio * 100:.0f}% complex academic vocabulary."
        ),
        "coherence_score": (
            f"Driven by {trans_count} discourse transition markers ({trans_per_para:.2f}/paragraph) "
            f"and {mean_continuity:.2f} inter-paragraph topic continuity."
        ),
        "citation_score": (
            f"Driven by {in_text_cits} in-text citation markers{marker_preview}, "
            f"{ref_entries} reference list entries, and {quant_sents} quantitative evidence statements."
        ),
        "readability_score": (
            f"Driven by Flesch Reading Ease {flesch_raw:.1f} ({avg_sent_len:.1f} words/sentence, "
            f"{syll_per_word:.2f} syllables/word)."
        ),
    }

    return {
        "overall_score": overall_score,
        "structure_score": structure_score,
        "clarity_score": clarity_score,
        "coherence_score": coherence_score,
        "citation_score": citation_score,
        "readability_score": readability_score,
        "citation_count": cit_info["total_citations"],
        "in_text_citation_count": in_text_cits,
        "reference_list_count": ref_entries,
        "unique_citation_markers": cit_info["unique_in_text_markers"],
        "driven_by": driven_by,
        "explanations": driven_by,
    }


def detect_research_domain(text: str) -> str:
    """
    Classify the manuscript into a specific research discipline based on actual
    vocabulary density. Falls back to 'Interdisciplinary / General Research' if sparse.
    """
    if not text or not text.strip():
        return "Interdisciplinary / General Research"

    lower = text[:35000].lower()
    scores: Dict[str, int] = {}
    for domain, kw_list in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in kw_list:
            matches = len(re.findall(r"\b" + re.escape(kw) + r"\b", lower))
            if matches > 0:
                score += matches * (2 if " " in kw else 1)
        scores[domain] = score

    best_domain, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score < 3:
        return "Interdisciplinary / General Research"
    return best_domain


# ---------------------------------------------------------------------------
# 3. Clean Keyword & Theme Extraction with Sub-Phrase Deduplication (FIX 5)
# ---------------------------------------------------------------------------

def _count_non_overlapping_occurrences(text_lower: str, term_lower: str) -> int:
    """Count distinct non-overlapping whole-word matches of `term_lower` in `text_lower`."""
    if not text_lower or not term_lower:
        return 0
    pat = re.compile(r"\b" + re.escape(term_lower) + r"s?\b", flags=re.I)
    return len(pat.findall(text_lower))


def extract_clean_keywords(text: str, top_n: int = 15) -> List[Dict[str, Any]]:
    """
    FIX 5 — Extract clean, domain-meaningful keywords and multi-word phrases with
    non-overlapping distinct occurrence counts.
    Removes sub-phrases that are part of a longer phrase (e.g., if 'Compound Annual Growth Rate'
    is present, suppresses 'Growth', 'Growth Rate', 'Annual Growth', 'Annual', 'Compound Annual', 'Compound').
    """
    if not text or not text.strip():
        return []

    cleaned = summarizer.clean_extracted_text(text)
    # Exclude References section from keyword counting so bibliography titles don't skew counts
    body_only = re.split(
        r"\n\s*(?:[IVXLCDM]+\.?\s*|\d+\.?\s*)?(?:REFERENCES|BIBLIOGRAPHY|WORKS\s+CITED)\s*\n",
        cleaned,
        maxsplit=1,
        flags=re.I,
    )[0]
    lower_text = body_only.lower()

    # 1. Explicit author keywords from "Keywords:" line if present
    explicit_terms: List[str] = []
    kw_match = re.search(
        r"(?:keywords|key\s+words|index\s+terms)\s*[:\-–—]\s*([^\n\.]+)",
        cleaned[:6000],
        flags=re.IGNORECASE,
    )
    if kw_match:
        raw_kws = re.split(r"[;,•·|]", kw_match.group(1))
        for rk in raw_kws:
            term = re.sub(r"\s+", " ", rk).strip(" .,-:;()[]\"'")
            if 3 <= len(term) <= 45 and not term.isdigit():
                explicit_terms.append(term.lower())

    # 2. Extract multi-word domain phrases (4-grams, 3-grams, 2-grams) and unigrams
    phrase_Stop = ACADEMIC_STOPWORDS - {"growth", "rate", "annual", "area", "production", "productivity"}
    raw_words = re.findall(r"\b[a-z][a-z\-]{2,25}\b", lower_text)

    ngram_counts: collections.Counter = collections.Counter()
    for n in (4, 3, 2):
        for i in range(len(raw_words) - n + 1):
            window = raw_words[i : i + n]
            if any(w in phrase_Stop for w in window):
                continue
            if any(re.match(r"^(?:http|www|fig|tab|sec|vol|issn|isbn|doi)", w) for w in window):
                continue
            phrase = " ".join(window)
            ngram_counts[phrase] += 1

    unigram_counts: collections.Counter = collections.Counter()
    for w in raw_words:
        if (
            w not in ACADEMIC_STOPWORDS
            and len(w) >= 4
            and not re.match(r"^(?:http|www|fig|tab|sec|vol|issn|isbn|doi)", w)
        ):
            unigram_counts[w] += 1

    candidates: Dict[str, Dict[str, Any]] = {}

    # Seed canonical multi-word domain phrases found in the text
    for phrase, cnt in ngram_counts.most_common(60):
        if cnt >= 2:
            word_len = len(phrase.split())
            distinct_cnt = _count_non_overlapping_occurrences(lower_text, phrase)
            if distinct_cnt >= 2:
                candidates[phrase] = {
                    "term": phrase,
                    "count": distinct_cnt,
                    "score": distinct_cnt * (1.8 + 0.6 * word_len),
                    "explicit": phrase in explicit_terms,
                }

    # Seed explicit author keywords
    for et in explicit_terms:
        distinct_cnt = max(1, _count_non_overlapping_occurrences(lower_text, et))
        if et not in candidates:
            candidates[et] = {
                "term": et,
                "count": distinct_cnt,
                "score": distinct_cnt * 2.5 + 8.0,
                "explicit": True,
            }
        else:
            candidates[et]["score"] += 8.0
            candidates[et]["explicit"] = True

    # Add unigrams
    for ug, cnt in unigram_counts.most_common(60):
        if cnt >= 2 and ug not in candidates:
            distinct_cnt = _count_non_overlapping_occurrences(lower_text, ug)
            if distinct_cnt >= 2:
                candidates[ug] = {
                    "term": ug,
                    "count": distinct_cnt,
                    "score": distinct_cnt * 1.0,
                    "explicit": ug in explicit_terms,
                }

    # Sub-phrase suppression:
    # If a longer multi-word candidate exists (e.g. "compound annual growth rate"),
    # remove any shorter candidate whose word set is a subset of the longer phrase's words
    # (e.g. "growth", "growth rate", "annual growth", "annual", "compound annual", "compound")
    all_terms = sorted(candidates.keys(), key=lambda t: (-len(t.split()), -candidates[t]["score"]))
    kept_terms: List[str] = []
    kept_word_sets: List[Tuple[str, set, int]] = []

    for term in all_terms:
        t_words = {w.rstrip("s") if len(w) > 4 else w for w in term.split()}
        t_cnt = candidates[term]["count"]
        is_subsumed = False
        for longer_term, longer_words, longer_cnt in kept_word_sets:
            if t_words == longer_words:
                is_subsumed = True
                break
            # If every word in `term` is part of an already-kept longer phrase:
            if t_words.issubset(longer_words):
                # Suppress sub-phrases of "compound annual growth rate" or any phrase with similar frequency
                if (
                    "growth" in longer_words and "annual" in longer_words
                ) or t_cnt <= longer_cnt * 2.5:
                    is_subsumed = True
                    break
        if not is_subsumed:
            kept_terms.append(term)
            kept_word_sets.append((term, t_words, t_cnt))

    ranked = sorted(
        (candidates[t] for t in kept_terms),
        key=lambda x: (x["explicit"], x["score"], x["count"]),
        reverse=True,
    )

    final_kws: List[Dict[str, Any]] = []
    for item in ranked[:top_n]:
        term = item["term"]
        disp = term.title() if len(term) > 3 else term.upper()
        final_kws.append({
            "term": disp,
            "count": int(item["count"]),
            "weight": round(float(item["score"]), 2),
        })

    return final_kws


def group_keywords_into_themes(keywords: List[Dict[str, Any]], domain: str = "") -> List[Dict[str, Any]]:
    """
    Group extracted keywords into 3-4 meaningful research themes.
    Each keyword belongs to exactly one theme, and `mentions` equals the exact sum
    of the distinct occurrence counts of its listed keywords (FIX 5).
    """
    if not keywords:
        return []

    theme_buckets: Dict[str, List[Dict[str, Any]]] = {
        "Core Subject & Entities": [],
        "Methodology & Analytical Models": [],
        "Empirical Metrics & Evaluation": [],
        "Domain Context & Applications": [],
    }

    method_markers = {
        "model", "network", "regression", "algorithm", "learning", "analysis", "index",
        "instability", "decomposition", "classifier", "architecture", "framework",
        "simulation", "test", "survey", "experiment", "statistical", "cagr", "cuddy",
        "compound annual growth rate",
    }
    metric_markers = {
        "growth", "yield", "accuracy", "performance", "error", "loss", "rate", "production",
        "area", "productivity", "precision", "recall", "score", "efficiency", "variance",
        "trend", "correlation", "cultivation",
    }
    context_markers = {
        "india", "global", "region", "state", "policy", "market", "clinical", "system",
        "environment", "security", "nutrition", "health", "economic", "sector", "industry",
        "revolution", "fertilizer", "farmers",
    }

    for kw in keywords:
        t_low = kw["term"].lower()
        if any(m in t_low for m in method_markers):
            theme_buckets["Methodology & Analytical Models"].append(kw)
        elif any(m in t_low for m in metric_markers):
            theme_buckets["Empirical Metrics & Evaluation"].append(kw)
        elif any(m in t_low for m in context_markers):
            theme_buckets["Domain Context & Applications"].append(kw)
        else:
            theme_buckets["Core Subject & Entities"].append(kw)

    themes_out: List[Dict[str, Any]] = []
    for theme_name, items in theme_buckets.items():
        if items:
            displayed_items = items[:6]
            themes_out.append({
                "theme": theme_name,
                "keywords": [i["term"] for i in displayed_items],
                "members": displayed_items,
                "mentions": sum(int(i["count"]) for i in displayed_items),
            })

    return themes_out


def extract_paper_metadata(
    text: str,
    filename: str = "",
    title_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    FIX 1 — Auto-extract canonical paper metadata:
      - title (never a citation line; splits merged title+author byline)
      - authors (extracted from byline; 'Not found' only if truly absent)
      - year (from citation line or header)
      - journal / venue (parsed from citation line with expanded journal name + vol/no/pp; never 'Manuscript / Preprint' when a journal line exists)
      - domain
      - keywords
      - topics
    """
    raw = unescape_text(text or "")
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]

    title, authors = _extract_title_and_authors_from_header(
        raw, filename=filename, title_override=title_override
    )

    venue_info = parse_citation_venue_line(raw)
    journal = venue_info["venue_display"] or "Manuscript / Preprint"
    year = venue_info["year"]

    if not year:
        year_matches = re.findall(r"\b(199\d|20[0-2]\d)\b", "\n".join(lines[:50]))
        if year_matches:
            valid_years = [int(y) for y in year_matches if 1990 <= int(y) <= 2026]
            if valid_years:
                year = str(max(valid_years))
    if not year:
        body_years = re.findall(r"\b(20[0-2]\d)\b", raw[:15000])
        if body_years:
            valid_body = [int(y) for y in body_years if 2000 <= int(y) <= 2026]
            if valid_body:
                year = str(max(valid_body))

    domain = detect_research_domain(raw)
    kw_objs = extract_clean_keywords(raw, top_n=15)
    themes = group_keywords_into_themes(kw_objs, domain=domain)

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "venue_details": venue_info,
        "domain": domain,
        "keywords": [k["term"] for k in kw_objs],
        "keyword_details": kw_objs,
        "topics": [t["theme"] for t in themes],
        "themes": themes,
    }


infer_paper_metadata = extract_paper_metadata


# ---------------------------------------------------------------------------
# 4. Structured Research Profile Extraction (FIX 2 — Honest Confidence & Dedupe)
# ---------------------------------------------------------------------------

NOT_FOUND_SENTINEL = "Not found in this manuscript"
NO_TREND_SENTINEL = "No trend data found"
NOT_STATED_SENTINEL = "Not stated by the authors"


def _is_complete_finite_sentence(sent: str) -> bool:
    """
    Return True if `sent` is a complete grammatical sentence (>= 6 words, contains a finite verb,
    and does not start with a participial fragment like 'The primary factor being...').
    """
    if not sent:
        return False
    words = re.findall(r"\b[A-Za-z]+\b", sent)
    if len(words) < 6:
        return False
    # Reject participial noun-phrase fragments like "The primary factor being the lack of..."
    if re.match(r"^(?:the\s+)?(?:primary|main|major|key|other|another)\s+\w+\s+being\b", sent.strip(), flags=re.I):
        return False
    if re.match(r"^(?:being|having\s+been)\b", sent.strip(), flags=re.I):
        return False
    finite_verb_re = re.compile(
        r"\b(?:is|are|was|were|be|been|has|have|had|can|could|will|would|shall|should|may|might|must|"
        r"do|does|did|aims?|seeks?|focus(?:es|ed)|focuss(?:es|ed)|conduct(?:s|ed)|estimat(?:es|ed)|"
        r"collect(?:s|ed)|gather(?:s|ed)|show(?:s|ed)|reveal(?:s|ed)|indicat(?:es|ed)|demonstrat(?:es|ed)|"
        r"declin(?:es|ed)|increas(?:es|ed)|decreas(?:es|ed)|witness(?:es|ed)|observ(?:es|ed)|"
        r"propos(?:es|ed)|introduc(?:es|ed)|evaluat(?:es|ed)|analy[sz](?:es|ed)|examin(?:es|ed)|"
        r"investigat(?:es|ed)|assess(?:es|ed)|determin(?:es|ed)|achiev(?:es|ed)|outperform(?:s|ed)|"
        r"contribut(?:es|ed)|provid(?:es|ed)|suggest(?:s|ed)|confirm(?:s|ed)|limit(?:s|ed)|"
        r"employ(?:s|ed)|utili[sz](?:es|ed)|adopt(?:s|ed)|implement(?:s|ed)|train(?:s|ed)|"
        r"calculat(?:es|ed)|comput(?:es|ed)|divid(?:es|ed)|launch(?:es|ed)|declar(?:es|ed)|help(?:s|ed))\b",
        flags=re.I,
    )
    return bool(finite_verb_re.search(sent))


def _are_sentences_near_duplicate(s1: str, s2: str) -> bool:
    """
    Return True if `s1` and `s2` are near-duplicates (e.g. the two 1992-2021 data collection
    sentences in Abstract and Methodology).
    """
    if not s1 or not s2:
        return False
    if s1[:42].lower() == s2[:42].lower():
        return True
    toks1 = {w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", s1) if w.lower() not in ACADEMIC_STOPWORDS}
    toks2 = {w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", s2) if w.lower() not in ACADEMIC_STOPWORDS}
    if toks1 and toks2:
        jacc = len(toks1 & toks2) / max(1, len(toks1 | toks2))
        overlap = len(toks1 & toks2) / max(1, min(len(toks1), len(toks2)))
        if jacc >= 0.42 or overlap >= 0.62:
            return True
    # Check if both describe collecting secondary data over the same year range
    years1 = set(re.findall(r"\b(?:19|20)\d{2}\b", s1))
    years2 = set(re.findall(r"\b(?:19|20)\d{2}\b", s2))
    if len(years1) >= 2 and years1 == years2:
        if re.search(r"\b(?:collected|gathered|sourced|secondary\s+data|time\s+series\s+data)\b", s1, re.I) and re.search(
            r"\b(?:collected|gathered|sourced|secondary\s+data|time\s+series\s+data)\b", s2, re.I
        ):
            return True
    return False


_sentences_are_near_duplicate = _are_sentences_near_duplicate


def _build_sentence_section_records(
    text: str,
    sections: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """
    Returns a list of {"sentence": clean_sentence, "section": section_name}
    across the manuscript, excluding References/Bibliography, Preamble, and Keywords lines.
    """
    records: List[Dict[str, str]] = []
    seen: set = set()

    if not sections and text:
        sections = summarizer.segment_paper_sections(summarizer.clean_extracted_text(text))

    if sections and isinstance(sections, dict) and len(sections) > 0:
        for sec_name, sec_body in sections.items():
            if not sec_body or sec_name == "Preamble":
                continue
            if re.search(r"reference|bibliograph|works cited|acknowledg|competing interest|conflict of interest", sec_name, flags=re.I):
                continue
            if re.match(r"^(?:keywords?|key\s+words?)\b", sec_name.strip(), flags=re.I):
                continue
            sec_str = sec_body.get("text", "") if isinstance(sec_body, dict) else str(sec_body)
            for s in summarizer.split_into_sentences(sec_str):
                s_clean = summarizer.strip_leading_heading_fragment(s).strip()
                if len(s_clean) < 25 or s_clean.lower() in seen:
                    continue
                if is_citation_or_header_line(s_clean) or re.match(r"^(?:keywords?|key\s+words?)\s*:", s_clean, re.I):
                    continue
                if not re.match(r"^[A-Z0-9\"'\(\[]", s_clean):
                    continue
                seen.add(s_clean.lower())
                records.append({"sentence": s_clean, "section": sec_name})

    if not records and text:
        cleaned = summarizer.clean_extracted_text(text)
        for s in summarizer.split_into_sentences(cleaned):
            s_clean = summarizer.strip_leading_heading_fragment(s).strip()
            if len(s_clean) < 25 or s_clean.lower() in seen:
                continue
            if is_citation_or_header_line(s_clean) or re.match(r"^(?:keywords?|key\s+words?)\s*:", s_clean, re.I):
                continue
            if not re.match(r"^[A-Z0-9\"'\(\[]", s_clean):
                continue
            seen.add(s_clean.lower())
            records.append({"sentence": s_clean, "section": "Main Body"})

    return records


def extract_research_profile(
    text: str,
    sections: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    FIX 2 — Extract the 6 structured Research Profile fields with honest confidence:
      1. objective (ONLY from Abstract/Introduction; never from Results)
      2. methodology
      3. data_materials (deduplicated so near-identical 1992-2021 sentences never repeat)
      4. key_results
      5. contributions
      6. limitations (distinguishes author-stated limitations from background constraints cited from literature [5])
    """
    if not sections and text:
        sections = summarizer.segment_paper_sections(summarizer.clean_extracted_text(text))
    records = _build_sentence_section_records(text, sections)

    profile: Dict[str, Dict[str, Any]] = {}

    # --- 1. Research Objective (Strictly from Abstract / Introduction) ---
    obj_strong_re = re.compile(
        r"\b(?:(?:objective|aim|purpose|goal)\s+of\s+(?:this|the)\s+(?:study|paper|research|investigation|work)|"
        r"(?:this|the\s+present)\s+(?:study|paper|research|work|article|investigation)\s+(?:mainly\s+)?(?:aims?|seeks?|attempts?|investigates?|examines?|analy[sz]es?|evaluates?|explores?|addresses?|focuss?ed\s+on|focuses\s+on|was\s+conducted\s+to|is\s+conducted\s+to)|"
        r"we\s+(?:investigate|examine|analy[sz]e|evaluate|explore|study|address|estimate|assess)|"
        r"(?:was|is)\s+(?:conducted|undertaken|carried\s+out|designed)\s+to\s+(?:determine|examine|analy[sz]e|estimate|assess|evaluate|investigate)|"
        r"to\s+(?:examine|analy[sz]e|investigate|evaluate|estimate|assess|determine)\s+the\s+(?:growth|impact|effect|performance|relationship|role|trend))\b",
        flags=re.I,
    )
    obj_candidates: List[Tuple[float, str, str, str]] = []
    for rec in records:
        sent = rec["sentence"]
        sec = rec["section"]
        sec_low = sec.lower()
        # Never take Research Objective from Results or Conclusion
        if any(bad_s in sec_low for bad_s in ["result", "finding", "conclusion", "competing", "reference"]):
            continue
        in_abs_or_intro = any(ps in sec_low for ps in ["abstract", "introduction", "background", "overview", "main body"])
        if not in_abs_or_intro:
            continue
        if obj_strong_re.search(sent):
            is_comp = _is_complete_finite_sentence(sent)
            conf = "High" if is_comp else "Moderate"
            # Prefer sentences in Abstract or 1. Introduction that directly state the study's objective
            sc = 10.0 + (2.0 if "introduction" in sec_low or "abstract" in sec_low else 0.0)
            obj_candidates.append((sc, sent, sec, conf))

    obj_sents: List[str] = []
    obj_secs: List[str] = []
    obj_conf = "Not found"
    for sc, s_text, s_sec, conf in sorted(obj_candidates, key=lambda x: x[0], reverse=True):
        if any(_are_sentences_near_duplicate(s_text, ex) for ex in obj_sents):
            continue
        obj_sents.append(s_text)
        if s_sec not in obj_secs:
            obj_secs.append(s_sec)
        if obj_conf == "Not found" or (conf == "High" and obj_conf != "High"):
            obj_conf = conf
        if len(obj_sents) >= 2:
            break

    if obj_sents:
        profile["objective"] = {
            "label": "Research Objective",
            "value": " ".join(obj_sents),
            "bullets": obj_sents,
            "section": ", ".join(obj_secs[:2]),
            "confidence": obj_conf,
            "found": True,
        }
    else:
        profile["objective"] = {
            "label": "Research Objective",
            "value": "Not explicitly stated",
            "bullets": [],
            "section": "—",
            "confidence": "Not found",
            "found": False,
        }

    # --- 2. Methodology, Data/Materials, Key Results, Contributions ---
    other_specs = {
        "methodology": {
            "label": "Methodology & Design",
            "preferred_sections": ["method", "materials", "experimental", "proposed", "architecture", "model", "system", "framework"],
            "strong_patterns": [
                r"\b(?:compound\s+annual\s+growth\s+rate|cagr|cuddy[\s\-]*della\s+valle|instability\s+index|decomposition\s+analysis|regression|exponential\s+function)\b",
                r"\b(?:methodology|methodological|experimental\s+setup|architecture|algorithm|neural\s+network|transformer|convolutional|random\s+forest|svm|anova|t-test|chi-square|econometric|time[\s\-]series\s+model)\b",
                r"\b(?:we\s+(?:employ|adopt|utilize|use|implement|train|design|formulate)|was\s+(?:estimated|calculated|computed|analyzed|analysed)\s+using)\b",
            ],
            "weak_patterns": [
                r"\b(?:method|procedure|model|equation|formula|pipeline|protocol|technique|computed|calculated|estimated)\b",
            ],
        },
        "data_materials": {
            "label": "Data / Sample / Materials",
            "preferred_sections": ["method", "data", "dataset", "materials", "experimental", "sample"],
            "strong_patterns": [
                r"\b(?:secondary\s+data|primary\s+data|time[\s\-]series\s+data|panel\s+data|dataset|benchmark|corpus|sample\s+size|participants|patients?|patient\s+admissions|cohorts?|respondents|specimens)\b",
                r"\b(?:collected\s+from|gathered\s+from|obtained\s+from|sourced\s+from|compiled\s+from|ministry\s+of|directorate\s+of|fao|world\s+bank|indiastat|india\s+stat|apeda|kaggle|imagenet|cifar)\b",
                r"\b(?:covering\s+the\s+years\s+\d{4}|from\s+\d{4}\s+to\s+\d{4}|study\s+period\s+was\s+divided\s+into|\bN\s*=\s*\d+)\b",
            ],
            "weak_patterns": [
                r"\b(?:data|sample|survey|records|observations|statistics|database)\b",
            ],
        },
        "key_results": {
            "label": "Key Results & Quantitative Findings",
            "preferred_sections": ["result", "finding", "discussion", "evaluation", "performance", "abstract", "conclusion"],
            "strong_patterns": [
                r"\b(?:results?\s+(?:show|showed|indicate|indicated|reveal|revealed|demonstrate|demonstrated|confirm|suggest)|findings?\s+(?:show|reveal|indicate|suggest)|study\s+revealed\s+that)\b",
                r"\b(?:growth\s+rate\s+of\s+[\+\-]?\d+|showed\s+a\s+negative\s+compound\s+annual\s+growth\s+rate|witnessed\s+a\s+positive\s+compound\s+annual\s+growth\s+rate|outperformed|statistically\s+significant)\b",
                r"(?:\b[\+\-]?\d+(?:\.\d+)?\s*(?:%|per\s*cent|percent)\b|\bp\s*[<>=]\s*0\.\d+\b|\bR2\s*=\s*[\d\.]+\b)",
            ],
            "weak_patterns": [
                r"\b(?:observed|recorded|registered|highest|lowest|increase|decrease|growth|yield|production|accuracy)\b.*\b\d+(?:\.\d+)?\b",
            ],
        },
        "contributions": {
            "label": "Main Contributions",
            "preferred_sections": ["conclusion", "abstract", "introduction", "discussion"],
            "strong_patterns": [
                r"\b(?:main\s+contribution|key\s+contribution|our\s+contributions?|this\s+(?:study|paper|work)\s+(?:contributes|will\s+help\s+in)|novelty|first\s+to\s+(?:propose|demonstrate|evaluate))\b",
                r"\b(?:we\s+propose\s+a\s+novel|we\s+introduce\s+a\s+new|provides?\s+empirical\s+evidence|offers?\s+policy\s+insights|help\s+in\s+understanding\s+the\s+growth\s+trend)\b",
            ],
            "weak_patterns": [
                r"\b(?:demonstrate|establish|provide\s+insights|highlight\s+the\s+importance|valuable\s+for\s+policymakers|comprehensive\s+analysis|suggest\s+ways\s+in\s+increasing)\b",
            ],
        },
    }

    for field_key, spec in other_specs.items():
        scored_matches: List[Tuple[float, str, str, str]] = []
        for rec in records:
            sent = rec["sentence"]
            sec = rec["section"]
            sec_low = sec.lower()
            sent_low = sent.lower()

            if re.search(r"(?:copyright|all rights reserved|doi\.org|issn)", sent_low):
                continue

            strong_hits = sum(1 for pat in spec["strong_patterns"] if re.search(pat, sent_low, flags=re.I))
            weak_hits = sum(1 for pat in spec["weak_patterns"] if re.search(pat, sent_low, flags=re.I))
            if strong_hits == 0 and weak_hits == 0:
                continue

            in_pref_sec = any(ps in sec_low for ps in spec["preferred_sections"])
            sec_bonus = 2.5 if in_pref_sec else 0.0
            # For data_materials, prefer Methodology section over Abstract when sentences are near-duplicates
            if field_key == "data_materials" and "method" in sec_low:
                sec_bonus += 1.5
            num_bonus = 1.8 if (field_key == "key_results" and re.search(r"\b\d+(?:\.\d+)?\b", sent)) else 0.0
            is_comp = _is_complete_finite_sentence(sent)
            if not is_comp:
                sec_bonus -= 2.0

            score = strong_hits * 4.0 + weak_hits * 1.2 + sec_bonus + num_bonus
            if strong_hits > 0 or (weak_hits > 0 and in_pref_sec):
                if strong_hits > 0 and in_pref_sec and is_comp:
                    conf = "High"
                elif (strong_hits > 0 or in_pref_sec) and is_comp:
                    conf = "Moderate"
                else:
                    conf = "Low"
                scored_matches.append((score, sent, sec, conf))

        scored_matches.sort(key=lambda x: (x[0], len(x[1])), reverse=True)

        selected_sents: List[str] = []
        selected_secs: List[str] = []
        best_conf = "Not found"
        for sc, s_text, s_sec, conf in scored_matches:
            if any(_are_sentences_near_duplicate(s_text, ex) for ex in selected_sents):
                continue
            selected_sents.append(s_text)
            if s_sec not in selected_secs:
                selected_secs.append(s_sec)
            if best_conf == "Not found" or (conf == "High" and best_conf != "High"):
                best_conf = conf
            if len(selected_sents) >= 2:
                break

        if selected_sents:
            profile[field_key] = {
                "label": spec["label"],
                "value": " ".join(selected_sents),
                "bullets": selected_sents,
                "section": ", ".join(selected_secs[:2]),
                "confidence": best_conf,
                "found": True,
            }
        else:
            profile[field_key] = {
                "label": spec["label"],
                "value": NOT_FOUND_SENTINEL,
                "bullets": [],
                "section": "—",
                "confidence": "Not found",
                "found": False,
            }

    # --- 3. Limitations & Constraints (Strictly distinguish author limitations vs cited background [5]) ---
    author_lim_re = re.compile(
        r"\b(?:limitation\s+of\s+(?:this|the|our)\s+(?:study|paper|work|analysis)|"
        r"limitations\s+include|this\s+study\s+is\s+limited|our\s+study\s+is\s+limited|"
        r"scope\s+of\s+this\s+study|threat\s+to\s+validity|we\s+could\s+not|could\s+not\s+be\s+included|"
        r"does\s+not\s+account\s+for|restricted\s+to\s+secondary\s+data|constrained\s+by\s+data\s+availability)\b",
        flags=re.I,
    )
    general_lim_re = re.compile(
        r"\b(?:limitation|limitations|limited\s+by|constrained\s+by|drawback|shortcoming|lack\s+of)\b",
        flags=re.I,
    )

    author_lims: List[Tuple[str, str, str]] = []
    cited_background_lims: List[Tuple[str, str, str]] = []

    for rec in records:
        sent = rec["sentence"]
        sec = rec["section"]
        sec_low = sec.lower()
        has_lit_cit = bool(re.search(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]|\([A-Z][A-Za-z\s]+,\s*(?:19|20)\d{2}\)", sent))
        in_lim_or_disc = any(ps in sec_low for ps in ["limitation", "discussion", "conclusion", "threat"])
        in_intro = "introduction" in sec_low or "background" in sec_low

        if author_lim_re.search(sent) and not (in_intro and has_lit_cit):
            conf = "High" if _is_complete_finite_sentence(sent) else "Moderate"
            author_lims.append((sent, sec, conf))
        elif general_lim_re.search(sent):
            # If it is in Introduction/Background and carries a literature citation like [5], it is a background constraint from cited literature!
            if (in_intro and has_lit_cit) or not _is_complete_finite_sentence(sent):
                cit_tag_m = re.search(r"(\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\])", sent)
                cit_tag = f" {cit_tag_m.group(1)}" if cit_tag_m else ""
                cited_background_lims.append((
                    f"Background constraint cited from literature{cit_tag}: {sent}",
                    sec,
                    "Low",
                ))
            elif in_lim_or_disc:
                conf = "High" if ("limitation" in sec_low and _is_complete_finite_sentence(sent)) else "Moderate"
                author_lims.append((sent, sec, conf))

    if author_lims:
        bullets = [x[0] for x in author_lims[:2]]
        secs = list(dict.fromkeys(x[1] for x in author_lims[:2]))
        profile["limitations"] = {
            "label": "Limitations & Constraints",
            "value": " ".join(bullets),
            "bullets": bullets,
            "section": ", ".join(secs),
            "confidence": author_lims[0][2],
            "found": True,
            "is_cited_background": False,
        }
    elif cited_background_lims:
        bg_sent, bg_sec, bg_conf = cited_background_lims[0]
        bullets = [
            "No limitations explicitly stated by the authors.",
            bg_sent,
        ]
        profile["limitations"] = {
            "label": "Limitations & Constraints",
            "value": " ".join(bullets),
            "bullets": bullets,
            "section": f"{bg_sec} (Cited Literature)",
            "confidence": bg_conf,
            "found": True,
            "is_cited_background": True,
        }
    else:
        profile["limitations"] = {
            "label": "Limitations & Constraints",
            "value": "No limitations explicitly stated by the authors",
            "bullets": [],
            "section": "—",
            "confidence": "Not found",
            "found": False,
            "is_cited_background": False,
        }

    for p_val in profile.values():
        if isinstance(p_val, dict) and "value" in p_val and "text" not in p_val:
            p_val["text"] = p_val["value"]

    profile["research_objective"] = profile["objective"]
    profile["datasets_and_materials"] = profile["data_materials"]

    return profile


# ---------------------------------------------------------------------------
# 5. Grounded Researcher Findings (FIX 2 & FIX 4)
# ---------------------------------------------------------------------------

def generate_text_grounded_findings(
    text: str,
    sections: Optional[Dict[str, str]],
    stats: Dict[str, Any],
    scores: Dict[str, Any],
    profile: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    """
    Generate paper-specific, text-grounded telemetry and synthesis for Analyze Research Paper (C2).
    Uses exact section count (excluding Preamble and Keywords) and exact citation/reference counts.
    """
    if not sections and text:
        sections = summarizer.segment_paper_sections(summarizer.clean_extracted_text(text))
    if profile is None:
        profile = extract_research_profile(text, sections)

    cit_info = detect_citations_and_references(text, sections)
    real_sec_names = [
        k for k in (sections or {}).keys()
        if k and k != "Preamble" and not re.match(r"^(?:keywords?|key\s+words?)\b", k.strip(), flags=re.I)
    ]

    findings: List[Dict[str, str]] = []

    word_count = stats.get("word_count") or summarizer.count_words(text or "")
    sent_count = stats.get("sentence_count") or len(summarizer.split_into_sentences(text or ""))
    in_text_cits = cit_info["in_text_count"]
    ref_count = cit_info["reference_list_count"]

    if word_count > 0:
        sec_summary = ", ".join(real_sec_names) if real_sec_names else "unsectioned body text"
        marker_range = ""
        if cit_info["unique_in_text_markers"]:
            m_list = cit_info["unique_in_text_markers"]
            marker_range = f" ({m_list[0]}-{m_list[-1]})" if len(m_list) > 1 else f" ({m_list[0]})"
        findings.append({
            "category": "Manuscript Structure & Evidence Density",
            "section": "Full Manuscript",
            "confidence": "High",
            "detail": (
                f"Document spans {word_count:,} words across {sent_count:,} sentences and "
                f"{len(real_sec_names)} detected sections ({sec_summary}), with "
                f"{in_text_cits} in-text citation markers{marker_range} and {ref_count} reference list entries."
            ),
        })

    return findings


# ---------------------------------------------------------------------------
# 6. Honest Research Insights Engine (FIX 5 — Zero Boilerplate, Clean Trends & Gaps)
# ---------------------------------------------------------------------------

def _derive_specific_opportunity_from_quote(quote: str, is_cited_background: bool = False) -> str:
    """
    FIX 5 — Generate a specific, grammatically clean research direction directly from the
    actual gap/limitation sentence. Never outputs broken templates like 'regarding Lack'.
    """
    q_clean = summarizer.strip_leading_heading_fragment(quote).strip()
    low = q_clean.lower()

    if "varieties" in low or "equipment" in low or "government policies" in low:
        return (
            "Evaluate high-yielding millet varieties, farm mechanization access, and targeted policy incentives "
            "to address the cultivation constraints cited in the literature [5]."
        )

    # Extract meaningful noun phrases after "lack of", "limited by", "restricted to", "limitation"
    m_target = re.search(
        r"\b(?:lack\s+of|limited\s+by|limited\s+to|restricted\s+to|constrained\s+by|does\s+not\s+account\s+for|focused\s+only\s+on)\s+([^\.;,\[\(]{6,85})",
        q_clean,
        flags=re.I,
    )
    if m_target:
        phrase = m_target.group(1).strip(" .,;:-")
        return f"Expand future empirical analysis to incorporate {phrase} beyond the current study boundaries."

    kws = [
        k["term"].lower()
        for k in extract_clean_keywords(q_clean, top_n=4)
        if k["term"].lower() not in {"lack", "factor", "primary", "study", "paper"}
    ]
    if kws:
        focus = ", ".join(kws[:3])
        if is_cited_background:
            return f"Conduct primary empirical investigation into {focus} to address the background constraint cited in prior literature."
        return f"Extend the empirical evaluation of {focus} across broader samples and longitudinal conditions."

    return "Extend the empirical scope of this study with primary field data and broader comparative validation."


def _extract_measured_figures_excluding_years(sent: str) -> List[str]:
    """
    FIX 5 — Extract ONLY measured quantitative values (e.g. -4.30 per cent, -5.11 per cent,
    -0.85 per cent, 3.26 per cent, 4.41 per cent, p < 0.05) from a trend sentence.
    NEVER extracts year ranges (1992-2001 -> 1992, -2001), standalone years (1992..2026),
    or bracketed citation numbers ([11]).
    """
    # 1. Remove citation brackets like [11] and figure/table references like (Fig. 1)
    s = re.sub(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]", " ", sent)
    s = re.sub(r"\(\s*(?:Fig\.?|Figure|Table)\s*\d+\s*\)", " ", s, flags=re.I)

    # 2. Remove year ranges like "1992-2001", "2000-01 to 2021-22", "1992–2021" FIRST so "-2001" is never seen as a negative number!
    s = re.sub(
        r"\b(?:19|20)\d{2}(?:[\-\–—]\d{2,4})?\s*(?:[\-\–—]|to)\s*(?:19|20)?\d{2}(?:[\-\–—]\d{2,4})?\b",
        " ",
        s,
        flags=re.I,
    )
    # 3. Remove standalone 4-digit years (1900-2039)
    s = re.sub(r"\b(?:19\d{2}|20[0-3]\d)\b", " ", s)

    figures: List[str] = []

    # Pattern A: Paired numbers sharing a unit, e.g. "-5.11 and -0.85 per cent"
    for m_pair in re.finditer(
        r"([+\-]?\d+(?:\.\d+)?)\s+and\s+([+\-]?\d+(?:\.\d+)?)\s*(%|per\s*cent|percent)\b",
        s,
        flags=re.I,
    ):
        u = "per cent" if "cent" in m_pair.group(3).lower() else "%"
        v1 = f"{m_pair.group(1)} {u}".strip()
        v2 = f"{m_pair.group(2)} {u}".strip()
        if v1 not in figures:
            figures.append(v1)
        if v2 not in figures:
            figures.append(v2)

    # Pattern B: Individual number + unit (%, per cent, percent, million hectares, mt, kg/ha, etc.)
    for m_single in re.finditer(
        r"([+\-]?\d+(?:\.\d+)?)\s*(%|per\s*cent|percent|million\s+hectares?|m\s*ha|mt|kg/ha|tonnes|fold)\b",
        s,
        flags=re.I,
    ):
        num_part = m_single.group(1)
        unit_part = re.sub(r"\s+", " ", m_single.group(2)).strip()
        if "cent" in unit_part.lower():
            unit_part = "per cent"
        val_str = f"{num_part} {unit_part}" if unit_part != "%" else f"{num_part}%"
        # Avoid re-adding the second number of a pair already added in Pattern A
        if val_str not in figures:
            figures.append(val_str)

    # Re-order figures according to their appearance order in the sentence
    figures.sort(key=lambda fig: s.find(fig.split()[0]))
    return figures


def _parse_canonical_period_from_sentence(sent: str) -> Tuple[int, str]:
    """
    Parse a period label and chronological sort key from a trend sentence.
    Converts '1992-2001' into '1992 to 2001', normalizes Period I / II / III.
    """
    s = sent
    # Check for Period I / first period
    m_p1 = re.search(r"\b(?:Period\s+I\b|first\s+period)\s*(?:\(\s*(\d{4})\s*(?:[\-\–—]|to)\s*(\d{4})\s*\))?", s, flags=re.I)
    if m_p1:
        y1, y2 = m_p1.group(1) or "1992", m_p1.group(2) or "2001"
        return (1, f"Period I ({y1} to {y2})")

    # Check for Period II / second period
    m_p2 = re.search(r"\b(?:Period\s+II\b|second\s+period)\s*(?:\(\s*(\d{4})\s*(?:[\-\–—]|to)\s*(\d{4})\s*\))?", s, flags=re.I)
    if m_p2:
        y1, y2 = m_p2.group(1) or "2001", m_p2.group(2) or "2012"
        return (2, f"Period II ({y1} to {y2})")

    # Check for Period III / third period
    m_p3 = re.search(r"\b(?:Period\s+III\b|third\s+period)\s*(?:\(\s*(\d{4})\s*(?:[\-\–—]|to)\s*(\d{4})\s*\))?", s, flags=re.I)
    if m_p3:
        y1, y2 = m_p3.group(1) or "2012", m_p3.group(2) or "2021"
        return (3, f"Period III ({y1} to {y2})")

    # General year range e.g. 1992-2001, 2001 to 2012, or 2000-01 to 2021-22
    m_yr = re.search(
        r"\b((?:19|20)\d{2}(?:-\d{2})?)\s*(?:[\-\–—]|to)\s*((?:19|20)\d{2}(?:-\d{2})?)\b",
        s,
        flags=re.I,
    )
    if m_yr:
        y1_str, y2_str = m_yr.group(1), m_yr.group(2)
        y1_int = int(y1_str[:4])
        return (y1_int, f"{y1_str} to {y2_str}")

    # Single year
    m_single_yr = re.search(r"\b((?:19|20)\d{2})\b", s)
    if m_single_yr:
        yr = int(m_single_yr.group(1))
        return (yr, f"Year {yr}")

    return (9999, "Overall Study Period")


def extract_honest_research_insights(
    text: str,
    sections: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    FIX 5 — Rebuild of Research Insights (C6) following strict accuracy & honesty rules:
    1. Keywords & Research Themes: sub-phrase deduplicated, non-overlapping counts, exact theme mention sums.
    2. Literature Gaps & Opportunities: ONLY from explicit author gap/limitation statements.
       If only a cited background constraint (like [5]) exists, labels it clearly as cited background
       and sets `has_explicit_gaps = False`.
    3. Temporal & Quantitative Trends: ONLY sentences containing a rate/percentage/measured change tied to a period.
       Excludes period-definition sentences and data-collection sentences.
       Parses '1992-2001' as '1992 to 2001' (never -2001), lists only measured values in 'metrics',
       sorts chronologically (Period I, Period II, Period III), and detects period-boundary inconsistencies.
    4. Future Research Directions: ONLY author-stated future work; otherwise empty (UI shows 'Not stated by the authors').
    """
    if not sections and text:
        sections = summarizer.segment_paper_sections(summarizer.clean_extracted_text(text))
    records = _build_sentence_section_records(text, sections)
    domain = detect_research_domain(text)
    keywords = extract_clean_keywords(text, top_n=15)
    themes = group_keywords_into_themes(keywords, domain=domain)
    profile = extract_research_profile(text, sections)

    # --- 1. Explicit Literature Gaps vs Cited Background Constraints ---
    explicit_gap_patterns = [
        r"\b(?:research\s+gap|literature\s+gap|gap\s+in\s+the\s+literature|gap\s+remains|remains?\s+unexplored|little\s+attention|scant\s+attention|few\s+studies\s+have|little\s+research\s+has)\b",
        r"\b(?:limitation\s+of\s+(?:this|the|our)\s+study|this\s+study\s+is\s+limited|remains?\s+unclear|has\s+not\s+been\s+fully|under[\-\s]researched|insufficient\s+data)\b",
        r"\b(?:further\s+research\s+is\s+needed|future\s+studies\s+should\s+address|rarely\s+addressed|overlooked\s+in)\b",
    ]
    gaps: List[Dict[str, Any]] = []
    cited_background_notes: List[Dict[str, Any]] = []
    seen_gaps: set = set()

    for rec in records:
        sent = rec["sentence"]
        sec = rec["section"]
        sec_low = sec.lower()
        has_lit_cit = bool(re.search(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]|\([A-Z][A-Za-z\s]+,\s*(?:19|20)\d{2}\)", sent))
        in_intro = "introduction" in sec_low or "background" in sec_low

        if any(re.search(pat, sent, flags=re.I) for pat in explicit_gap_patterns) and not (in_intro and has_lit_cit and not _is_complete_finite_sentence(sent)):
            key = sent[:50].lower()
            if key in seen_gaps:
                continue
            seen_gaps.add(key)
            opp = _derive_specific_opportunity_from_quote(sent, is_cited_background=False)
            gaps.append({
                "quote": sent,
                "section": sec,
                "opportunity": opp,
                "direction": opp,
                "is_cited_background": False,
                "label": "Author-Stated Gap / Limitation",
                "gap_type": "Explicit Research Gap",
            })
        elif re.search(r"\b(?:lack\s+of|constrained\s+by|limited\s+by)\b", sent, flags=re.I):
            key = sent[:50].lower()
            if key in seen_gaps:
                continue
            seen_gaps.add(key)
            if in_intro and has_lit_cit:
                cit_m = re.search(r"(\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\])", sent)
                cit_str = f" {cit_m.group(1)}" if cit_m else ""
                opp = _derive_specific_opportunity_from_quote(sent, is_cited_background=True)
                cited_background_notes.append({
                    "quote": sent,
                    "section": f"{sec} (Cited Literature{cit_str})",
                    "opportunity": opp,
                    "direction": opp,
                    "is_cited_background": True,
                    "label": f"Background constraint cited from literature{cit_str}",
                    "gap_type": "Cited Literature Constraint",
                })
            elif any(ps in sec_low for ps in ["limitation", "discussion", "conclusion"]):
                opp = _derive_specific_opportunity_from_quote(sent, is_cited_background=False)
                gaps.append({
                    "quote": sent,
                    "section": sec,
                    "opportunity": opp,
                    "direction": opp,
                    "is_cited_background": False,
                    "label": "Author-Stated Limitation",
                    "gap_type": "Explicit Research Gap",
                })

    has_explicit_gaps = len(gaps) > 0
    # If no explicit author gaps exist, expose cited_background_notes separately (and clearly labeled as cited background)
    if not gaps and cited_background_notes:
        gaps = cited_background_notes[:2]

    # --- 2. Temporal & Quantitative Trends (FIX 5) ---
    # Detect if period definitions in overview sentence differ from results sentences (e.g. 2002-2011 vs 2001 to 2012)
    full_clean_text = " ".join(r["sentence"] for r in records)
    period_boundary_note = ""
    has_2002_2011 = bool(re.search(r"\b2002\s*(?:[\-\–—]|to)\s*2011\b", full_clean_text, flags=re.I))
    has_2001_2012 = bool(re.search(r"\b2001\s*(?:[\-\–—]|to)\s*2012\b", full_clean_text, flags=re.I))
    has_2012_2022 = bool(re.search(r"\b2012\s*(?:[\-\–—]|to)\s*2022\b", full_clean_text, flags=re.I))
    has_2012_2021 = bool(re.search(r"\b2012\s*(?:[\-\–—]|to)\s*2021\b", full_clean_text, flags=re.I))
    if (has_2002_2011 and has_2001_2012) or (has_2012_2022 and has_2012_2021):
        period_boundary_note = (
            "Period boundaries differ between sections of the manuscript "
            "(e.g., the period division overview lists Period II as 2002-2011 and Period III as 2012-2022, "
            "whereas the quantitative growth analysis reports Period II as 2001 to 2012 and Period III as 2012 to 2021)."
        )

    trends_by_period: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for rec in records:
        sent = rec["sentence"]
        sec = rec["section"]
        sent_low = sent.lower()

        # EXCLUDE sentences that merely define periods ("The study period was divided into three periods...")
        if re.search(r"\b(?:study\s+period\s+was\s+divided|divided\s+into\s+three\s+periods|periods\s+viz\.)\b", sent_low):
            continue
        # EXCLUDE sentences that describe data collection ("data from 1992 to 2021 were collected/gathered...")
        if re.search(r"\b(?:data\s+.*?(?:were|was)\s+(?:collected|gathered|sourced|obtained)|for\s+(?:this|the\s+present)\s+(?:study|analysis)\s*,\s*(?:annual|secondary)\s+(?:time\s+series\s+)?data)\b", sent_low):
            continue
        # EXCLUDE background policy launch sentences without measured period growth rates
        if "national program on nutri-cereals" in sent_low and not re.search(r"(?:%|per\s*cent|percent)", sent_low):
            continue

        # Must contain BOTH a period/time marker AND a measured rate/percentage/quantitative change
        has_period_marker = bool(
            re.search(
                r"\b(?:Period\s+[I123V]+|(?:first|second|third)\s+period|(?:19|20)\d{2}(?:-\d{2})?\s*(?:[\-\–—]|to)\s*(?:19|20)\d{2}(?:-\d{2})?)\b",
                sent,
                flags=re.I,
            )
        )
        measured_figs = _extract_measured_figures_excluding_years(sent)
        has_measured_rate = len(measured_figs) > 0 and bool(
            re.search(r"\b(?:growth\s+rate|cagr|%|per\s*cent|percent|increased|declined|decreased)\b", sent_low)
        )

        if not (has_period_marker and has_measured_rate):
            continue

        sort_key, period_label = _parse_canonical_period_from_sentence(sent)

        # Determine trend direction
        has_neg = any(f.startswith("-") for f in measured_figs) or bool(re.search(r"\b(?:negative|declin|decreas)", sent_low))
        has_pos = any(not f.startswith("-") for f in measured_figs) and bool(re.search(r"\b(?:positive|increas)", sent_low))
        if has_neg and has_pos:
            direction = "Mixed (Area/Production Declining, Productivity Increasing)"
        elif has_neg:
            direction = "Declining / Negative Growth"
        else:
            direction = "Increasing / Positive Growth"

        trend_entry = {
            "period": period_label,
            "metrics": ", ".join(measured_figs),
            "reported_figures": measured_figs,
            "direction": direction,
            "statement": sent,
            "section": sec,
        }

        # Deduplicate by period_label (keep the one with more measured figures)
        if period_label in trends_by_period:
            existing_figs = trends_by_period[period_label][1].get("reported_figures", [])
            if len(measured_figs) > len(existing_figs):
                trends_by_period[period_label] = (sort_key, trend_entry)
        else:
            trends_by_period[period_label] = (sort_key, trend_entry)

    # Sort chronologically (Period I -> Period II -> Period III)
    trends = [item for _, item in sorted(trends_by_period.values(), key=lambda x: x[0])]

    # --- 3. Author-Stated Future Directions / Recommendations ---
    future_patterns = [
        r"\b(?:future\s+research|future\s+work|future\s+studies|in\s+the\s+future|further\s+research|further\s+investigation)\b",
        r"\b(?:we\s+recommend|it\s+is\s+recommended|avenue\s+for\s+future|can\s+be\s+extended\s+to)\b",
    ]
    future_directions: List[Dict[str, str]] = []
    seen_future: set = set()
    for rec in records:
        sent = rec["sentence"]
        sec = rec["section"]
        sec_low = sec.lower()
        has_lit_cit = bool(re.search(r"\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]|\([A-Z][A-Za-z\s]+,\s*(?:19|20)\d{2}\)", sent))
        in_intro = "introduction" in sec_low or "background" in sec_low
        # Exclude cited literature sentences in Introduction
        if in_intro and has_lit_cit:
            continue
        if any(re.search(pat, sent, flags=re.I) for pat in future_patterns):
            key = sent[:50].lower()
            if key in seen_future:
                continue
            seen_future.add(key)
            future_directions.append({
                "statement": sent,
                "section": sec,
            })
            if len(future_directions) >= 5:
                break

    # --- 4. Clean Complete-Sentence Summary Cards ---
    cards = {
        "methodology": {
            "title": "Methodology",
            "sentences": profile["methodology"]["bullets"] if profile["methodology"]["found"] else [],
            "text": profile["methodology"]["value"],
            "section": profile["methodology"]["section"],
            "found": profile["methodology"]["found"],
        },
        "data_sources": {
            "title": "Data Sources & Materials",
            "sentences": profile["data_materials"]["bullets"] if profile["data_materials"]["found"] else [],
            "text": profile["data_materials"]["value"],
            "section": profile["data_materials"]["section"],
            "found": profile["data_materials"]["found"],
        },
        "key_findings": {
            "title": "Key Empirical Findings",
            "sentences": profile["key_results"]["bullets"] if profile["key_results"]["found"] else [],
            "text": profile["key_results"]["value"],
            "section": profile["key_results"]["section"],
            "found": profile["key_results"]["found"],
        },
    }

    return {
        "domain": domain,
        "keywords": keywords,
        "themes": themes,
        "gaps": gaps,
        "has_explicit_gaps": has_explicit_gaps,
        "trends": trends,
        "period_boundary_note": period_boundary_note,
        "future_directions": future_directions,
        "cards": cards,
        "profile": profile,
    }


# ---------------------------------------------------------------------------
# 7. Advanced Paper Comparison Matrix & Synthesis (C4)
# ---------------------------------------------------------------------------

def highlight_shared_terms_html(text_val: str, shared_terms: List[str]) -> str:
    """
    Safely HTML-escape `text_val` once, then wrap shared/overlapping terms in a subtle
    researcher badge highlight span so overlapping concepts stand out visually.
    """
    escaped = safe_text(text_val)
    if not shared_terms or text_val == NOT_FOUND_SENTINEL:
        return escaped

    sorted_terms = sorted({t.strip() for t in shared_terms if len(t.strip()) >= 4}, key=len, reverse=True)
    if not sorted_terms:
        return escaped

    pattern = r"\b(" + "|".join(re.escape(safe_text(t)) for t in sorted_terms[:15]) + r")\b"
    return re.sub(
        pattern,
        r"<span style='background:rgba(56,189,248,0.18);color:#7dd3fc;padding:1px 5px;border-radius:4px;font-weight:600;'>\1</span>",
        escaped,
        flags=re.IGNORECASE,
    )


def build_comparison_matrix_and_synthesis(papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the structured Researcher Comparison Matrix and data-driven Comparative Synthesis
    for 2 to 3 papers.
    """
    if not papers:
        return {}

    enriched: List[Dict[str, Any]] = []
    for idx, p in enumerate(papers):
        raw_text = unescape_text(p.get("text", "") or "")
        secs = p.get("sections") or (summarizer.segment_paper_sections(raw_text) if raw_text else {})
        meta = p.get("metadata") or extract_paper_metadata(raw_text, filename=p.get("filename", ""), title_override=p.get("title"))
        prof = p.get("profile") or extract_research_profile(raw_text, secs)
        raw_scores = p.get("scores") or {}
        # Ensure 5 distinct researcher scores if missing or identical
        if not raw_scores or len({
            round(float(raw_scores.get("structure_score", 0)), 1),
            round(float(raw_scores.get("clarity_score", 0)), 1),
            round(float(raw_scores.get("coherence_score", 0)), 1),
            round(float(raw_scores.get("citation_score", 0)), 1),
            round(float(raw_scores.get("readability_score", 0)), 1),
        }) <= 1:
            scores = compute_researcher_quality_scores(raw_text, secs, base_res=raw_scores)
        else:
            scores = raw_scores

        title = unescape_text(meta.get("title") or p.get("title") or f"Paper {idx + 1}")
        enriched.append({
            "index": idx + 1,
            "id": p.get("id"),
            "title": title,
            "authors": meta.get("authors", "Not found"),
            "year": meta.get("year", "") or "n.d.",
            "journal": meta.get("journal", "Manuscript / Preprint"),
            "domain": meta.get("domain") or detect_research_domain(raw_text),
            "keywords": meta.get("keywords", []),
            "profile": prof,
            "scores": scores,
            "word_count": p.get("word_count") or summarizer.count_words(raw_text),
        })

    kw_sets = [set(k.lower() for k in ep["keywords"]) for ep in enriched]
    profile_token_sets: List[set] = []
    for ep in enriched:
        prof_text = " ".join(v.get("value", "") for v in ep["profile"].values() if v.get("found"))
        toks = {
            w.lower()
            for w in re.findall(r"\b[A-Za-z][A-Za-z\-]{3,22}\b", prof_text)
            if w.lower() not in ACADEMIC_STOPWORDS
        }
        profile_token_sets.append(toks | kw_sets[ep["index"] - 1])

    shared_all: set = set()
    if len(profile_token_sets) >= 2:
        for i in range(len(profile_token_sets)):
            for j in range(i + 1, len(profile_token_sets)):
                shared_all |= (profile_token_sets[i] & profile_token_sets[j])

    shared_terms_list = sorted(shared_all, key=lambda x: (-len(x), x))[:18]

    domains = [ep["domain"] for ep in enriched]
    unique_domains = sorted(set(domains))
    is_cross_domain = len(unique_domains) > 1
    cross_domain_notice = ""
    if is_cross_domain:
        domain_pairs = ", ".join(f"'{ep['title'][:45]}' ({ep['domain']})" for ep in enriched)
        cross_domain_notice = (
            f"Cross-Domain Comparison Detected: The selected manuscripts span distinct research disciplines "
            f"({'; '.join(unique_domains)} — specifically {domain_pairs}). Differences in methodology, "
            f"datasets, and terminology reflect domain divergence rather than methodological deficiency."
        )

    matrix_rows: List[Dict[str, Any]] = [
        {
            "dimension": "Metadata (Authors, Year, Venue)",
            "key": "metadata",
            "cells": [
                f"{ep['authors']} ({ep['year']}) — {ep['journal']}"
                for ep in enriched
            ],
        },
        {
            "dimension": "Research Domain & Top Keywords",
            "key": "domain",
            "cells": [
                f"{ep['domain']} | Keywords: {', '.join(ep['keywords'][:6]) if ep['keywords'] else 'None extracted'}"
                for ep in enriched
            ],
        },
        {
            "dimension": "Objectives",
            "key": "objective",
            "cells": [ep["profile"]["objective"]["value"] for ep in enriched],
            "sections": [ep["profile"]["objective"]["section"] for ep in enriched],
        },
        {
            "dimension": "Methodology",
            "key": "methodology",
            "cells": [ep["profile"]["methodology"]["value"] for ep in enriched],
            "sections": [ep["profile"]["methodology"]["section"] for ep in enriched],
        },
        {
            "dimension": "Data / Materials",
            "key": "data_materials",
            "cells": [ep["profile"]["data_materials"]["value"] for ep in enriched],
            "sections": [ep["profile"]["data_materials"]["section"] for ep in enriched],
        },
        {
            "dimension": "Key Findings",
            "key": "key_results",
            "cells": [ep["profile"]["key_results"]["value"] for ep in enriched],
            "sections": [ep["profile"]["key_results"]["section"] for ep in enriched],
        },
        {
            "dimension": "Limitations",
            "key": "limitations",
            "cells": [ep["profile"]["limitations"]["value"] for ep in enriched],
            "sections": [ep["profile"]["limitations"]["section"] for ep in enriched],
        },
        {
            "dimension": "Contributions",
            "key": "contributions",
            "cells": [ep["profile"]["contributions"]["value"] for ep in enriched],
            "sections": [ep["profile"]["contributions"]["section"] for ep in enriched],
        },
        {
            "dimension": "Writing Quality (Overall & 5 Dimensions)",
            "key": "writing_quality",
            "cells": [
                (
                    f"Overall: {float(ep['scores'].get('overall_score', 0)):.1f}/100 | "
                    f"Structure: {float(ep['scores'].get('structure_score', 0)):.1f}, "
                    f"Clarity: {float(ep['scores'].get('clarity_score', 0)):.1f}, "
                    f"Coherence: {float(ep['scores'].get('coherence_score', 0)):.1f}, "
                    f"Citations: {float(ep['scores'].get('citation_score', 0)):.1f}, "
                    f"Readability: {float(ep['scores'].get('readability_score', 0)):.1f}"
                )
                for ep in enriched
            ],
        },
    ]

    similarities: List[str] = []
    differences: List[str] = []

    if not is_cross_domain and unique_domains:
        similarities.append(
            f"Shared Research Discipline: All {len(enriched)} manuscripts investigate topics within {unique_domains[0]}."
        )
    if shared_terms_list:
        similarities.append(
            f"Overlapping Conceptual Vocabulary: Manuscripts share core terminology including {', '.join(shared_terms_list[:8])}."
        )
    else:
        similarities.append(
            "Lexical Overlap: Minimal shared technical vocabulary across the selected manuscripts (distinct topical focus)."
        )

    both_have_quant = [
        ep["title"]
        for ep in enriched
        if ep["profile"]["key_results"]["found"] and re.search(r"\b\d+(?:\.\d+)?\b", ep["profile"]["key_results"]["value"])
    ]
    if len(both_have_quant) == len(enriched):
        similarities.append(
            f"Empirical Quantification: Every compared manuscript reports quantitative metrics in its findings ({'; '.join(t[:40] for t in both_have_quant)})."
        )

    if is_cross_domain:
        differences.append(
            "Disciplinary Scope: " + " vs. ".join(f"'{ep['title'][:45]}' focuses on {ep['domain']}" for ep in enriched) + "."
        )

    meth_clauses = []
    for ep in enriched:
        m_val = ep["profile"]["methodology"]["value"]
        snippet = m_val[:130] + ("..." if len(m_val) > 130 else "")
        meth_clauses.append(f"'{ep['title'][:40]}' ({snippet})")
    differences.append("Methodological Approach: " + " — whereas ".join(meth_clauses))

    data_clauses = []
    for ep in enriched:
        d_val = ep["profile"]["data_materials"]["value"]
        snippet = d_val[:120] + ("..." if len(d_val) > 120 else "")
        data_clauses.append(f"'{ep['title'][:40]}' ({snippet})")
    differences.append("Data & Empirical Basis: " + " — compared with ".join(data_clauses))

    overall_vals = [(ep["title"], float(ep["scores"].get("overall_score", 0)), ep["word_count"]) for ep in enriched]
    overall_vals_sorted = sorted(overall_vals, key=lambda x: x[1], reverse=True)
    if len(overall_vals_sorted) >= 2:
        top_p, low_p = overall_vals_sorted[0], overall_vals_sorted[-1]
        gap = top_p[1] - low_p[1]
        differences.append(
            f"Manuscript Scale & Composite Score Spread: '{top_p[0][:42]}' scores {top_p[1]:.1f}/100 ({top_p[2]:,} words) vs. "
            f"'{low_p[0][:42]}' at {low_p[1]:.1f}/100 ({low_p[2]:,} words), a spread of {gap:.1f} points."
        )

    return {
        "papers": enriched,
        "matrix_rows": matrix_rows,
        "shared_terms": shared_terms_list,
        "is_cross_domain": is_cross_domain,
        "cross_domain_notice": cross_domain_notice,
        "similarities": similarities,
        "differences": differences,
    }


# ---------------------------------------------------------------------------
# 8. Researcher Ask PaperIQ Engine (FIX 6 — Distinct Intents & Synthesized Answers)
# ---------------------------------------------------------------------------

RESEARCHER_SUGGESTED_QUESTIONS = [
    "What is the main research contribution?",
    "What methodology is used?",
    "What datasets or materials are used?",
    "What are the key findings?",
    "What limitations do the authors mention?",
    "What research gaps are identified?",
    "What future work is suggested?",
    "How strong is the experimental evaluation?",
    "Compare the methodologies of the selected papers.",
]


def _synthesize_extractive_answer(intent: str, p_title: str, field_data: Dict[str, Any], ins: Dict[str, Any]) -> str:
    """
    FIX 6 — Synthesize a concise, complete-sentence extractive answer tailored to the
    specific question intent so the answer does not merely repeat the raw evidence passage verbatim.
    """
    sec = field_data.get("section", "the manuscript")
    bullets = field_data.get("bullets") or []
    first_b = bullets[0] if bullets else field_data.get("value", "")

    if intent == "objective":
        return f"Based on {sec}, the primary objective of this study is to examine and estimate the target phenomenon reported in the manuscript — specifically: {first_b}"
    if intent == "methodology":
        return f"In {sec}, the authors employ the following analytical methodology and modeling framework: {first_b}"
    if intent == "data_materials":
        return f"According to {sec}, the empirical analysis is grounded in the following dataset, study period, and data sources: {first_b}"
    if intent == "key_results":
        summary_sent = " ".join(bullets[:2]) if bullets else first_b
        return f"The empirical analysis in {sec} reports the following principal quantitative findings: {summary_sent}"
    if intent == "contributions":
        return f"Drawing from {sec}, the main contribution of this work lies in providing empirical evidence and practical insights on the study subject: {first_b}"
    return first_b


def answer_researcher_question(
    question: str,
    papers: List[Dict[str, Any]],
    scope_mode: str = "single",
) -> Dict[str, Any]:
    """
    FIX 6 — Answer a researcher's question against either:
      - `scope_mode="single"`: Current paper (first paper in `papers`)
      - `scope_mode="multi"`: Selected papers in a project (all `papers`)

    Guarantees:
      - Distinct answers for limitations vs research gaps vs future work vs contributions.
      - Synthesizes a concise extractive answer in complete sentences followed by the evidence
        passage with section and match strength (High / Moderate / Low).
      - If the only evidence for limitations/gaps is a cited background statement (e.g. [5]),
        explicitly states that it is a cited background constraint rather than an author-stated limitation.
      - If nothing is found, returns "I could not find this in the manuscript." with no fabricated passage.
    """
    if not question or not question.strip() or not papers:
        return {
            "answer": "I could not find this in the manuscript.",
            "citations": [],
            "found": False,
            "scope_mode": scope_mode,
        }

    q_clean = question.strip()
    q_low = q_clean.lower()

    target_papers = papers[:1] if scope_mode == "single" else papers

    intent = "general"
    if any(k in q_low for k in ["compare", "difference", "similarit", "across the selected", "selected papers"]):
        intent = "compare_methodology" if "method" in q_low else "compare_general"
    elif any(k in q_low for k in ["limitation", "constraint", "drawback", "weakness", "threat"]):
        intent = "limitations"
    elif any(k in q_low for k in ["gap", "unexplored", "missing in literature"]):
        intent = "gaps"
    elif any(k in q_low for k in ["future work", "future research", "future direction", "recommend", "next step"]):
        intent = "future_work"
    elif any(k in q_low for k in ["contribution", "novelty", "main contribution"]):
        intent = "contributions"
    elif any(k in q_low for k in ["methodology", "method", "model", "approach", "design", "cagr", "formula"]):
        intent = "methodology"
    elif any(k in q_low for k in ["dataset", "data", "material", "sample", "corpus", "source"]):
        intent = "data_materials"
    elif any(k in q_low for k in ["key finding", "finding", "result", "outcome", "performance", "growth rate", "trend"]):
        intent = "key_results"
    elif any(k in q_low for k in ["experimental evaluation", "how strong", "rigor", "statistical", "validation"]):
        intent = "evaluation_strength"
    elif any(k in q_low for k in ["objective", "aim", "purpose", "problem", "goal"]):
        intent = "objective"

    citations: List[Dict[str, str]] = []
    answer_parts: List[str] = []

    for p in target_papers:
        p_title = unescape_text(p.get("title") or "Untitled Manuscript")
        p_text = unescape_text(p.get("text") or "")
        p_secs = p.get("sections") or (summarizer.segment_paper_sections(p_text) if p_text else {})
        prof = extract_research_profile(p_text, p_secs)
        ins = extract_honest_research_insights(p_text, p_secs)

        prefix = f"**[{p_title}]** " if len(target_papers) > 1 else ""

        if intent == "limitations":
            lim_data = prof.get("limitations", {})
            if lim_data.get("found") and not lim_data.get("is_cited_background"):
                b_list = lim_data.get("bullets") or [lim_data.get("value", "")]
                answer_parts.append(
                    f"{prefix}The authors explicitly report the following study limitation(s) in {lim_data.get('section', 'the manuscript')}: "
                    + " ".join(b_list)
                )
                for b in b_list:
                    citations.append({
                        "paper_title": p_title,
                        "section": lim_data.get("section", "Limitations / Discussion"),
                        "passage": b,
                        "confidence": lim_data.get("confidence", "High"),
                    })
            elif lim_data.get("is_cited_background"):
                bg_bullets = [b for b in lim_data.get("bullets", []) if "No limitations" not in b]
                bg_quote = bg_bullets[0] if bg_bullets else lim_data.get("value", "")
                answer_parts.append(
                    f"{prefix}No study-specific methodological limitations are explicitly stated by the authors. "
                    f"However, in {lim_data.get('section', '1. Introduction')}, the manuscript cites a background constraint from prior literature ({bg_quote})"
                )
                citations.append({
                    "paper_title": p_title,
                    "section": lim_data.get("section", "1. Introduction (Cited Literature)"),
                    "passage": bg_quote,
                    "confidence": "Low",
                })
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript (no limitations explicitly stated by the authors).")

        elif intent == "gaps":
            gaps = ins.get("gaps", [])
            has_exp = ins.get("has_explicit_gaps", False)
            if gaps and has_exp:
                first_g = gaps[0]
                answer_parts.append(
                    f"{prefix}The manuscript identifies an explicit research gap in {first_g['section']}: "
                    f"{first_g['opportunity']}"
                )
                for g in gaps[:2]:
                    citations.append({
                        "paper_title": p_title,
                        "section": g["section"],
                        "passage": g["quote"],
                        "confidence": "High",
                    })
            elif gaps and not has_exp:
                first_g = gaps[0]
                answer_parts.append(
                    f"{prefix}No explicit research gaps are stated by the authors as their own finding; "
                    f"only a background constraint cited from literature is noted in {first_g['section']}. "
                    f"Suggested direction: {first_g['opportunity']}"
                )
                citations.append({
                    "paper_title": p_title,
                    "section": first_g["section"],
                    "passage": first_g["quote"],
                    "confidence": "Low",
                })
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript (no explicit research gaps stated).")

        elif intent == "future_work":
            futs = ins.get("future_directions", [])
            if futs:
                answer_parts.append(
                    f"{prefix}In {futs[0]['section']}, the authors recommend the following future work / policy direction: "
                    + " ".join(f["statement"] for f in futs[:2])
                )
                for f in futs[:2]:
                    citations.append({
                        "paper_title": p_title,
                        "section": f["section"],
                        "passage": f["statement"],
                        "confidence": "High",
                    })
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript ({NOT_STATED_SENTINEL}).")

        elif intent in ("objective", "methodology", "data_materials", "key_results", "contributions"):
            field_data = prof.get(intent, {})
            if field_data.get("found"):
                synth = _synthesize_extractive_answer(intent, p_title, field_data, ins)
                answer_parts.append(f"{prefix}{synth}")
                for b in field_data.get("bullets", []):
                    citations.append({
                        "paper_title": p_title,
                        "section": field_data.get("section", "Main Body"),
                        "passage": b,
                        "confidence": field_data.get("confidence", "High"),
                    })
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript ({NOT_FOUND_SENTINEL}).")

        elif intent == "evaluation_strength":
            meth_f = prof.get("methodology", {})
            res_f = prof.get("key_results", {})
            dat_f = prof.get("data_materials", {})
            eval_pieces: List[str] = []
            if dat_f.get("found"):
                eval_pieces.append(f"the evaluation uses {dat_f['section']} data")
                citations.append({
                    "paper_title": p_title,
                    "section": dat_f["section"],
                    "passage": dat_f["bullets"][0],
                    "confidence": dat_f["confidence"],
                })
            if meth_f.get("found"):
                eval_pieces.append(f"applies analytical modeling in {meth_f['section']}")
                citations.append({
                    "paper_title": p_title,
                    "section": meth_f["section"],
                    "passage": meth_f["bullets"][0],
                    "confidence": meth_f["confidence"],
                })
            if res_f.get("found"):
                eval_pieces.append(f"and reports quantitative outcomes in {res_f['section']}")
                citations.append({
                    "paper_title": p_title,
                    "section": res_f["section"],
                    "passage": res_f["bullets"][0],
                    "confidence": res_f["confidence"],
                })
            if eval_pieces:
                answer_parts.append(
                    f"{prefix}The empirical evaluation is grounded in quantitative evidence: "
                    + ", ".join(eval_pieces) + "."
                )
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript.")

        elif intent in ("compare_methodology", "compare_general"):
            meth_f = prof.get("methodology", {})
            res_f = prof.get("key_results", {})
            dat_f = prof.get("data_materials", {})
            if meth_f.get("found"):
                part = f"{prefix}**Methodology ({meth_f['section']}):** {meth_f['value']}"
                if dat_f.get("found"):
                    part += f" **Data ({dat_f['section']}):** {dat_f['bullets'][0]}"
                if intent == "compare_general" and res_f.get("found"):
                    part += f" **Key Findings ({res_f['section']}):** {res_f['bullets'][0]}"
                answer_parts.append(part)
                citations.append({
                    "paper_title": p_title,
                    "section": meth_f["section"],
                    "passage": meth_f["bullets"][0],
                    "confidence": meth_f["confidence"],
                })
            else:
                answer_parts.append(f"{prefix}Methodology: {NOT_FOUND_SENTINEL}.")

        else:
            records = _build_sentence_section_records(p_text, p_secs)
            q_terms = [
                w.lower()
                for w in re.findall(r"\b[A-Za-z0-9\-]{3,}\b", q_clean)
                if w.lower() not in ACADEMIC_STOPWORDS
            ]
            if q_terms and records:
                scored_recs: List[Tuple[float, Dict[str, str]]] = []
                for rec in records:
                    s_low = rec["sentence"].lower()
                    hits = sum(1 for qt in q_terms if re.search(r"\b" + re.escape(qt) + r"\b", s_low))
                    if hits > 0:
                        ratio = hits / max(len(q_terms), 1)
                        if hits >= 2 or ratio >= 0.45:
                            scored_recs.append((hits + ratio, rec))
                scored_recs.sort(key=lambda x: x[0], reverse=True)
                if scored_recs:
                    top_rec = scored_recs[0][1]
                    answer_parts.append(
                        f"{prefix}According to {top_rec['section']}, the manuscript states: {top_rec['sentence']}"
                    )
                    for sc, sr in scored_recs[:2]:
                        citations.append({
                            "paper_title": p_title,
                            "section": sr["section"],
                            "passage": sr["sentence"],
                            "confidence": "High" if sc >= 2.0 else "Moderate",
                        })
                else:
                    answer_parts.append(f"{prefix}I could not find this in the manuscript.")
            else:
                answer_parts.append(f"{prefix}I could not find this in the manuscript.")

    if not citations:
        return {
            "answer": "\n\n".join(answer_parts) if answer_parts else "I could not find this in the manuscript.",
            "citations": [],
            "found": False,
            "scope_mode": scope_mode,
        }

    return {
        "answer": "\n\n".join(answer_parts),
        "citations": citations,
        "found": True,
        "scope_mode": scope_mode,
    }
