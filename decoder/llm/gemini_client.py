"""Gemini-backed LLMClient implementation — a real, cloud-provider option
alongside decoder.llm.ollama_client.OllamaLLMClient (per user direction,
2026-09-14: "wire up any kind of client which can come openai google gemini
opensource model").

Uses Google's current `google-genai` SDK (`pip install google-genai`,
`from google import genai`) — the successor to the deprecated
`google-generativeai` package; verified against the SDK's own README
(2026-09-14) rather than assumed, since package names and call shapes in
this space have changed before.

The API key is read from an environment variable, never hardcoded, never
logged, and never accepted as a constructor string literal — the only way
to authenticate is to have GEMINI_API_KEY (or GOOGLE_API_KEY) set in the
environment before constructing this client. See this module's
GeminiAPIKeyMissingError for what happens otherwise.

Defaults to temperature=0, same rationale as OllamaLLMClient: a
document-fact-checking/extraction role benefits from deterministic output,
not creative variation — see ollama_client.py's module docstring for the
real bug this caught there.

Retry behaviour, added after observing real failures (2026-09-14): two
transient 503s ("high demand") came back from the API across a handful of
manual test calls in one session, plus a user-flagged concern about free-
tier rate limits (HTTP 429). These need different handling, not one blind
retry loop:
- 5xx (ServerError, e.g. 503) — transient, worth a short exponential-backoff
  retry (a few seconds total), since the same request often succeeds
  moments later.
- 429 specifically — a rate limit, not a transient blip. Retrying it in a
  tight loop would make the underlying problem worse (hammering an
  already-exhausted quota). Raised immediately as GeminiRateLimitError
  instead, so the caller can decide what to do (fall back to
  decoder.llm.ollama_client.OllamaLLMClient for that call, queue, surface a
  clear message) rather than the client silently spinning or hanging.
- Any other error (e.g. a 404 for a deprecated/wrong model name — see the
  model-name note below) is not retried at all and propagates immediately;
  retrying a request that's wrong by construction just delays the same
  failure.
"""

from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

from decoder.llm.interface import LLMClient

_API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_RATE_LIMIT_STATUS_CODE = 429
_MAX_TRANSIENT_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 1.0


class GeminiAPIKeyMissingError(RuntimeError):
    """Raised at construction time if neither GEMINI_API_KEY nor
    GOOGLE_API_KEY is set — fails fast and explicitly, rather than letting
    the underlying SDK raise its own less-obvious error on the first call."""


class GeminiRateLimitError(RuntimeError):
    """Raised immediately (never retried by this client) when the API
    returns HTTP 429 — a quota/rate-limit condition, most likely on the
    free tier. The caller decides how to respond; blindly retrying here
    would only make the underlying rate-limit problem worse."""


def _read_api_key() -> str:
    for var in _API_KEY_ENV_VARS:
        value = os.environ.get(var)
        if value:
            return value
    raise GeminiAPIKeyMissingError(
        f"Set one of {_API_KEY_ENV_VARS} in the environment before "
        "constructing GeminiLLMClient. Never paste the key into chat or "
        "commit it — export it in your own shell/terminal."
    )


class GeminiLLMClient(LLMClient):
    def __init__(self, temperature: float = 0.0) -> None:
        self._client = genai.Client(api_key=_read_api_key())
        self._temperature = temperature

    def generate(self, prompt: str, system: str, model: str) -> str:
        backoff = _INITIAL_BACKOFF_SECONDS
        last_error: errors.ServerError | None = None
        for attempt in range(_MAX_TRANSIENT_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=self._temperature,
                    ),
                )
                return response.text or ""
            except errors.ClientError as exc:
                if exc.code == _RATE_LIMIT_STATUS_CODE:
                    raise GeminiRateLimitError(
                        "Gemini API rate limit hit (HTTP 429) — likely the "
                        "free tier's quota. Not retrying automatically; "
                        "consider decoder.llm.ollama_client.OllamaLLMClient "
                        "as a fallback for this call."
                    ) from exc
                raise  # any other 4xx (bad model name, auth, ...) — don't retry
            except errors.ServerError as exc:
                last_error = exc
                if attempt < _MAX_TRANSIENT_RETRIES - 1:
                    time.sleep(backoff)
                    backoff *= 2
        assert last_error is not None
        raise last_error
