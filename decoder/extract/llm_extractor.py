"""LLM-located, code-verified field extraction — docs/HANDOVER.md §6, §14 M1.

Covers the fields decoder.extract.regex_extractor deliberately leaves out:
waiting periods, co-payment, and room-category eligibility. Phrasing for
these varies too much to regex safely, but a free LLM value is exactly the
"wrong number with a correct-looking citation" risk §1/§6 warn about.

The fix mirrors decoder.verify.entailment's isolation + deciding-words
discipline instead of inventing a new one: the model's only job, given ONE
field definition and ONE span, is to say whether that span states the
field's value and to quote the exact words that do. The quote must be a
verbatim substring of the span (decoder.verify.span_containment) or it is
discarded. For numeric fields the actual number is then parsed out of that
verified quote by a field-specific regex, in code, never accepted as a
number the model states on its own — a hallucinated digit in the model's
quote fails the regex and the span is simply dropped, not trusted. For
text fields (room category) there is no separate value: the value IS the
verified quote.

Also covers the proportionate-deduction expense-head lists
(docs/HANDOVER.md §4 point 2) via extract_list() — see
decoder.schema.ExtractedListField for the SPIKE-6 representation decision
(§15, resolved 2026-09-15) this implements: the same per-span isolation and
hallucination trap as the scalar fields above, with no further attempt to
split one span's prose into sub-items.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from decoder.extract.interfaces import FieldExtractor, ListFieldExtractor
from decoder.llm.interface import LLMClient
from decoder.schema import ExtractedField, ExtractedListField, Span
from decoder.verify.span_containment import is_verbatim_in_span

# Wording follows the same fail-safe-to-not-found posture as
# decoder/verify/entailment.py's _SYSTEM_PROMPT — split across shorter
# source lines only, the resulting string is unchanged.
_SYSTEM_PROMPT_TEMPLATE = (
    "You are extracting ONE specific field from a health insurance policy "
    "passage. You will be given a field definition and ONE passage from the "
    "document. Use ONLY this passage — no outside knowledge of typical "
    "insurance terms, no assumptions, no inference beyond what is literally "
    "stated.\n\n"
    "Field: {field_description}\n\n"
    "Decide whether this passage states a value for this field. Respond in "
    "EXACTLY this format and nothing else, with no quotation marks around "
    "the quoted text:\n"
    "FOUND: <one word, exactly YES or NO, no other word is allowed>\n"
    "QUOTE: <the exact contiguous substring copied verbatim from the "
    "passage that states the value, or NONE if FOUND is NO>"
)

_FOUND_RE = re.compile(r"FOUND:\s*(\w+)", re.IGNORECASE)
_QUOTE_RE = re.compile(r"QUOTE:\s*(.+)", re.IGNORECASE | re.DOTALL)

# A list-field quote must contain at least this many commas to be accepted
# as a genuine enumeration rather than a passage that just mentions the
# term in passing — see extract_list()'s use of this.
_MIN_ENUMERATION_COMMAS = 2


def _strip_stray_quote_marks(text: str) -> str:
    return text.strip().strip("\"“”'").strip()


def _parse_model_response(raw_response: str) -> str | None:
    """Returns the model's quote if it claims to have found a value, None
    otherwise. Any response that doesn't conform to the requested format
    fails closed to None — the same fail-safe posture as
    decoder.verify.entailment._parse_model_response."""
    found_match = _FOUND_RE.search(raw_response)
    if not found_match or found_match.group(1).upper() != "YES":
        return None
    quote_match = _QUOTE_RE.search(raw_response)
    if not quote_match:
        return None
    quote = _strip_stray_quote_marks(quote_match.group(1).splitlines()[0])
    if not quote or quote.upper() == "NONE":
        return None
    return quote


@dataclass(frozen=True)
class _NumericFieldSpec:
    description: str
    keyword_filter: re.Pattern[str]
    value_re: re.Pattern[str]
    unit: str
    basis: str


@dataclass(frozen=True)
class _TextFieldSpec:
    description: str
    keyword_filter: re.Pattern[str]
    unit: str | None
    basis: str


_NUMERIC_FIELDS: dict[str, _NumericFieldSpec] = {
    "waiting_period_initial_days": _NumericFieldSpec(
        description=(
            "The initial/cooling-off waiting period in days — the time from "
            "policy inception before any claim other than an accident is "
            "payable."
        ),
        keyword_filter=re.compile(r"initial|cooling", re.IGNORECASE),
        value_re=re.compile(r"(\d+)\s*day", re.IGNORECASE),
        unit="DAYS",
        basis="INITIAL_WAITING_PERIOD",
    ),
    "waiting_period_ped_months": _NumericFieldSpec(
        description=(
            "The waiting period before pre-existing diseases (PED) are "
            "covered, stated as a number of months or years."
        ),
        keyword_filter=re.compile(r"pre-?existing", re.IGNORECASE),
        value_re=re.compile(r"(\d+)\s*(?:month|year)", re.IGNORECASE),
        unit="MONTHS_OR_YEARS_AS_STATED",
        basis="PED_WAITING_PERIOD",
    ),
    "waiting_period_specific_illness_months": _NumericFieldSpec(
        description=(
            "The waiting period for specific named illnesses or procedures "
            "(e.g. cataract, hernia, joint replacement), stated as a number "
            "of months or years — distinct from the general PED waiting "
            "period."
        ),
        keyword_filter=re.compile(
            r"specific|named\s+ailment|specified\s+disease", re.IGNORECASE
        ),
        value_re=re.compile(r"(\d+)\s*(?:month|year)", re.IGNORECASE),
        unit="MONTHS_OR_YEARS_AS_STATED",
        basis="SPECIFIC_ILLNESS_WAITING_PERIOD",
    ),
    "co_payment_percent": _NumericFieldSpec(
        description="The co-payment percentage the insured must bear on an admissible claim.",
        keyword_filter=re.compile(r"co-?pay", re.IGNORECASE),
        value_re=re.compile(r"(\d+(?:\.\d+)?)\s*%"),
        unit="PERCENT",
        basis="CO_PAYMENT",
    ),
}

_TEXT_FIELDS: dict[str, _TextFieldSpec] = {
    "room_category_eligibility": _TextFieldSpec(
        description=(
            "The room CATEGORY the insured is ENTITLED TO or RESTRICTED TO "
            "under this policy (e.g. 'single private AC room', 'twin "
            "sharing', 'general ward'). This is an eligibility/entitlement "
            "statement about what the policyholder gets, NOT a glossary "
            "entry — do NOT match a clause that merely DEFINES a room-type "
            "term (e.g. one starting 'Definition:', 'Def. N', or phrased as "
            "'X means a room with...') without also stating the insured is "
            "entitled to or limited to it. Also not a ₹/day or "
            "%-of-sum-insured numeric room-rent limit, which is a different "
            "field."
        ),
        keyword_filter=re.compile(r"room", re.IGNORECASE),
        unit=None,
        basis="ROOM_CATEGORY",
    ),
}


@dataclass(frozen=True)
class _ListFieldSpec:
    description: str
    keyword_filter: re.Pattern[str]
    basis: str


_LIST_FIELDS: dict[str, _ListFieldSpec] = {
    "proportionate_deduction_included_heads": _ListFieldSpec(
        description=(
            "The expense heads (e.g. consultation fees, operation theatre "
            "charges, nursing, anesthesia, ICU charges, medicines, "
            "diagnostics) that this policy states are included within "
            "'Associated Medical Expenses' — and are therefore SUBJECT TO "
            "proportionate deduction when the room rent exceeds the "
            "eligible limit. Match a passage that actually ENUMERATES or "
            "DEFINES this set — not a passage that merely mentions "
            "'Associated Medical Expenses' in passing (e.g. saying room "
            "rent 'includes' them, or that a deduction 'applies to' them) "
            "without listing what the term covers."
        ),
        keyword_filter=re.compile(r"associated\s+medical\s+expenses", re.IGNORECASE),
        basis="PROPORTIONATE_DEDUCTION_INCLUDED",
    ),
    "proportionate_deduction_carveouts": _ListFieldSpec(
        description=(
            "The expense heads this policy explicitly states are EXCLUDED "
            "or CARVED OUT from proportionate deduction — i.e. paid in "
            "full regardless of any room-rent limit breach (e.g. a "
            "statement that pharmacy, implants, diagnostics, or ICU "
            "charges are NOT subject to the proportionate reduction). Do "
            "NOT match a passage listing expenses that ARE subject to "
            "proportionate deduction — that is a different field, and most "
            "Indian policies do not state a carve-out list at all, which "
            "is a valid and expected 'not found' outcome, not a failure."
        ),
        keyword_filter=re.compile(
            r"not\s+(?:be\s+)?subject\s+to\s+proportion"
            r"|excluded\s+from\s+(?:the\s+)?proportion"
            r"|shall\s+not\s+apply\s+to\s+.*proportion",
            re.IGNORECASE,
        ),
        basis="PROPORTIONATE_DEDUCTION_CARVEOUT",
    ),
}

KNOWN_FIELDS = frozenset({*_NUMERIC_FIELDS, *_TEXT_FIELDS})
KNOWN_LIST_FIELDS = frozenset(_LIST_FIELDS)


class LLMFieldExtractor(FieldExtractor, ListFieldExtractor):
    def __init__(self, llm: LLMClient, model: str = "qwen2.5-coder:7b") -> None:
        self._llm = llm
        self._model = model

    def extract(self, field_name: str, spans: list[Span]) -> ExtractedField:
        if field_name in _NUMERIC_FIELDS:
            return self._extract_numeric(field_name, _NUMERIC_FIELDS[field_name], spans)
        if field_name in _TEXT_FIELDS:
            return self._extract_text(field_name, _TEXT_FIELDS[field_name], spans)
        raise NotImplementedError(
            f"LLMFieldExtractor does not implement {field_name!r}. Known "
            f"scalar fields: {sorted(KNOWN_FIELDS)}. List-valued fields go "
            f"through extract_list() instead: {sorted(KNOWN_LIST_FIELDS)}."
        )

    def extract_list(self, field_name: str, spans: list[Span]) -> ExtractedListField:
        if field_name not in _LIST_FIELDS:
            raise NotImplementedError(
                f"LLMFieldExtractor does not implement {field_name!r} as a "
                f"list field. Known list fields: {sorted(KNOWN_LIST_FIELDS)}."
            )
        spec = _LIST_FIELDS[field_name]
        items: list[ExtractedField] = []
        for span in self._candidate_spans(spans, spec.keyword_filter):
            quote = self._query_span(spec.description, span)
            if quote is None:
                continue
            if quote.count(",") < _MIN_ENUMERATION_COMMAS:
                # Model said FOUND: YES with a verified-verbatim quote that
                # doesn't actually look like an enumeration (e.g. a passage
                # that just mentions the term in passing, such as "...
                # Room Rent ... including all Associated Medical Expenses
                # incurred at Hospital ..." — a real false positive caught
                # by hand against the starter corpus, 2026-09-15). A
                # deterministic structural gate, same fail-closed posture
                # as the numeric fields' value regex.
                continue
            items.append(
                ExtractedField(
                    field_name=field_name,
                    value=quote,
                    unit=None,
                    basis=spec.basis,
                    spans=[span],
                    extraction_method="LLM_STRUCTURED",
                    # True by construction: quote was already verified
                    # verbatim-in-span by _query_span's hallucination trap.
                    verbatim_match=True,
                )
            )
        return ExtractedListField(
            field_name=field_name, items=items, extraction_method="LLM_STRUCTURED"
        )

    @staticmethod
    def _candidate_spans(spans: list[Span], keyword_filter: re.Pattern[str]) -> list[Span]:
        return [s for s in spans if keyword_filter.search(s.text)]

    def _query_span(self, description: str, span: Span) -> str | None:
        system = _SYSTEM_PROMPT_TEMPLATE.format(field_description=description)
        prompt = f"Passage: {span.text}"
        raw_response = self._llm.generate(prompt=prompt, system=system, model=self._model)
        quote = _parse_model_response(raw_response)
        if quote is None:
            return None
        # Hallucination trap (mirrors decoder.verify.span_containment): a
        # quote that isn't actually in the span is discarded, not trusted.
        if not is_verbatim_in_span(quote, span.text):
            return None
        return quote

    def _extract_numeric(
        self, field_name: str, spec: _NumericFieldSpec, spans: list[Span]
    ) -> ExtractedField:
        candidates: list[tuple[Span, str, object]] = []
        for span in self._candidate_spans(spans, spec.keyword_filter):
            quote = self._query_span(spec.description, span)
            if quote is None:
                continue
            match = spec.value_re.search(quote)
            if not match:
                # Model claimed a value but its (verified-verbatim) quote
                # contains no parseable number for this field — fail closed.
                continue
            candidates.append((span, match.group(1), float(match.group(1))))
        return self._resolve_candidates(field_name, candidates, spec.unit, spec.basis)

    def _extract_text(
        self, field_name: str, spec: _TextFieldSpec, spans: list[Span]
    ) -> ExtractedField:
        candidates: list[tuple[Span, str, object]] = []
        for span in self._candidate_spans(spans, spec.keyword_filter):
            quote = self._query_span(spec.description, span)
            if quote is None:
                continue
            candidates.append((span, quote, quote))
        return self._resolve_candidates(field_name, candidates, spec.unit, spec.basis)

    @staticmethod
    def _resolve_candidates(
        field_name: str,
        candidates: list[tuple[Span, str, object]],
        unit: str | None,
        basis: str,
    ) -> ExtractedField:
        if not candidates:
            return ExtractedField(
                field_name=field_name,
                value=None,
                unit=unit,
                basis=basis,
                spans=[],
                extraction_method="LLM_STRUCTURED",
                verbatim_match=False,
            )

        distinct_values = {value for _, _, value in candidates}
        primary_span, matched_text, primary_value = candidates[0]
        # True by construction: matched_text was either regex-captured from
        # a quote already verified verbatim-in-span (numeric fields), or IS
        # that verified quote itself (text fields) — computed explicitly
        # rather than hardcoded True, same rationale as regex_extractor.
        verbatim = matched_text in primary_span.text

        if len(distinct_values) == 1:
            return ExtractedField(
                field_name=field_name,
                value=primary_value,
                unit=unit,
                basis=basis,
                spans=[span for span, _, _ in candidates],
                extraction_method="LLM_STRUCTURED",
                verbatim_match=verbatim,
            )

        # Different spans disagree on the value — surface as conflicting
        # candidates, never silently pick one (§6).
        conflicting = [
            ExtractedField(
                field_name=field_name,
                value=value,
                unit=unit,
                basis=basis,
                spans=[span],
                extraction_method="LLM_STRUCTURED",
                verbatim_match=text in span.text,
            )
            for span, text, value in candidates
        ]
        return ExtractedField(
            field_name=field_name,
            value=primary_value,
            unit=unit,
            basis=basis,
            spans=[primary_span],
            extraction_method="LLM_STRUCTURED",
            verbatim_match=verbatim,
            conflicting_candidates=conflicting,
        )
