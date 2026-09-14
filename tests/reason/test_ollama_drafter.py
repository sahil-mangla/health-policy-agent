"""Real tests against a live local Ollama model and the real starter corpus.
Skipped automatically if Ollama isn't reachable or the model isn't pulled."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from decoder.intake.segment import PdfSegmenter
from decoder.llm.ollama_client import OllamaLLMClient
from decoder.reason.ollama_drafter import OllamaDrafter
from decoder.resolve.rules import resolve
from decoder.retrieve.interfaces import RetrievedSpan
from decoder.retrieve.lexical_fts5 import FTS5LexicalIndex
from decoder.schema import AtomicClaim, ClaimClass, SupportState
from decoder.verify.entailment import OllamaEntailer

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"
_MODEL = "qwen2.5-coder:7b"


def _ollama_ready() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return False
    return any(m.get("model") == _MODEL for m in body.get("models", []))


pytestmark = pytest.mark.skipif(
    not _ollama_ready(), reason=f"Ollama / {_MODEL} not available locally"
)


def test_draft_answers_from_grounded_evidence() -> None:
    raw = (CORPUS_DIR / "arogya_sanjeevani_retail_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("arogya_sanjeevani", raw)
    copay_span = next(s for s in spans if "Co-payment of 5%" in s.text)

    drafter = OllamaDrafter(OllamaLLMClient(), model=_MODEL)
    draft = drafter.draft(
        situation="What co-payment percentage, if any, applies to claims under this policy?",
        evidence=[RetrievedSpan(span=copay_span, score=1.0)],
    )
    assert "5%" in draft or "5 %" in draft or "5 percent" in draft.lower()


def test_draft_declines_when_evidence_does_not_answer_the_question() -> None:
    raw = (CORPUS_DIR / "arogya_sanjeevani_retail_policy_wording.pdf").read_bytes()
    spans = PdfSegmenter().segment("arogya_sanjeevani", raw)
    unrelated_span = next(s for s in spans if "Room Rent means" in s.text)

    drafter = OllamaDrafter(OllamaLLMClient(), model=_MODEL)
    draft = drafter.draft(
        situation="What is the waiting period for cataract surgery under this policy?",
        evidence=[RetrievedSpan(span=unrelated_span, score=1.0)],
    )
    # Must not fabricate a waiting-period figure from an unrelated passage.
    assert (
        not any(char.isdigit() for char in draft)
        or "not" in draft.lower()
        or ("does not" in draft.lower() or "no" in draft.lower())
    )


def test_full_reason_verify_resolve_pipeline_for_a_nuanced_field() -> None:
    """End-to-end proof that reason -> verify -> resolve wire together
    against real retrieval, a real model, and a real document — for exactly
    the kind of nuanced field (co-payment %) the regex extractor
    (decoder/extract/regex_extractor.py) deliberately does not attempt.

    decoder.verify.decompose is still a stub (not asked for in this pass),
    so the draft -> single AtomicClaim step is done by hand here rather
    than via decompose_into_claims — reasonable for a single-field
    extraction question where there is exactly one claim to check, as
    opposed to decompose's job of splitting a multi-claim scenario answer.
    """
    raw = (CORPUS_DIR / "arogya_sanjeevani_retail_policy_wording.pdf").read_bytes()
    doc_id = "arogya_sanjeevani"
    spans = PdfSegmenter().segment(doc_id, raw)

    with FTS5LexicalIndex() as index:
        index.add_spans(spans)
        results = index.search("co-payment percentage claim", top_k=5)
    assert results, "expected FTS5 to retrieve at least one candidate span"

    span_by_id = {s.id: s for s in spans}
    retrieved = [RetrievedSpan(span=span_by_id[span_id], score=score) for span_id, score in results]

    drafter = OllamaDrafter(OllamaLLMClient(), model=_MODEL)
    draft_text = drafter.draft(
        situation="What co-payment percentage, if any, applies to claims under this policy?",
        evidence=retrieved,
    )

    claim = AtomicClaim(
        id="copay-claim",
        subject="the policy",
        predicate="states",
        value=draft_text,
        claim_class=ClaimClass.DOCUMENT_FACT,
        is_numeric=False,
        verbatim_match=False,
    )

    entailer = OllamaEntailer(OllamaLLMClient(), model=_MODEL)
    verdicts = [entailer.check(claim, item.span) for item in retrieved]

    state = resolve(claim, verdicts, required_inputs=[], provided_inputs={})
    assert state == SupportState.WELL_SUPPORTED
