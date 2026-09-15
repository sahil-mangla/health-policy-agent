"""Field extraction with provenance — docs/HANDOVER.md §6.

decoder.extract.regex_extractor.RegexFieldExtractor is a real implementation
for the mechanically-safe fields (UIN, explicit numeric room-rent caps).
decoder.extract.llm_extractor.LLMFieldExtractor covers waiting periods,
co-payment, room-category eligibility, and (via ListFieldExtractor below)
the proportionate-deduction expense-head lists. See §14 M1.
"""

from __future__ import annotations

from typing import Protocol

from decoder.schema import ExtractedField, ExtractedListField, Span


class FieldExtractor(Protocol):
    def extract(self, field_name: str, spans: list[Span]) -> ExtractedField:
        """Must set verbatim_match=False (never True) whenever the returned
        value's string form does not literally appear in a source span —
        resolve.resolve() depends on this to force the numeric-downgrade
        rule (§6, §8)."""
        ...


class ListFieldExtractor(Protocol):
    def extract_list(self, field_name: str, spans: list[Span]) -> ExtractedListField:
        """See decoder.schema.ExtractedListField for the representation
        decision (SPIKE-6, §15) this satisfies: one item per matched span,
        never an algorithmic sub-split of one span's prose."""
        ...
