"""Continuity-date requirement — docs/HANDOVER.md §9.3.

"The hero scenario and every waiting-period question depend on continuous
coverage across renewals, which a single uploaded PDF usually cannot
establish. Model continuity date as a first-class required input, not an
assumption. If it is absent, waiting-period claims are NEEDS_INFORMATION —
never WELL_SUPPORTED."

decoder.verify.decompose never sets AtomicClaim.required_inputs — it only
identifies and classifies claims, per its own docstring. This module is the
missing link: run after decompose(), it scans each claim's own text for
waiting-period / pre-existing-disease language and attaches
CONTINUITY_DATE to anything that matches.

Deliberately keyword-based, not another model call: the signal is a
handful of stable English terms that show up in decompose's own claim
phrasing regardless of which document produced it, and a model call here
would add cost, latency, and a new failure surface for something a regex
already does reliably.
"""

from __future__ import annotations

import re

from decoder.schema import AtomicClaim, RequiredInput

CONTINUITY_DATE = RequiredInput(
    name="continuity_date",
    value_type="date",
    description=(
        "The date your health cover first began, continuous through every "
        "renewal since (no lapse or gap). Waiting periods count from this "
        "date, not from when this particular document was issued — a "
        "policy renewed every year for five years already cleared a "
        "4-year pre-existing-disease wait, even though this wording was "
        "only issued this year."
    ),
)

_WAITING_PERIOD_RE = re.compile(r"waiting\s+period|pre-?existing|\bped\b", re.IGNORECASE)


def attach_continuity_requirement(claims: list[AtomicClaim]) -> list[AtomicClaim]:
    """Returns a new list, same order: any claim whose subject, predicate,
    or value mentions a waiting period or pre-existing-disease exclusion
    carries CONTINUITY_DATE in its required_inputs, added to whatever is
    already there. A claim that already lists it is left untouched rather
    than duplicated.

    Deliberately does not distinguish DOCUMENT_FACT from DERIVED here —
    both mention the same words when they're about a waiting period, and
    resolve()'s required_inputs check applies uniformly to any claim
    class.
    """
    updated: list[AtomicClaim] = []
    for claim in claims:
        text = f"{claim.subject} {claim.predicate} {claim.value}"
        already_present = any(r.name == CONTINUITY_DATE.name for r in claim.required_inputs)
        if _WAITING_PERIOD_RE.search(text) and not already_present:
            updated.append(
                claim.model_copy(
                    update={"required_inputs": [*claim.required_inputs, CONTINUITY_DATE]}
                )
            )
        else:
            updated.append(claim)
    return updated
