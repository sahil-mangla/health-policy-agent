"""Real tests against the live Gemini API when a key is available locally
(see tests/llm/test_gemini_client.py for the same skip-guard pattern)."""

from __future__ import annotations

import os

import pytest

from decoder.respond.translate import (
    GeminiHindiTranslator,
    NumericFidelityError,
    check_numeric_fidelity,
)


class TestCheckNumericFidelity:
    """Pure logic — no model call."""

    def test_matching_figures_passes(self) -> None:
        # Matches how the real Gemini translator behaves: Hindi prose with
        # the numeral kept in Arabic-numeral form, per the source instruction.
        check_numeric_fidelity("a co-payment of 5% applies", "हर दावे पर 5% सह-भुगतान लागू होगा")

    def test_missing_figure_raises(self) -> None:
        with pytest.raises(NumericFidelityError):
            check_numeric_fidelity("a co-payment of 5% applies", "सह-भुगतान लागू है")

    def test_altered_figure_raises(self) -> None:
        with pytest.raises(NumericFidelityError):
            check_numeric_fidelity(
                "room rent limit of INR 5,000 per day", "कमरे के किराए की सीमा INR 50,000 प्रति दिन"
            )

    def test_reformatted_but_same_value_passes(self) -> None:
        # Comma grouping differs (8000 vs 8,000) but the numeric value is
        # identical — this must not be treated as altered.
        check_numeric_fidelity("a tariff of 8,000 per day", "प्रति दिन 8000 का शुल्क")

    def test_no_numbers_in_source_passes_trivially(self) -> None:
        check_numeric_fidelity(
            "the policy covers hospitalisation", "पॉलिसी अस्पताल में भर्ती को कवर करती है"
        )


def _has_gemini_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


@pytest.mark.skipif(not _has_gemini_key(), reason="GEMINI_API_KEY / GOOGLE_API_KEY not set")
def test_real_translation_preserves_figures_and_is_devanagari() -> None:
    from decoder.llm.gemini_client import GeminiLLMClient

    text = (
        "The policy specifies a co-payment of 5% applicable to every claim. "
        "If your room tariff of INR 8,000 per day exceeds the eligible "
        "limit of INR 5,000 per day, a proportionate deduction of 16.8% "
        "will apply to your associated medical expenses."
    )
    translator = GeminiHindiTranslator(GeminiLLMClient())
    translation = translator.translate(text)

    # Genuinely Devanagari script, not an untranslated or garbled response.
    assert any("ऀ" <= ch <= "ॿ" for ch in translation)
    for figure in ("5", "8,000", "5,000", "16.8"):
        assert figure.replace(",", "") in translation.replace(",", "")
