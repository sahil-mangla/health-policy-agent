"""Real Drafter implementation against a local Ollama model.

See decoder/llm/ollama_client.py for why Ollama (no API key, no cloud
egress) and decoder/verify/entailment.py for the isolation rule this output
eventually gets checked against — the draft produced here is NEVER shown to
a user directly (docs/HANDOVER.md §5's "no fast path" rule); it only ever
feeds decoder.verify.decompose (still a stub) or, for now, a caller that
manually wraps it into an AtomicClaim for entailment checking (see
tests/reason/test_ollama_drafter.py for a real end-to-end example against
the starter corpus).

Prompt is deliberately instructed to answer ONLY from the given passages and
say so explicitly when they don't answer the question — this is what makes
"the passages don't say this" a valid, expected drafter output rather than
something decompose/entailment has to catch after the fact. It doesn't
replace verification (a model can still misreport what a passage says), but
it reduces how often ungrounded claims get drafted in the first place.
"""

from __future__ import annotations

from decoder.llm.interface import LLMClient
from decoder.retrieve.interfaces import RetrievedSpan

# Wording is exactly as validated by hand against the real corpus and a
# live model (2026-09-14) — the string value below is identical to that
# tested text; it's only split across shorter source lines (adjacent string
# literals concatenate automatically) to satisfy the line-length lint
# without inserting characters into the actual prompt.
_SYSTEM_PROMPT = (
    "You are a careful document analyst. You will be given a QUESTION and "
    "one or more PASSAGES from an insurance policy document.\n\n"
    "Answer the question using ONLY information literally stated in the "
    "passages. Do not use outside knowledge of how insurance typically "
    "works. If the passages do not answer the question, say clearly that "
    "the documents do not state this.\n\n"
    "Be concise and factual — state exactly what the passage says, citing "
    "the specific figures or terms verbatim."
)


class OllamaDrafter:
    def __init__(self, llm: LLMClient, model: str = "qwen2.5-coder:7b") -> None:
        self._llm = llm
        self._model = model

    def draft(self, situation: str, evidence: list[RetrievedSpan]) -> str:
        passages = "\n\n".join(
            f"PASSAGE {i}: {item.span.text}" for i, item in enumerate(evidence, start=1)
        )
        prompt = f"QUESTION: {situation}\n\n{passages}" if passages else f"QUESTION: {situation}"
        return self._llm.generate(prompt=prompt, system=_SYSTEM_PROMPT, model=self._model)
