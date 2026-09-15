"""HTTP layer tests.

These drive the REAL pipeline — real retrieval over a real corpus document,
real decomposition parsing, real hallucination trap, real resolution — with
a scripted model (web.fake_llm) standing in for the LLM. What is being
asserted is the contract the browser depends on, not a 7B model's wording.
"""

from __future__ import annotations

import io
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web import corpus_library, uploaded_documents
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
    provided_inputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"doc_id": doc_id, "situation": situation}
    if room_tariff_per_day is not None:
        body["room_tariff_per_day"] = room_tariff_per_day
    if sum_insured is not None:
        body["sum_insured"] = sum_insured
    if provided_inputs is not None:
        body["provided_inputs"] = provided_inputs
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
    # NEEDS_INFORMATION claims (e.g. the room-rent panel's cap claim, which
    # runs unconditionally alongside every question — decoder.extract.
    # room_rent_limit) ask for their named missing input instead of quoting
    # their own claim text (decoder.respond.question_generation), so this
    # must target a claim whose state actually does interpolate claim text.
    unsupported = [
        c for c in answer["claims"] if c["state"] not in ("WELL_SUPPORTED", "NEEDS_INFORMATION")
    ]
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


# --- Upload: a real path to analyse the reader's own policy, not just the
# bundled demo picker (docs/HANDOVER.md's spec assumes a real uploaded
# policy throughout §9.1/§9.2/§9.3/§9.5, but nothing implemented that path
# until now). ---------------------------------------------------------------


def _upload(client: TestClient, filename: str, content: bytes, content_type: str) -> Any:
    return client.post("/api/upload", files={"file": (filename, io.BytesIO(content), content_type)})


