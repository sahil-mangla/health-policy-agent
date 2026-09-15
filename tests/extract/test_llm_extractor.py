"""Real tests against a live local Ollama model and the real starter corpus
for the "verified by hand" cases (see tests/verify/test_entailment.py for
the same pattern), plus pure/synthetic tests for the parsing and
hallucination-trap logic that don't need a live model."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from decoder.extract.llm_extractor import LLMFieldExtractor, _parse_model_response
from decoder.intake.segment import PdfSegmenter
from decoder.llm.interface import LLMClient
from decoder.llm.ollama_client import OllamaLLMClient
from decoder.schema import Span

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw"
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


def _spans(relative_path: str) -> list[Span]:
    path = CORPUS_DIR / relative_path
    return PdfSegmenter().segment(path.stem, path.read_bytes())


@pytest.fixture(scope="module")
def arogya_sanjeevani_wording_spans() -> list[Span]:
    return _spans("hdfc_ergo/arogya_sanjeevani_retail_policy_wording.pdf")


@pytest.fixture(scope="module")
def easy_health_cis_spans() -> list[Span]:
    return _spans("hdfc_ergo/easy_health_cis.pdf")


@pytest.fixture(scope="module")
def optima_restore_cis_spans() -> list[Span]:
    return _spans("hdfc_ergo/optima_restore_cis.pdf")


@pytest.fixture(scope="module")
def star_comprehensive_wording_spans() -> list[Span]:
    return _spans("star_health/star_comprehensive_policy_wording.pdf")


@pytest.fixture(scope="module")
def star_comprehensive_cis_spans() -> list[Span]:
    return _spans("star_health/star_comprehensive_cis.pdf")


def test_copayment_arogya_sanjeevani(arogya_sanjeevani_wording_spans: list[Span]) -> None:
    # Real clause: "Each and every claim under the Policy shall be subject
    # to a Co-payment of 5%..." — same span test_entailment.py's copay
    # tests use, confirmed here for extraction rather than verification.
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "co_payment_percent", arogya_sanjeevani_wording_spans
    )
    assert field.value == 5.0
    assert field.unit == "PERCENT"
    assert field.verbatim_match is True
    assert len(field.spans) > 0


def test_copayment_star_comprehensive_senior_citizen(
    star_comprehensive_cis_spans: list[Span],
) -> None:
    # Real clause: "This policy is subject to co-payment of 10% of each and
    # every claim amount ... for Insured Persons whose age at the time of
    # entry is 61 [and above]" — a different insurer, different number,
    # confirming the extractor isn't overfit to one document's phrasing.
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "co_payment_percent", star_comprehensive_cis_spans
    )
    assert field.value == 10.0
    assert field.verbatim_match is True


def test_ped_waiting_period_arogya_sanjeevani(
    arogya_sanjeevani_wording_spans: list[Span],
) -> None:
    # Real clause: "...shall be excluded until the expiry of 36months of
    # continuous coverage after the date of inception of the first policy
    # with us."
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "waiting_period_ped_months", arogya_sanjeevani_wording_spans
    )
    assert field.value == 36.0
    assert field.verbatim_match is True


def test_initial_waiting_period_star_comprehensive(
    star_comprehensive_wording_spans: list[Span],
) -> None:
    # Real clause: "An initial waiting period of 30 days shall apply from
    # the first inception of..."
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "waiting_period_initial_days", star_comprehensive_wording_spans
    )
    assert field.value == 30.0
    assert field.unit == "DAYS"
    assert field.verbatim_match is True


def test_initial_waiting_period_optima_restore(optima_restore_cis_spans: list[Span]) -> None:
    # Real clause: "Initial waiting Period: 30 days for all illnesses..."
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "waiting_period_initial_days", optima_restore_cis_spans
    )
    assert field.value == 30.0


def test_specific_illness_waiting_period_easy_health(easy_health_cis_spans: list[Span]) -> None:
    # Real clause: "...24 months for listed diseases/procedure..." — the
    # source PDF's two-column layout interleaves this clause's text, so this
    # is also a real test of the extractor tolerating messy segmentation.
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "waiting_period_specific_illness_months", easy_health_cis_spans
    )
    assert field.value == 24.0


def test_room_category_eligibility_not_in_starter_corpus() -> None:
    # None of the starter corpus documents state an explicit room CATEGORY
    # eligibility clause (corpus/README.md's own "still needed" list flags
    # this gap) — this is not a hand-verified positive case; it exists to
    # record that gap rather than silently skip the field.
    #
    # This is also a real caught false-positive, not a hypothetical: the
    # first version of this field's prompt matched Easy Health's "Def. 17
    # Single occupancy ... means a Hospital room with only one patient bed"
    # — a glossary entry, not an eligibility statement — because it never
    # told the model to tell the two apart. Fixed by tightening the field
    # description to explicitly exclude definition-shaped clauses; this
    # test is what would catch a regression of that.
    all_spans: list[Span] = []
    for rel in [
        "hdfc_ergo/easy_health_policy_wording.pdf",
        "hdfc_ergo/arogya_sanjeevani_retail_policy_wording.pdf",
    ]:
        all_spans.extend(_spans(rel))
    field = LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
        "room_category_eligibility", all_spans
    )
    assert field.value is None
    assert field.spans == []


def test_unknown_field_name_raises_not_implemented(
    arogya_sanjeevani_wording_spans: list[Span],
) -> None:
    with pytest.raises(NotImplementedError):
        LLMFieldExtractor(OllamaLLMClient(), model=_MODEL).extract(
            "proportionate_deduction_carveouts", arogya_sanjeevani_wording_spans
        )


class _FakeLLMClient(LLMClient):
    """Pure stand-in for tests that don't need a live model: returns
    `response` for every call, regardless of prompt/system/model."""

    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, prompt: str, system: str, model: str) -> str:
        return self._response


def _span(text: str, span_id: str = "s1") -> Span:
    return Span(id=span_id, doc_id="synthetic", page=1, char_start=0, char_end=len(text), text=text)


def test_hallucination_trap_drops_fabricated_quote() -> None:
    # The model claims FOUND: YES with a quote that is not actually in the
    # span — must be discarded, not trusted, exactly like
    # decoder.verify.entailment's deciding-words trap.
    fake = _FakeLLMClient("FOUND: YES\nQUOTE: a co-payment of 99%")
    span = _span("Each and every claim is subject to a Co-payment of 5%.")
    field = LLMFieldExtractor(fake).extract("co_payment_percent", [span])
    assert field.value is None
    assert field.spans == []


def test_verified_quote_with_no_parseable_number_fails_closed() -> None:
    # The model's quote IS verbatim in the span (passes the hallucination
    # trap) but contains no number this field's regex can parse — the span
    # must still be dropped, not trusted with a guessed value.
    fake = _FakeLLMClient("FOUND: YES\nQUOTE: subject to a Co-payment")
    span = _span("Each and every claim is subject to a Co-payment of 5%.")
    field = LLMFieldExtractor(fake).extract("co_payment_percent", [span])
    assert field.value is None


def test_found_no_yields_not_found() -> None:
    fake = _FakeLLMClient("FOUND: NO\nQUOTE: NONE")
    span = _span("Each and every claim is subject to a Co-payment of 5%.")
    field = LLMFieldExtractor(fake).extract("co_payment_percent", [span])
    assert field.value is None
    assert field.spans == []


def test_malformed_response_fails_closed() -> None:
    assert _parse_model_response("I think there might be a co-payment here.") is None


def test_text_field_value_is_the_verified_quote_itself() -> None:
    fake = _FakeLLMClient("FOUND: YES\nQUOTE: single private AC room")
    span = _span("The Insured Person is eligible for a single private AC room only.")
    field = LLMFieldExtractor(fake).extract("room_category_eligibility", [span])
    assert field.value == "single private AC room"
    assert field.verbatim_match is True


def test_conflicting_candidates_are_surfaced_not_silently_resolved() -> None:
    # Two spans disagreeing on the co-payment percentage — a fake LLM that
    # echoes back whatever's in the passage it was given, so each span
    # yields its own (verbatim) quote.
    class _EchoingFakeLLMClient(LLMClient):
        def generate(self, prompt: str, system: str, model: str) -> str:
            passage = prompt.removeprefix("Passage: ")
            return f"FOUND: YES\nQUOTE: {passage}"

    span_a = _span("Co-payment of 5% applies to every claim.", span_id="a")
    span_b = _span("An endorsement raises the Co-payment to 10%.", span_id="b")
    field = LLMFieldExtractor(_EchoingFakeLLMClient()).extract(
        "co_payment_percent", [span_a, span_b]
    )
    assert len(field.conflicting_candidates) == 2
    values = {c.value for c in field.conflicting_candidates}
    assert values == {5.0, 10.0}
