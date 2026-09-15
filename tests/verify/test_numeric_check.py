from __future__ import annotations

import pytest

from decoder.resolve.rules import resolve
from decoder.schema import (
    AtomicClaim,
    ClaimClass,
    DerivedOperation,
    EntailmentVerdict,
    SupportState,
)
from decoder.verify.numeric_check import (
    MissingDerivedOperationError,
    entailment_result_for_derived_claim,
    render_operation_text,
    verify_derived_claim,
)


def _derived_claim(operator: str, left: float, right: float, asserted: bool) -> AtomicClaim:
    return AtomicClaim(
        id="c1",
        subject="the room tariff",
        predicate="exceeds the eligible limit",
        value=asserted,
        claim_class=ClaimClass.DERIVED,
        is_numeric=True,
        verbatim_match=False,
        derived_operation=DerivedOperation(
            operator=operator, left_operand=left, right_operand=right
        ),
    )


@pytest.mark.parametrize(
    ("operator", "left", "right", "expected_computed"),
    [
        ("GREATER_THAN", 8000, 5000, True),
        ("GREATER_THAN", 3000, 5000, False),
        ("LESS_THAN", 3000, 5000, True),
        ("LESS_THAN", 8000, 5000, False),
        ("GREATER_OR_EQUAL", 5000, 5000, True),
        ("LESS_OR_EQUAL", 5000, 5000, True),
        ("EQUAL", 5000, 5000, True),
        ("EQUAL", 5000, 5001, False),
    ],
)
def test_correctly_asserted_claim_is_supports(
    operator: str, left: float, right: float, expected_computed: bool
) -> None:
    # The hero scenario's own example (§4/§7.1): a room at ₹8,000/day
    # exceeds the ₹5,000/day eligible limit — asserted correctly here.
    claim = _derived_claim(operator, left, right, asserted=expected_computed)
    assert verify_derived_claim(claim) == EntailmentVerdict.SUPPORTS


def test_wrongly_asserted_claim_is_contradicts() -> None:
    # 8000 > 5000 is True, but the claim asserts False.
    claim = _derived_claim("GREATER_THAN", 8000, 5000, asserted=False)
    assert verify_derived_claim(claim) == EntailmentVerdict.CONTRADICTS


def test_missing_derived_operation_raises() -> None:
    claim = AtomicClaim(
        id="c1",
        subject="x",
        predicate="y",
        value=True,
        claim_class=ClaimClass.DERIVED,
        is_numeric=True,
        verbatim_match=False,
    )
    with pytest.raises(MissingDerivedOperationError):
        verify_derived_claim(claim)


def test_entailment_result_for_derived_claim_raises_not_asserts_when_operation_missing() -> None:
    # Regression: entailment_result_for_derived_claim used to carry its own
    # premature `assert claim.derived_operation is not None` ahead of
    # calling verify_derived_claim, which shadowed the documented
    # MissingDerivedOperationError with a bare, undocumented
    # AssertionError — found 2026-09-15 by decoder.eval actually driving a
    # live model against real documents (decompose can legitimately
    # classify a drafted claim DERIVED without extractable operands from
    # free text, per its own module docstring), which crashed
    # decoder.orchestrator.PolicyDecoder.answer() entirely instead of
    # reaching the caller's exception handler.
    claim = AtomicClaim(
        id="c1",
        subject="x",
        predicate="y",
        value=True,
        claim_class=ClaimClass.DERIVED,
        is_numeric=True,
        verbatim_match=False,
    )
    with pytest.raises(MissingDerivedOperationError):
        entailment_result_for_derived_claim(claim)


def test_non_bool_value_raises() -> None:
    claim = AtomicClaim(
        id="c1",
        subject="x",
        predicate="y",
        value="8000",  # a raw number, not an asserted comparison result
        claim_class=ClaimClass.DERIVED,
        is_numeric=True,
        verbatim_match=False,
        derived_operation=DerivedOperation(
            operator="GREATER_THAN", left_operand=8000, right_operand=5000
        ),
    )
    with pytest.raises(MissingDerivedOperationError):
        verify_derived_claim(claim)


def test_render_operation_text() -> None:
    op = DerivedOperation(operator="GREATER_THAN", left_operand=8000, right_operand=5000)
    assert render_operation_text(op) == "8000.0 > 5000.0"


def test_entailment_result_wraps_verdict_with_synthetic_span() -> None:
    claim = _derived_claim("GREATER_THAN", 8000, 5000, asserted=True)
    result = entailment_result_for_derived_claim(claim)
    assert result.verdict == EntailmentVerdict.SUPPORTS
    assert result.span.doc_id == "__computed__"
    assert result.deciding_quote == "8000.0 > 5000.0"


def test_derived_claim_feeds_resolve_to_well_supported() -> None:
    # End-to-end: the hero scenario's derived claim, verified in code, feeds
    # decoder.resolve.rules.resolve() the same way a document-grounded
    # claim would.
    claim = _derived_claim("GREATER_THAN", 8000, 5000, asserted=True)
    result = entailment_result_for_derived_claim(claim)
    state = resolve(claim, [result], required_inputs=[], provided_inputs={})
    assert state == SupportState.WELL_SUPPORTED


def test_contradicted_derived_claim_feeds_resolve_to_conflicting() -> None:
    claim = _derived_claim("GREATER_THAN", 8000, 5000, asserted=False)
    result = entailment_result_for_derived_claim(claim)
    state = resolve(claim, [result], required_inputs=[], provided_inputs={})
    assert state == SupportState.CONFLICTING
