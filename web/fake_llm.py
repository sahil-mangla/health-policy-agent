"""A scripted LLMClient for testing the web tier and the UI.

Drives the REAL pipeline — real retrieval, real decomposition parsing, real
hallucination trap, real resolution — with a model whose output is fixed.
The point is to test the §8 UI contract without tying those assertions to a
7B model's wording, which would make them flaky for reasons that have
nothing to do with the interface.

Recognises its role from a marker in the system prompt rather than being
told which role it is playing, so the pipeline wiring stays exactly as it
is in production: nothing in decoder/ knows this exists.
"""

from __future__ import annotations

import hashlib

import numpy as np
from numpy.typing import NDArray

from decoder.llm.interface import LLMClient

DRAFT = "The policy applies a co-payment of 5% to every admissible claim."

# Two claims: one the scripted entailer will ground (so the UI has a
# WELL_SUPPORTED row to render) and one it never will (so the UI also has
# an unsupported row, and therefore a follow-up question, to render).
CLAIMS = (
    "CLAIM: the policy | applies a co-payment of | 5% | DOCUMENT_FACT\n"
    "CLAIM: the policy | covers | overseas dental implants | DOCUMENT_FACT"
)

GROUNDED_QUOTE = "Co-payment"


class ScriptedLLMClient(LLMClient):
    def generate(self, prompt: str, system: str, model: str) -> str:
        if "split a draft answer" in system:
            return CLAIMS
        if "strict fact-checker" in system:
            return self._entail(prompt)
        return DRAFT

    @staticmethod
    def _entail(prompt: str) -> str:
        """Grounds the co-payment claim only when the span it was handed
        actually contains the word — so the verdict still depends on real
        retrieved text, and a span that doesn't mention it correctly comes
        back NEUTRAL instead of being rubber-stamped."""
        claim_line, _, passage = prompt.partition("Passage:")
        if "co-payment" in claim_line.lower() and GROUNDED_QUOTE in passage:
            return f"VERDICT: SUPPORTS\nQUOTE: {GROUNDED_QUOTE}"
        return "VERDICT: NEUTRAL\nQUOTE: NONE"


class FakeEmbeddingModel:
    """Deterministic, hash-seeded stand-in for the real SentenceTransformer
    (decoder.retrieve.dense) — exercises the real DenseIndex/HybridRetriever
    code path (so web tests drive genuinely hybrid retrieval, not silently
    lexical-only) without downloading or running an actual transformer in
    every test run, for the same reason ScriptedLLMClient stands in for a
    real LLM above."""

    _DIM = 16

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> NDArray[np.float32]:
        vectors = np.array([self._vector(text) for text in texts], dtype=np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vectors = vectors / norms
        return vectors

    def _vector(self, text: str) -> NDArray[np.float32]:
        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
        return np.random.default_rng(seed).standard_normal(self._DIM).astype(np.float32)
