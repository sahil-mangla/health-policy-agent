"""Atomic claim decomposition — docs/HANDOVER.md §7.1.

Splits a drafted answer into AtomicClaims, each with one subject, one
predicate, one value. Blocked on decoder/reason/'s output shape not being
fixed yet (M3).
"""

from __future__ import annotations

from decoder.schema import AtomicClaim


def decompose_into_claims(draft_text: str) -> list[AtomicClaim]:
    raise NotImplementedError(
        "TODO(M3 — Reasoning and verification): needs decoder.reason's "
        "drafter output format to be fixed first; see docs/HANDOVER.md §7.1 "
        "and §14 M3."
    )
