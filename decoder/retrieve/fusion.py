"""Reciprocal Rank Fusion — merges ranked candidate lists without dropping
anything either list found.

See docs/spikes/retrieval-stack.md (SPIKE-3): chosen over weighted-sum fusion
because BM25 and cosine-similarity scores live on incompatible scales, and
chosen over any reranking step because docs/HANDOVER.md §10 forbids
"reranking that can drop a contradicting span" — RRF is a union/merge, so
nothing found by either ranked list is ever discarded here.
"""

from __future__ import annotations

from collections.abc import Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
) -> list[str]:
    """`ranked_lists` is one or more best-first sequences of item ids (e.g.
    span ids). Returns the union of all ids, ordered by summed reciprocal
    rank (`1 / (k + rank)` per list, 1-indexed), best first."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)
