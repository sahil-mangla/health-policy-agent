"""Concrete Anthropic-backed LLMClient implementation.

Not blocked on M3 anymore — decoder.reason and decoder.verify are both real
and working against decoder.llm.ollama_client.OllamaLLMClient and
decoder.llm.gemini_client.GeminiLLMClient. This one is just unwired because
no Anthropic API key has been provided yet (2026-09-14). Deliberately does
not `import anthropic` at module level: the method only raises for now, so
importing the SDK here would add an unused, uninstalled dependency to
pyproject.toml for nothing. Add the `anthropic` dependency and the real
import together when a key is actually available — mirror
decoder/llm/gemini_client.py's pattern (read the key from an environment
variable, never hardcode or log it, fail fast and clearly if it's missing).
"""

from __future__ import annotations

from decoder.llm.interface import LLMClient


class AnthropicLLMClient(LLMClient):
    def generate(self, prompt: str, system: str, model: str) -> str:
        raise NotImplementedError(
            "TODO: real Anthropic API call not yet implemented — no "
            "ANTHROPIC_API_KEY has been provided. No network calls happen "
            "in this codebase today for this client."
        )
