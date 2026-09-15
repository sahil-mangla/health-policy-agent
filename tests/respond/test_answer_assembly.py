"""Answer assembly and question generation — docs/HANDOVER.md §8.

Pure functions over already-resolved claims: no model, no I/O.
"""

from __future__ import annotations

from decoder.respond.answer_assembly import assemble_answer, render_answer_text
from decoder.respond.labels import NO_CHECKABLE_CLAIMS_TEXT, SUPPORT_STATE_LABELS
from decoder.respond.question_generation import generate_follow_up_questions
from decoder.schema import (
    AtomicClaim,
    ClaimClass,
    EntailmentResult,
    EntailmentVerdict,
    RequiredInput,
    ResolvedClaim,
    Span,
    SupportState,
)


def _span(text: str, doc_id: str = "policy", page: int = 3, span_id: str = "s1") -> Span:
    return Span(id=span_id, doc_id=doc_id, page=page, char_start=0, char_end=len(text), text=text)


def _claim(
    value: str = "5%",
    claim_class: ClaimClass = ClaimClass.DOCUMENT_FACT,
    required_inputs: list[RequiredInput] | None = None,
) -> AtomicClaim:
    return AtomicClaim(
        id="c1",
        subject="the policy",
        predicate="applies a co-payment of",
        value=value,
        claim_class=claim_class,
        is_numeric=True,
        verbatim_match=True,
        required_inputs=required_inputs or [],
    )


def _resolved(
    state: SupportState,
    verdicts: list[EntailmentResult] | None = None,
    claim: AtomicClaim | None = None,
) -> ResolvedClaim:
    return ResolvedClaim(claim=claim or _claim(), verdicts=verdicts or [], state=state)


def _verdict(verdict: EntailmentVerdict, quote: str, span: Span | None = None) -> EntailmentResult:
    return EntailmentResult(
        claim_id="c1",
        span=span or _span(f"... {quote} ..."),
        verdict=verdict,
        deciding_quote=quote,
    )


def test_overall_state_is_the_weakest_claim_not_an_average() -> None:
    answer = assemble_answer(
        [
            _resolved(SupportState.WELL_SUPPORTED),
            _resolved(SupportState.WELL_SUPPORTED),
            _resolved(SupportState.CONFLICTING),
        ]
    )
    assert answer.overall_state == SupportState.CONFLICTING


def test_every_claim_renders_with_its_state_label() -> None:
    text = render_answer_text([_resolved(SupportState.NEEDS_CONFIRMATION)])
    assert SUPPORT_STATE_LABELS[SupportState.NEEDS_CONFIRMATION] in text


def test_contradicting_evidence_survives_assembly() -> None:
    # §8 requires a CONFLICTING claim to show "both spans, side by side,
    # with which document each came from" — only possible if the
    # contradicting verdict isn't filtered out on the way to the reader.
    text = render_answer_text(
        [
            _resolved(
                SupportState.CONFLICTING,
                verdicts=[
                    _verdict(
                        EntailmentVerdict.SUPPORTS,
                        "Co-payment of 5%",
                        _span("Co-payment of 5%", doc_id="policy_wording", page=20),
                    ),
                    _verdict(
                        EntailmentVerdict.CONTRADICTS,
                        "Co-payment of 10%",
                        _span("Co-payment of 10%", doc_id="cis", page=2),
                    ),
                ],
            )
        ]
    )
    assert "Co-payment of 5%" in text
    assert "Co-payment of 10%" in text
    assert "policy_wording" in text
    assert "cis" in text


def test_neutral_verdicts_are_not_rendered_as_evidence() -> None:
    text = render_answer_text(
        [
            _resolved(
                SupportState.INSUFFICIENT_EVIDENCE,
                verdicts=[
                    EntailmentResult(
                        claim_id="c1",
                        span=_span("something unrelated about grace periods"),
                        verdict=EntailmentVerdict.NEUTRAL,
                        deciding_quote=None,
                    )
                ],
            )
        ]
    )
    assert "grace periods" not in text
    assert "None" not in text


def test_no_claims_still_produces_an_answer_never_a_refusal() -> None:
    # §8: "Never refuse outright. Every state produces an answer."
    answer = assemble_answer([])
    assert answer.overall_state == SupportState.INSUFFICIENT_EVIDENCE
    assert answer.text == NO_CHECKABLE_CLAIMS_TEXT


def test_missing_inputs_are_named_not_just_counted() -> None:
    required = RequiredInput(
        name="continuity_date",
        value_type="date",
        description="the date your cover first began, unbroken through renewals",
    )
    answer = assemble_answer(
        [_resolved(SupportState.NEEDS_INFORMATION, claim=_claim(required_inputs=[required]))]
    )
    assert answer.missing_inputs == [required]


def test_provided_inputs_are_not_reported_missing() -> None:
    required = RequiredInput(name="room_tariff", value_type="int", description="₹/day")
    answer = assemble_answer(
        [_resolved(SupportState.NEEDS_INFORMATION, claim=_claim(required_inputs=[required]))],
        provided_inputs={"room_tariff": 8000},
    )
    assert answer.missing_inputs == []


def test_questions_are_derived_from_actual_gaps() -> None:
    questions = generate_follow_up_questions(
        [
            _resolved(SupportState.WELL_SUPPORTED),
            _resolved(SupportState.INSUFFICIENT_EVIDENCE),
        ]
    )
    # The supported claim contributes nothing; the gap contributes a
    # question naming what was actually claimed.
    assert len(questions) == 1
    assert "applies a co-payment of" in questions[0]


def test_well_supported_answer_generates_no_questions() -> None:
    assert generate_follow_up_questions([_resolved(SupportState.WELL_SUPPORTED)]) == []


def test_needs_information_asks_for_the_named_input() -> None:
    required = RequiredInput(
        name="room_tariff",
        value_type="int",
        description="the per-day room rent the hospital actually charges",
    )
    questions = generate_follow_up_questions(
        [_resolved(SupportState.NEEDS_INFORMATION, claim=_claim(required_inputs=[required]))]
    )
    assert len(questions) == 1
    assert "room_tariff" in questions[0]
    assert "the per-day room rent the hospital actually charges" in questions[0]
