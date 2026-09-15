"""The hero scenario's arithmetic — docs/HANDOVER.md §4. Pure logic tests
(compute_room_rent_limit, build_cap_claim, build_comparison_claim) plus a
real-corpus integration test against the actual Arogya Sanjeevani compound
clause (2% of SI, capped at ₹5,000/day) — the case that motivated this
module: a drafter once flattened it to just "₹5,000/day" and dropped that
it only binds below a ₹2.5L sum insured."""

from __future__ import annotations

from pathlib import Path

import pytest

from decoder.extract.room_rent_limit import (
    ROOM_TARIFF_INPUT,
    SUM_INSURED_INPUT,
    analyze_room_rent,
    build_cap_claim,
    build_comparison_claim,
    compute_deduction_ratio,
    compute_room_rent_limit,
)
from decoder.intake.segment import PdfSegmenter
from decoder.schema import ExtractedField, Span, SupportState

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"
BAJAJ_CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "bajaj_allianz"


def _field(field_name: str, value: float | None, spans: list[Span] | None = None) -> ExtractedField:
    return ExtractedField(
        field_name=field_name,
        value=value,
        spans=spans or [],
        extraction_method="REGEX",
        verbatim_match=value is not None,
    )


def _span(text: str, span_id: str = "s1") -> Span:
    return Span(id=span_id, doc_id="policy", page=7, char_start=0, char_end=len(text), text=text)


# --- compute_room_rent_limit -------------------------------------------------


def test_no_cap_stated() -> None:
    finding = compute_room_rent_limit(_field("pct", None), _field("flat", None), sum_insured=None)
    assert finding.basis == "NO_CAP_STATED"
    assert finding.eligible_limit_per_day is None
    assert finding.needs_sum_insured is False


def test_flat_only_needs_no_sum_insured() -> None:
    finding = compute_room_rent_limit(_field("pct", None), _field("flat", 5000.0), sum_insured=None)
    assert finding.basis == "FLAT_AMOUNT"
    assert finding.eligible_limit_per_day == 5000.0
    assert finding.needs_sum_insured is False


def test_percent_only_needs_sum_insured() -> None:
    finding = compute_room_rent_limit(_field("pct", 1.0), _field("flat", None), sum_insured=None)
    assert finding.basis == "PERCENT_OF_SI"
    assert finding.eligible_limit_per_day is None
    assert finding.needs_sum_insured is True


def test_percent_only_computes_once_sum_insured_given() -> None:
    finding = compute_room_rent_limit(
        _field("pct", 1.0), _field("flat", None), sum_insured=1_000_000
    )
    assert finding.eligible_limit_per_day == 10_000.0


def test_compound_takes_the_minimum() -> None:
    # The real Arogya Sanjeevani clause: 2% of SI, capped at ₹5,000/day.
    # At ₹1L sum insured, 2% is ₹2,000 — well under the flat cap, so THAT
    # is the binding number, not ₹5,000. This is exactly the case the
    # drafter got wrong in the live run this module exists to fix.
    finding = compute_room_rent_limit(
        _field("pct", 2.0), _field("flat", 5000.0), sum_insured=100_000
    )
    assert finding.basis == "COMPOUND_MIN"
    assert finding.eligible_limit_per_day == 2000.0


def test_compound_at_high_sum_insured_the_flat_cap_binds() -> None:
    # At ₹10L, 2% is ₹20,000 — now the flat ₹5,000 cap is what actually
    # binds, the opposite of the previous case with the same clause.
    finding = compute_room_rent_limit(
        _field("pct", 2.0), _field("flat", 5000.0), sum_insured=1_000_000
    )
    assert finding.eligible_limit_per_day == 5000.0


