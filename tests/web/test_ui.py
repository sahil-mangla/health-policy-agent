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
    # NEEDS_INFORMATION claims (e.g. the room-rent panel's cap claim, which
    # runs unconditionally alongside every question) ask for their named
    # missing input instead of quoting their own claim text
    # (decoder.respond.question_generation), so this must target a claim
    # whose state actually does interpolate claim text.
    unsupported = page.locator(".claim:not(.s-WELL_SUPPORTED):not(.s-NEEDS_INFORMATION)")
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


def test_upload_your_own_document_and_analyse_it(page) -> None:  # type: ignore[no-untyped-def]
    # docs/HANDOVER.md's spec assumes a real uploaded policy throughout
    # §9.1/§9.2/§9.3/§9.5 — this is that path actually reaching the browser,
    # not just the bundled demo picker.
    from web.corpus_library import entry_for

    page.set_input_files("#upload-input", str(entry_for("easy_health").path))
    page.wait_for_selector("#upload-status.ok", timeout=10_000)
    selected = page.locator("#doc-select option:checked").inner_text()
    assert "Your upload" in selected

    _analyse(page, "What co-payment applies to my claim?")
    assert page.locator(".claim").count() > 0


def test_missing_input_form_lets_the_reader_supply_a_named_value_and_recheck(page) -> None:  # type: ignore[no-untyped-def]
    # §8's UI-mapping table: NEEDS_INFORMATION must "name the missing input,
    # offer to accept it" — an actual field, not a read-only list.
    _analyse(page, "How long is the waiting period for pre-existing diseases?")
    page.wait_for_selector("#inputs-panel:not([hidden])")
    field = page.locator("#missing-input-continuity_date")
    assert field.count() == 1

    field.fill("2018-01-01")
    page.click("#missing-inputs-form button[type=submit]")
    # Not a second `#results:not([hidden])` wait — results are already
    # visible from the first analysis, so that would resolve immediately
    # without actually waiting for the re-check to land. The
    # continuity_date field disappearing is specific to the SECOND
    # response: it only leaves missing_inputs once resolve() sees it in
    # provided_inputs.
    page.wait_for_function(
        "!document.getElementById('missing-input-continuity_date')", timeout=120_000
    )

    # Matched on .claim-text specifically, not .claim as a whole: the
    # room-rent claim's own real cited evidence happens to be one long
    # clause block that also contains the words "waiting period" later in
    # the same passage (a real Arogya Sanjeevani compound clause), so a
    # plain `.claim` has_text match would pick up that unrelated claim too.
    waiting_claim = (
        page.locator(".claim")
        .filter(has=page.locator(".claim-text", has_text="waiting period"))
        .first
    )
    assert waiting_claim.get_attribute("data-state") == "WELL_SUPPORTED"


def test_chat_quick_actions_answer_from_already_verified_content(page) -> None:  # type: ignore[no-untyped-def]
    # M6's status: chat is a scoped secondary affordance for exactly three
    # uses, never a general-purpose "chat with your PDF" (out of scope, §2).
    _analyse(page)
    claim = page.locator(".claim").first
    claim.locator(".claim-head").click()

    claim.locator(".chat-chip", has_text="Why is this flagged?").click()
    why_text = claim.locator(".why").inner_text().strip()
    bubble = claim.locator(".chat-bubble.answer").first
    assert bubble.inner_text().strip() == why_text

    claim.locator(".chat-chip", has_text="Explain more simply").click()
    page.wait_for_function(
        "el => el.querySelectorAll('.chat-bubble.answer').length >= 2",
        arg=claim.element_handle(),
        timeout=10_000,
    )


def test_hindi_toggle_shows_translation_alongside_the_original_not_instead_of_it(page) -> None:  # type: ignore[no-untyped-def]
    # §9.4: "Do not translate quoted clause text — show the original and
    # the translation together."
    _analyse(page)
    claim = page.locator(".claim").first
    claim.locator(".claim-head").click()
    original = claim.locator(".claim-text").inner_text().strip()

    claim.locator(".hindi-toggle").click()
    page.wait_for_selector(".hindi-block", timeout=10_000)
    assert claim.locator(".claim-text").inner_text().strip() == original