def _minimal_pdf(page_text: str) -> bytes:
    """A real, valid, single-page PDF with `page_text` as its only content
    — built by hand (correct xref table, byte offsets computed as it's
    assembled) rather than depending on a PDF-writing library nothing else
    in this project needs. Distinct from an actually-broken upload (see
    test_upload_unparseable_file_is_refused...): this one must parse
    cleanly so decoder.intake.classify can reach its own keyword-based
    classification logic on real, if minimal, extracted text."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 12 Tf 10 250 Td ({page_text}) Tj ET".encode()
    objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(buf.tell())
        buf.write(f"{i} 0 obj\n".encode())
        buf.write(obj)
        buf.write(b"\nendobj\n")
    xref_offset = buf.tell()
    count = len(objects) + 1
    buf.write(f"xref\n0 {count}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buf.write(f"{offset:010d} 00000 n \n".encode())
    buf.write(b"trailer\n")
    buf.write(f"<< /Size {count} /Root 1 0 R >>\n".encode())
    buf.write(b"startxref\n")
    buf.write(f"{xref_offset}\n".encode())
    buf.write(b"%%EOF")
    return buf.getvalue()


def test_upload_a_real_document_and_then_analyse_it(client: TestClient) -> None:
    real_pdf = corpus_library.entry_for("easy_health").path.read_bytes()
    uploaded = _upload(client, "my_policy.pdf", real_pdf, "application/pdf")
    assert uploaded.status_code == 200
    doc_id = uploaded.json()["doc_id"]
    assert doc_id != "easy_health"  # a real generated id, not aliasing the bundled one

    job = _run(client, "What co-payment applies to my claim?", doc_id=doc_id)
    assert job["status"] == "done"
    assert job["answer"]["claims"]


def test_uploaded_document_evidence_renders_its_own_page_image(client: TestClient) -> None:
    # The uploaded PDF has no on-disk path (§9.5: never written to disk) —
    # this is the real regression case for web.page_image accepting bytes.
    real_pdf = corpus_library.entry_for("easy_health").path.read_bytes()
    doc_id = _upload(client, "my_policy.pdf", real_pdf, "application/pdf").json()["doc_id"]
    response = client.get(f"/api/page-image/{doc_id}/1")
    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG")


def test_upload_unparseable_file_is_refused_with_the_specific_unreadable_message(
    client: TestClient,
) -> None:
    # Not a corpus fixture at all — a genuinely non-PDF upload, which
    # pdfplumber fails on differently than a scanned-but-real PDF (raises
    # rather than returning empty text), so this exercises a distinct code
    # path from decoder.intake.classify's own UNREADABLE_SCAN detection.
    uploaded = _upload(client, "not_a_policy.txt", b"hello, this is not a pdf", "text/plain")
    assert uploaded.status_code == 422
    assert "readable text" in uploaded.json()["detail"].lower()


def test_upload_wrong_document_type_is_refused_with_its_specific_message(
    client: TestClient,
) -> None:
    # A real motor/life policy would need a fixture we don't have; a
    # minimal-but-valid PDF whose only text trips decoder.intake.classify's
    # own HOSPITAL_BILL keyword set exercises the same §9.1 refusal path
    # with a real (if tiny) document instead.
    hospital_bill_pdf = _minimal_pdf(
        "Itemized Bill No. 12345 Amount Payable Rs 40000 Discharge Summary"
    )
    uploaded = _upload(client, "bill.pdf", hospital_bill_pdf, "application/pdf")
    assert uploaded.status_code == 422
    assert "hospital bill" in uploaded.json()["detail"].lower()


def test_upload_too_large_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uploaded_documents, "MAX_UPLOAD_BYTES", 10)
    uploaded = _upload(
        client, "big.pdf", _minimal_pdf("irrelevant, rejected on size alone"), "application/pdf"
    )
    assert uploaded.status_code == 413


def test_unknown_uploaded_doc_id_is_404(client: TestClient) -> None:
    started = client.post(
        "/api/analyze", json={"doc_id": "upload-doesnotexist", "situation": "hello"}
    )
    assert started.status_code == 404


# --- Generic missing-input "offer to accept" (§8's UI-mapping table: a
# NEEDS_INFORMATION claim must "name the missing input, offer to accept
# it" — previously only room_tariff_per_day/sum_insured could ever be
# supplied at all). --------------------------------------------------------


def test_missing_continuity_date_is_named(client: TestClient) -> None:
    job = _run(client, "How long is the waiting period for pre-existing diseases?")
    claim = next(c for c in job["answer"]["claims"] if "waiting period" in c["text"].lower())
    assert claim["state"] == "NEEDS_INFORMATION"
    assert any(i["name"] == "continuity_date" for i in job["answer"]["missing_inputs"])


def test_supplying_the_named_input_resolves_the_claim(client: TestClient) -> None:
    job = _run(
        client,
        "How long is the waiting period for pre-existing diseases?",
        provided_inputs={"continuity_date": "2018-01-01"},
    )
    claim = next(c for c in job["answer"]["claims"] if "waiting period" in c["text"].lower())
    assert claim["state"] == "WELL_SUPPORTED"
    assert not any(i["name"] == "continuity_date" for i in job["answer"]["missing_inputs"])


# --- Hindi translation (§9.4: "output must be translatable... show the
# original and the translation together") and the "simpler language" chat
# quick-action (M6 status: chat as a scoped secondary affordance) — both
# previously implemented in decoder/respond/ but never reachable from the
# web tier at all. ------------------------------------------------------


def test_translate_endpoint_returns_a_translation(client: TestClient) -> None:
    response = client.post("/api/translate", json={"text": "The co-payment is 5%."})
    assert response.status_code == 200
    assert response.json()["translation"] == "[HI] The co-payment is 5%."


def test_simplify_endpoint_returns_a_rewording(client: TestClient) -> None:
    response = client.post("/api/claims/simplify", json={"text": "The co-payment is 5%."})
    assert response.status_code == 200
    assert response.json()["simplified"] == "[SIMPLE] The co-payment is 5%."


def test_translate_without_a_configured_api_key_fails_clearly(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real (non-scripted) path: no GEMINI_API_KEY in this test environment,
    # so this must fail with a clear, specific status — never a raw crash.
    monkeypatch.delenv(FAKE_LLM_ENV_VAR, raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    response = client.post("/api/translate", json={"text": "The co-payment is 5%."})
    assert response.status_code == 503
