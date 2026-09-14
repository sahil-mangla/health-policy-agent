"""Real tests against the live Gemini API when a key is available locally.
Skipped automatically otherwise — this key is never committed or written to
a file by this codebase; export GEMINI_API_KEY (or GOOGLE_API_KEY) in your
own shell before running these."""

from __future__ import annotations

import os

import pytest

from decoder.llm.gemini_client import GeminiAPIKeyMissingError, GeminiLLMClient

_MODEL = "gemini-3.6-flash"


def _has_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def test_missing_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(GeminiAPIKeyMissingError):
        GeminiLLMClient()


@pytest.mark.skipif(not _has_api_key(), reason="GEMINI_API_KEY / GOOGLE_API_KEY not set")
def test_generate_returns_real_model_output() -> None:
    client = GeminiLLMClient()
    result = client.generate(
        prompt="Reply with exactly the word: PONG",
        system="You are a terse assistant that follows instructions exactly.",
        model=_MODEL,
    )
    assert "PONG" in result.upper()


@pytest.mark.skipif(not _has_api_key(), reason="GEMINI_API_KEY / GOOGLE_API_KEY not set")
def test_generate_is_grounded_not_fabricated() -> None:
    # Same grounding check already validated for OllamaDrafter — confirms
    # Gemini, used the same way, also declines rather than fabricates.
    client = GeminiLLMClient()
    result = client.generate(
        prompt=(
            "QUESTION: What co-payment percentage applies?\n\n"
            "PASSAGE: Def. 42 Room Rent means the amount charged by a "
            "hospital towards room and boarding expenses."
        ),
        system=(
            "Answer the question using ONLY information literally stated "
            "in the passage. If the passage does not answer the question, "
            "say clearly that it does not."
        ),
        model=_MODEL,
    )
    lowered = result.lower()
    assert any(phrase in lowered for phrase in ("not", "no mention", "doesn't", "does not"))
