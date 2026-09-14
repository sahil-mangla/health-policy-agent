"""Field extraction with provenance — docs/HANDOVER.md §6.

Stub: blocked on the per-field extraction methodology decision (regex vs LLM
vs table-parser, decided per field type) and on SPIKE-6 (final policy schema
beyond the hero fields). See §14 M1.
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
