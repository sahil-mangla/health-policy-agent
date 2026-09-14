"""Per-claim, isolated, single-span entailment checking — docs/HANDOVER.md §7.2.

The Entailer must see ONLY the claim and ONE span — never the draft answer,
the user's scenario, or other claims. This isolation is what stops the model
rubber-stamping ("is this analysis correct?" is unfalsifiable). The
constraint is expressed here at the signature level (check() takes exactly
claim + span, nothing else), not just in a docstring, so a future
implementation cannot accidentally widen the context it sees.

Model choice for this role is open (SPIKE-5, docs/HANDOVER.md §15) — the
verifier arguably should be a cheaper/dumber model than the drafter, and
should not be hardcoded to match it.
"""

from __future__ import annotations

from typing import Protocol

from decoder.schema import AtomicClaim, EntailmentResult, Span


class Entailer(Protocol):
    def check(self, claim: AtomicClaim, span: Span) -> EntailmentResult:
        """Must return a verdict plus a deciding_quote; callers should pass
        the result through decoder.verify.span_containment.enforce_hallucination_trap
        before trusting it."""
        ...


class StubEntailer:
    """No real implementation yet — blocked on SPIKE-5 (verifier model
    choice) and on decoder.llm having a working concrete client."""

    def check(self, claim: AtomicClaim, span: Span) -> EntailmentResult:
        raise NotImplementedError(
            "TODO(M3 — Reasoning and verification, SPIKE-5): needs a "
            "decoder.llm.LLMClient implementation and a decided verifier "
            "model; see docs/HANDOVER.md §7.2 and §15."
        )
