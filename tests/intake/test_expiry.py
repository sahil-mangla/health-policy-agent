"""§9.2: "If the [policy] period has lapsed ... say so before any
analysis. Analysis of a lapsed policy is misinformation."

Pure logic against plain text (see find_policy_period_dates_in_text's
docstring for why this is split from the PDF-reading path) — real-corpus
integration coverage lives in tests/intake/test_classify.py and
tests/test_orchestrator_live.py.
"""

from __future__ import annotations

from datetime import date

from decoder.intake.classify import is_expired_from_text


def test_past_end_date_is_expired() -> None:
    text = "The Policy Period is from 01/04/2019 to 31/03/2020 as per the schedule."
    assert is_expired_from_text(text, as_of=date(2026, 9, 15)) is True


def test_future_end_date_is_not_expired() -> None:
    text = "Policy Period 01/04/2026 to 31/03/2027."
    assert is_expired_from_text(text, as_of=date(2026, 9, 15)) is False


def test_end_date_equal_to_as_of_is_not_expired() -> None:
    # "unambiguously before" — the boundary day itself still counts as in
    # force, not lapsed.
    text = "Policy Period 01/04/2026 to 15/09/2026."
    assert is_expired_from_text(text, as_of=date(2026, 9, 15)) is False


def test_hyphenated_dates_are_parsed() -> None:
    text = "Policy Period - 01-04-2019 to 31-03-2020"
    assert is_expired_from_text(text, as_of=date(2026, 9, 15)) is True


def test_no_policy_period_mentioned_is_undetermined() -> None:
    assert is_expired_from_text("This document defines Policy Period as a term.") is None


def test_two_digit_year_is_undetermined_not_guessed() -> None:
    # Ambiguous ("10" could be 1910 or 2010) — must not silently assume
    # a century rather than say "cannot tell".
    text = "Policy Period 01/04/10 to 31/03/11."
    assert is_expired_from_text(text) is None


def test_invalid_calendar_end_date_is_undetermined() -> None:
    # Only the end date is actually parsed/used (is_expired_from_text
    # cares whether the policy has *lapsed*, i.e. the end date), so this
    # exercises the parser on the field it reads: 31 Feb doesn't exist.
    text = "Policy Period 01/04/2020 to 31/02/2021."
    assert is_expired_from_text(text) is None


def test_a_real_specimen_wording_with_no_dates_is_undetermined() -> None:
    # A downloadable specimen defines the term but carries no actual
    # dates (those live in a customer Schedule) — must not be treated as
    # "not expired", it is genuinely unknown.
    from pathlib import Path

    from decoder.intake.classify import is_policy_expired

    corpus_dir = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw" / "hdfc_ergo"
    raw = (corpus_dir / "easy_health_policy_wording.pdf").read_bytes()
    assert is_policy_expired(raw) is None
