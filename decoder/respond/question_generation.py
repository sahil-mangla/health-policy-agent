"""Actionable-question generation — docs/HANDOVER.md §2 (F3), §8 UI mapping.

Questions must be derived from the actual gaps a resolved answer found
(NEEDS_INFORMATION's missing input, NEEDS_CONFIRMATION's uncertain claim,
INSUFFICIENT_EVIDENCE's absent field, CONFLICTING's disagreeing spans) — not
a generic template list. Blocked on §14 M4's UI-state content requirements
being implemented alongside answer_assembly.
"""

from __future__ import annotations

from decoder.schema import ResolvedClaim


def generate_follow_up_questions(resolved_claims: list[ResolvedClaim]) -> list[str]:
    raise NotImplementedError(
        "TODO(M4 — Resolution and response): question templates per "
        "SupportState are not designed yet; see docs/HANDOVER.md §8 UI "
        "mapping table and §14 M4."
    )
