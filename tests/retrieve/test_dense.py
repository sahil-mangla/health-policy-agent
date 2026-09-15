"""Unit tests for DenseIndex's plumbing (batching, top_k, ranking, empty
cases) using a small hand-crafted fake embedding model — not the real
~130MB transformer, so these stay fast and deterministic. Semantic quality
of the real BAAI/bge-small-en-v1.5 model is exercised separately by
test_orchestrator_live.py's real end-to-end pipeline runs.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from decoder.retrieve.dense import DenseIndex
from decoder.schema import Span


class _FakeModel:
    """Maps each text to a hand-assigned 2D vector via an explicit lookup —
    so a test can assert exact ranking order by construction, not by
    hoping a real model agrees with the test's intuition of "similar"."""

    def __init__(self, vectors: dict[str, tuple[float, float]]) -> None:
        self._vectors = vectors

    def encode(
        self, texts: list[str], normalize_embeddings: bool = True
    ) -> NDArray[np.float32]:
        raw = np.array([self._vectors[t] for t in texts], dtype=np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(raw, axis=1, keepdims=True)
            raw = raw / norms
        return raw


def _span(span_id: str, text: str) -> Span:
    return Span(
        id=span_id, doc_id="policy-001", page=1, char_start=0, char_end=len(text), text=text
    )


def test_empty_index_returns_empty_list() -> None:
    index = DenseIndex(model=_FakeModel({"room rent query": (1.0, 0.0)}))
    assert index.search("room rent query") == []


def test_blank_query_returns_empty_list_without_raising() -> None:
    model = _FakeModel(
        {
            "room rent is capped": (1.0, 0.0),
            "Represent this sentence for searching relevant passages: ": (1.0, 0.0),
        }
    )
    index = DenseIndex(model=model)
    index.add_span(_span("s1", "room rent is capped"))
    assert index.search("") == []
    assert index.search("   ") == []


def test_closest_span_by_cosine_similarity_ranks_first() -> None:
    model = _FakeModel(
        {
            "room rent clause": (1.0, 0.0),
            "waiting period clause": (0.0, 1.0),
            "Represent this sentence for searching relevant passages: room rent question": (
                0.9,
                0.1,
            ),
        }
    )
    index = DenseIndex(model=model)
    index.add_span(_span("room", "room rent clause"))
    index.add_span(_span("waiting", "waiting period clause"))
    results = index.search("room rent question")
    assert [span_id for span_id, _ in results] == ["room", "waiting"]
    # Cosine similarity to the near-identical vector should be high, to the
    # near-orthogonal one near zero.
    assert results[0][1] > 0.9
    assert results[1][1] < 0.2


def test_top_k_truncates_results() -> None:
    model = _FakeModel(
        {
            "a": (1.0, 0.0),
            "b": (0.9, 0.1),
            "c": (0.8, 0.2),
            "Represent this sentence for searching relevant passages: q": (1.0, 0.0),
        }
    )
    index = DenseIndex(model=model)
    for text in ("a", "b", "c"):
        index.add_span(_span(text, text))
    assert len(index.search("q", top_k=2)) == 2


def test_add_spans_batches_in_one_encode_call() -> None:
    calls: list[list[str]] = []

    class _CountingModel(_FakeModel):
        def encode(
            self, texts: list[str], normalize_embeddings: bool = True
        ) -> NDArray[np.float32]:
            calls.append(list(texts))
            return super().encode(texts, normalize_embeddings=normalize_embeddings)

    model = _CountingModel({"a": (1.0, 0.0), "b": (0.0, 1.0)})
    index = DenseIndex(model=model)
    index.add_spans([_span("a", "a"), _span("b", "b")])
    assert calls == [["a", "b"]]


def test_add_spans_on_an_existing_index_appends_rather_than_replaces() -> None:
    model = _FakeModel(
        {
            "a": (1.0, 0.0),
            "b": (0.0, 1.0),
            "Represent this sentence for searching relevant passages: a-ish": (1.0, 0.0),
        }
    )
    index = DenseIndex(model=model)
    index.add_spans([_span("a", "a")])
    index.add_spans([_span("b", "b")])
    results = dict(index.search("a-ish", top_k=2))
    assert set(results) == {"a", "b"}
