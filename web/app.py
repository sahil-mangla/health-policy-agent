"""HTTP layer for the analysis view.

Deliberately thin: it starts pipeline runs, reports their progress, and
serializes the resulting Answer. It makes no judgement of its own about
what is supported — every state and label the reader sees comes from
decoder.resolve and decoder.respond.labels, so there is no second,
divergent opinion about evidence living in the web tier.

Analysis runs in a background thread and is polled, rather than being
awaited in the request: a real run is tens of seconds of LLM calls, and
§8's states are worth waiting for with an honest progress indicator rather
than behind a spinner that has to invent one.

PII (§9.5): document text reaches the browser (it is the evidence — §8
requires the verbatim span), but nothing here logs it, and job records live
in memory for the life of the process only.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, Thread
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from decoder.extract.room_rent_limit import (
    ROOM_TARIFF_INPUT,
    SUM_INSURED_INPUT,
    RoomRentAnalysis,
    analyze_room_rent,
)
from decoder.llm.interface import LLMClient
from decoder.llm.ollama_client import OllamaLLMClient
from decoder.orchestrator import LoadedDocument, PolicyDecoder, Progress, UnusableDocumentError
from decoder.respond.answer_assembly import render_claim_statement
from decoder.respond.labels import SUPPORT_STATE_LABELS
from decoder.respond.question_generation import generate_follow_up_questions
from decoder.retrieve.dense import EmbeddingModel
from decoder.schema import Answer, EntailmentVerdict
from web import corpus_library
from web.page_image import PageImageError, render_page_with_span

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Browser tests and API tests drive the real pipeline code with a scripted
# model instead of a live one: the UI contract (§8) is what they assert, and
# tying those assertions to a 7B model's wording would make them flaky for
# reasons that have nothing to do with the UI.
FAKE_LLM_ENV_VAR = "POLICY_AGENT_FAKE_LLM"


class AnalyzeRequest(BaseModel):
    doc_id: str
    situation: str = Field(min_length=1, max_length=2000)
    # §4's hero scenario, both optional: without them the cap itself is
    # still reported (or its absence is), just not compared against
    # anything yet. See decoder.extract.room_rent_limit for why sum
    # insured is a required INPUT here rather than an extracted field —
    # it's a per-policyholder choice, not something the generic wording
    # or CIS states.
    room_tariff_per_day: float | None = Field(default=None, gt=0)
    sum_insured: float | None = Field(default=None, gt=0)


class JobStarted(BaseModel):
    job_id: str


class ProgressOut(BaseModel):
    stage: str
    detail: str
    completed: int
    total: int


class EvidenceOut(BaseModel):
    verdict: Literal["SUPPORTS", "CONTRADICTS"]
    quote: str
    doc_id: str
    page: int
    span_id: str
    # "x0,top,x1,bottom" in PDF points, or "" when the span carries no
    # geometry — the browser passes it straight back to /api/page-image to
    # get the page with this span boxed (§8's evidence path).
    bbox: str


class ClaimOut(BaseModel):
    text: str
    state: str
    label: str
    claim_class: str
    evidence: list[EvidenceOut]


class RoomRentCalculationOut(BaseModel):
    """§4 point 3: "show the arithmetic explicitly, with the input numbers
    labelled." The underlying cap/comparison claims already appear in
    `claims` with their citations — this is the same numbers laid out as
    a labelled calculation rather than prose, for the UI's dedicated
    arithmetic panel."""

    eligible_limit_per_day: float | None
    room_tariff_per_day: float | None
    exceeds_limit: bool | None
    deduction_ratio_percent: float | None


class AnswerOut(BaseModel):
    overall_state: str
    overall_label: str
    claims: list[ClaimOut]
    questions: list[str]
    missing_inputs: list[dict[str, str]]
    room_rent_calculation: RoomRentCalculationOut | None
    text: str | None


class JobOut(BaseModel):
    job_id: str
    status: Literal["running", "done", "failed"]
    progress: ProgressOut
    answer: AnswerOut | None = None
    error: str | None = None


@dataclass
class _Job:
    job_id: str
    status: str = "running"
    progress: Progress = field(default_factory=lambda: Progress("queued", "Starting"))
    answer: Answer | None = None
    room_rent: RoomRentAnalysis | None = None
    error: str | None = None


_jobs: dict[str, _Job] = {}
_jobs_lock = Lock()


def _llm_client() -> LLMClient:
    if os.environ.get(FAKE_LLM_ENV_VAR):
        from web.fake_llm import ScriptedLLMClient

        return ScriptedLLMClient()
    return OllamaLLMClient()


_embedding_model_cache: EmbeddingModel | None = None


def _embedding_model() -> EmbeddingModel:
    """Cached at process scope, unlike `_llm_client()` — an LLMClient is
    cheap to construct (it connects lazily), but the real embedding model
    means loading an actual transformer, which every job would otherwise
    pay for again."""
    global _embedding_model_cache
    if _embedding_model_cache is None:
        if os.environ.get(FAKE_LLM_ENV_VAR):
            from web.fake_llm import FakeEmbeddingModel

            _embedding_model_cache = FakeEmbeddingModel()
        else:
            from decoder.retrieve.dense import load_default_model

            _embedding_model_cache = load_default_model()
    return _embedding_model_cache


def create_app() -> FastAPI:
    app = FastAPI(title="Health Policy Decoder")

    @app.get("/api/documents")
    def list_documents() -> list[dict[str, str]]:
        return [
            {
                "doc_id": entry.doc_id,
                "insurer": entry.insurer,
                "product": entry.product,
                "note": entry.note,
            }
            for entry in corpus_library.available()
        ]

    @app.get("/api/room-rent-inputs")
    def room_rent_inputs() -> dict[str, dict[str, str]]:
        # Single source of truth for the two optional §4 inputs' help text
        # — decoder.extract.room_rent_limit's own RequiredInput objects,
        # not a copy the UI could drift from.
        return {
            "room_tariff_per_day": {
                "name": ROOM_TARIFF_INPUT.name,
                "description": ROOM_TARIFF_INPUT.description,
            },
            "sum_insured": {
                "name": SUM_INSURED_INPUT.name,
                "description": SUM_INSURED_INPUT.description,
            },
        }

    @app.post("/api/analyze")
    def start_analysis(request: AnalyzeRequest) -> JobStarted:
        try:
            document = corpus_library.get(request.doc_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown document") from None
        except UnusableDocumentError as exc:
            # §9.1's refusal, surfaced with its specific message rather
            # than flattened into a generic error.
            raise HTTPException(status_code=422, detail=str(exc)) from None

        job = _Job(job_id=uuid.uuid4().hex[:12])
        with _jobs_lock:
            _jobs[job.job_id] = job

        Thread(
            target=_run_analysis,
            args=(
                job,
                document,
                request.situation,
                request.room_tariff_per_day,
                request.sum_insured,
            ),
            daemon=True,
        ).start()
        return JobStarted(job_id=job.job_id)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> JobOut:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job")
        return _serialize_job(job)

    @app.get("/api/page-image/{doc_id}/{page}")
    def page_image(doc_id: str, page: int, bbox: str | None = None) -> Response:
        """`bbox` is "x0,top,x1,bottom" in PDF points, straight from the
        Span the reader clicked — §8's evidence path ends here."""
        try:
            entry = corpus_library.entry_for(doc_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown document") from None
        try:
            rendered = render_page_with_span(entry.path, page, _parse_bbox(bbox))
        except PageImageError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        headers = {}
        if rendered.highlight_fraction is not None:
            # Lets the browser scroll straight to the boxed passage instead
            # of opening at the top of the page and making the reader hunt.
            headers["X-Highlight-Fraction"] = f"{rendered.highlight_fraction:.4f}"
            headers["Access-Control-Expose-Headers"] = "X-Highlight-Fraction"
        return Response(content=rendered.png, media_type="image/png", headers=headers)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        return None
    try:
        x0, top, x1, bottom = (float(p) for p in parts)
    except ValueError:
        return None
    return (x0, top, x1, bottom)


def _run_analysis(
    job: _Job,
    document: LoadedDocument,
    situation: str,
    room_tariff_per_day: float | None,
    sum_insured: float | None,
) -> None:
    def report(progress: Progress) -> None:
        with _jobs_lock:
            job.progress = progress

    try:
        # Cheap and deterministic (no LLM call) — runs unconditionally
        # alongside whatever the user actually asked, per
        # decoder.extract.room_rent_limit's own module docstring.
        room_rent = analyze_room_rent(document.spans, room_tariff_per_day, sum_insured)
        extra_resolved = [room_rent.cap_claim]
        if room_rent.comparison_claim is not None:
            extra_resolved.append(room_rent.comparison_claim)

        decoder = PolicyDecoder(_llm_client(), top_k=_top_k(), embedding_model=_embedding_model())
        answer = decoder.answer(
            [document], situation, extra_resolved_claims=extra_resolved, on_progress=report
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a failed job
        with _jobs_lock:
            job.status = "failed"
            # The exception type, never document text (§9.5).
            job.error = type(exc).__name__
        return

    with _jobs_lock:
        job.answer = answer
        job.room_rent = room_rent
        job.status = "done"
        job.progress = Progress("done", "Finished", job.progress.total, job.progress.total)


def _top_k() -> int:
    return int(os.environ.get("POLICY_AGENT_TOP_K", "4"))


def _serialize_job(job: _Job) -> JobOut:
    return JobOut(
        job_id=job.job_id,
        status=job.status,
        progress=ProgressOut(
            stage=job.progress.stage,
            detail=job.progress.detail,
            completed=job.progress.completed,
            total=job.progress.total,
        ),
        answer=_serialize_answer(job.answer, job.room_rent) if job.answer is not None else None,
        error=job.error,
    )


def _serialize_room_rent(room_rent: RoomRentAnalysis | None) -> RoomRentCalculationOut | None:
    if room_rent is None or room_rent.eligible_limit_per_day is None:
        # Nothing computable yet (no cap stated, or the cap needs a sum
        # insured nobody supplied) — the cap claim itself still explains
        # why, via the normal claims list; there's no calculation to show.
        return None
    exceeds = (
        room_rent.room_tariff_per_day > room_rent.eligible_limit_per_day
        if room_rent.room_tariff_per_day is not None
        else None
    )
    return RoomRentCalculationOut(
        eligible_limit_per_day=room_rent.eligible_limit_per_day,
        room_tariff_per_day=room_rent.room_tariff_per_day,
        exceeds_limit=exceeds,
        deduction_ratio_percent=(
            room_rent.deduction_ratio * 100 if room_rent.deduction_ratio is not None else None
        ),
    )


def _serialize_answer(answer: Answer, room_rent: RoomRentAnalysis | None = None) -> AnswerOut:
    return AnswerOut(
        overall_state=answer.overall_state.value,
        overall_label=SUPPORT_STATE_LABELS[answer.overall_state],
        claims=[
            ClaimOut(
                text=render_claim_statement(r.claim),
                state=r.state.value,
                label=SUPPORT_STATE_LABELS[r.state],
                claim_class=r.claim.claim_class.value,
                evidence=[
                    EvidenceOut(
                        verdict=v.verdict.value,
                        quote=v.deciding_quote or "",
                        doc_id=v.span.doc_id,
                        page=v.span.page,
                        span_id=v.span.id,
                        bbox=",".join(str(c) for c in v.span.bbox) if v.span.bbox else "",
                    )
                    for v in r.verdicts
                    if v.verdict != EntailmentVerdict.NEUTRAL
                ],
            )
            for r in answer.claims
        ],
        questions=generate_follow_up_questions(list(answer.claims)),
        missing_inputs=[
            {"name": i.name, "value_type": i.value_type, "description": i.description}
            for i in answer.missing_inputs
        ],
        room_rent_calculation=_serialize_room_rent(room_rent),
        text=answer.text,
    )


app = create_app()
