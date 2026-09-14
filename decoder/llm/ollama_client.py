"""Ollama-backed LLMClient implementation — a locally running model, no API
key, no external network egress.

Chosen over a cloud provider for this project (per user direction,
2026-09-14): no API key to manage or leak, no per-call cost, and it keeps
document content entirely on-machine during development — a meaningful plus
for the §9.5 PII posture, not just convenience.

Uses stdlib `urllib.request` rather than adding an HTTP client dependency —
Ollama's API is a single simple POST endpoint, not worth a new dependency.

Model choice is a runtime parameter (`generate`'s `model` argument), not
hardcoded here — SPIKE-5 (docs/HANDOVER.md §15) is explicit that the drafter
and verifier need not share a model. Whatever is passed must already be
pulled locally (`ollama pull <model>`); this client does not pull models.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from decoder.llm.interface import LLMClient

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT_SECONDS = 120


class OllamaConnectionError(RuntimeError):
    """Raised when the local Ollama server can't be reached — distinct from
    a model producing a bad response, since the caller should handle
    "Ollama isn't running" very differently from "the model said something
    unparseable"."""


class OllamaLLMClient(LLMClient):
    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, system: str, model: str) -> str:
        payload = json.dumps(
            {"model": model, "prompt": prompt, "system": system, "stream": False}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"Could not reach Ollama at {self._base_url} — is `ollama serve` "
                f"running and is model {model!r} pulled (`ollama pull {model}`)?"
            ) from exc
        return str(body["response"])
