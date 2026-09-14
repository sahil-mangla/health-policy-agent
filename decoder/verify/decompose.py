"""Atomic claim decomposition — docs/HANDOVER.md §7.1.

Splits a drafted answer (decoder.reason.ollama_drafter.OllamaDrafter's
output) into AtomicClaims, each with one subject, one predicate, one value.

Real implementation against a local Ollama model, with defensive parsing:
malformed lines are dropped, never guessed-and-kept. This matters more here
than almost anywhere else in the codebase — verified by hand (2026-09-14)
that this model reliably identifies claim boundaries and classifies
DOCUMENT_FACT/REGULATORY_FACT/INTERPRETATION claims, but is UNRELIABLE at
splitting a DERIVED claim's comparison into clean numeric operands (dropped
numbers, inconsistent field counts). Consequently:

- DOCUMENT_FACT / REGULATORY_FACT / INTERPRETATION claims from this
  decomposer are usable as-is (still subject to decoder.verify.entailment
  afterward, same as any other claim — decompose only identifies and
  classifies, it never grounds).
- DERIVED claims are classified but returned WITHOUT a derived_operation —
  decoder.verify.numeric_check.verify_derived_claim will refuse to verify
  them (raises MissingDerivedOperationError) until application code that
  already has the real operand values populates derived_operation
  directly. Decompose does not attempt this extraction; see
  decoder.schema.DerivedOperation's docstring for why.
"""

from __future__ import annotations

import re
import uuid

from decoder.llm.interface import LLMClient
from decoder.schema import AtomicClaim, ClaimClass

# Wording is exactly as validated by hand against a live model (2026-09-14)
# — split across shorter source lines only, same convention as
# decoder/reason/ollama_drafter.py and decoder/verify/entailment.py.
_SYSTEM_PROMPT = (
    "You split a draft answer about an insurance policy into ATOMIC "
    "CLAIMS — each with exactly one subject, one predicate, and one "
    "value, independently checkable as true or false.\n\n"
    "For each atomic claim, output exactly one line in this exact format "
    "(exactly 3 pipe characters per line, no more):\n"
    "CLAIM: <subject> | <predicate> | <value> | <class>\n\n"
    "<class> must be exactly one of: DOCUMENT_FACT, REGULATORY_FACT, "
    "DERIVED, INTERPRETATION\n\n"
    "Example input:\n"
    "The policy specifies a room-rent limit of INR 5,000 per day.\n\n"
    "Example output:\n"
    "CLAIM: the policy | specifies a room-rent limit of | INR 5,000 per "
    "day | DOCUMENT_FACT\n\n"
    "Keep the value field short (just the number/fact), and put any "
    "extra descriptive words into the predicate field instead. Output "
    "ONLY the CLAIM lines, nothing else."
)

_CLAIM_LINE_RE = re.compile(r"^CLAIM:\s*(.+)$", re.IGNORECASE)
_VALID_CLASSES = {c.value for c in ClaimClass}


def _parse_claim_line(line: str) -> AtomicClaim | None:
    """Returns None (dropped, not guessed-at) for any line that doesn't
    cleanly parse into exactly 4 pipe-separated fields with a recognized
    class — see this module's docstring for why silent leniency here is
    worse than dropping the claim."""
    match = _CLAIM_LINE_RE.match(line.strip())
    if not match:
        return None
    parts = [p.strip() for p in match.group(1).split("|")]
    if len(parts) != 4:
        return None
    subject, predicate, value, claim_class_word = parts
    if not subject or not predicate or not value:
        return None
    claim_class_word = claim_class_word.upper()
    if claim_class_word not in _VALID_CLASSES:
        return None

    return AtomicClaim(
        id=uuid.uuid4().hex[:12],
        subject=subject,
        predicate=predicate,
        value=value,
        claim_class=ClaimClass(claim_class_word),
        is_numeric=any(char.isdigit() for char in value),
        verbatim_match=False,  # decompose never checks grounding — entailment does
    )


class OllamaDecomposer:
    def __init__(self, llm: LLMClient, model: str = "qwen2.5-coder:7b") -> None:
        self._llm = llm
        self._model = model

    def decompose(self, draft_text: str) -> list[AtomicClaim]:
        raw_response = self._llm.generate(
            prompt=draft_text, system=_SYSTEM_PROMPT, model=self._model
        )
        claims = []
        for line in raw_response.splitlines():
            claim = _parse_claim_line(line)
            if claim is not None:
                claims.append(claim)
        return claims
