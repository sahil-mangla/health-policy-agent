"""Exhaustive branch coverage for decoder.resolve.rules, per the handover
spec's target of 100% branch coverage on resolve/ (docs/HANDOVER.md §14 M4).
Each test below corresponds to exactly one branch of resolve()."""

from __future__ import annotations

import pytest

from decoder.resolve.rules import aggregate_answer_state, resolve
from decoder.schema import (
    AtomicClaim,
    ClaimClass,
    EntailmentResult,
    EntailmentVerdict,
    RequiredInput,
    Span,
    SupportState,
)


def _span(span_id: str = "s1", text: str = "the room rent limit is INR 5,000 per day") -> Span:
    return Span(
        id=span_id, doc_id="policy-001", page=1, char_start=0, char_end=len(text), text=text
    )


def _verdict(verdict: EntailmentVerdict, span_id: str = "s1") -> EntailmentResult:
    return EntailmentResult(claim_id="c1", span=_span(span_id), verdict=verdict)


def _claim(
    claim_class: ClaimClass = ClaimClass.DOCUMENT_FACT,
    is_numeric: bool = False,
    verbatim_match: bool = True,
    required_inputs: list[RequiredInput] | None = None,
) -> AtomicClaim:
    return AtomicClaim(
        id="c1",
        subject="policy",
        predicate="has room rent limit",
        value=5000,
        claim_class=claim_class,
        is_numeric=is_numeric,
        verbatim_match=verbatim_match,
        required_inputs=required_inputs or [],
    )


def test_supports_and_contradicts_is_conflicting() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS), _verdict(EntailmentVerdict.CONTRADICTS)]
    assert resolve(_claim(), verdicts, [], {}) == SupportState.CONFLICTING


def test_contradicts_only_is_conflicting() -> None:
    verdicts = [_verdict(EntailmentVerdict.CONTRADICTS)]
    assert resolve(_claim(), verdicts, [], {}) == SupportState.CONFLICTING


def test_no_supports_at_all_is_insufficient_evidence() -> None:
    verdicts = [_verdict(EntailmentVerdict.NEUTRAL)]
    assert resolve(_claim(), verdicts, [], {}) == SupportState.INSUFFICIENT_EVIDENCE


def test_empty_verdicts_is_insufficient_evidence() -> None:
    assert resolve(_claim(), [], [], {}) == SupportState.INSUFFICIENT_EVIDENCE


def test_missing_required_input_is_needs_information() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    required = [RequiredInput(name="continuity_date", value_type="date", description="d")]
    assert resolve(_claim(), verdicts, required, {}) == SupportState.NEEDS_INFORMATION


def test_provided_required_input_does_not_block() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    required = [RequiredInput(name="continuity_date", value_type="date", description="d")]
    provided = {"continuity_date": "2020-01-01"}
    assert resolve(_claim(), verdicts, required, provided) == SupportState.WELL_SUPPORTED


def test_interpretation_claim_caps_at_needs_confirmation() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.INTERPRETATION)
    assert resolve(claim, verdicts, [], {}) == SupportState.NEEDS_CONFIRMATION


def test_numeric_document_fact_without_verbatim_match_needs_confirmation() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DOCUMENT_FACT, is_numeric=True, verbatim_match=False)
    assert resolve(claim, verdicts, [], {}) == SupportState.NEEDS_CONFIRMATION


def test_numeric_document_fact_with_verbatim_match_is_well_supported() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DOCUMENT_FACT, is_numeric=True, verbatim_match=True)
    assert resolve(claim, verdicts, [], {}) == SupportState.WELL_SUPPORTED


def test_non_numeric_document_fact_is_well_supported() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DOCUMENT_FACT, is_numeric=False, verbatim_match=False)
    assert resolve(claim, verdicts, [], {}) == SupportState.WELL_SUPPORTED


def test_derived_claim_with_weak_input_needs_confirmation() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DERIVED)
    input_states = [SupportState.WELL_SUPPORTED, SupportState.NEEDS_CONFIRMATION]
    assert resolve(claim, verdicts, [], {}, input_states) == SupportState.NEEDS_CONFIRMATION


def test_derived_claim_with_all_well_supported_inputs_is_well_supported() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DERIVED)
    input_states = [SupportState.WELL_SUPPORTED, SupportState.WELL_SUPPORTED]
    assert resolve(claim, verdicts, [], {}, input_states) == SupportState.WELL_SUPPORTED


def test_derived_claim_with_no_input_states_is_well_supported() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.DERIVED)
    assert resolve(claim, verdicts, [], {}) == SupportState.WELL_SUPPORTED


def test_regulatory_fact_happy_path_is_well_supported() -> None:
    verdicts = [_verdict(EntailmentVerdict.SUPPORTS)]
    claim = _claim(claim_class=ClaimClass.REGULATORY_FACT)
    assert resolve(claim, verdicts, [], {}) == SupportState.WELL_SUPPORTED


class TestAggregateAnswerState:
    def test_empty_claim_states_is_insufficient_evidence(self) -> None:
        assert aggregate_answer_state([]) == SupportState.INSUFFICIENT_EVIDENCE

    def test_all_well_supported_is_well_supported(self) -> None:
        states = [SupportState.WELL_SUPPORTED, SupportState.WELL_SUPPORTED]
        assert aggregate_answer_state(states) == SupportState.WELL_SUPPORTED

    @pytest.mark.parametrize(
        ("states", "expected"),
        [
            (
                [SupportState.WELL_SUPPORTED, SupportState.NEEDS_CONFIRMATION],
                SupportState.NEEDS_CONFIRMATION,
            ),
            (
                [SupportState.NEEDS_CONFIRMATION, SupportState.NEEDS_INFORMATION],
                SupportState.NEEDS_INFORMATION,
            ),
            (
                [SupportState.NEEDS_INFORMATION, SupportState.INSUFFICIENT_EVIDENCE],
                SupportState.INSUFFICIENT_EVIDENCE,
            ),
            (
                [SupportState.INSUFFICIENT_EVIDENCE, SupportState.CONFLICTING],
                SupportState.CONFLICTING,
            ),
            (
                [SupportState.WELL_SUPPORTED, SupportState.CONFLICTING],
                SupportState.CONFLICTING,
            ),
            (
                [SupportState.CONFLICTING, SupportState.CONFLICTING],
                SupportState.CONFLICTING,
            ),
        ],
    )
    def test_most_severe_state_wins(
        self, states: list[SupportState], expected: SupportState
    ) -> None:
        assert aggregate_answer_state(states) == expected
