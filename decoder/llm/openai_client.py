"""Concrete OpenAI-backed LLMClient implementation.

Unwired because no OpenAI API key has been provided (2026-09-14). Same
pattern as decoder/llm/anthropic_client.py: no `openai` import at module
level (the method only raises), no dependency added to pyproject.toml until
this is real. When a key is available, mirror
decoder/llm/gemini_client.py's pattern — read the key from an environment
variable (`OPENAI_API_KEY`), never hardcode or log it, fail fast and
clearly if it's missing, default to temperature=0 for the same determinism
reasons documented in ollama_client.py's module docstring.
"""

from __future__ import annotations

from decoder.llm.interface import LLMClient


class OpenAILLMClient(LLMClient):
    def generate(self, prompt: str, system: str, model: str) -> str:
        raise NotImplementedError(
            "TODO: real OpenAI API call not yet implemented — no "
            "OPENAI_API_KEY has been provided. No network calls happen in "
            "this codebase today for this client."
        )
