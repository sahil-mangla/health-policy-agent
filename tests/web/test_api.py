"""HTTP layer tests.

These drive the REAL pipeline — real retrieval over a real corpus document,
real decomposition parsing, real hallucination trap, real resolution — with
a scripted model (web.fake_llm) standing in for the LLM. What is being
asserted is the contract the browser depends on, not a 7B model's wording.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web import corpus_library
from web.app import FAKE_LLM_ENV_VAR, create_app


@pytest.fixture(autouse=True)
def _scripted_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FAKE_LLM_ENV_VAR, "1")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _run(
    client: TestClient,
    situation: str,
    doc_id: str = "arogya_sanjeevani",
    room_tariff_per_day: float | None = None,
    sum_insured: float | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"doc_id": doc_id, "situation": situation}
    if room_tariff_per_day is not None:
        body["room_tariff_per_day"] = room_tariff_per_day
    if sum_insured is not None:
        body["sum_insured"] = sum_insured
    started = client.post("/api/analyze", json=body)
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    for _ in range(600):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            assert isinstance(job, dict)
            return job
        time.sleep(0.1)
    raise AssertionError("analysis did not finish")


def test_documents_are_listed_with_what_makes_each_worth_picking(client: TestClient) -> None:
    documents = client.get("/api/documents").json()
    assert documents
    for document in documents:
        assert document["note"], f"{document['doc_id']} has no note explaining its structure"


def test_analysis_returns_states_and_labels_from_the_decoder(client: TestClient) -> None:
    job = _run(client, "What co-payment applies to my claim?")
    assert job["status"] == "done"
    answer = job["answer"]

    assert answer["claims"], "no claims reached the browser"
    states = {c["state"] for c in answer["claims"]}
    assert "WELL_SUPPORTED" in states
    # The label must be the one decoder.respond.labels defines — the web
    # tier must not invent its own vocabulary for how sure the system is.
    supported = next(c for c in answer["claims"] if c["state"] == "WELL_SUPPORTED")
    assert supported["label"] == "Stated in your policy"


def test_every_piece_of_evidence_carries_a_real_locatable_source(client: TestClient) -> None:
    # §8: "Do not ship a citation that is only a section number." Each
    # evidence item must carry the verbatim quote plus enough provenance to
    # render the page it came from with the passage boxed.
    job = _run(client, "What co-payment applies to my claim?")
    evidence = [e for c in job["answer"]["claims"] for e in c["evidence"]]
    assert evidence
    for item in evidence:
        assert item["quote"]
        assert item["doc_id"] == "arogya_sanjeevani"
        assert item["page"] >= 1
        assert item["bbox"].count(",") == 3


def test_unsupported_claim_produces_a_specific_question(client: TestClient) -> None:
    job = _run(client, "What co-payment applies to my claim?")
    answer = job["answer"]
    unsupported = [c for c in answer["claims"] if c["state"] != "WELL_SUPPORTED"]
    assert unsupported
    assert answer["questions"]
    # The question names what was actually claimed, rather than being a
    # generic "check with your insurer" line (§2 F3).
    assert any(unsupported[0]["text"] in q for q in answer["questions"])


def test_progress_is_reported_while_running(client: TestClient) -> None:
    started = client.post(
        "/api/analyze",
        json={"doc_id": "arogya_sanjeevani", "situation": "What co-payment applies?"},
    )
    job_id = started.json()["job_id"]
    stages = set()
    for _ in range(600):
        job = client.get(f"/api/jobs/{job_id}").json()
        stages.add(job["progress"]["stage"])
        if job["status"] != "running":
            break
        time.sleep(0.02)
    assert "done" in stages
    assert stages & {"retrieving", "drafting", "decomposing", "verifying", "resolving"}


def test_page_image_renders_with_the_highlight_position(client: TestClient) -> None:
    response = client.get(
        "/api/page-image/arogya_sanjeevani/20",
        params={"bbox": "45.0,650.0,553.6,705.9"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    fraction = float(response.headers["X-Highlight-Fraction"])
    assert 0.0 <= fraction <= 1.0


def test_page_image_without_a_bbox_still_renders_the_page(client: TestClient) -> None:
    response = client.get("/api/page-image/arogya_sanjeevani/1")
    assert response.status_code == 200
    assert "X-Highlight-Fraction" not in response.headers


def test_page_beyond_the_document_is_404(client: TestClient) -> None:
    assert client.get("/api/page-image/arogya_sanjeevani/9999").status_code == 404


def test_unknown_document_is_404(client: TestClient) -> None:
    started = client.post("/api/analyze", json={"doc_id": "nope", "situation": "hello"})
    assert started.status_code == 404


def test_empty_situation_is_rejected(client: TestClient) -> None:
    started = client.post("/api/analyze", json={"doc_id": "arogya_sanjeevani", "situation": ""})
    assert started.status_code == 422


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/deadbeef").status_code == 404


def test_room_rent_inputs_expose_the_decoder_side_descriptions(client: TestClient) -> None:
    inputs = client.get("/api/room-rent-inputs").json()
    assert inputs["room_tariff_per_day"]["name"] == "room_tariff_per_day"
    assert inputs["sum_insured"]["description"]


def test_room_rent_cap_claim_always_present_even_without_inputs(client: TestClient) -> None:
    # §4's hero scenario runs unconditionally alongside the situational
    # question, whether or not the user supplied a tariff yet.
    job = _run(client, "What co-payment applies to my claim?")
    claims = job["answer"]["claims"]
    assert any("room-rent" in c["text"].lower() for c in claims)
    assert job["answer"]["room_rent_calculation"] is None  # nothing computable without SI


def test_room_rent_calculation_appears_once_both_inputs_given(client: TestClient) -> None:
    # Real Arogya Sanjeevani clause: 2% of SI, capped at ₹5,000/day. At
    # ₹1L sum insured the binding number is ₹2,000, not the flat ₹5,000 —
    # the exact case that motivated computing this in code (HANDOVER's M5
    # status note).
    job = _run(
        client,
        "What co-payment applies to my claim?",
        room_tariff_per_day=8000,
        sum_insured=100_000,
    )
    calc = job["answer"]["room_rent_calculation"]
    assert calc is not None
    assert calc["eligible_limit_per_day"] == 2000.0
    assert calc["room_tariff_per_day"] == 8000.0
    assert calc["exceeds_limit"] is True
    assert calc["deduction_ratio_percent"] == pytest.approx(25.0)

    comparison = next(
        c for c in job["answer"]["claims"] if "exceeds" in c["text"] or "within" in c["text"]
    )
    assert comparison["state"] == "WELL_SUPPORTED"
    assert "True" not in comparison["text"]  # boolean value must not leak into the rendered text


def test_room_rent_calculation_absent_without_sum_insured(client: TestClient) -> None:
    # Tariff alone isn't enough for a %-of-SI cap — must not guess a
    # sum insured to produce a number anyway.
    job = _run(client, "What co-payment applies to my claim?", room_tariff_per_day=8000)
    assert job["answer"]["room_rent_calculation"] is None
    cap_claim = next(c for c in job["answer"]["claims"] if "capped at" in c["text"])
    assert cap_claim["state"] == "NEEDS_INFORMATION"
    assert any(i["name"] == "sum_insured" for i in job["answer"]["missing_inputs"])


def test_catalogue_entries_all_point_at_real_analysable_documents() -> None:
    # A picker offering a document that cannot be opened, or that turns out
    # not to be a health policy (§9.1), is worse than a shorter list.
    for entry in corpus_library.available():
        document = corpus_library.get(entry.doc_id)
        assert document.spans, f"{entry.doc_id} segmented to nothing"
