"""Draft generation — the ONLY creative LLM call in the pipeline
(docs/HANDOVER.md §5). Its output is never shown to a user directly; it must
pass through decoder.verify and decoder.resolve first (§5's "no fast path"
rule, enforced structurally in decoder.orchestrator).

decoder.reason.ollama_drafter.OllamaDrafter is a real implementation of this
Protocol, against a local Ollama model. See §14 M3.
"""

from __future__ import annotations

from typing import Protocol

from decoder.retrieve.interfaces import RetrievedSpan


class Drafter(Protocol):
    def draft(self, situation: str, evidence: list[RetrievedSpan]) -> str:
        """Produces free-text draft reasoning over the given evidence spans.
        This text is never shown to a user directly — it is only ever passed
        to decoder.verify.decompose.OllamaDecomposer.decompose(), per the
        architecture in docs/HANDOVER.md §5."""
        ...
