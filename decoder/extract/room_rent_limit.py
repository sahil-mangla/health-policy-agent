"""The hero scenario's arithmetic — docs/HANDOVER.md §4.

decoder.extract.regex_extractor already pulls the two numeric room-rent
components (percent-of-sum-insured, flat ₹/day) with real spans and a
code-checked verbatim_match. This module does the rest of §4: resolve
those into one eligible ₹/day limit (taking the minimum when both a
percent and a flat cap are stated — the real compound clause verified
against the corpus reads "up to 2% of the sum insured subject to maximum
of Rs.5000/-, per day", i.e. whichever bites first), then compare it
against the user's actual room tariff.

This exists because letting a drafter summarise a compound limit in prose
is exactly the failure caught by hand on 2026-09-15 (docs/HANDOVER.md's
M5 status note): asked for the room-rent limit, the system reported the
flat ₹5,000/day component and silently dropped that it only applies below
a ₹2.5L sum insured. The fix is computing the number in code from real
extracted operands, never trusting a model to have done the arithmetic
correctly in its own head.

Both claims this module builds skip the LLM entirely: the cap claim's
"evidence" IS the extraction's own span (a numeric DOCUMENT_FACT is
checked "in code, not model" per §7.2 — verbatim_match already did that
at extraction time), and the comparison claim's derived_operation is
built from real operand values, exactly as decoder.schema.DerivedOperation
requires. Both still go through decoder.resolve.rules.resolve() like any
other claim — nothing here bypasses resolution, it only skips a
redundant, riskier LLM round-trip to re-confirm what code already knows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from decoder.extract.regex_extractor import RegexFieldExtractor
from decoder.resolve.rules import resolve
from decoder.schema import (
    AtomicClaim,
    ClaimClass,
    DerivedOperation,
    EntailmentResult,
    EntailmentVerdict,
    ExtractedField,
    RequiredInput,
    ResolvedClaim,
    Span,
)
from decoder.verify.numeric_check import entailment_result_for_derived_claim

SUM_INSURED_INPUT = RequiredInput(
    name="sum_insured",
    value_type="int",
    description=(
        "Your policy's actual sum insured in ₹ — needed to convert a "
        "%-of-sum-insured room-rent cap into a ₹/day figure. This is "
        "chosen at purchase from the insurer's available options and "
        "isn't in the generic policy wording, only your personal "
        "Schedule."
    ),
)

ROOM_TARIFF_INPUT = RequiredInput(
    name="room_tariff_per_day",
    value_type="int",
    description=(
        "The hospital's actual (or expected) room charge in ₹ per day, "
        "to check it against your eligible limit."
    ),
)

_CAP_CLAIM_ID = "room_rent_cap"
_COMPARISON_CLAIM_ID = "room_rent_comparison"


@dataclass(frozen=True)
class RoomRentLimitFinding:
    """What the document states about the room-rent cap, and the ₹/day
    number that follows from it — None when that number can't be computed
    yet, distinguished by `needs_sum_insured`."""

    basis: str  # "NO_CAP_STATED" | "FLAT_AMOUNT" | "PERCENT_OF_SI" | "COMPOUND_MIN"
    percent_value: float | None
    flat_value: float | None
    eligible_limit_per_day: float | None
    needs_sum_insured: bool
    contributing_fields: list[ExtractedField] = field(default_factory=list)


def compute_room_rent_limit(
    percent_field: ExtractedField,
    flat_field: ExtractedField,
    sum_insured: float | None,
) -> RoomRentLimitFinding:
    has_percent = isinstance(percent_field.value, (int, float))
    has_flat = isinstance(flat_field.value, (int, float))
    contributing = [
        f for f, present in ((percent_field, has_percent), (flat_field, has_flat)) if present
    ]

    if not has_percent and not has_flat:
        return RoomRentLimitFinding(
            basis="NO_CAP_STATED",
            percent_value=None,
            flat_value=None,
            eligible_limit_per_day=None,
            needs_sum_insured=False,
        )

    basis = (
        "COMPOUND_MIN"
        if has_percent and has_flat
        else ("PERCENT_OF_SI" if has_percent else "FLAT_AMOUNT")
    )
    percent_value = float(percent_field.value) if has_percent else None  # type: ignore[arg-type]
    flat_value = float(flat_field.value) if has_flat else None  # type: ignore[arg-type]

    if has_percent and sum_insured is None:
        # The %-of-SI component can't be turned into a ₹ figure without
        # knowing the actual sum insured — never guess a "typical" SI (§1,
        # §16). If a flat cap ALSO exists, its ₹ number is still known
        # on its own, but the true eligible limit is the minimum of the
        # two, which isn't knowable until the percent side is too.
        return RoomRentLimitFinding(
            basis=basis,
            percent_value=percent_value,
            flat_value=flat_value,
            eligible_limit_per_day=None,
            needs_sum_insured=True,
            contributing_fields=contributing,
        )

    candidates: list[float] = []
    if percent_value is not None:
        assert sum_insured is not None  # guaranteed by the branch above
        candidates.append(percent_value / 100 * float(sum_insured))
    if flat_value is not None:
        candidates.append(flat_value)

    return RoomRentLimitFinding(
        basis=basis,
        percent_value=percent_value,
        flat_value=flat_value,
        eligible_limit_per_day=min(candidates),
        needs_sum_insured=False,
        contributing_fields=contributing,
    )


def _describe_basis(finding: RoomRentLimitFinding) -> str:
    parts = []
    if finding.percent_value is not None:
        if finding.needs_sum_insured:
            parts.append(f"{finding.percent_value:g}% of your sum insured per day")
        else:
            parts.append(f"{finding.percent_value:g}% of sum insured")
    if finding.flat_value is not None:
        parts.append(f"₹{finding.flat_value:,.0f}/day")
    description = f"{parts[0]} or {parts[1]}, whichever is lower" if len(parts) == 2 else parts[0]
    if finding.eligible_limit_per_day is not None:
        return f"{description} — ₹{finding.eligible_limit_per_day:,.0f}/day at your sum insured"
    return description


def _unique_spans(fields: list[ExtractedField]) -> list[Span]:
    seen: dict[str, Span] = {}
    for extracted in fields:
        for span in extracted.spans:
            seen.setdefault(span.id, span)
    return list(seen.values())


def build_cap_claim(finding: RoomRentLimitFinding) -> ResolvedClaim:
    """Always constructible — including the "no cap" case, which §4's own
    warning treats as a fact worth stating explicitly ("Do not hardcode a
    default carve-out list" applies just as much to a room-rent cap: a
    document with no stated limit is not the same as one that confirms
    unlimited room eligibility)."""
    if finding.basis == "NO_CAP_STATED":
        claim = AtomicClaim(
            id=_CAP_CLAIM_ID,
            subject="This policy",
            predicate="states a numeric room-rent eligibility limit",
            value=None,
            claim_class=ClaimClass.DOCUMENT_FACT,
            is_numeric=False,
            verbatim_match=False,
        )
        verdicts: list[EntailmentResult] = []
    else:
        required = [SUM_INSURED_INPUT] if finding.needs_sum_insured else []
        claim = AtomicClaim(
            id=_CAP_CLAIM_ID,
            subject="Your room-rent eligibility",
            predicate="is capped at",
            value=_describe_basis(finding),
            claim_class=ClaimClass.DOCUMENT_FACT,
            is_numeric=False,
            # The extraction's own verbatim_match already confirmed each
            # contributing field's value literally appears in its span
            # (§6) — re-asserted True here rather than re-run, not
            # guessed.
            verbatim_match=True,
            required_inputs=required,
        )
        verdicts = [
            EntailmentResult(
                claim_id=claim.id,
                span=span,
                verdict=EntailmentVerdict.SUPPORTS,
                deciding_quote=span.text,
            )
            for span in _unique_spans(finding.contributing_fields)
        ]

    state = resolve(
        claim=claim,
        verdicts=verdicts,
        required_inputs=claim.required_inputs,
        provided_inputs={},
    )
    return ResolvedClaim(claim=claim, verdicts=verdicts, state=state)


def build_comparison_claim(
    eligible_limit_per_day: float, room_tariff_per_day: float
) -> ResolvedClaim:
    """Only meaningful once both operands are real numbers — callers
    should not construct this while either is missing (see
    analyze_room_rent, which gates on exactly that).

    `value` is fixed to True and the operator is chosen so that it's the
    comparison that actually holds — never varies with the outcome — so
    the predicate itself carries the direction. See
    decoder.respond.answer_assembly.render_claim_statement for why: a
    DERIVED claim's predicate is written as a complete sentence, and
    appending a raw boolean to it would be redundant and unreadable.
    """
    exceeds = room_tariff_per_day > eligible_limit_per_day
    if exceeds:
        operator = "GREATER_THAN"
        predicate = (
            f"exceeds your eligible room-rent limit of ₹{eligible_limit_per_day:,.0f}/day "
            "— proportionate deduction on associated medical expenses applies to the excess"
        )
    else:
        operator = "LESS_OR_EQUAL"
        predicate = (
            f"is within your eligible room-rent limit of ₹{eligible_limit_per_day:,.0f}/day "
            "— no proportionate deduction applies"
        )

    claim = AtomicClaim(
        id=_COMPARISON_CLAIM_ID,
        subject=f"Your room tariff of ₹{room_tariff_per_day:,.0f}/day",
        predicate=predicate,
        value=True,
        claim_class=ClaimClass.DERIVED,
        is_numeric=False,
        verbatim_match=True,
        derived_operation=DerivedOperation(
            operator=operator,
            left_operand=room_tariff_per_day,
            right_operand=eligible_limit_per_day,
        ),
    )
    verdict = entailment_result_for_derived_claim(claim)
    state = resolve(claim=claim, verdicts=[verdict], required_inputs=[], provided_inputs={})
    return ResolvedClaim(claim=claim, verdicts=[verdict], state=state)


def compute_deduction_ratio(
    eligible_limit_per_day: float, room_tariff_per_day: float
) -> float | None:
    """§4 point 3: "compute the deduction ratio and show the arithmetic
    explicitly." Returns None when the tariff doesn't exceed the limit —
    there is no deduction to show a ratio for."""
    if room_tariff_per_day <= eligible_limit_per_day or room_tariff_per_day <= 0:
        return None
    return eligible_limit_per_day / room_tariff_per_day


@dataclass(frozen=True)
class RoomRentAnalysis:
    cap_claim: ResolvedClaim
    comparison_claim: ResolvedClaim | None
    deduction_ratio: float | None
    eligible_limit_per_day: float | None
    room_tariff_per_day: float | None


def analyze_room_rent(
    spans: list[Span],
    room_tariff_per_day: float | None,
    sum_insured: float | None,
) -> RoomRentAnalysis:
    """The single entry point web/app.py calls: given a document's spans
    plus whatever the user supplied, runs the whole §4 computation and
    returns everything the UI needs to show it. Cheap and deterministic —
    no LLM call — so callers can run it unconditionally alongside whatever
    situational question the user actually asked."""
    extractor = RegexFieldExtractor()
    percent_field = extractor.extract("room_rent_percent_of_si_per_day", spans)
    flat_field = extractor.extract("room_rent_max_amount_per_day", spans)
    finding = compute_room_rent_limit(percent_field, flat_field, sum_insured)
    cap_claim = build_cap_claim(finding)

    comparison_claim = None
    deduction_ratio = None
    if finding.eligible_limit_per_day is not None and room_tariff_per_day is not None:
        comparison_claim = build_comparison_claim(
            finding.eligible_limit_per_day, room_tariff_per_day
        )
        deduction_ratio = compute_deduction_ratio(
            finding.eligible_limit_per_day, room_tariff_per_day
        )

    return RoomRentAnalysis(
        cap_claim=cap_claim,
        comparison_claim=comparison_claim,
        deduction_ratio=deduction_ratio,
        eligible_limit_per_day=finding.eligible_limit_per_day,
        room_tariff_per_day=room_tariff_per_day,
    )
