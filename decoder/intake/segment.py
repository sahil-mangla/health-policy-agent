"""Real Segmenter implementation — docs/HANDOVER.md §5, §6.

Splits a PDF into paragraph/clause-sized Spans with page + bbox provenance,
satisfying decoder.intake.interfaces.Segmenter. char_start/char_end are
offsets into a reconstructed full-document text stream (all paragraphs,
reading order, joined by "\\n\\n") — this is the offset space every Span
from a given doc_id shares, not a per-page offset.
"""

from __future__ import annotations

import uuid

from decoder.intake.pdf_extract import extract_all_paragraphs
from decoder.schema import Span


class PdfSegmenter:
    def segment(self, doc_id: str, raw_bytes: bytes) -> list[Span]:
        paragraphs = extract_all_paragraphs(raw_bytes)
        spans: list[Span] = []
        cursor = 0
        for page_number, paragraph in paragraphs:
            text = paragraph.text
            if not text.strip():
                continue
            start = cursor
            end = start + len(text)
            cursor = end + 2  # account for the "\n\n" joiner between spans
            spans.append(
                Span(
                    id=f"{doc_id}:{uuid.uuid4().hex[:12]}",
                    doc_id=doc_id,
                    page=page_number,
                    char_start=start,
                    char_end=end,
                    text=text,
                    bbox=paragraph.bbox,
                )
            )
        return spans
