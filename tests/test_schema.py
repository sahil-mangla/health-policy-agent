from __future__ import annotations

import pytest
from pydantic import ValidationError

from decoder.schema import ExtractedField, ExtractedListField, Span


def _make_span(text: str = "the room rent limit is INR 5,000 per day") -> Span:
    return Span(
        id="span-1",
        doc_id="policy-001",
        page=18,
        char_start=100,
        char_end=141,
        text=text,
    )


def test_span_repr_never_contains_document_text() -> None:
    secret = "policyholder Jane Doe, DOB 1990-01-01, policy no. XYZ123"
    span = _make_span(text=secret)
    assert secret not in repr(span)
    assert secret not in str(span)
    assert "redacted" in repr(span)


def test_span_is_frozen() -> None:
    span = _make_span()
    with pytest.raises(ValidationError):
        span.text = "mutated"  # type: ignore[misc]


def test_extracted_field_none_value_with_spans_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExtractedField(
            field_name="room_rent_limit_per_day",
            value=None,
            basis="FLAT_AMOUNT",
            spans=[_make_span()],
            extraction_method="LLM_STRUCTURED",
            verbatim_match=False,
        )


def test_extracted_field_none_value_with_no_spans_is_valid() -> None:
    field = ExtractedField(
        field_name="room_rent_limit_per_day",
        value=None,
        basis="FLAT_AMOUNT",
        spans=[],
        extraction_method="LLM_STRUCTURED",
        verbatim_match=False,
    )
    assert field.value is None
    assert field.spans == []


def test_extracted_list_field_empty_items_is_a_valid_not_found_state() -> None:
    # SPIKE-6 (§15): absence is reportable, never a fabricated default list
    # (§4 point 2, §6).
    field = ExtractedListField(
        field_name="proportionate_deduction_carveouts",
        items=[],
        extraction_method="LLM_STRUCTURED",
    )
    assert field.items == []


def test_extracted_list_field_items_carry_independent_provenance() -> None:
    span_a = _make_span(text="Consultation fees are included.")
    span_b = _make_span(text="Operation theatre charges are included.")
    field = ExtractedListField(
        field_name="proportionate_deduction_included_heads",
        items=[
            ExtractedField(
                field_name="proportionate_deduction_included_heads",
                value="Consultation fees",
                spans=[span_a],
                extraction_method="LLM_STRUCTURED",
                verbatim_match=True,
            ),
            ExtractedField(
                field_name="proportionate_deduction_included_heads",
                value="Operation theatre charges",
                spans=[span_b],
                extraction_method="LLM_STRUCTURED",
                verbatim_match=True,
            ),
        ],
        extraction_method="LLM_STRUCTURED",
    )
    assert len(field.items) == 2
    assert field.items[0].spans[0] is span_a
    assert field.items[1].spans[0] is span_b


def test_extracted_list_field_is_frozen() -> None:
    field = ExtractedListField(
        field_name="proportionate_deduction_carveouts",
        items=[],
        extraction_method="LLM_STRUCTURED",
    )
    with pytest.raises(ValidationError):
        field.items = []  # type: ignore[misc]
