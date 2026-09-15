"""EvalCase — one annotated (document, situation) pair with a human-decided
expected outcome, for the annotated eval set docs/HANDOVER.md §11/§12
requires (M0's DoD: "30 annotated eval cases exist, of which ≥8 are
correctly-abstain cases").

Each case runs against a REAL document already in `corpus/raw/` through the
actual `decoder.orchestrator.PolicyDecoder.answer()` pipeline — never
free-standing text — because that is what §12's metrics (recall@k,
unsupported-claim rate, appropriate abstention) are meant to measure: real
retrieval, real drafting, real verification, real resolution.

Fact patterns (the numbers and dispute type — never quoted text) are drawn
from real adjudicated NCDRC/State Consumer Commission judgments where noted
in a case's `note` field (see docs/corpus/ncdrc-feasibility.md) — this
solves the structural problem that none of those judgments publish the
underlying policy PDF: instead of trying to reconstruct one, each case's
situation and expected outcome are independently written against a REAL
document this project already has, using the judgment only for a realistic
number and dispute shape (facts/ideas, not the judgment's own protected
expression).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from decoder.schema import SupportState


@dataclass(frozen=True)
class ExpectedOutcome:
    """One thing a human annotator decided the system must get right.

    `concerns` is a lowercase keyword/phrase expected to appear in the
    matching claim's rendered statement (decoder.respond.answer_assembly.
    render_claim_statement) — claim wording is drafted freely by an LLM and
    is not stable across model versions, so grading matches on topic, not
    on exact text, then checks that claim's resolved `state`.
    """

    concerns: str
    state: SupportState


@dataclass(frozen=True)
class EvalCase:
    id: str
    doc_id: str
    situation: str
    expected: tuple[ExpectedOutcome, ...] = ()
    provided_inputs: Mapping[str, object] = field(default_factory=dict)
    # Mirrors web/app.py's _run_analysis: the room-rent panel
    # (decoder.extract.room_rent_limit.analyze_room_rent) runs alongside
    # every situational question in the real system, not just room-rent
    # ones — so the runner always calls it, and these are None when a case
    # has no room tariff / sum insured to supply.
    room_tariff_per_day: float | None = None
    sum_insured: float | None = None
    # True when the documents genuinely cannot answer `situation` — the
    # correct system behavior is to abstain (NEEDS_INFORMATION /
    # INSUFFICIENT_EVIDENCE), never to fabricate a value. Used to count
    # M0's DoD ("≥8 correctly-abstain cases") and to grade the case even
    # when `expected` is empty (no specific claim to check, just: did the
    # system avoid answering).
    correctly_abstain: bool = False
    # Provenance, in this project's own words only — e.g. "numbers inspired
    # by Niraj Kajaria v. United India Insurance (W.B. State Commission,
    # 2017)" — never a quoted excerpt of the judgment or the ombudsman
    # award it might reference. See this module's own docstring for why.
    note: str = ""
