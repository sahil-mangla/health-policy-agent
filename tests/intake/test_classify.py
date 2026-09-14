from __future__ import annotations

from pathlib import Path

import pytest

from decoder.intake.classify import HeuristicDocumentClassifier, find_policy_period_dates
from decoder.intake.interfaces import DocumentType

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"

_EXPECTED = [
    ("easy_health_policy_wording.pdf", DocumentType.HEALTH_POLICY_WORDING),
    ("easy_health_cis.pdf", DocumentType.CUSTOMER_INFORMATION_SHEET),
    ("optima_restore_policy_wording.pdf", DocumentType.HEALTH_POLICY_WORDING),
    ("optima_restore_cis.pdf", DocumentType.CUSTOMER_INFORMATION_SHEET),
    ("arogya_sanjeevani_retail_policy_wording.pdf", DocumentType.HEALTH_POLICY_WORDING),
    ("arogya_sanjeevani_retail_cis.pdf", DocumentType.CUSTOMER_INFORMATION_SHEET),
]


@pytest.mark.parametrize(("filename", "expected"), _EXPECTED)
def test_classifies_real_corpus_documents_correctly(filename: str, expected: DocumentType) -> None:
    path = CORPUS_DIR / filename
    raw = path.read_bytes()
    assert HeuristicDocumentClassifier().classify(filename, raw) == expected


# A minimal, valid, single blank page PDF (no text content at all) — stands
# in for a scanned/image-only document with no extractable text layer.
_BLANK_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n165\n%%EOF"
)


def test_blank_page_document_is_unreadable_scan() -> None:
    doc_type = HeuristicDocumentClassifier().classify("blank", _BLANK_PDF_BYTES)
    assert doc_type == DocumentType.UNREADABLE_SCAN


def test_find_policy_period_dates_returns_none_for_a_specimen_wording() -> None:
    # A generic downloadable specimen policy wording defines the *term*
    # "Policy Period" but doesn't carry concrete dates (those live in a
    # customer-specific Schedule, not in this document) — so this must
    # honestly return None, not fabricate a match.
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    assert find_policy_period_dates(raw) is None
