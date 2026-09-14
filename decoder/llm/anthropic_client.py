"""Concrete Anthropic-backed LLMClient implementation.

Deliberately does not `import anthropic` at module level: the method only
raises for now, so importing the SDK here would add an unused, uninstalled
dependency to pyproject.toml for nothing. Add the `anthropic` dependency and
the real import together when this is actually wired up (blocked on M3 —
Reasoning and verification needing a real drafter/verifier call path).
"""

from __future__ import annotations

from decoder.llm.interface import LLMClient


class AnthropicLLMClient(LLMClient):
    def generate(self, prompt: str, system: str, model: str) -> str:
        raise NotImplementedError(
            "TODO(M3 — Reasoning and verification): real Anthropic API call "
            "not yet implemented; no network calls happen in this codebase "
            "today. See docs/HANDOVER.md §14 M3."
        )
