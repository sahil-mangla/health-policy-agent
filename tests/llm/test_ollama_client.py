from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from decoder.llm.ollama_client import OllamaConnectionError, OllamaLLMClient

_MODEL = "qwen2.5-coder:7b"


def _ollama_reachable() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
    except urllib.error.URLError:
        return False
    return True


def _model_pulled(model: str) -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return False
    return any(m.get("model") == model for m in body.get("models", []))


pytestmark = pytest.mark.skipif(
    not _ollama_reachable(), reason="Ollama is not running locally on :11434"
)


def test_generate_returns_real_model_output() -> None:
    if not _model_pulled(_MODEL):
        pytest.skip(f"{_MODEL} is not pulled locally")
    client = OllamaLLMClient()
    result = client.generate(
        prompt="Reply with exactly the word: PONG",
        system="You are a terse assistant that follows instructions exactly.",
        model=_MODEL,
    )
    assert "PONG" in result.upper()


def test_unreachable_server_raises_connection_error() -> None:
    client = OllamaLLMClient(base_url="http://localhost:1", timeout_seconds=2)
    with pytest.raises(OllamaConnectionError):
        client.generate(prompt="hi", system="", model=_MODEL)
