from __future__ import annotations

from decoder.schema import EntailmentVerdict
from decoder.verify.span_containment import enforce_hallucination_trap, is_verbatim_in_span

SPAN_TEXT = "The eligible room rent limit is INR 5,000 per day for a single private AC room."


def test_quote_present_verbatim_is_unchanged() -> None:
    verdict, quote = enforce_hallucination_trap(
        EntailmentVerdict.SUPPORTS, "INR 5,000 per day", SPAN_TEXT
    )
    assert verdict == EntailmentVerdict.SUPPORTS
    assert quote == "INR 5,000 per day"


def test_quote_absent_forces_neutral_and_clears_quote() -> None:
    verdict, quote = enforce_hallucination_trap(
        EntailmentVerdict.SUPPORTS, "INR 10,000 per day", SPAN_TEXT
    )
    assert verdict == EntailmentVerdict.NEUTRAL
    assert quote is None


def test_none_quote_with_non_neutral_verdict_forces_neutral() -> None:
    verdict, quote = enforce_hallucination_trap(EntailmentVerdict.CONTRADICTS, None, SPAN_TEXT)
    assert verdict == EntailmentVerdict.NEUTRAL
    assert quote is None


def test_neutral_verdict_passes_through_regardless_of_quote() -> None:
    verdict, quote = enforce_hallucination_trap(
        EntailmentVerdict.NEUTRAL, "not present anywhere", SPAN_TEXT
    )
    assert verdict == EntailmentVerdict.NEUTRAL
    assert quote == "not present anywhere"


def test_containment_is_case_sensitive() -> None:
    assert is_verbatim_in_span("inr 5,000 per day", SPAN_TEXT) is False
    assert is_verbatim_in_span("INR 5,000 per day", SPAN_TEXT) is True


def test_empty_quote_is_never_considered_contained() -> None:
    assert is_verbatim_in_span("", SPAN_TEXT) is False
