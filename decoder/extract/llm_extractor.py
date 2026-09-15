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

NOT implemented here: the proportionate-deduction carve-out list
(docs/HANDOVER.md §4 point 2). It is list-valued and
decoder.schema.ExtractedField.value is scalar (str | int | float | bool |
None) — extending that is a schema decision (SPIKE-6, still NOT STARTED
per §15), not one to make unilaterally inside an extractor module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from decoder.extract.interfaces import FieldExtractor
from decoder.llm.interface import LLMClient
from decoder.schema import ExtractedField, Span
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

KNOWN_FIELDS = frozenset({*_NUMERIC_FIELDS, *_TEXT_FIELDS})


class LLMFieldExtractor(FieldExtractor):
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
            f"fields: {sorted(KNOWN_FIELDS)}. See this module's docstring "
            "for why the carve-out list isn't here yet."
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
