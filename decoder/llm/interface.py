"""Provider-agnostic LLM client interface.

Other packages (decoder.reason, decoder.verify) must depend only on this
interface, never import a concrete SDK directly — model choice differs by
role (SPIKE-5, docs/HANDOVER.md §15: the drafter and the verifier need not
share a model, and the verifier arguably should be cheaper/dumber).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str, model: str) -> str: ...
