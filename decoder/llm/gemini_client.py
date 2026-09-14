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
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types

from decoder.llm.interface import LLMClient

_API_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class GeminiAPIKeyMissingError(RuntimeError):
    """Raised at construction time if neither GEMINI_API_KEY nor
    GOOGLE_API_KEY is set — fails fast and explicitly, rather than letting
    the underlying SDK raise its own less-obvious error on the first call."""


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
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=self._temperature,
            ),
        )
        return response.text or ""
