"""Shared typed data models for the policy decoder.

Vocabulary here matches docs/HANDOVER.md §3 exactly — do not introduce
synonyms, and never use the word "confidence" anywhere in this codebase.

Every evidence-bearing model is frozen: extraction and verification results
are records of what was found, not mutable state.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class ClaimClass(StrEnum):
    DOCUMENT_FACT = "DOCUMENT_FACT"
    REGULATORY_FACT = "REGULATORY_FACT"
    DERIVED = "DERIVED"
    INTERPRETATION = "INTERPRETATION"


class EntailmentVerdict(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class SupportState(StrEnum):
    WELL_SUPPORTED = "WELL_SUPPORTED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING = "CONFLICTING"


class Span(BaseModel):
    """The atomic unit of evidence: a contiguous character range in a source
    document, with page and bounding box. Never cite a whole section."""

    model_config = ConfigDict(frozen=True)

    id: str
    doc_id: str
    page: int
    char_start: int
    char_end: int
    text: str  # verbatim source text — never log this field directly
    bbox: tuple[float, float, float, float] | None = None

    def __repr__(self) -> str:
        # Structural PII guard (docs/HANDOVER.md §9.5): default repr/str never
        # leaks document content, so `logging.info(f"{span}")` cannot leak
        # text by accident.
        return (
            f"Span(id={self.id!r}, doc_id={self.doc_id!r}, page={self.page}, "
            f"char_start={self.char_start}, char_end={self.char_end}, "
            f"text=<redacted:{len(self.text)} chars>)"
        )

    __str__ = __repr__


class RequiredInput(BaseModel):
    """A named, typed, user-supplied fact a claim depends on (e.g. continuity
    date). Named and requestable, never assumed."""

    model_config = ConfigDict(frozen=True)

    name: str
    value_type: str  # e.g. "date", "int", "bool"
    description: str

    def __hash__(self) -> int:
        return hash(self.name)


class ExtractedField(BaseModel):
    """A typed value pulled from a span into the structured policy, with full
    provenance. See docs/HANDOVER.md §6."""

    model_config = ConfigDict(frozen=True)

    field_name: str
    value: str | int | float | bool | None
    unit: str | None = None
    basis: str | None = None
    spans: list[Span] = []
    extraction_method: str
    verbatim_match: bool
    conflicting_candidates: list[ExtractedField] = []

    @model_validator(mode="after")
    def _absent_value_has_no_spans(self) -> ExtractedField:
        # "A field that cannot be found is null with an empty span list.
        # Absence is a valid, reportable state." (§6)
        if self.value is None and self.spans:
            raise ValueError("a None-valued ExtractedField must carry no spans")
        return self


class AtomicClaim(BaseModel):
    """One subject/predicate/value assertion that can be marked right or
    wrong on its own. See docs/HANDOVER.md §7.1.

    `input_claim_ids` (not `input_claims`) is deliberate: AtomicClaim is
    frozen and constructed before resolution happens, so it cannot hold a
    live `.state` for its own inputs the way the handover's pseudocode
    (`claim.input_claims[i].state`) implies. `resolve()` takes the already-
    resolved states of these inputs as an explicit parameter instead — the
    caller resolves a DERIVED claim's inputs first, in dependency order.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    subject: str
    predicate: str
    value: str | int | float | bool | None
    claim_class: ClaimClass
    is_numeric: bool
    verbatim_match: bool
    required_inputs: list[RequiredInput] = []
    input_claim_ids: list[str] = []


class EntailmentResult(BaseModel):
    """One (claim, span) verdict. If verdict is not NEUTRAL, `deciding_quote`
    must be a verbatim substring of `span.text` — decoder.verify.span_containment
    enforces this and forces the verdict to NEUTRAL otherwise (the
    hallucination trap, §7.2)."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    span: Span
    verdict: EntailmentVerdict
    deciding_quote: str | None = None


class ResolvedClaim(BaseModel):
    """Output of resolve.resolve() — the only object respond/ may consume.
    There is no function that turns a raw AtomicClaim into an Answer without
    going through this."""

    model_config = ConfigDict(frozen=True)

    claim: AtomicClaim
    verdicts: list[EntailmentResult]
    state: SupportState


class Answer(BaseModel):
    """A user-facing answer. `overall_state` must be computed via
    resolve.aggregate_answer_state(), never re-derived ad hoc."""

    model_config = ConfigDict(frozen=True)

    claims: list[ResolvedClaim]
    overall_state: SupportState
    text: str | None = None
    missing_inputs: list[RequiredInput] = []
