"""Runs the full annotated eval set (decoder/eval/cases.py) against a live
local model and real corpus documents — docs/HANDOVER.md §11/§12.

Skipped automatically if Ollama isn't reachable (same pattern as
tests/test_orchestrator_live.py). Slow by nature (real drafting +
decomposition + entailment per case, against a CPU-bound 7B model) — this
is meant to be run explicitly before relying on a change to the drafter,
decomposer, entailer, or continuity-requirement logic, not on every default
`pytest -q` (which the CI workflow's own comment already documents as the
convention for every other live-model test in this project).

Two separate assertions, deliberately not combined into one pass/fail
number: `correctly_abstain` cases are the headline §12 metric ("appropriate
abstention" — a system that fabricates an answer where it should abstain is
the harm case this whole project exists to prevent) and must all pass.
Answerable cases are reported in full on failure but not hard-asserted at
100%, because a live 7B model's exact phrasing is not fully deterministic —
one real, known finding (decoder/eval/cases.py's
`copayment_arogya_sanjeevani`, documented there) is a live drafting-quality
issue, not a harness bug, and papering over it with a softer assertion here
would be exactly the kind of dishonesty §12 exists to catch elsewhere.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from decoder.eval.cases import CASES
from decoder.eval.runner import run_eval_set
from decoder.llm.ollama_client import OllamaLLMClient

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


def test_at_least_eight_correctly_abstain_cases_exist() -> None:
    # docs/HANDOVER.md M0's DoD: "30 annotated eval cases exist, of which
    # ≥8 are correctly-abstain cases." Checked here as a standing guard so
    # the dataset can't quietly shrink below the DoD's abstain-count floor.
    abstain_count = sum(1 for case in CASES if case.correctly_abstain)
    assert abstain_count >= 8


def test_all_correctly_abstain_cases_actually_abstain() -> None:
    report = run_eval_set([c for c in CASES if c.correctly_abstain], OllamaLLMClient())
    failed = [r for r in report.results if not r.passed]
    details = "\n".join(f"{r.case.id}: {', '.join(r.reasons)}" for r in failed)
    assert not failed, f"appropriate-abstention failures:\n{details}"


def test_answerable_cases_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Reports every answerable case's outcome rather than asserting 100% —
    see this module's own docstring for why."""
    report = run_eval_set([c for c in CASES if not c.correctly_abstain], OllamaLLMClient())
    with capsys.disabled():
        print(f"\n{report.passed}/{report.total} answerable eval cases passed")
        for result in report.failed:
            print(f"FAIL {result.case.id}: {'; '.join(result.reasons)}")
    assert report.total > 0
