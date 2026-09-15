"""§7.2's `DOCUMENT_FACT`, numeric row: "Exact string match of the value in
the span. Code, not model." Pure string logic, no model involved."""

from __future__ import annotations

import pytest

from decoder.verify.numeric_check import numeric_value_appears_verbatim


@pytest.mark.parametrize(
    ("claim_value", "span_text"),
    [
        ("5%", "subject to a Co-payment of 5% applicable to claim amount"),
        # How Indian policy wording actually writes amounts — the "." here
        # is an abbreviation point, not a decimal separator.
        ("Rs.5000/-", "up to 2% of the sum insured subject to maximum of Rs.5000/-, per day"),
        ("5000", "maximum of Rs.5000/-, per day"),
        ("36 months", "excluded until the expiry of 36months of continuous coverage"),
        # Every number in a compound value must be present, and is here.
        ("2% of SI capped at 5000", "up to 2% of the sum insured subject to maximum of Rs.5000/-"),
    ],
)
def test_value_present_in_span_is_verbatim(claim_value: str, span_text: str) -> None:
    assert numeric_value_appears_verbatim(claim_value, span_text) is True


@pytest.mark.parametrize(
    ("claim_value", "span_text"),
    [
        # The whole point: a figure the span does not state.
        ("20%", "subject to a Co-payment of 5% applicable to claim amount"),
        # Must not match as a fragment of a larger number.
        ("5", "the limit is 1500 per day"),
        ("500", "the limit is 12,500 per day"),
        ("5000", "the factor is 1.5000 for this purpose"),
        # Strict about formatting, which fails safe: the claim is
        # downgraded to NEEDS_CONFIRMATION rather than wrongly promoted.
        ("5,000", "maximum of Rs.5000/- per day"),
        # One number present, the other absent — all must match.
        ("2% of SI capped at 7500", "up to 2% of the sum insured subject to maximum of Rs.5000/-"),
    ],
)
def test_value_absent_from_span_is_not_verbatim(claim_value: str, span_text: str) -> None:
    assert numeric_value_appears_verbatim(claim_value, span_text) is False


def test_value_with_no_number_is_never_verbatim() -> None:
    # A non-numeric value has nothing for this check to match; saying True
    # would assert a verification that never happened.
    room = "a single private AC room"
    assert numeric_value_appears_verbatim(room, room) is False
