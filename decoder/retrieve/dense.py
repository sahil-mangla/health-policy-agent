"""Dense (embedding) retrieval — see docs/spikes/retrieval-stack.md (SPIKE-3).

Was blocked on the SPIKE-2 corpus; unblocked as of 2026-09-15 now that 5
real policy+CIS pairs exist (corpus/README.md). Implementation: a small
local sentence-transformers model (`BAAI/bge-small-en-v1.5`, 384-dim,
confirmed against the model card 2026-09-15 — not guessed from training
knowledge, since a wrong query/passage-prefix convention would silently
degrade retrieval quality rather than error) with brute-force numpy cosine
similarity, per SPIKE-3's decision. FAISS/Chroma are the natural swap-in if
corpus size later warrants it; not needed yet.

BGE's own usage convention (asymmetric, verified against the model card):
a query gets a fixed instruction prefix so the model knows it's the *short*
side of a search pair, a passage/span gets none. Embeddings are requested
pre-normalized, so cosine similarity is just a dot product — this is a
sentence-transformers/BGE convention, not a general embedding-API one, and
is worth stating explicitly since getting it backwards (prefixing spans
instead of queries) would silently work but retrieve worse.

`EmbeddingModel` is a narrow Protocol, not `SentenceTransformer` itself, so
tests can inject a fast deterministic fake instead of loading the real
~130MB transformer for every unit test — mirrors how
decoder.llm.interface.LLMClient lets decoder/verify's tests use a scripted
model instead of live Ollama.
"""

from __future__ import annotations

from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from decoder.schema import Span

_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE v1.5's documented retrieval convention: queries carry this instruction,
# passages carry none.
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingModel(Protocol):
    def encode(
        self, texts: list[str], normalize_embeddings: bool = ...
    ) -> NDArray[np.float32]: ...


def load_default_model() -> EmbeddingModel:
    # Imported lazily so importing this module doesn't pull in torch/
    # sentence-transformers (a real but heavy dependency, per
    # pyproject.toml) for callers who never construct a DenseIndex without
    # injecting their own model — e.g. every test that passes a fake one.
    from sentence_transformers import SentenceTransformer

    # SentenceTransformer.encode's real signature is a much wider overload
    # set (multimodal inputs, several output-shape options) than this
    # module ever calls it with — `cast` rather than widening EmbeddingModel
    # to match, since the narrow Protocol is what makes a fake injectable
    # in tests without reimplementing all of that surface.
    return cast(EmbeddingModel, SentenceTransformer(_MODEL_NAME))


class DenseIndex:
    """Brute-force cosine-similarity search over span embeddings. Fine at
    the corpus sizes in play here (a handful of documents at a time, per
    SPIKE-3) — an ANN index is deliberately not added ahead of a scale
    problem that doesn't exist yet."""

    def __init__(self, model: EmbeddingModel | None = None) -> None:
        self._model = model or load_default_model()
        self._span_ids: list[str] = []
        self._embeddings: NDArray[np.float32] | None = None

    def add_span(self, span: Span) -> None:
        self.add_spans([span])

    def add_spans(self, spans: list[Span]) -> None:
        """Batched (one encode() call for all spans) rather than per-span —
        matters in practice, since a single real policy wording segments
        into hundreds of spans (docs/HANDOVER.md M1 status: 424 for one
        52-page document)."""
        if not spans:
            return
        vectors = np.asarray(
            self._model.encode([span.text for span in spans], normalize_embeddings=True),
            dtype=np.float32,
        )
        self._span_ids.extend(span.id for span in spans)
        self._embeddings = (
            vectors if self._embeddings is None else np.vstack([self._embeddings, vectors])
        )

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Returns `[(span_id, cosine_similarity), ...]`, best match first.
        An empty index or a blank query both return `[]` without raising —
        same contract as decoder.retrieve.lexical_fts5.FTS5LexicalIndex."""
        if self._embeddings is None or not query.strip():
            return []
        query_vector = np.asarray(
            self._model.encode([_QUERY_INSTRUCTION + query], normalize_embeddings=True),
            dtype=np.float32,
        )[0]
        # Both sides are pre-normalized, so the dot product IS the cosine
        # similarity — no separate norm division needed.
        similarities = self._embeddings @ query_vector
        k = min(top_k, len(self._span_ids))
        top_indices = np.argsort(-similarities)[:k]
        return [(self._span_ids[i], float(similarities[i])) for i in top_indices]
