"""Dense (embedding) retrieval — see docs/spikes/retrieval-stack.md.

Blocked on the SPIKE-2 corpus (docs/HANDOVER.md §11): implementing this
against zero real documents would produce no verifiable signal. Intended
implementation once unblocked: a small local sentence-transformers model
(bge-small-en-v1.5 or e5-small-v2) with brute-force numpy cosine similarity
(install via `uv sync --extra dense`); swap for FAISS/Chroma only if corpus
size later warrants it.
"""

from __future__ import annotations

from decoder.schema import Span


class DenseIndex:
    def add_span(self, span: Span) -> None:
        raise NotImplementedError(
            "TODO(SPIKE-2 corpus + embedding model wiring): blocked on real "
            "documents to index; see docs/spikes/retrieval-stack.md."
        )

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        raise NotImplementedError(
            "TODO(SPIKE-2 corpus + embedding model wiring): blocked on real "
            "documents to search; see docs/spikes/retrieval-stack.md."
        )
