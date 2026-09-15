from __future__ import annotations

import pytest

import decoder
import decoder.orchestrator
from decoder.intake.interfaces import DocumentType
from decoder.llm.interface import LLMClient
from decoder.orchestrator import (
    LoadedDocument,
    PolicyDecoder,
    UnusableDocumentError,
    load_document,
)
from decoder.schema import Span, SupportState


def test_package_imports_cleanly() -> None:
    assert decoder.__version__ == "0.1.0"


def test_all_subpackages_import_cleanly() -> None:
    import decoder.eval  # noqa: F401
    import decoder.extract.interfaces  # noqa: F401
    import decoder.extract.llm_extractor  # noqa: F401
    import decoder.intake.interfaces  # noqa: F401
    import decoder.intake.span_store  # noqa: F401
    import decoder.llm.anthropic_client  # noqa: F401
    import decoder.llm.interface  # noqa: F401
    import decoder.reason.interfaces  # noqa: F401
    import decoder.resolve.rules  # noqa: F401
    import decoder.respond.answer_assembly  # noqa: F401
    import decoder.respond.labels  # noqa: F401
    import decoder.respond.question_generation  # noqa: F401
    import decoder.retrieve.dense  # noqa: F401
    import decoder.retrieve.fusion  # noqa: F401
    import decoder.retrieve.interfaces  # noqa: F401
    import decoder.retrieve.lexical_fts5  # noqa: F401
    import decoder.verify.decompose  # noqa: F401
    import decoder.verify.entailment  # noqa: F401
    import decoder.verify.numeric_check  # noqa: F401
    import decoder.verify.span_containment  # noqa: F401


_DRAFT_TEXT = "The policy applies a co-payment of 5% to every admissible claim."


class _ScriptedLLMClient(LLMClient):
    """Returns a different canned response per pipeline role, recognised by
    a marker in the system prompt — so the whole pipeline can be driven
    deterministically without a live model."""

    def __init__(
        self, entailment_response: str = "VERDICT: SUPPORTS\nQUOTE: Co-payment of 5%"
    ) -> None:
        self.entailment_response = entailment_response

    def generate(self, prompt: str, system: str, model: str) -> str:
        if "split a draft answer" in system:
            return "CLAIM: the policy | applies a co-payment of | 5% | DOCUMENT_FACT"
        if "strict fact-checker" in system:
            return self.entailment_response
        return _DRAFT_TEXT


def _document() -> LoadedDocument:
    text = "Each and every claim shall be subject to a Co-payment of 5% of the admissible amount."
    return LoadedDocument(
        doc_id="policy",
        doc_type=DocumentType.HEALTH_POLICY_WORDING,
        spans=[
            Span(id="s1", doc_id="policy", page=20, char_start=0, char_end=len(text), text=text)
        ],
    )


def test_pipeline_produces_a_resolved_answer() -> None:
    answer = PolicyDecoder(_ScriptedLLMClient()).answer([_document()], "what co-payment applies?")
    assert answer.overall_state == SupportState.WELL_SUPPORTED
    assert len(answer.claims) == 1
    assert answer.claims[0].verdicts, "a claim reached the answer without any verdict"


def test_no_answer_path_bypasses_verification() -> None:
    # §14 M4's DoD ("no answer path bypasses verification (assert this in a
    # test)") and §5's "no quick answer path" rule. The draft is the one
    # piece of model output that never passed verification, so the check
    # that matters is that its prose cannot reach the reader: the answer
    # text must be rebuilt from resolved claims, not carried through.
    answer = PolicyDecoder(_ScriptedLLMClient()).answer([_document()], "what co-payment applies?")
    assert answer.text is not None
    assert _DRAFT_TEXT not in answer.text
    assert all(resolved.verdicts for resolved in answer.claims)


def test_unverifiable_claim_is_never_well_supported() -> None:
    # Same pipeline, but the entailer finds nothing in the span. Every
    # claim must come back INSUFFICIENT_EVIDENCE — a claim that could not
    # be grounded must not inherit a supported state from anywhere else.
    llm = _ScriptedLLMClient(entailment_response="VERDICT: NEUTRAL\nQUOTE: NONE")
    answer = PolicyDecoder(llm).answer([_document()], "what co-payment applies?")
    assert answer.overall_state == SupportState.INSUFFICIENT_EVIDENCE


def test_fabricated_quote_cannot_support_a_claim() -> None:
    # The entailer returns a well-formatted SUPPORTS whose quote is not in
    # the span. decoder.verify.span_containment must force it to NEUTRAL,
    # and the answer must fall back to INSUFFICIENT_EVIDENCE rather than
    # reporting a supported claim (§7.2's hallucination trap, reached
    # through the real pipeline rather than called directly).
    llm = _ScriptedLLMClient(
        entailment_response="VERDICT: SUPPORTS\nQUOTE: a co-payment of 40% applies"
    )
    answer = PolicyDecoder(llm).answer([_document()], "what co-payment applies?")
    assert answer.overall_state == SupportState.INSUFFICIENT_EVIDENCE


def test_wrong_document_type_is_refused_before_any_analysis() -> None:
    # §9.1: "Silently analysing a motor policy as health is a catastrophic
    # first impression." The refusal must happen at load time, and must be
    # specific about what was actually uploaded.
    class _MotorClassifier:
        def classify(self, doc_id: str, raw_bytes: bytes) -> DocumentType:
            return DocumentType.MOTOR_OR_LIFE_POLICY

    class _ExplodingSegmenter:
        def segment(self, doc_id: str, raw_bytes: bytes) -> list[Span]:
            raise AssertionError("segmentation ran on a document that should have been refused")

    with pytest.raises(UnusableDocumentError) as excinfo:
        load_document(
            "motor-001", b"irrelevant", _MotorClassifier(), _ExplodingSegmenter()
        )
    assert excinfo.value.doc_type == DocumentType.MOTOR_OR_LIFE_POLICY
    assert "motor or life" in str(excinfo.value)
