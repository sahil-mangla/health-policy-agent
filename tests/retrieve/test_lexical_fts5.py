from __future__ import annotations

from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import Span


def _span(span_id: str, text: str) -> Span:
    return Span(
        id=span_id, doc_id="policy-001", page=1, char_start=0, char_end=len(text), text=text
    )


class TestSearch:
    """Natural-language OR-of-terms retrieval — for evidence retrieval over
    a free-text situation/question (docs/HANDOVER.md §10), not exact
    matching. See decoder/retrieve/lexical_fts5.py's module docstring for
    why this differs from search_phrase()."""

    def test_on_empty_index_returns_empty_list(self) -> None:
        with FTS5LexicalIndex() as index:
            assert index.search("room rent") == []

    def test_ranks_span_matching_more_terms_first(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "the eligible room rent limit is INR 5000 per day"))
            index.add_span(_span("s2", "the waiting period for pre-existing diseases is 4 years"))
            results = index.search("room rent")
            assert results
            assert results[0][0] == "s1"

    def test_matches_even_when_not_every_term_is_present(self) -> None:
        # This is the real gap a phrase-only search has: a natural question
        # rarely repeats a clause's exact wording. Verified against real
        # data (2026-09-14): "co-payment percentage claim" against a real
        # clause containing "Co-payment" and "claim" but never the word
        # "percentage" must still retrieve it.
        with FTS5LexicalIndex() as index:
            index.add_span(
                _span(
                    "s1",
                    "Each and every claim under the Policy shall be subject to a "
                    "Co-payment of 5% applicable to claim amount admissible.",
                )
            )
            results = index.search("co-payment percentage claim")
            assert results
            assert results[0][0] == "s1"

    def test_with_no_matching_terms_returns_empty_list(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "the waiting period for pre-existing diseases is 4 years"))
            assert index.search("proportionate deduction") == []

    def test_handles_special_characters_without_raising(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", 'the room category is "single private AC"'))
            # A naive caller might pass through quotes/FTS5 operator words;
            # the index must not crash, and terms like "OR"/"NOT" are
            # searched for as literal words, never parsed as FTS5 boolean
            # operators (every token is quoted before being sent to FTS5).
            results = index.search('"single private AC" OR NOT room*')
            assert results  # "single"/"private"/"AC"/"room" all present in s1

    def test_blank_query_returns_empty_list_without_raising(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "some text"))
            assert index.search("   ") == []

    def test_query_with_no_usable_tokens_returns_empty_list(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "some text"))
            assert index.search("!!! ??? ---") == []


class TestSearchPhrase:
    """Exact-phrase lookup — the whole query as one literal substring, for
    re-finding a span by a known verbatim citation."""

    def test_on_empty_index_returns_empty_list(self) -> None:
        with FTS5LexicalIndex() as index:
            assert index.search_phrase("room rent") == []

    def test_matches_exact_contiguous_phrase(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "the eligible room rent limit is INR 5000 per day"))
            index.add_span(_span("s2", "the waiting period for pre-existing diseases is 4 years"))
            results = index.search_phrase("room rent")
            assert results
            assert results[0][0] == "s1"

    def test_does_not_match_when_terms_are_present_but_not_contiguous(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", "the room shall have a rent-free grace period"))
            # "room" and "rent" both appear, but not as the phrase "room rent".
            assert index.search_phrase("room rent") == []

    def test_handles_special_characters_without_raising(self) -> None:
        with FTS5LexicalIndex() as index:
            index.add_span(_span("s1", 'the room category is "single private AC"'))
            results = index.search_phrase('"single private AC" OR NOT room*')
            assert results == []
