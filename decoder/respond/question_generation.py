"""Actionable-question generation — docs/HANDOVER.md §2 (F3), §8 UI mapping.

Questions must be derived from the actual gaps a resolved answer found
(NEEDS_INFORMATION's missing input, NEEDS_CONFIRMATION's uncertain claim,
INSUFFICIENT_EVIDENCE's absent field, CONFLICTING's disagreeing spans) — not
a generic template list.

The phrasing lives in decoder.respond.labels (§9.4); what makes each
question specific and answerable is that the claim or the named input it
came from is interpolated into it. A state with no gap — WELL_SUPPORTED —
produces no question at all, which is the point: the question list is the
gaps, so an empty list means there were none.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from decoder.respond.answer_assembly import missing_inputs
from decoder.respond.labels import QUESTION_TEMPLATES
from decoder.schema import ResolvedClaim, SupportState


def generate_follow_up_questions(
    resolved_claims: list[ResolvedClaim],
    provided_inputs: Mapping[str, object] | None = None,
) -> list[str]:
    provided = provided_inputs or {}
    questions: list[str] = []

    for required in missing_inputs(resolved_claims, provided):
        questions.append(
            QUESTION_TEMPLATES[SupportState.NEEDS_INFORMATION].format(
                input_name=required.name,
                input_description=required.description,
            )
        )

    for resolved in resolved_claims:
        template = QUESTION_TEMPLATES.get(resolved.state)
        if template is None or resolved.state == SupportState.NEEDS_INFORMATION:
            # WELL_SUPPORTED has no template (no gap to ask about), and
            # NEEDS_INFORMATION was already covered above by its named
            # input, which is more specific than the claim text.
            continue
        claim = resolved.claim
        questions.append(template.format(claim=f"{claim.subject} {claim.predicate} {claim.value}"))

    return _deduped(questions)


def _deduped(questions: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for question in questions:
        if question not in seen:
            seen.add(question)
            unique.append(question)
    return unique
