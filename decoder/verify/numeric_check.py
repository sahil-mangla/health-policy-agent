"""DERIVED claim verification — docs/HANDOVER.md §7.2.

"DERIVED [claims are] executed in code. The inputs must themselves be
verified claims." Pure arithmetic, no model call — and deliberately no
attempt to extract the operation from a model's free-text draft (see
decoder.schema.DerivedOperation's docstring for why that was tried and
rejected). A DERIVED AtomicClaim must carry a populated `derived_operation`
before this can verify it; that field is set by whatever code already has
the operand values on hand (e.g. a user-supplied room tariff compared
against an already-extracted numeric field), not by decompose.
"""

from __future__ import annotations

from collections.abc import Callable

from decoder.schema import AtomicClaim, DerivedOperation, EntailmentResult, EntailmentVerdict, Span

_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "GREATER_THAN": lambda left, right: left > right,
    "LESS_THAN": lambda left, right: left < right,
    "GREATER_OR_EQUAL": lambda left, right: left >= right,
    "LESS_OR_EQUAL": lambda left, right: left <= right,
    "EQUAL": lambda left, right: left == right,
}


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
    assert claim.derived_operation is not None  # verify_derived_claim already checks this
    operation_text = render_operation_text(claim.derived_operation)
    verdict = verify_derived_claim(claim)
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
