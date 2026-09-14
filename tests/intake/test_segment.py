from __future__ import annotations

from pathlib import Path

from decoder.intake.segment import PdfSegmenter

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"


def test_segments_real_policy_wording_into_many_spans() -> None:
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("easy_health_pw", raw)
    # A 52-page policy wording should produce well over a hundred
    # paragraph/clause-level spans, not one span per page.
    assert len(spans) > 100


def test_isolates_the_room_rent_definition_as_a_single_precise_span() -> None:
    # This is the exact clause the hero scenario (docs/HANDOVER.md §4) needs
    # to cite precisely — never as part of a whole-section span.
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("easy_health_pw", raw)
    matches = [s for s in spans if "Room Rent means" in s.text]
    assert len(matches) == 1
    span = matches[0]
    assert span.text.startswith("Def. 42")
    assert "associated medical expenses" in span.text
    # It should not have swallowed the next definition too.
    assert "Def. 43" not in span.text


def test_spans_carry_page_and_nonzero_bbox() -> None:
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("easy_health_pw", raw)
    for span in spans[:20]:
        assert span.page >= 1
        assert span.bbox is not None
        x0, top, x1, bottom = span.bbox
        assert x1 > x0
        assert bottom > top


def test_char_offsets_are_monotonic_and_nonoverlapping() -> None:
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("easy_health_pw", raw)
    for prev, cur in zip(spans, spans[1:], strict=False):
        assert cur.char_start >= prev.char_end
        assert cur.char_end > cur.char_start


def test_span_text_round_trips_through_char_offsets_within_each_span() -> None:
    raw = (CORPUS_DIR / "easy_health_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("easy_health_pw", raw)
    for span in spans[:20]:
        assert span.char_end - span.char_start == len(span.text)
