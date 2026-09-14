"""Provider-agnostic LLM client interface.

Other packages (decoder.reason, decoder.verify) must depend only on this
interface, never import a concrete SDK directly — model choice differs by
role (SPIKE-5, docs/HANDOVER.md §15: the drafter and the verifier need not
share a model, and the verifier arguably should be cheaper/dumber), and as
of 2026-09-14 provider differs too. Implementations:
- decoder.llm.ollama_client.OllamaLLMClient — real, local, no API key.
- decoder.llm.gemini_client.GeminiLLMClient — real, needs GEMINI_API_KEY
  (or GOOGLE_API_KEY) in the environment.
- decoder.llm.anthropic_client.AnthropicLLMClient — stub, no key yet.
- decoder.llm.openai_client.OpenAILLMClient — stub, no key yet.
All four satisfy this exact interface — swapping providers means
constructing a different class, nothing else in the call site changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str, model: str) -> str: ...
