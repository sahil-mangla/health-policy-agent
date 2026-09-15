"""HybridRetriever: proves fusion actually widens recall — a span found by
only one of the two retrieval methods must still come back, which is the
entire point of hybrid retrieval over either method alone (docs/HANDOVER.md
§10: pure lexical misses paraphrases, pure dense misses exact terms/numbers).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from decoder.retrieve.dense import DenseIndex
from decoder.retrieve.hybrid import HybridRetriever
from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import Span


class _FakeModel:
    """A minimal embedding model where similarity is just 1 - normalized
    hamming-ish distance over hand-picked 2D points, so a test can force
    "semantically close but lexically unrelated" without needing a real
    transformer to agree."""

    def __init__(self, vectors: dict[str, tuple[float, float]]) -> None:
        self._vectors = vectors

    def encode(
        self, texts: list[str], normalize_embeddings: bool = True
    ) -> NDArray[np.float32]:
        raw = np.array([self._vectors[t] for t in texts], dtype=np.float32)
        if normalize_embeddings:
            raw = raw / np.linalg.norm(raw, axis=1, keepdims=True)
        return raw


def _span(span_id: str, text: str) -> Span:
    return Span(
        id=span_id, doc_id="policy-001", page=1, char_start=0, char_end=len(text), text=text
    )


def test_span_found_only_by_dense_still_surfaces() -> None:
    # "waiting period" (query) vs. "the cooling-off interval before cover
    # begins" (span) share no words at all — FTS5 alone would never
    # retrieve it — but the fake embedding model places them close together,
    # standing in for real paraphrase-level semantic similarity.
    query = "waiting period"
    paraphrase_text = "the cooling-off interval before cover begins"
    model = _FakeModel(
        {
            f"Represent this sentence for searching relevant passages: {query}": (1.0, 0.0),
            paraphrase_text: (0.95, 0.05),
            "totally unrelated clause about hospital cafeteria hours": (0.0, 1.0),
        }
    )
    with FTS5LexicalIndex() as lexical:
        retriever = HybridRetriever(lexical, DenseIndex(model=model))
        retriever.add_spans(
            [
                _span("paraphrase", paraphrase_text),
                _span("unrelated", "totally unrelated clause about hospital cafeteria hours"),
            ]
        )
        # Lexical alone would find nothing (zero shared terms).
        assert lexical.search(query) == []
        results = [span_id for span_id, _ in retriever.search(query)]
    assert "paraphrase" in results


def test_span_found_only_by_lexical_still_surfaces() -> None:
    # An exact numeric figure a dense model's fake embedding here places far
    # from the query — the case FTS5 alone must catch and dense might miss.
    query = "5000"
    exact_text = "the flat cap is Rs.5000 per day"
    model = _FakeModel(
        {
            f"Represent this sentence for searching relevant passages: {query}": (1.0, 0.0),
            exact_text: (0.0, 1.0),
            "an unrelated clause with no numbers at all": (0.0, -1.0),
        }
    )
    with FTS5LexicalIndex() as lexical:
        retriever = HybridRetriever(lexical, DenseIndex(model=model))
        retriever.add_spans(
            [
                _span("exact", exact_text),
                _span("unrelated", "an unrelated clause with no numbers at all"),
            ]
        )
        results = [span_id for span_id, _ in retriever.search(query)]
    assert "exact" in results


def test_span_found_by_both_ranks_above_span_found_by_only_one() -> None:
    query = "room rent"
    both_text = "room rent limit is capped"
    lexical_only_text = "room rent excludes cosmetic surgery entirely unrelated topic"
    model = _FakeModel(
        {
            f"Represent this sentence for searching relevant passages: {query}": (1.0, 0.0),
            both_text: (0.99, 0.01),
            lexical_only_text: (0.0, 1.0),
        }
    )
    with FTS5LexicalIndex() as lexical:
        retriever = HybridRetriever(lexical, DenseIndex(model=model))
        retriever.add_spans([_span("both", both_text), _span("lex_only", lexical_only_text)])
        results = [span_id for span_id, _ in retriever.search(query)]
    assert results.index("both") < results.index("lex_only")


def test_empty_retriever_returns_empty_list() -> None:
    with FTS5LexicalIndex() as lexical:
        retriever = HybridRetriever(lexical, DenseIndex(model=_FakeModel({})))
        assert retriever.search("anything") == []
