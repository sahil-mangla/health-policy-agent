"""Answer assembly — docs/HANDOVER.md §5, §8.

The type signature here IS the enforcement mechanism for "nothing reaches
the user that has not passed through claim decomposition and support-state
resolution" (§5): this function only accepts `list[ResolvedClaim]`, and the
only function in this codebase that can construct a ResolvedClaim is
decoder.resolve.rules.resolve(). There is no way to build an Answer directly
from raw AtomicClaims or LLM output.

That invariant is why `Answer.text` is rendered from the resolved claims
here rather than carrying the drafter's prose through: the draft is the one
piece of model output that never passed verification, so letting it reach
the reader would be exactly the "quick answer path that bypasses
verification" §5 forbids, however good it reads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from decoder.resolve.rules import aggregate_answer_state
from decoder.respond.labels import (
    EVIDENCE_PREFIX_CONTRADICTS,
    EVIDENCE_PREFIX_SUPPORTS,
    NO_CHECKABLE_CLAIMS_TEXT,
    SUPPORT_STATE_LABELS,
)
from decoder.schema import (
    Answer,
    EntailmentResult,
    EntailmentVerdict,
    RequiredInput,
    ResolvedClaim,
    SupportState,
)


def assemble_answer(
    resolved_claims: list[ResolvedClaim],
    provided_inputs: Mapping[str, object] | None = None,
) -> Answer:
    """`provided_inputs` is needed only to report which named inputs are
    still missing — resolve() already used it to decide the states, but a
    ResolvedClaim doesn't carry it, and reporting "depends on information
    we don't have" without naming that information would violate §8's
    requirement that the state come with its accompanying content."""
    provided = provided_inputs or {}
    return Answer(
        claims=resolved_claims,
        overall_state=aggregate_answer_state([rc.state for rc in resolved_claims]),
        text=render_answer_text(resolved_claims),
        missing_inputs=missing_inputs(resolved_claims, provided),
    )


def missing_inputs(
    resolved_claims: Sequence[ResolvedClaim],
    provided_inputs: Mapping[str, object],
) -> list[RequiredInput]:
    """Named inputs that claims depend on and nobody has supplied, deduped
    by name, in first-seen order."""
    seen: set[str] = set()
    missing: list[RequiredInput] = []
    for resolved in resolved_claims:
        if resolved.state != SupportState.NEEDS_INFORMATION:
            continue
        for required in resolved.claim.required_inputs:
            if required.name in provided_inputs or required.name in seen:
                continue
            seen.add(required.name)
            missing.append(required)
    return missing


def render_answer_text(resolved_claims: Sequence[ResolvedClaim]) -> str:
    """One block per claim: its §8 label, the claim itself, and the verbatim
    deciding words of every non-NEUTRAL verdict with the document and page
    they came from.

    Both supporting and contradicting evidence is rendered, never just the
    side that agrees — §8 requires a CONFLICTING claim to show "both spans,
    side by side, with which document each came from," and that is only
    possible if contradictions survive assembly.
    """
    if not resolved_claims:
        return NO_CHECKABLE_CLAIMS_TEXT

    blocks: list[str] = []
    for resolved in resolved_claims:
        claim = resolved.claim
        lines = [
            f"[{SUPPORT_STATE_LABELS[resolved.state]}] "
            f"{claim.subject} {claim.predicate} {claim.value}"
        ]
        lines.extend(
            f"    {_evidence_line(verdict)}"
            for verdict in resolved.verdicts
            if verdict.verdict != EntailmentVerdict.NEUTRAL
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _evidence_line(verdict: EntailmentResult) -> str:
    prefix = (
        EVIDENCE_PREFIX_SUPPORTS
        if verdict.verdict == EntailmentVerdict.SUPPORTS
        else EVIDENCE_PREFIX_CONTRADICTS
    )
    span = verdict.span
    return f'{prefix} {span.doc_id} (page {span.page}): "{verdict.deciding_quote}"'
