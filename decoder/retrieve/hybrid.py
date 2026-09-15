"""HybridRetriever — lexical + dense retrieval, unioned via Reciprocal Rank
Fusion. See docs/spikes/retrieval-stack.md (SPIKE-3) for the decision, and
docs/HANDOVER.md §10 for why hybrid (not lexical-only, not dense-only) is
the actual requirement: "insurance wording is full of exact terms and
numbers that pure dense retrieval misses" and the converse also holds — a
contradicting span phrased in different words than the query needs the
dense half to be found at all.

This module only wires decoder.retrieve.lexical_fts5.FTS5LexicalIndex and
decoder.retrieve.dense.DenseIndex together through
decoder.retrieve.fusion.reciprocal_rank_fusion; neither retrieval method's
own logic lives here.
"""

from __future__ import annotations

from decoder.retrieve.dense import DenseIndex
from decoder.retrieve.fusion import reciprocal_rank_fusion
from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import Span


class HybridRetriever:
    def __init__(self, lexical: FTS5LexicalIndex, dense: DenseIndex) -> None:
        self._lexical = lexical
        self._dense = dense

    def add_span(self, span: Span) -> None:
        self.add_spans([span])

    def add_spans(self, spans: list[Span]) -> None:
        self._lexical.add_spans(spans)
        self._dense.add_spans(spans)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Returns `[(span_id, score), ...]`, best match first — the fused
        union of what each retrieval method found on its own, so a span
        only the dense half would have retrieved (or only the lexical half)
        still gets through, never dropped by a reranking step (§10
        forbids "reranking that can drop a contradicting span").

        `score` here is a rank-based placeholder (n_results - fused_rank),
        not a probability or a value comparable across queries — RRF's own
        point is that BM25 and cosine scores live on incompatible scales
        (see decoder.retrieve.fusion's docstring), so it discards both and
        keeps only rank order. Nothing downstream currently reads a
        RetrievedSpan's score value, only its presence and rank in the
        list, so this is honest about what it actually is.
        """
        lexical_ids = [span_id for span_id, _ in self._lexical.search(query, top_k=top_k)]
        dense_ids = [span_id for span_id, _ in self._dense.search(query, top_k=top_k)]
        fused = reciprocal_rank_fusion([lexical_ids, dense_ids])[:top_k]
        n = len(fused)
        return [(span_id, float(n - rank)) for rank, span_id in enumerate(fused)]
