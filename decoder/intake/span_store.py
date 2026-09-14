"""A trivial in-memory Span store.

Exists so decoder.retrieve and tests have something real to index against
without a real intake pipeline (classification/OCR/segmentation are all
still stubs in decoder.intake.interfaces).
"""

from __future__ import annotations

from decoder.schema import Span


class InMemorySpanStore:
    def __init__(self) -> None:
        self._spans: dict[str, Span] = {}

    def add(self, span: Span) -> None:
        self._spans[span.id] = span

    def get(self, span_id: str) -> Span | None:
        return self._spans.get(span_id)

    def all_for_doc(self, doc_id: str) -> list[Span]:
        return [s for s in self._spans.values() if s.doc_id == doc_id]

    def __len__(self) -> int:
        return len(self._spans)
