from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from decoder.llm.ollama_client import OllamaLLMClient
from decoder.schema import ClaimClass
from decoder.verify.decompose import OllamaDecomposer, _parse_claim_line

_MODEL = "qwen2.5-coder:7b"


class TestParseClaimLine:
    """Pure parsing logic — no model call. This is the defensive half that
    matters most: malformed lines must be dropped, never guessed-and-kept."""

    def test_well_formed_line_parses(self) -> None:
        line = (
            "CLAIM: the policy | specifies a room-rent limit of | INR 5,000 per day | DOCUMENT_FACT"
        )
        claim = _parse_claim_line(line)
        assert claim is not None
        assert claim.subject == "the policy"
        assert claim.predicate == "specifies a room-rent limit of"
        assert claim.value == "INR 5,000 per day"
        assert claim.claim_class == ClaimClass.DOCUMENT_FACT
        assert claim.is_numeric is True

    def test_non_claim_line_is_dropped(self) -> None:
        assert _parse_claim_line("Here are the claims:") is None

    def test_wrong_field_count_is_dropped(self) -> None:
        # 4 pipes (5 fields) instead of exactly 3 pipes — seen for real
        # from a live model on a DERIVED comparison (2026-09-14).
        line = "CLAIM: a room at | INR 8,000 per day | exceeds | the INR 5,000 limit | DERIVED"
        assert _parse_claim_line(line) is None

    def test_unrecognized_class_is_dropped(self) -> None:
        line = "CLAIM: the policy | covers | AYUSH treatment | SOMETHING_ELSE"
        assert _parse_claim_line(line) is None

    def test_empty_field_is_dropped(self) -> None:
        line = "CLAIM: a room | costs INR 8,000 per day |  | DERIVED"
        assert _parse_claim_line(line) is None

    def test_non_numeric_value_sets_is_numeric_false(self) -> None:
        line = "CLAIM: the policy | covers | AYUSH treatment | DOCUMENT_FACT"
        claim = _parse_claim_line(line)
        assert claim is not None
        assert claim.is_numeric is False

    def test_case_insensitive_class_word(self) -> None:
        line = "CLAIM: the policy | covers | AYUSH treatment | document_fact"
        claim = _parse_claim_line(line)
        assert claim is not None
        assert claim.claim_class == ClaimClass.DOCUMENT_FACT


def _ollama_ready() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return False
    return any(m.get("model") == _MODEL for m in body.get("models", []))


@pytest.mark.skipif(not _ollama_ready(), reason=f"Ollama / {_MODEL} not available locally")
def test_decomposes_a_real_multi_claim_draft() -> None:
    # The hero scenario's own worked example (docs/HANDOVER.md §7.1).
    draft = (
        "The policy specifies a room-rent limit of INR 5,000 per day. "
        "The policy applies proportionate deduction to associated medical "
        "expenses when the room rent exceeds the eligible limit."
    )
    decomposer = OllamaDecomposer(OllamaLLMClient(), model=_MODEL)
    claims = decomposer.decompose(draft)
    # At least the two DOCUMENT_FACT claims should come through cleanly —
    # not asserting on exact count/wording since that's model-dependent,
    # only that decomposition produces usable, well-typed claims at all.
    assert len(claims) >= 1
    assert all(c.claim_class in ClaimClass for c in claims)
    assert any("5,000" in str(c.value) or "5000" in str(c.value) for c in claims)
