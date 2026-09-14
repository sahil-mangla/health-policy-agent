"""Tests run against the real starter corpus (corpus/README.md), not
synthetic fixtures — every assertion here was verified by hand against the
actual extracted values before being written (2026-09-14): see
decoder/extract/regex_extractor.py's module docstring for the survey."""

from __future__ import annotations

from pathlib import Path

import pytest

from decoder.extract.regex_extractor import RegexFieldExtractor
from decoder.intake.segment import PdfSegmenter
from decoder.schema import Span

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"


def _spans(filename: str) -> list[Span]:
    raw = (CORPUS_DIR / filename).read_bytes()
    return PdfSegmenter().segment(filename, raw)


@pytest.fixture(scope="module")
def easy_health_spans() -> list[Span]:
    return _spans("easy_health_policy_wording.pdf")


@pytest.fixture(scope="module")
def optima_restore_spans() -> list[Span]:
    return _spans("optima_restore_policy_wording.pdf")


@pytest.fixture(scope="module")
def arogya_sanjeevani_spans() -> list[Span]:
    return _spans("arogya_sanjeevani_retail_policy_wording.pdf")


@pytest.mark.parametrize(
    ("fixture_name", "expected_uin"),
    [
        ("easy_health_spans", "HDFHLIP26054V102526"),
        ("optima_restore_spans", "HDFHLIP26055V102526"),
        ("arogya_sanjeevani_spans", "HDFHLIP20175V011920"),
    ],
)
def test_uin_extracted_with_verbatim_match(
    request: pytest.FixtureRequest, fixture_name: str, expected_uin: str
) -> None:
    spans = request.getfixturevalue(fixture_name)
    field = RegexFieldExtractor().extract("uin", spans)
    assert field.value == expected_uin
    assert field.verbatim_match is True
    assert len(field.spans) > 0


def test_easy_health_room_rent_percent_not_found(easy_health_spans: list[Span]) -> None:
    # Confirmed by hand: Easy Health's In-Patient Treatment clause covers
    # "Hospital room rent or boarding" with no stated numeric cap anywhere
    # in the document — this must be None (not found), never a guessed 0 or
    # a fabricated "no limit" value.
    field = RegexFieldExtractor().extract("room_rent_percent_of_si_per_day", easy_health_spans)
    assert field.value is None
    assert field.spans == []
    assert field.verbatim_match is False


def test_easy_health_room_rent_flat_amount_not_found(easy_health_spans: list[Span]) -> None:
    field = RegexFieldExtractor().extract("room_rent_max_amount_per_day", easy_health_spans)
    assert field.value is None
    assert field.spans == []


def test_optima_restore_room_rent_percent_not_found(optima_restore_spans: list[Span]) -> None:
    field = RegexFieldExtractor().extract("room_rent_percent_of_si_per_day", optima_restore_spans)
    assert field.value is None


def test_arogya_sanjeevani_room_rent_percent_of_si(arogya_sanjeevani_spans: list[Span]) -> None:
    field = RegexFieldExtractor().extract(
        "room_rent_percent_of_si_per_day", arogya_sanjeevani_spans
    )
    assert field.value == 2.0
    assert field.unit == "PERCENT_OF_SUM_INSURED_PER_DAY"
    assert field.verbatim_match is True
    assert len(field.spans) == 2  # stated identically in two places, no conflict
    assert field.conflicting_candidates == []


def test_arogya_sanjeevani_room_rent_flat_cap(arogya_sanjeevani_spans: list[Span]) -> None:
    field = RegexFieldExtractor().extract("room_rent_max_amount_per_day", arogya_sanjeevani_spans)
    assert field.value == 5000.0
    assert field.unit == "INR_PER_DAY"
    assert field.verbatim_match is True


def test_unknown_field_name_raises_not_implemented(easy_health_spans: list[Span]) -> None:
    with pytest.raises(NotImplementedError):
        RegexFieldExtractor().extract("waiting_period_years", easy_health_spans)


def test_conflicting_candidates_are_surfaced_not_silently_resolved() -> None:
    # Synthetic case (not from the real corpus): two spans of the *same*
    # document disagreeing on the room-rent percentage. This scenario is
    # exactly what §6 requires be surfaced as CONFLICTING, never silently
    # picked — the real corpus doesn't happen to contain a genuine
    # cross-clause conflict, so this is constructed to prove the mechanism
    # works rather than left untested.
    span_a = Span(
        id="a",
        doc_id="synthetic",
        page=1,
        char_start=0,
        char_end=50,
        text="Room Rent shall be limited to 1% of the Sum Insured per day.",
    )
    span_b = Span(
        id="b",
        doc_id="synthetic",
        page=9,
        char_start=100,
        char_end=150,
        text="An endorsement raises the Room Rent limit to 2% of the Sum Insured per day.",
    )
    field = RegexFieldExtractor().extract("room_rent_percent_of_si_per_day", [span_a, span_b])
    assert len(field.conflicting_candidates) == 2
    values = {c.value for c in field.conflicting_candidates}
    assert values == {1.0, 2.0}
