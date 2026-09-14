"""Per-claim, isolated, single-span entailment checking — docs/HANDOVER.md §7.2.

The Entailer must see ONLY the claim and ONE span — never the draft answer,
the user's scenario, or other claims. This isolation is what stops the model
rubber-stamping ("is this analysis correct?" is unfalsifiable). The
constraint is expressed here at the signature level (check() takes exactly
claim + span, nothing else), not just in a docstring, so a future
implementation cannot accidentally widen the context it sees.

OllamaEntailer is a real implementation against a local Ollama model — see
decoder/llm/ollama_client.py for why Ollama (no API key, no cloud egress).
Model choice for this role is still open (SPIKE-5, docs/HANDOVER.md §15);
only qwen2.5-coder:7b is pulled in this environment, and the model name is a
constructor parameter here, not hardcoded — swap it freely.
"""

from __future__ import annotations

import re
from typing import Protocol

from decoder.llm.interface import LLMClient
from decoder.schema import AtomicClaim, EntailmentResult, EntailmentVerdict, Span
from decoder.verify.span_containment import enforce_hallucination_trap


class Entailer(Protocol):
    def check(self, claim: AtomicClaim, span: Span) -> EntailmentResult:
        """Must return a verdict plus a deciding_quote; callers should pass
        the result through decoder.verify.span_containment.enforce_hallucination_trap
        before trusting it."""
        ...


def render_claim_text(claim: AtomicClaim) -> str:
    """Renders an AtomicClaim as a natural-language sentence for the
    entailment prompt. Deliberately simple (subject + predicate + value) —
    good enough for the claim shapes this codebase currently produces
    (regex/LLM field extraction); revisit if claim phrasing needs richer
    templates once decoder.reason produces free-text drafts to decompose."""
    return f"{claim.subject} {claim.predicate} {claim.value}".strip()


# Wording is exactly as validated by hand against the real corpus and a
# live model (2026-09-14) — split across shorter source lines only (see the
# same note in decoder/reason/ollama_drafter.py); the resulting string
# value is unchanged.
_SYSTEM_PROMPT = (
    "You are a strict fact-checker. You will be given ONE claim and ONE "
    "passage from a document.\n\n"
    "Decide whether the passage SUPPORTS the claim, CONTRADICTS the claim, "
    "or is NEUTRAL to the claim (says nothing relevant). Use ONLY the "
    "passage text — no outside knowledge, no assumptions, no inference "
    "beyond what is literally stated.\n\n"
    "Respond in EXACTLY this format and nothing else, with no quotation "
    "marks around the quoted text:\n"
    "VERDICT: <one word, exactly SUPPORTS or CONTRADICTS or NEUTRAL, no "
    "other word is allowed>\n"
    "QUOTE: <the exact contiguous substring copied verbatim from the "
    "passage, with no surrounding quote marks, or NONE if the verdict is "
    "NEUTRAL>"
)

_VERDICT_RE = re.compile(r"VERDICT:\s*(\w+)", re.IGNORECASE)
_QUOTE_RE = re.compile(r"QUOTE:\s*(.+)", re.IGNORECASE | re.DOTALL)
_VALID_VERDICTS = {v.value for v in EntailmentVerdict}


def _strip_stray_quote_marks(text: str) -> str:
    return text.strip().strip("\"“”'").strip()


def _parse_model_response(raw_response: str) -> tuple[EntailmentVerdict, str | None]:
    """Strict parsing: any response that doesn't conform to the requested
    format, or names a verdict word outside {SUPPORTS, CONTRADICTS,
    NEUTRAL}, is treated as NEUTRAL with no quote — the same
    fail-safe-to-NEUTRAL posture as the hallucination trap itself (§7.2).
    Deliberately does NOT try to fuzzy-map near-miss verdict words (e.g. a
    model saying "CONFLICTS" instead of "CONTRADICTS") — guessing what an
    off-format response "really meant" is exactly the kind of unverified
    inference this system exists to avoid."""
    verdict_match = _VERDICT_RE.search(raw_response)
    if not verdict_match:
        return EntailmentVerdict.NEUTRAL, None
    verdict_word = verdict_match.group(1).upper()
    if verdict_word not in _VALID_VERDICTS:
        return EntailmentVerdict.NEUTRAL, None
    verdict = EntailmentVerdict(verdict_word)

    if verdict == EntailmentVerdict.NEUTRAL:
        return verdict, None

    quote_match = _QUOTE_RE.search(raw_response)
    if not quote_match:
        return EntailmentVerdict.NEUTRAL, None
    quote = _strip_stray_quote_marks(quote_match.group(1).splitlines()[0])
    if not quote or quote.upper() == "NONE":
        return EntailmentVerdict.NEUTRAL, None
    return verdict, quote


class OllamaEntailer:
    def __init__(self, llm: LLMClient, model: str = "qwen2.5-coder:7b") -> None:
        self._llm = llm
        self._model = model

    def check(self, claim: AtomicClaim, span: Span) -> EntailmentResult:
        claim_text = render_claim_text(claim)
        prompt = f"Claim: {claim_text}\n\nPassage: {span.text}"
        raw_response = self._llm.generate(prompt=prompt, system=_SYSTEM_PROMPT, model=self._model)
        verdict, quote = _parse_model_response(raw_response)

        # The hallucination trap (§7.2): a verdict is only trusted if its
        # quote is a real, verbatim substring of the span — this is the
        # same check regardless of whether the model followed the format,
        # so a well-formatted but fabricated quote is caught here too, not
        # just a malformed response.
        verdict, quote = enforce_hallucination_trap(verdict, quote, span.text)

        return EntailmentResult(
            claim_id=claim.id,
            span=span,
            verdict=verdict,
            deciding_quote=quote,
        )
