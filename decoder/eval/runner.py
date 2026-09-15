"""Runs EvalCases against the real pipeline and grades the result —
docs/HANDOVER.md §12's metrics start here.

Mirrors web/app.py's `_run_analysis`: `analyze_room_rent` runs alongside
every situational question, exactly as the real system does, not as a
room-rent-case special case (decoder.extract.room_rent_limit's own module
docstring: "runs unconditionally alongside whatever situational question
the user actually asked").
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from decoder.eval.corpus_docs import raw_bytes
from decoder.eval.schema import EvalCase
from decoder.extract.room_rent_limit import analyze_room_rent
from decoder.llm.interface import LLMClient
from decoder.orchestrator import PolicyDecoder, load_document
from decoder.respond.answer_assembly import render_claim_statement
from decoder.schema import Answer, ResolvedClaim, SupportState


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    passed: bool
    reasons: tuple[str, ...]
    answer: Answer


@dataclass(frozen=True)
class EvalReport:
    results: tuple[CaseResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> tuple[CaseResult, ...]:
        return tuple(r for r in self.results if not r.passed)

    def appropriate_abstention_rate(self) -> float | None:
        """§12: "on cases annotated as genuinely undeterminable ... how
        often the system reaches NEEDS_INFORMATION / INSUFFICIENT_EVIDENCE
        rather than answering." None when the report has no
        correctly_abstain cases at all, rather than a misleading 0/0."""
        abstain_cases = [r for r in self.results if r.case.correctly_abstain]
        if not abstain_cases:
            return None
        return sum(1 for r in abstain_cases if r.passed) / len(abstain_cases)


_ABSTAIN_STATES = frozenset({SupportState.NEEDS_INFORMATION, SupportState.INSUFFICIENT_EVIDENCE})


def run_case(case: EvalCase, decoder: PolicyDecoder) -> CaseResult:
    """`decoder` is a caller-owned PolicyDecoder, not built fresh here — its
    embedding model (decoder.retrieve.dense.load_default_model) is a real
    transformer load, expensive enough that reloading it per case turns a
    20-case run into 20 model loads instead of one. See run_eval_set, the
    normal entry point, which builds one decoder for the whole set."""
    document = load_document(case.doc_id, raw_bytes(case.doc_id))
    room_rent = analyze_room_rent(document.spans, case.room_tariff_per_day, case.sum_insured)
    extra_resolved = [room_rent.cap_claim]
    if room_rent.comparison_claim is not None:
        extra_resolved.append(room_rent.comparison_claim)

    answer = decoder.answer(
        [document],
        case.situation,
        provided_inputs=case.provided_inputs,
        extra_resolved_claims=extra_resolved,
    )
    return _grade(case, answer)


def _grade(case: EvalCase, answer: Answer) -> CaseResult:
    reasons: list[str] = []

    for expected in case.expected:
        match = _find_claim(answer.claims, expected.concerns)
        if match is None:
            reasons.append(f"no claim found concerning {expected.concerns!r}")
            continue
        if match.state != expected.state:
            reasons.append(
                f"{expected.concerns!r}: expected {expected.state.value}, got {match.state.value}"
            )

    if case.correctly_abstain and answer.overall_state not in _ABSTAIN_STATES:
        reasons.append(
            f"expected the system to abstain (NEEDS_INFORMATION/INSUFFICIENT_EVIDENCE), "
            f"got overall_state={answer.overall_state.value}"
        )

    return CaseResult(case=case, passed=not reasons, reasons=tuple(reasons), answer=answer)


def _find_claim(claims: Sequence[ResolvedClaim], concerns: str) -> ResolvedClaim | None:
    needle = concerns.lower()
    for resolved in claims:
        if needle in render_claim_statement(resolved.claim).lower():
            return resolved
    return None


def run_eval_set(cases: Sequence[EvalCase], llm: LLMClient) -> EvalReport:
    decoder = PolicyDecoder(llm)
    return EvalReport(results=tuple(run_case(case, decoder) for case in cases))
