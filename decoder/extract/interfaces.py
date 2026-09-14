"""Field extraction with provenance — docs/HANDOVER.md §6.

decoder.extract.regex_extractor.RegexFieldExtractor is a real implementation
for the mechanically-safe fields (UIN, explicit numeric room-rent caps). The
remaining fields (waiting periods, co-pay, room-category eligibility, the
carve-out list) need LLM-based structured extraction — blocked on
decoder.reason/decoder.verify being wired against decoder.llm.ollama_client,
and on SPIKE-6 (final policy schema beyond the hero fields). See §14 M1.
"""

from __future__ import annotations

from typing import Protocol

from decoder.schema import ExtractedField, Span


class FieldExtractor(Protocol):
    def extract(self, field_name: str, spans: list[Span]) -> ExtractedField:
        """Must set verbatim_match=False (never True) whenever the returned
        value's string form does not literally appear in a source span —
        resolve.resolve() depends on this to force the numeric-downgrade
        rule (§6, §8)."""
        ...
