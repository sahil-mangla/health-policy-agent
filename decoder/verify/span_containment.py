"""The "deciding words" hallucination trap — docs/HANDOVER.md §7.2.

"The verifier must return the deciding words from the span. If those words
are not actually present in the span, the verdict is discarded and treated
as NEUTRAL." Pure string logic, no model call, so it's implemented for real
now even though the entailment model call itself (decoder/verify/entailment.py)
is still a stub.
"""

from __future__ import annotations

from decoder.schema import EntailmentVerdict


def is_verbatim_in_span(quote: str, span_text: str) -> bool:
    """Exact, case-sensitive substring check. Deliberately no normalization
    (no case-folding, no whitespace collapsing): insurance clause wording is
    precise enough that normalizing risks accepting a paraphrase as if it
    were a quote."""
    return bool(quote) and quote in span_text


def enforce_hallucination_trap(
    verdict: EntailmentVerdict,
    deciding_quote: str | None,
    span_text: str,
) -> tuple[EntailmentVerdict, str | None]:
    """If `verdict` is SUPPORTS or CONTRADICTS, `deciding_quote` must be a
    verbatim substring of `span_text` or the verdict is forced to NEUTRAL and
    the quote is cleared. NEUTRAL verdicts pass through unchanged."""
    if verdict == EntailmentVerdict.NEUTRAL:
        return verdict, deciding_quote
    if deciding_quote is None or not is_verbatim_in_span(deciding_quote, span_text):
        return EntailmentVerdict.NEUTRAL, None
    return verdict, deciding_quote
