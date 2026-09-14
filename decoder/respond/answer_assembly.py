"""Answer assembly — docs/HANDOVER.md §5, §8.

The type signature here IS the enforcement mechanism for "nothing reaches
the user that has not passed through claim decomposition and support-state
resolution" (§5): this function only accepts `list[ResolvedClaim]`, and the
only function in this codebase that can construct a ResolvedClaim is
decoder.resolve.rules.resolve(). There is no way to build an Answer directly
from raw AtomicClaims or LLM output.
"""

from __future__ import annotations

from decoder.schema import Answer, ResolvedClaim


def assemble_answer(resolved_claims: list[ResolvedClaim]) -> Answer:
    raise NotImplementedError(
        "TODO(M4 — Resolution and response): once implemented, compute "
        "overall_state via decoder.resolve.rules.aggregate_answer_state("
        "[rc.state for rc in resolved_claims]) rather than reinventing "
        "aggregation here; see docs/HANDOVER.md §8 and §14 M4."
    )
