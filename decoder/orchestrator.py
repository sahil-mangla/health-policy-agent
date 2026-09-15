"""The single public entry point for producing a user-facing Answer.

Pipeline (docs/HANDOVER.md §5): intake -> retrieve -> reason (draft) ->
verify (decompose + entail) -> resolve (support state) -> respond (assemble).

Structural guarantee, not just convention: decoder.respond.answer_assembly.
assemble_answer() only accepts list[ResolvedClaim] (decoder.schema), and the
only function that can construct a ResolvedClaim is decoder.resolve.rules.
resolve(). There is no function anywhere in this codebase that turns a raw
AtomicClaim or LLM draft directly into an Answer — verification and
resolution are not optional stops on the way to a response, they are the
only door in. The drafter's prose is used solely as decomposition input and
never reaches the returned Answer.

Retrieval here is lexical-only (decoder.retrieve.lexical_fts5). Dense
retrieval is still a stub blocked on corpus size, and §10 requires hybrid
retrieval — so this pipeline currently under-retrieves relative to the
spec, which shows up as a recall gap (a contradicting span that only dense
retrieval would have found is never entailed against), not as a wrong
answer. Wire decoder.retrieve.dense + fusion.reciprocal_rank_fusion in here
when M2 lands; nothing else in this module changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from decoder.intake.classify import HeuristicDocumentClassifier, is_policy_expired
from decoder.intake.interfaces import DocumentClassifier, DocumentType, Segmenter
from decoder.intake.segment import PdfSegmenter
from decoder.intake.span_store import InMemorySpanStore
from decoder.llm.interface import LLMClient
from decoder.reason.ollama_drafter import OllamaDrafter
from decoder.resolve.rules import resolve
from decoder.respond.answer_assembly import assemble_answer
from decoder.respond.labels import UNUSABLE_DOCUMENT_MESSAGES
from decoder.retrieve.interfaces import RetrievedSpan
from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import (
    Answer,
    AtomicClaim,
    ClaimClass,
    EntailmentResult,
    EntailmentVerdict,
    ResolvedClaim,
    Span,
    SupportState,
)
from decoder.verify.continuity_requirement import attach_continuity_requirement
from decoder.verify.decompose import OllamaDecomposer
from decoder.verify.entailment import OllamaEntailer
from decoder.verify.numeric_check import (
    entailment_result_for_derived_claim,
    numeric_value_appears_verbatim,
)

ANALYSABLE_DOCUMENT_TYPES = frozenset(
    {DocumentType.HEALTH_POLICY_WORDING, DocumentType.CUSTOMER_INFORMATION_SHEET}
)


class UnusableDocumentError(ValueError):
    """§9.1: a document of the wrong type is refused before any analysis
    runs, with a message specific to what was actually uploaded. Carries
    the classified type so a caller can react to the kind of mistake, not
    just print the message."""

    def __init__(self, doc_id: str, doc_type: DocumentType, message: str) -> None:
        super().__init__(message)
        self.doc_id = doc_id
        self.doc_type = doc_type


@dataclass(frozen=True)
class LoadedDocument:
    doc_id: str
    doc_type: DocumentType
    spans: list[Span]


@dataclass(frozen=True)
class Progress:
    """Where the pipeline has got to. Reported rather than estimated: a full
    run is dominated by claims x top_k entailment calls and takes tens of
    seconds, so a caller showing a progress indicator would otherwise have
    to invent one, and an invented progress bar is its own small lie."""

    stage: str
    detail: str = ""
    completed: int = 0
    total: int = 0


ProgressCallback = Callable[[Progress], None]


def load_document(
    doc_id: str,
    raw_bytes: bytes,
    classifier: DocumentClassifier | None = None,
    segmenter: Segmenter | None = None,
) -> LoadedDocument:
    """Classify first, segment second — §9.1's "classify on intake before
    anything else", enforced by ordering here rather than left to callers:
    a wrong-type document raises before a single span is produced."""
    classifier = classifier or HeuristicDocumentClassifier()
    doc_type = classifier.classify(doc_id, raw_bytes)

    # §9.2: analysis of a lapsed policy is misinformation, so this check
    # runs before the type gate below rather than after — an expired
    # policy is caught the same way a wrong document type is, not as an
    # afterthought once analysis has already started. Only overrides
    # doc_type when expiry is POSITIVELY confirmed (never on None — §9.2
    # forbids guessing "not expired" from an absence of dates).
    if doc_type in ANALYSABLE_DOCUMENT_TYPES and is_policy_expired(raw_bytes) is True:
        doc_type = DocumentType.EXPIRED_POLICY

    if doc_type not in ANALYSABLE_DOCUMENT_TYPES:
        raise UnusableDocumentError(doc_id, doc_type, UNUSABLE_DOCUMENT_MESSAGES[doc_type])
    segmenter = segmenter or PdfSegmenter()
    return LoadedDocument(
        doc_id=doc_id, doc_type=doc_type, spans=segmenter.segment(doc_id, raw_bytes)
    )


class PolicyDecoder:
    """Runs the full pipeline for one situation against already-loaded
    documents.

    `top_k` is a real cost knob, not a tuning detail: every retrieved span
    is entailed against every claim (§7.2's "run every claim against all
    retrieved spans"), so LLM calls scale as claims x top_k.
    """

    def __init__(
        self,
        llm: LLMClient,
        model: str = "qwen2.5-coder:7b",
        top_k: int = 8,
    ) -> None:
        self._drafter = OllamaDrafter(llm, model=model)
        self._decomposer = OllamaDecomposer(llm, model=model)
        self._entailer = OllamaEntailer(llm, model=model)
        self._top_k = top_k

    def answer(
        self,
        documents: Sequence[LoadedDocument],
        situation: str,
        provided_inputs: Mapping[str, object] | None = None,
        derived_claims: Sequence[AtomicClaim] = (),
        extra_resolved_claims: Sequence[ResolvedClaim] = (),
        on_progress: ProgressCallback | None = None,
    ) -> Answer:
        """`derived_claims` are DERIVED AtomicClaims built by code that
        already holds the real operand values (e.g. an extracted room-rent
        cap against a user-supplied tariff). They are deliberately not
        parsed out of the draft — see decoder.schema.DerivedOperation for
        why — and are verified arithmetically rather than by entailment
        here, through the usual per-claim resolution path.

        `extra_resolved_claims` is a different shape for a different
        reason: ResolvedClaims a caller has ALREADY fully resolved outside
        this pipeline (decoder.extract.room_rent_limit is the first real
        source — its cap claim is grounded directly in an extraction's own
        span, not in anything retrieval would find for the user's
        situational question, so re-running it through entailment here
        would be both redundant and wrong). These are merged straight into
        the answer, unmodified — and placed FIRST, ahead of the drafted
        claims: they're grounded in code-verified arithmetic over a real
        extraction rather than the drafter's own free-text summary of the
        same clause, so a reader should reach them before a claim that may
        flatten the same fact (§12/§14's headline harm case — the drafter's
        own room-rent claim stating just the flat cap, correct number
        appearing only afterward). This doesn't suppress the drafted claim,
        it only fixes which one a hasty reader sees first.
        """
        report = on_progress or _ignore_progress
        provided = dict(provided_inputs or {})

        report(Progress("retrieving", "Searching your documents"))
        evidence = self._retrieve(documents, situation)

        report(Progress("drafting", "Reading the clauses found"))
        draft = self._drafter.draft(situation, evidence)

        report(Progress("decomposing", "Splitting into checkable claims"))
        claims = self._decomposer.decompose(draft)
        # §9.3: a waiting-period claim's applicability depends on
        # continuous coverage, which decompose has no way to know about on
        # its own — attached here, uniformly, regardless of which document
        # or claim class produced the claim.
        claims = attach_continuity_requirement(claims)

        # Non-DERIVED first, so a DERIVED claim's inputs already have
        # resolved states by the time it needs them (§8's DERIVED branch,
        # and decoder.schema.AtomicClaim's note on input_claim_ids).
        plain = [c for c in claims if c.claim_class != ClaimClass.DERIVED]
        derived = [c for c in claims if c.claim_class == ClaimClass.DERIVED]
        total = len(plain) + len(derived) + len(derived_claims)

        resolved: list[ResolvedClaim] = []
        for claim in plain:
            report(Progress("verifying", "Checking each claim", len(resolved), total))
            resolved.append(self._resolve_claim(claim, evidence, provided, {}))
        states_by_claim_id = {r.claim.id: r.state for r in resolved}

        for claim in [*derived, *derived_claims]:
            report(Progress("verifying", "Checking each claim", len(resolved), total))
            resolved.append(self._resolve_claim(claim, evidence, provided, states_by_claim_id))

        report(Progress("resolving", "Deciding what is actually supported", total, total))
        return assemble_answer([*extra_resolved_claims, *resolved], provided)

    def _retrieve(self, documents: Sequence[LoadedDocument], situation: str) -> list[RetrievedSpan]:
        store = InMemorySpanStore()
        with FTS5LexicalIndex() as index:
            for document in documents:
                for span in document.spans:
                    store.add(span)
                    index.add_span(span)
            hits = index.search(situation, top_k=self._top_k)

        evidence: list[RetrievedSpan] = []
        for span_id, score in hits:
            hit_span = store.get(span_id)
            if hit_span is not None:
                evidence.append(RetrievedSpan(span=hit_span, score=score))
        return evidence

    def _resolve_claim(
        self,
        claim: AtomicClaim,
        evidence: Sequence[RetrievedSpan],
        provided_inputs: Mapping[str, object],
        states_by_claim_id: Mapping[str, SupportState],
    ) -> ResolvedClaim:
        verdicts = self._verdicts_for(claim, evidence)
        claim = _with_numeric_verbatim_check(claim, verdicts)
        input_states = [
            states_by_claim_id[input_id]
            for input_id in claim.input_claim_ids
            if input_id in states_by_claim_id
        ]
        state = resolve(
            claim=claim,
            verdicts=verdicts,
            required_inputs=claim.required_inputs,
            provided_inputs=provided_inputs,
            input_claim_states=input_states,
        )
        return ResolvedClaim(claim=claim, verdicts=verdicts, state=state)

    def _verdicts_for(
        self, claim: AtomicClaim, evidence: Sequence[RetrievedSpan]
    ) -> list[EntailmentResult]:
        if claim.claim_class == ClaimClass.DERIVED:
            # Executed in code, never asked of a model (§7.2).
            return [entailment_result_for_derived_claim(claim)]
        # Every claim against every retrieved span, not just the one the
        # drafter cited: "Contradictions are found by looking, not by
        # hoping" (§7.2).
        return [self._entailer.check(claim, item.span) for item in evidence]


def _ignore_progress(progress: Progress) -> None:
    """Default when a caller doesn't care — keeps `answer()` free of
    `if on_progress is not None` noise at every stage."""


def _with_numeric_verbatim_check(
    claim: AtomicClaim, verdicts: Sequence[EntailmentResult]
) -> AtomicClaim:
    """§7.2's `DOCUMENT_FACT`, numeric row — the figure itself is checked by
    exact string match in code, independently of what the model concluded.

    Decompose always emits verbatim_match=False (it never checks grounding),
    so without this step every numeric document fact would be downgraded to
    NEEDS_CONFIRMATION by §8's rule even when the figure is plainly there in
    the cited clause. Only spans the entailer marked SUPPORTS are searched:
    finding the number inside a span that contradicts the claim is not
    grounding, it is a coincidence.
    """
    if claim.claim_class != ClaimClass.DOCUMENT_FACT or not claim.is_numeric:
        return claim
    supporting_texts = [
        verdict.span.text for verdict in verdicts if verdict.verdict == EntailmentVerdict.SUPPORTS
    ]
    verbatim = any(
        numeric_value_appears_verbatim(str(claim.value), text) for text in supporting_texts
    )
    return claim.model_copy(update={"verbatim_match": verbatim})
