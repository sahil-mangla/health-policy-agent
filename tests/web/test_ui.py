"""Browser tests for the analysis view.

What these assert is docs/HANDOVER.md §8's UI contract — that each support
state reaches the reader with its required accompanying content, that the
evidence path ends at a highlighted passage in the real page, and that the
forbidden generic disclaimer is absent. They run the real pipeline against
a real corpus document with a scripted model (web.fake_llm), so a failure
here means the interface changed, not that a 7B model phrased something
differently.

Skipped automatically if the Playwright browser isn't installed
(`uv run playwright install chromium`).
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from web.app import FAKE_LLM_ENV_VAR, create_app

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright

SITUATION = "What co-payment applies to my claim?"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def app_url() -> Iterator[str]:
    import os

    os.environ[FAKE_LLM_ENV_VAR] = "1"
    port = _free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 30
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.skip("test server did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
    os.environ.pop(FAKE_LLM_ENV_VAR, None)


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - missing browser binary
            pytest.skip(f"Chromium not available for Playwright: {type(exc).__name__}")
        yield launched
        launched.close()


@pytest.fixture
def page(browser, app_url: str):  # type: ignore[no-untyped-def]
    page = browser.new_page(viewport={"width": 1200, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on(
        "console",
        lambda message: errors.append(message.text) if message.type == "error" else None,
    )
    page.goto(app_url, wait_until="networkidle")
    yield page
    assert errors == [], f"browser reported errors: {errors}"
    page.close()


def _analyse(page, situation: str = SITUATION) -> None:  # type: ignore[no-untyped-def]
    page.fill("#situation", situation)
    page.click("#analyze")
    page.wait_for_selector("#results:not([hidden])", timeout=120_000)


def test_document_picker_is_populated_with_its_note(page) -> None:  # type: ignore[no-untyped-def]
    assert page.locator("#doc-select option").count() > 0
    assert page.locator("#doc-note").inner_text().strip() != ""


def test_analysis_renders_one_row_per_claim_with_a_state_label(page) -> None:  # type: ignore[no-untyped-def]
    _analyse(page)
    claims = page.locator(".claim")
    assert claims.count() > 0
    for index in range(claims.count()):
        claim = claims.nth(index)
        state = claim.get_attribute("data-state")
        assert state in {
            "WELL_SUPPORTED",
            "NEEDS_CONFIRMATION",
            "NEEDS_INFORMATION",
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING",
        }
        assert claim.locator(".state-chip").inner_text().strip() != ""


def test_every_state_shown_carries_its_accompanying_explanation(page) -> None:  # type: ignore[no-untyped-def]
    # §8's UI mapping table: a state is never shown bare — it comes with
    # the content that makes it actionable.
    _analyse(page)
    claims = page.locator(".claim")
    for index in range(claims.count()):
        claims.nth(index).locator(".claim-head").click()
        why = claims.nth(index).locator(".why")
        assert why.inner_text().strip() != "", "a state was shown with no explanation"


def test_supported_claim_shows_the_verbatim_quote_not_a_section_number(page) -> None:  # type: ignore[no-untyped-def]
    _analyse(page)
    supported = page.locator(".claim.s-WELL_SUPPORTED").first
    supported.locator(".claim-head").click()
    quote = supported.locator(".evidence-quote").first.inner_text()
    assert len(quote.strip("“” ")) > 0
    source = supported.locator(".evidence-source").first.inner_text()
    assert "page" in source.lower()


def test_evidence_path_ends_at_the_highlighted_page_image(page) -> None:  # type: ignore[no-untyped-def]
    # §8: "Every claim supports the path Answer -> Why -> Evidence, ending
    # at the highlighted span in the rendered page image."
    _analyse(page)
    supported = page.locator(".claim.s-WELL_SUPPORTED").first
    supported.locator(".claim-head").click()
    supported.locator(".evidence-source").first.click()

    page.wait_for_selector("#evidence-dialog[open]")
    page.wait_for_function(
        "() => { const i = document.getElementById('page-image');"
        " return i && i.complete && i.naturalWidth > 0; }",
        timeout=30_000,
    )
    assert page.locator("#dialog-quote").inner_text().strip() != ""
    # And it scrolls to the passage rather than opening at the top of the
    # page and leaving the reader to find it.
    page.wait_for_timeout(1200)
    assert page.evaluate("document.getElementById('evidence-dialog').scrollTop") > 0


def test_unsupported_claim_produces_a_question_naming_it(page) -> None:  # type: ignore[no-untyped-def]
    _analyse(page)
    unsupported = page.locator(".claim:not(.s-WELL_SUPPORTED)")
    assert unsupported.count() > 0
    questions = page.locator("#questions li")
    assert questions.count() > 0
    claim_text = unsupported.first.locator(".claim-text").inner_text().strip()
    assert any(claim_text in questions.nth(i).inner_text() for i in range(questions.count()))


def test_no_generic_ai_disclaimer_banner_anywhere(page) -> None:  # type: ignore[no-untyped-def]
    # §8 forbids this explicitly: "A generic 'AI can make mistakes' banner
    # is forbidden — it trains users to ignore the one warning that
    # matters." This is a standing guard against someone adding one later.
    _analyse(page)
    body = page.locator("body").inner_text().lower()
    for phrase in [
        "ai can make mistakes",
        "may produce inaccurate",
        "double-check its responses",
        "ai-generated content may be incorrect",
    ]:
        assert phrase not in body, f"forbidden generic disclaimer present: {phrase!r}"


def test_empty_situation_is_refused_without_calling_the_pipeline(page) -> None:  # type: ignore[no-untyped-def]
    page.fill("#situation", "   ")
    page.click("#analyze")
    page.wait_for_selector("#error-panel:not([hidden])")
    assert page.locator("#results").is_hidden()
