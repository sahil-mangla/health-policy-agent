"""DERIVED claim verification — docs/HANDOVER.md §7.2.

"DERIVED [claims are] executed in code. The inputs must themselves be
verified claims." No model call belongs here at all — this is meant to be
pure arithmetic once it's built. Blocked on decoder.reason not yet emitting a
structured "operation" representation for DERIVED claims (what arithmetic to
execute, and on which input claim values) — that has to be locked alongside
reason/'s output shape before this can be real code rather than an interface.
"""

from __future__ import annotations

from decoder.schema import AtomicClaim, EntailmentVerdict


def verify_derived_claim(claim: AtomicClaim) -> EntailmentVerdict:
    raise NotImplementedError(
        "TODO(M3 — Reasoning and verification): needs a structured "
        "arithmetic-operation representation on DERIVED claims, defined "
        "alongside decoder.reason's output shape; see docs/HANDOVER.md §7.1-7.2."
    )
