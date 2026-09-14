from __future__ import annotations

from decoder.intake.span_store import InMemorySpanStore
from decoder.schema import Span


def _span(span_id: str, doc_id: str, text: str) -> Span:
    return Span(id=span_id, doc_id=doc_id, page=1, char_start=0, char_end=len(text), text=text)


def test_add_and_get_round_trip() -> None:
    store = InMemorySpanStore()
    span = _span("s1", "doc1", "room rent limit is INR 5,000 per day")
    store.add(span)
    assert store.get("s1") == span


def test_get_missing_returns_none() -> None:
    store = InMemorySpanStore()
    assert store.get("nope") is None


def test_all_for_doc_filters_by_doc_id() -> None:
    store = InMemorySpanStore()
    store.add(_span("s1", "doc1", "a"))
    store.add(_span("s2", "doc1", "b"))
    store.add(_span("s3", "doc2", "c"))
    assert {s.id for s in store.all_for_doc("doc1")} == {"s1", "s2"}
    assert len(store) == 3
