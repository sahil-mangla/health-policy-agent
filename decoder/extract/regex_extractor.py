"""Deterministic, regex-based FieldExtractor — the mechanically-safe subset
of extraction (docs/HANDOVER.md §6), built without an LLM.

Only implements fields where a wrong regex match is implausible and a
missed match safely degrades to "not found" rather than a wrong answer:
the UIN (always printed verbatim, unambiguous format) and the two numeric
room-rent cap components (percent-of-SI and flat-amount) when explicitly
stated in a room-rent-mentioning clause.

Deliberately NOT implemented here: room-CATEGORY eligibility (e.g. "single
private AC room" — too much phrasing variety to regex safely), waiting
periods, and co-pay — now covered by decoder.extract.llm_extractor
instead. The carve-out/associated-medical-expenses list is not implemented
anywhere yet (list-valued, needs a SPIKE-6 schema decision — see
decoder.extract.llm_extractor's module docstring). Regex-guessing any of
these risks exactly the "wrong number with a correct-looking citation"
failure §1 of the handover calls out as worse than no answer — safer to
return INSUFFICIENT_EVIDENCE via resolve() than to fabricate a pattern
match.

Verified empirically against the real starter corpus (2026-09-14): Easy
Health and Optima Restore's policy wordings contain no explicit numeric
room-rent cap anywhere findable by these patterns (both correctly extract
value=None — NOT the same claim as "confirmed no cap", see
docs/HANDOVER.md §4's own warning against inventing that distinction).
Arogya Sanjeevani (Retail) contains the explicit compound pattern "up to 2%
of the sum insured subject to maximum of Rs.5000/-, per day", appearing
twice with identical values (no conflict).
"""

from __future__ import annotations

import re

from decoder.extract.interfaces import FieldExtractor
from decoder.schema import ExtractedField, Span

# A UIN-shaped token (letters, then digits, then a letter, then digits —
# e.g. "HDFHLIP26054V102526"), searched for within any span that mentions
# "UIN" anywhere in its text. Deliberately NOT anchored immediately after
# "UIN:" — verified against the real corpus (2026-09-14) that
# decoder.intake.segment's line-grouping sometimes reorders words within a
# footer line (e.g. Optima Restore's footer extracts as "UIN: Optima
# Restore - HDFHLIP26055V102526", not "... - UIN: HDFHLIP26055V102526"), so
# strict adjacency silently misses real matches rather than mismatching.
_UIN_MENTION_RE = re.compile(r"\bUIN\b", re.IGNORECASE)
_UIN_TOKEN_RE = re.compile(r"\b([A-Z]{3,10}\d{4,6}[A-Z]\d{5,7})\b")

# Only searched within spans that mention "room rent" at all, to avoid
# matching an unrelated per-day figure (e.g. a daily-cash benefit amount)
# elsewhere in the document.
_ROOM_RENT_MENTION_RE = re.compile(r"room\s+rent", re.IGNORECASE)
_PERCENT_OF_SI_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s*of\s*(?:the\s+)?sum\s+insured", re.IGNORECASE
)
_FLAT_AMOUNT_PER_DAY_RE = re.compile(
    r"(?:Rs\.?|INR|₹)\s*([\d,]+)(?:/-)?\s*,?\s*per\s+day", re.IGNORECASE
)

_KNOWN_FIELDS = frozenset(
    {"uin", "room_rent_percent_of_si_per_day", "room_rent_max_amount_per_day"}
)


class RegexFieldExtractor(FieldExtractor):
    def extract(self, field_name: str, spans: list[Span]) -> ExtractedField:
        if field_name not in _KNOWN_FIELDS:
            raise NotImplementedError(
                f"RegexFieldExtractor does not implement {field_name!r} — it "
                "only handles the mechanically-safe fields listed in this "
                "module's docstring. See decoder.extract.interfaces for the "
                "LLM-based path once decoder.llm.ollama_client is wired into "
                "a real FieldExtractor."
            )
        if field_name == "uin":
            return self._extract_uin(spans)
        return self._extract_room_rent_numeric(field_name, spans)

    def _extract_uin(self, spans: list[Span]) -> ExtractedField:
        uin_spans = [s for s in spans if _UIN_MENTION_RE.search(s.text)]
        candidates = self._collect_candidates(uin_spans, _UIN_TOKEN_RE, parse=str)
        return self._resolve_candidates(
            field_name="uin",
            candidates=candidates,
            unit=None,
            basis="VERBATIM_HEADER_TEXT",
        )

    def _extract_room_rent_numeric(self, field_name: str, spans: list[Span]) -> ExtractedField:
        pattern = (
            _PERCENT_OF_SI_RE
            if field_name == "room_rent_percent_of_si_per_day"
            else _FLAT_AMOUNT_PER_DAY_RE
        )
        room_rent_spans = [s for s in spans if _ROOM_RENT_MENTION_RE.search(s.text)]
        candidates = self._collect_candidates(room_rent_spans, pattern, parse=_parse_number)
        unit = "PERCENT_OF_SUM_INSURED_PER_DAY" if pattern is _PERCENT_OF_SI_RE else "INR_PER_DAY"
        return self._resolve_candidates(
            field_name=field_name,
            candidates=candidates,
            unit=unit,
            basis="PERCENT_OF_SI" if pattern is _PERCENT_OF_SI_RE else "FLAT_AMOUNT",
        )

    @staticmethod
    def _collect_candidates(
        spans: list[Span],
        pattern: re.Pattern[str],
        parse: type | object,
    ) -> list[tuple[Span, str, object]]:
        """Returns (span, matched_text, parsed_value) for every match found.
        `matched_text` is the exact substring pulled from the span — kept
        alongside the parsed value so verbatim_match can be checked against
        the literal source text, not the parsed/normalized form."""
        results: list[tuple[Span, str, object]] = []
        for span in spans:
            match = pattern.search(span.text)
            if match:
                matched_text = match.group(1)
                results.append((span, matched_text, parse(matched_text)))  # type: ignore[operator]
        return results

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
                extraction_method="REGEX",
                verbatim_match=False,
            )

        distinct_values = {value for _, _, value in candidates}
        primary_span, matched_text, primary_value = candidates[0]

        # verbatim_match is true here by construction — the regex only ever
        # captures a literal substring of the span it matched in — but it's
        # still computed explicitly (via decoder.verify.span_containment's
        # own logic) rather than hardcoded True, so this stays correct if
        # `parse()` ever normalizes the matched text before comparison.
        verbatim = matched_text in primary_span.text

        if len(distinct_values) == 1:
            return ExtractedField(
                field_name=field_name,
                value=primary_value,
                unit=unit,
                basis=basis,
                spans=[span for span, _, _ in candidates],
                extraction_method="REGEX",
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
                extraction_method="REGEX",
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
            extraction_method="REGEX",
            verbatim_match=verbatim,
            conflicting_candidates=conflicting,
        )


def _parse_number(text: str) -> float:
    return float(text.replace(",", ""))
