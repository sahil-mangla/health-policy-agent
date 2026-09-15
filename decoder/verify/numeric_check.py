"""The numeric checks §7.2 assigns to code rather than a model — both rows
of docs/HANDOVER.md §7.2's table that say "code, not model":

- `DERIVED`: "executed in code. The inputs must themselves be verified
  claims." Pure arithmetic, and deliberately no attempt to extract the
  operation from a model's free-text draft (see
  decoder.schema.DerivedOperation's docstring for why that was tried and
  rejected). A DERIVED AtomicClaim must carry a populated
  `derived_operation` before this can verify it; that field is set by
  whatever code already has the operand values on hand (e.g. a
  user-supplied room tariff compared against an already-extracted numeric
  field), not by decompose.
- `DOCUMENT_FACT`, numeric: "Exact string match of the value in the span."
  See numeric_value_appears_verbatim() — this is what decides a numeric
  claim's `verbatim_match`, which §6/§8 then use to force the
  NEEDS_CONFIRMATION downgrade when the figure cannot be found literally
  in the cited text.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from decoder.schema import AtomicClaim, DerivedOperation, EntailmentResult, EntailmentVerdict, Span

_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "GREATER_THAN": lambda left, right: left > right,
    "LESS_THAN": lambda left, right: left < right,
    "GREATER_OR_EQUAL": lambda left, right: left >= right,
    "LESS_OR_EQUAL": lambda left, right: left <= right,
    "EQUAL": lambda left, right: left == right,
}


_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numeric_value_appears_verbatim(claim_value: str, span_text: str) -> bool:
    """§7.2's `DOCUMENT_FACT`, numeric row: "Exact string match of the value
    in the span. Code, not model."

    Every number in `claim_value` must appear literally in `span_text`,
    bounded so a bare "5" does not match inside "1500" or "35" — a loose
    substring hit here would wrongly mark a claim verbatim and let §8
    promote it to WELL_SUPPORTED, which is the one direction of error this
    system cannot afford (§12's confident-and-wrong case).

    Deliberately strict about formatting: "5,000" does not match "5000".
    That fails safe — the claim is merely downgraded to NEEDS_CONFIRMATION
    (§6), which is the honest outcome when the figure as stated cannot be
    found as stated.

    Returns False for a value containing no number at all: a non-numeric
    value has nothing for this check to match, and claiming otherwise
    would assert a verification that never happened.
    """
    numbers = _NUMBER_RE.findall(claim_value)
    if not numbers:
        return False
    return all(_number_appears(number, span_text) for number in numbers)


def _number_appears(number: str, span_text: str) -> bool:
    # The two lookbehinds reject a match that is part of a LARGER number —
    # "5" inside "1500", or "5000" inside "1.5000" / "12,500" — while still
    # matching "Rs.5000/-", where the "." is an abbreviation point rather
    # than a decimal separator. Distinguishing those two needs the check to
    # look past the punctuation at whether a digit precedes it; a simpler
    # `(?<![\d.,])` rejects "Rs.5000" too, which is how Indian policy
    # wording almost always states an amount.
    return bool(re.search(rf"(?<!\d)(?<!\d[.,]){re.escape(number)}(?!\d)", span_text))


class MissingDerivedOperationError(ValueError):
    """Raised when asked to verify a DERIVED claim that has no
    derived_operation set — this is a caller bug (constructing an
    unverifiable DERIVED claim), not something to guess around."""


def verify_derived_claim(claim: AtomicClaim) -> EntailmentVerdict:
    """Executes `claim.derived_operation` and compares the result to
    `claim.value` (interpreted as a bool — a DERIVED claim of the kind this
    system produces asserts that a comparison holds, e.g. "the room tariff
    exceeds the eligible limit").

    Returns SUPPORTS if the computed result matches the claim's asserted
    value, CONTRADICTS if it doesn't. Never NEUTRAL — a fully-specified
    arithmetic comparison is not ambiguous; if the operation or the
    claimed value is missing or malformed, that's an error to raise, not a
    verdict to soften into NEUTRAL (unlike the LLM entailment path, there
    is no "model didn't follow the format" failure mode to fail safely
    around here — either the caller supplied a well-formed comparison or
    they didn't).
    """
    operation = claim.derived_operation
    if operation is None:
        raise MissingDerivedOperationError(
            f"claim {claim.id!r} is class DERIVED but has no derived_operation set"
        )
    if not isinstance(claim.value, bool):
        raise MissingDerivedOperationError(
            f"claim {claim.id!r} has derived_operation set but its value "
            f"({claim.value!r}) is not a bool — a DERIVED claim must assert "
            "whether the comparison holds, not the raw computed number"
        )

    compare = _OPERATORS[operation.operator]
    computed_result = compare(operation.left_operand, operation.right_operand)
    return (
        EntailmentVerdict.SUPPORTS
        if computed_result == claim.value
        else EntailmentVerdict.CONTRADICTS
    )


def render_operation_text(operation: DerivedOperation) -> str:
    """Renders a DerivedOperation as human-readable text — used as the
    synthetic "span" text when a DERIVED verdict needs to be packaged into
    an EntailmentResult for decoder.resolve.rules.resolve() (which expects
    verdicts uniformly, regardless of whether they came from a document
    span or a code-executed comparison)."""
    symbols = {
        "GREATER_THAN": ">",
        "LESS_THAN": "<",
        "GREATER_OR_EQUAL": ">=",
        "LESS_OR_EQUAL": "<=",
        "EQUAL": "==",
    }
    symbol = symbols[operation.operator]
    return f"{operation.left_operand} {symbol} {operation.right_operand}"


def entailment_result_for_derived_claim(claim: AtomicClaim) -> EntailmentResult:
    """Wraps verify_derived_claim()'s verdict into an EntailmentResult, so a
    DERIVED claim can feed decoder.resolve.rules.resolve() the same way a
    document-grounded claim does (resolve() expects a uniform sequence of
    EntailmentResults regardless of source). The "span" here is synthetic —
    doc_id="__computed__", text is the rendered comparison itself — since
    there is no document passage to cite for arithmetic; this is a
    deliberate, documented convention, not a document Span standing in for
    something it isn't.
    """
    # Checked (and, if unset, raises MissingDerivedOperationError) BEFORE
    # touching claim.derived_operation below — verify_derived_claim is the
    # single source of truth for this validation; re-asserting it here
    # first would only shadow that documented exception with a bare
    # AssertionError (a real bug, caught 2026-09-15 by
    # decoder.eval actually driving a live model against real documents:
    # decompose can legitimately classify a drafted claim DERIVED without
    # being able to extract real operands from free text — its own
    # module docstring says so — and this function crashed instead of
    # letting the caller handle the documented exception).
    verdict = verify_derived_claim(claim)
    assert claim.derived_operation is not None  # verify_derived_claim guarantees this now
    operation_text = render_operation_text(claim.derived_operation)
    synthetic_span = Span(
        id=f"{claim.id}:computed",
        doc_id="__computed__",
        page=0,
        char_start=0,
        char_end=len(operation_text),
        text=operation_text,
    )
    return EntailmentResult(
        claim_id=claim.id,
        span=synthetic_span,
        verdict=verdict,
        deciding_quote=operation_text if verdict != EntailmentVerdict.NEUTRAL else None,
    )
