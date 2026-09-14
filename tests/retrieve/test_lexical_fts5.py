from __future__ import annotations

from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import Span


def _span(span_id: str, text: str) -> Span:
    return Span(
        id=span_id, doc_id="policy-001", page=1, char_start=0, char_end=len(text), text=text
    )


def test_search_on_empty_index_returns_empty_list() -> None:
    with FTS5LexicalIndex() as index:
        assert index.search("room rent") == []


def test_search_ranks_lexical_match_first() -> None:
    with FTS5LexicalIndex() as index:
        index.add_span(_span("s1", "the eligible room rent limit is INR 5000 per day"))
        index.add_span(_span("s2", "the waiting period for pre-existing diseases is 4 years"))
        results = index.search("room rent")
        assert results
        assert results[0][0] == "s1"


def test_search_with_no_matches_returns_empty_list() -> None:
    with FTS5LexicalIndex() as index:
        index.add_span(_span("s1", "the waiting period for pre-existing diseases is 4 years"))
        assert index.search("proportionate deduction") == []


def test_search_handles_query_with_fts5_special_characters_without_raising() -> None:
    with FTS5LexicalIndex() as index:
        index.add_span(_span("s1", 'the room category is "single private AC"'))
        # A naive caller might pass through quotes/operators; the index must
        # not crash and must treat the input as a literal exact phrase.
        results = index.search('"single private AC" OR NOT room*')
        assert results == []


def test_blank_query_returns_empty_list_without_raising() -> None:
    with FTS5LexicalIndex() as index:
        index.add_span(_span("s1", "some text"))
        assert index.search("   ") == []
