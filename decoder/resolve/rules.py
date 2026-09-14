"""Support state resolution — docs/HANDOVER.md §8. LOCKED.

Pure functions only. No model calls, no I/O, no thresholds, no floats. This
is the part of the system a skeptic will interrogate hardest, so it must stay
fully unit-testable without any external dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from decoder.schema import (
    AtomicClaim,
    ClaimClass,
    EntailmentResult,
    EntailmentVerdict,
    RequiredInput,
    SupportState,
)


def resolve(
    claim: AtomicClaim,
    verdicts: Sequence[EntailmentResult],
    required_inputs: Sequence[RequiredInput],
    provided_inputs: Mapping[str, object],
    input_claim_states: Sequence[SupportState] = (),
) -> SupportState:
    """Direct, branch-for-branch translation of the handover's locked
    pseudocode (§8).

    `input_claim_states` carries the already-resolved SupportStates of this
    claim's `input_claim_ids`, for the DERIVED branch — see the note on
    `AtomicClaim.input_claim_ids` in decoder/schema.py for why AtomicClaim
    itself cannot carry a live `.state`. The caller (eventually the
    orchestrator) is responsible for resolving a DERIVED claim's inputs
    first, in dependency order.
    """
    supports = [v for v in verdicts if v.verdict == EntailmentVerdict.SUPPORTS]
    contradicts = [v for v in verdicts if v.verdict == EntailmentVerdict.CONTRADICTS]

    if supports and contradicts:
        return SupportState.CONFLICTING
    if contradicts and not supports:
        return SupportState.CONFLICTING  # drafter asserted the opposite of the document
    if not supports:
        return SupportState.INSUFFICIENT_EVIDENCE

    missing = [r for r in required_inputs if r.name not in provided_inputs]
    if missing:
        return SupportState.NEEDS_INFORMATION

    if claim.claim_class == ClaimClass.INTERPRETATION:
        return SupportState.NEEDS_CONFIRMATION
    if (
        claim.claim_class == ClaimClass.DOCUMENT_FACT
        and claim.is_numeric
        and not claim.verbatim_match
    ):
        return SupportState.NEEDS_CONFIRMATION
    if claim.claim_class == ClaimClass.DERIVED and any(
        s != SupportState.WELL_SUPPORTED for s in input_claim_states
    ):
        return SupportState.NEEDS_CONFIRMATION  # derived results inherit the weakest input

    return SupportState.WELL_SUPPORTED


# Severity order for answer-level aggregation, most to least severe. The
# handover spec (§8) only says "answer-level state = the weakest state among
# its claims" and does not itself rank the four non-WELL_SUPPORTED states
# against each other — but this exact order is the reverse of the row order
# the spec's own §8 UI-mapping table already uses (WELL_SUPPORTED ->
# NEEDS_CONFIRMATION -> NEEDS_INFORMATION -> INSUFFICIENT_EVIDENCE ->
# CONFLICTING), so it is not an arbitrary choice.
_SEVERITY_ORDER: list[SupportState] = [
    SupportState.CONFLICTING,
    SupportState.INSUFFICIENT_EVIDENCE,
    SupportState.NEEDS_INFORMATION,
    SupportState.NEEDS_CONFIRMATION,
    SupportState.WELL_SUPPORTED,
]


def aggregate_answer_state(claim_states: Sequence[SupportState]) -> SupportState:
    """Answer-level state = the most severe state among its claims. No
    averaging (§8): a single CONFLICTING claim makes the whole answer
    CONFLICTING."""
    if not claim_states:
        return SupportState.INSUFFICIENT_EVIDENCE
    return min(claim_states, key=_SEVERITY_ORDER.index)
