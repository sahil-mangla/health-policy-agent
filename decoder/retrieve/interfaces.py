"""Retriever interface. decoder.retrieve.lexical_fts5.FTS5LexicalIndex and
decoder.retrieve.dense.DenseIndex both satisfy the shape of this;
decoder.retrieve.hybrid.HybridRetriever combines them via
decoder.retrieve.fusion.reciprocal_rank_fusion and is what
decoder.orchestrator.PolicyDecoder actually retrieves through.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from decoder.schema import Span


class RetrievedSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    span: Span
    score: float


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Returns `[(span_id, score), ...]`, best match first."""
        ...