def test_compound_needs_sum_insured_even_though_flat_alone_is_known() -> None:
    # The flat ₹ figure is knowable without SI, but the TRUE eligible
    # limit (the minimum of the two) is not — must not silently fall
    # back to the flat number as if it were the answer.
    finding = compute_room_rent_limit(_field("pct", 2.0), _field("flat", 5000.0), sum_insured=None)
    assert finding.eligible_limit_per_day is None
    assert finding.needs_sum_insured is True
    assert finding.flat_value == 5000.0


# --- build_cap_claim ----------------------------------------------------------


def test_no_cap_claim_is_insufficient_evidence() -> None:
    finding = compute_room_rent_limit(_field("pct", None), _field("flat", None), sum_insured=None)
    resolved = build_cap_claim(finding)
    assert resolved.state == SupportState.INSUFFICIENT_EVIDENCE


def test_known_cap_claim_is_well_supported_with_real_span_evidence() -> None:
    span = _span("up to 2% of the sum insured subject to maximum of Rs.5000/-, per day")
    finding = compute_room_rent_limit(
        _field("pct", 2.0, spans=[span]), _field("flat", 5000.0, spans=[span]), sum_insured=100_000
    )
    resolved = build_cap_claim(finding)
    assert resolved.state == SupportState.WELL_SUPPORTED
    # Deduped: both fields point at the same span, so it must appear once.
    assert len(resolved.verdicts) == 1
    assert resolved.verdicts[0].deciding_quote == span.text


def test_percent_cap_missing_sum_insured_is_needs_information() -> None:
    span = _span("up to 2% of the sum insured per day")
    finding = compute_room_rent_limit(
        _field("pct", 2.0, spans=[span]), _field("flat", None), sum_insured=None
    )
    resolved = build_cap_claim(finding)
    assert resolved.state == SupportState.NEEDS_INFORMATION
    assert SUM_INSURED_INPUT in resolved.claim.required_inputs


# --- build_comparison_claim ---------------------------------------------------


def test_tariff_exceeding_limit_is_well_supported_and_says_so() -> None:
    resolved = build_comparison_claim(eligible_limit_per_day=5000.0, room_tariff_per_day=8000.0)
    assert resolved.state == SupportState.WELL_SUPPORTED
    assert "exceeds" in resolved.claim.predicate
    assert resolved.claim.value is True


def test_tariff_within_limit_is_well_supported_and_says_so() -> None:
    resolved = build_comparison_claim(eligible_limit_per_day=5000.0, room_tariff_per_day=3000.0)
    assert resolved.state == SupportState.WELL_SUPPORTED
    assert "within" in resolved.claim.predicate


# --- compute_deduction_ratio ---------------------------------------------------


def test_deduction_ratio_matches_the_ombudsman_worked_example() -> None:
    # Chennai Ombudsman Centre, Case No. 11.12.1782/2011-12 (docs/corpus/
    # ombudsman-feasibility.md): entitled ₹1,500/day, actual ₹8,900/day,
    # "works out to 16.8%".
    ratio = compute_deduction_ratio(eligible_limit_per_day=1500.0, room_tariff_per_day=8900.0)
    assert ratio is not None
    assert round(ratio * 100, 1) == 16.9  # 1500/8900 = 0.16853... rounds to 16.9, not 16.8


def test_no_ratio_when_tariff_does_not_exceed_the_limit() -> None:
    assert (
        compute_deduction_ratio(eligible_limit_per_day=5000.0, room_tariff_per_day=3000.0) is None
    )


# --- analyze_room_rent (real corpus, integration) -----------------------------


@pytest.fixture(scope="module")
def arogya_spans() -> list[Span]:
    path = CORPUS_DIR / "arogya_sanjeevani_retail_policy_wording.pdf"
    return PdfSegmenter().segment("arogya_sanjeevani", path.read_bytes())


@pytest.fixture(scope="module")
def easy_health_spans() -> list[Span]:
    path = CORPUS_DIR / "easy_health_policy_wording.pdf"
    return PdfSegmenter().segment("easy_health", path.read_bytes())


