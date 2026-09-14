"""Document intake — classification, OCR, segmentation.

All stubs: blocked on document-classification taxonomy and OCR tooling
decisions not yet made. See docs/HANDOVER.md §9.1 (wrong/unusable document
handling must happen here, before anything downstream runs) and §14 M1.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from decoder.schema import Span


class DocumentType(StrEnum):
    """§9.1: classify on intake before anything else."""

    HEALTH_POLICY_WORDING = "HEALTH_POLICY_WORDING"
    CUSTOMER_INFORMATION_SHEET = "CUSTOMER_INFORMATION_SHEET"
    MOTOR_OR_LIFE_POLICY = "MOTOR_OR_LIFE_POLICY"
    EXPIRED_POLICY = "EXPIRED_POLICY"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    UNREADABLE_SCAN = "UNREADABLE_SCAN"
    NOT_INSURANCE_DOCUMENT = "NOT_INSURANCE_DOCUMENT"


class DocumentClassifier(Protocol):
    def classify(self, doc_id: str, raw_bytes: bytes) -> DocumentType: ...


class Segmenter(Protocol):
    def segment(self, doc_id: str, raw_bytes: bytes) -> list[Span]:
        """Splits a document into Spans with page + bbox provenance."""
        ...
