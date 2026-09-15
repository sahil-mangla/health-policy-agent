"""Full pipeline against real corpus documents and a live local model —
intake through to an assembled Answer, nothing mocked.

Skipped automatically if Ollama isn't reachable (same pattern as
tests/verify/test_entailment.py). Every expectation here was checked by
hand against the actual output before being written (2026-09-15).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from decoder.intake.interfaces import DocumentType
from decoder.llm.ollama_client import OllamaLLMClient
from decoder.orchestrator import LoadedDocument, PolicyDecoder, load_document
from decoder.respond.question_generation import generate_follow_up_questions
from decoder.schema import EntailmentVerdict, SupportState

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus" / "raw"
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


@pytest.fixture(scope="module")
def arogya_sanjeevani() -> LoadedDocument:
    path = CORPUS_DIR / "hdfc_ergo" / "arogya_sanjeevani_retail_policy_wording.pdf"
    return load_document("arogya_sanjeevani", path.read_bytes())


def _decoder() -> PolicyDecoder:
    # top_k is small on purpose: every retrieved span is entailed against
    # every claim (§7.2), so this is the dominant cost in the test suite.
    return PolicyDecoder(OllamaLLMClient(), model=_MODEL, top_k=4)


def test_real_policy_classifies_as_health_policy_wording(
    arogya_sanjeevani: LoadedDocument,
) -> None:
    assert arogya_sanjeevani.doc_type == DocumentType.HEALTH_POLICY_WORDING
    assert len(arogya_sanjeevani.spans) > 100


def test_answerable_question_produces_supported_claims_with_real_spans(
    arogya_sanjeevani: LoadedDocument,
) -> None:
    # This policy really does state "a Co-payment of 5%" (the same clause
    # tests/verify/test_entailment.py checks against).
    answer = _decoder().answer([arogya_sanjeevani], "What co-payment applies to my claim?")

    assert answer.overall_state != SupportState.INSUFFICIENT_EVIDENCE
    assert answer.claims

    supporting = [
        verdict
        for resolved in answer.claims
        for verdict in resolved.verdicts
        if verdict.verdict == EntailmentVerdict.SUPPORTS
    ]
    assert supporting, "no claim was grounded in any real span"
    for verdict in supporting:
        # The evidence path must end at real text in a real document, not
        # a section number (§8) — and the quote must actually be there.
        assert verdict.deciding_quote is not None
        assert verdict.deciding_quote in verdict.span.text
        assert verdict.span.doc_id == "arogya_sanjeevani"

    assert answer.text is not None
    assert "5%" in answer.text


def test_unanswerable_question_abstains_rather_than_inventing(
    arogya_sanjeevani: LoadedDocument,
) -> None:
    # The documents genuinely do not address this. The correct output is
    # not an answer — it is the right abstention (§11's adversarial intent,
    # §12's appropriate-abstention metric).
    answer = _decoder().answer(
        [arogya_sanjeevani],
        "Does my policy cover dental implants for purely cosmetic reasons?",
    )
    assert answer.overall_state in {
        SupportState.INSUFFICIENT_EVIDENCE,
        SupportState.NEEDS_INFORMATION,
    }
    for resolved in answer.claims:
        assert resolved.state != SupportState.WELL_SUPPORTED


def test_answer_text_never_carries_the_unverified_draft(
    arogya_sanjeevani: LoadedDocument,
) -> None:
    # §5's no-fast-path rule against a real model: whatever the drafter
    # wrote, the reader only ever sees text rebuilt from resolved claims,
    # each line carrying a state label from §8's mapping.
    answer = _decoder().answer([arogya_sanjeevani], "What co-payment applies to my claim?")
    assert answer.text is not None
    for resolved in answer.claims:
        assert f"{resolved.claim.subject} {resolved.claim.predicate}" in answer.text
    assert answer.text.startswith("[")


def test_gaps_produce_specific_questions_supported_claims_do_not(
    arogya_sanjeevani: LoadedDocument,
) -> None:
    answer = _decoder().answer([arogya_sanjeevani], "What co-payment applies to my claim?")
    questions = generate_follow_up_questions(list(answer.claims))
    unsupported = [r for r in answer.claims if r.state != SupportState.WELL_SUPPORTED]
    assert len(questions) == len(unsupported)