@pytest.fixture(scope="module")
def bajaj_health_guard_silver_spans() -> list[Span]:
    path = BAJAJ_CORPUS_DIR / "health_guard_silver_pw_cis.pdf"
    return PdfSegmenter().segment("bajaj_health_guard_silver", path.read_bytes())


def test_real_compound_clause_end_to_end_without_sum_insured(arogya_spans: list[Span]) -> None:
    analysis = analyze_room_rent(arogya_spans, room_tariff_per_day=8000.0, sum_insured=None)
    assert analysis.eligible_limit_per_day is None
    assert analysis.cap_claim.state == SupportState.NEEDS_INFORMATION
    assert SUM_INSURED_INPUT in analysis.cap_claim.claim.required_inputs
    # Can't compare without knowing the real limit yet.
    assert analysis.comparison_claim is None


def test_real_compound_clause_end_to_end_with_sum_insured(arogya_spans: list[Span]) -> None:
    analysis = analyze_room_rent(arogya_spans, room_tariff_per_day=8000.0, sum_insured=100_000)
    assert analysis.eligible_limit_per_day == 2000.0  # 2% of ₹1L, not the ₹5,000 flat cap
    assert analysis.cap_claim.state == SupportState.WELL_SUPPORTED
    assert analysis.comparison_claim is not None
    assert analysis.comparison_claim.state == SupportState.WELL_SUPPORTED
    assert "exceeds" in analysis.comparison_claim.claim.predicate
    assert analysis.deduction_ratio == pytest.approx(2000.0 / 8000.0)


def test_real_pure_percent_clause_end_to_end_with_sum_insured(
    bajaj_health_guard_silver_spans: list[Span],
) -> None:
    # Bajaj Health Guard Silver (corpus/README.md): "up to 1% of Sum
    # Insured per day ... or actual, whichever is lower" — a pure
    # %-of-SI structure with no flat-amount component at all, the third
    # of M5's ≥3 required real room-rent structures (compound and
    # no-cap are already covered above).
    analysis = analyze_room_rent(
        bajaj_health_guard_silver_spans, room_tariff_per_day=8000.0, sum_insured=500_000
    )
    assert analysis.eligible_limit_per_day == 5000.0  # 1% of ₹5L
    assert analysis.cap_claim.state == SupportState.WELL_SUPPORTED
    assert analysis.comparison_claim is not None
    assert analysis.comparison_claim.state == SupportState.WELL_SUPPORTED
    assert "exceeds" in analysis.comparison_claim.claim.predicate
    assert analysis.deduction_ratio == pytest.approx(5000.0 / 8000.0)


def test_real_pure_percent_clause_end_to_end_without_sum_insured(
    bajaj_health_guard_silver_spans: list[Span],
) -> None:
    analysis = analyze_room_rent(
        bajaj_health_guard_silver_spans, room_tariff_per_day=8000.0, sum_insured=None
    )
    assert analysis.eligible_limit_per_day is None
    assert analysis.cap_claim.state == SupportState.NEEDS_INFORMATION
    assert SUM_INSURED_INPUT in analysis.cap_claim.claim.required_inputs
    assert analysis.comparison_claim is None


def test_real_no_cap_document_reports_insufficient_evidence_not_unlimited(
    easy_health_spans: list[Span],
) -> None:
    # corpus/README.md: Easy Health has no stated room-rent restriction —
    # this must read as "not found", never as a confirmed absence of a
    # limit (§4, §6).
    analysis = analyze_room_rent(easy_health_spans, room_tariff_per_day=8000.0, sum_insured=100_000)
    assert analysis.eligible_limit_per_day is None
    assert analysis.cap_claim.state == SupportState.INSUFFICIENT_EVIDENCE
    assert analysis.comparison_claim is None


def test_room_tariff_input_is_defined_for_the_ui_to_reference() -> None:
    assert ROOM_TARIFF_INPUT.name == "room_tariff_per_day"
