"""Hindi translation of generated explanatory text — docs/HANDOVER.md §9.4
(SPIKE-4), docs/spikes/translation-language.md.

Translates ONLY generated prose (a drafter's answer text, a follow-up
question) — NEVER a quoted clause/span. Per §9.4: "Do not translate quoted
clause text — show the original and the translation together." This module
only accepts plain strings, never a Span, by design — callers are
responsible for keeping quoted evidence text out of what they pass here and
showing it in its original English alongside any translation.

Provider choice: GeminiHindiTranslator, not Ollama. Tested by hand
(2026-09-14) with identical source text on both: the local qwen2.5-coder:7b
model produced grammatically broken, partly nonsensical Hindi (invented
non-words), while Gemini produced fluent, natural Hindi. Both preserved
numeric figures correctly, but quality differs enough that this is the one
role in this codebase where the cloud provider is clearly better suited
than the local one — the verification/extraction roles keep using Ollama
(decoder/verify/entailment.py, decoder/verify/decompose.py); only
translation uses Gemini. See docs/spikes/translation-language.md for the
full comparison.

Numeric-fidelity check: every number/percentage/currency figure in the
English source must have a matching value somewhere in the Hindi
translation — the same principle as decoder.verify.span_containment's
hallucination trap (never trust unverified model output), applied to a
different failure mode: silent renumbering during translation, not
fabricated citation. A translation that drops or alters a figure is
rejected, not silently shown to the user.
"""

from __future__ import annotations

import re

from decoder.llm.interface import LLMClient

_SYSTEM_PROMPT = (
    "You translate English insurance-related text into natural, simple "
    "Hindi that an ordinary consumer can understand. Preserve every "
    "number, percentage, and currency figure EXACTLY as written in the "
    "English original — do not reformat, round, or alter them in any "
    "way. Output ONLY the Hindi translation, nothing else."
)

_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*")


class NumericFidelityError(ValueError):
    """Raised when a translation drops or alters a numeric figure present
    in the source text — never silently shown to the user."""


def _extract_numeric_values(text: str) -> list[float]:
    values = []
    for match in _NUMBER_RE.findall(text):
        cleaned = match.replace(",", "")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def check_numeric_fidelity(source: str, translation: str) -> None:
    """Every numeric value present in `source` must also be present
    (as a value — formatting like comma grouping may legitimately differ)
    somewhere in `translation`. Does not check the reverse (a translation
    introducing an extra number not in the source is a different, rarer
    failure mode not handled here)."""
    source_values = _extract_numeric_values(source)
    translation_values = _extract_numeric_values(translation)
    missing = [v for v in source_values if v not in translation_values]
    if missing:
        raise NumericFidelityError(
            f"translation is missing or altered these figures from the source text: {missing}"
        )


class GeminiHindiTranslator:
    def __init__(self, llm: LLMClient, model: str = "gemini-3.6-flash") -> None:
        self._llm = llm
        self._model = model

    def translate(self, text: str) -> str:
        """Raises NumericFidelityError rather than returning a translation
        that silently dropped or altered a figure — callers should treat
        that as "translation unavailable for this text," e.g. by falling
        back to showing the English original, not by retrying blindly."""
        translation = self._llm.generate(prompt=text, system=_SYSTEM_PROMPT, model=self._model)
        check_numeric_fidelity(text, translation)
        return translation
