"""Real tests against the live Gemini API when a key is available locally.
Skipped automatically otherwise — this key is never committed or written to
a file by this codebase; export GEMINI_API_KEY (or GOOGLE_API_KEY) in your
own shell before running these."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from google.genai import errors

from decoder.llm.gemini_client import (
    GeminiAPIKeyMissingError,
    GeminiLLMClient,
    GeminiRateLimitError,
)

_MODEL = "gemini-3.6-flash"


def _has_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def test_missing_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(GeminiAPIKeyMissingError):
        GeminiLLMClient()


class TestRetryBehavior:
    """Deterministic tests for the retry/rate-limit logic — no live API
    call, no dependence on a real transient failure actually occurring.
    Motivated by two real 503s observed in one session's worth of manual
    testing, plus a user-flagged free-tier rate-limit concern (2026-09-14)."""

    def _client_with_fake_key(self, monkeypatch: pytest.MonkeyPatch) -> GeminiLLMClient:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-unit-tests")
        monkeypatch.setattr("decoder.llm.gemini_client.time.sleep", lambda _seconds: None)
        return GeminiLLMClient()

    def test_transient_server_error_is_retried_and_recovers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = self._client_with_fake_key(monkeypatch)
        success_response = MagicMock(text="recovered")
        mock_generate = MagicMock(
            side_effect=[
                errors.ServerError(503, {"error": {"message": "high demand"}}),
                success_response,
            ]
        )
        monkeypatch.setattr(client._client.models, "generate_content", mock_generate)
        result = client.generate(prompt="p", system="s", model=_MODEL)
        assert result == "recovered"
        assert mock_generate.call_count == 2

    def test_server_error_exhausts_retries_and_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = self._client_with_fake_key(monkeypatch)
        mock_generate = MagicMock(
            side_effect=errors.ServerError(503, {"error": {"message": "high demand"}})
        )
        monkeypatch.setattr(client._client.models, "generate_content", mock_generate)
        with pytest.raises(errors.ServerError):
            client.generate(prompt="p", system="s", model=_MODEL)
        assert mock_generate.call_count == 3  # _MAX_TRANSIENT_RETRIES

    def test_rate_limit_raises_immediately_without_retrying(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = self._client_with_fake_key(monkeypatch)
        mock_generate = MagicMock(
            side_effect=errors.ClientError(429, {"error": {"message": "quota exceeded"}})
        )
        monkeypatch.setattr(client._client.models, "generate_content", mock_generate)
        with pytest.raises(GeminiRateLimitError):
            client.generate(prompt="p", system="s", model=_MODEL)
        assert mock_generate.call_count == 1  # never retried

    def test_other_client_error_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = self._client_with_fake_key(monkeypatch)
        mock_generate = MagicMock(
            side_effect=errors.ClientError(404, {"error": {"message": "model not found"}})
        )
        monkeypatch.setattr(client._client.models, "generate_content", mock_generate)
        with pytest.raises(errors.ClientError):
            client.generate(prompt="p", system="s", model=_MODEL)
        assert mock_generate.call_count == 1


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
