# SPIKE-4 — Second output language and when

**Status: RESOLVED for "which language and how" (2026-09-14). "When" —
i.e. which milestone ships this in the UI — is still open, since no
frontend exists yet.**

Constraints from `docs/HANDOVER.md` §9.4: input documents stay English-only;
output must be translatable; user-facing strings and generated explanations
must be kept separable from logic; quoted clause text is **never**
translated — always show the original alongside any translation.

## Decision: Hindi, via Gemini, as a distinct post-verification step

**Language: Hindi**, per the user's explicit preference (2026-09-14) and
consistent with §2's "ordinary Indian consumer" framing — Hindi has by far
the largest number of speakers among Indian languages after English.

**Mechanism: translate only the final, already-verified answer text — never
translate before or during verification.** Concretely:
1. `decoder.reason`/`decoder.verify`/`decoder.resolve` run entirely in
   English, exactly as already built — untouched by this decision.
2. Only once an `Answer`'s text is finalized does
   `decoder.respond.translate.GeminiHindiTranslator` translate the
   generated prose (the drafted explanation, follow-up questions) into
   Hindi.
3. Quoted clause spans are never passed to the translator at all — the
   module's `translate()` only accepts plain generated strings, matching
   §9.4's "show the original and the translation together" requirement
   structurally, not just by convention.

This was a deliberate rejection of the alternative (asking the LLM to
answer directly in Hindi from the start, skipping a separate translation
step): that would mean `decoder.verify.entailment`'s isolated single-span
checks would need to verify a Hindi claim against an English span —
cross-lingual entailment, which is strictly harder and riskier than the
same-language checking this project already found genuinely fragile (see
`decoder/llm/ollama_client.py`'s module docstring — a real false-SUPPORTS
case was caught and fixed just for English-to-English checking). Keeping
generation/verification in English and translating only the final,
already-checked output confines translation risk to translation quality
alone, not fact-verification correctness.

## Provider choice: Gemini, not Ollama — tested, not assumed

Ran the identical source text through both `decoder.llm.ollama_client.OllamaLLMClient`
(local `qwen2.5-coder:7b`) and `decoder.llm.gemini_client.GeminiLLMClient`
(`gemini-3.6-flash`), same system prompt, same instruction to preserve
every figure exactly:

> Source: "The policy specifies a co-payment of 5% applicable to every
> claim. If your room tariff of INR 8,000 per day exceeds the eligible
> limit of INR 5,000 per day, a proportionate deduction of 16.8% will
> apply to your associated medical expenses."

**Ollama (qwen2.5-coder:7b) — grammatically broken, partly nonsensical:**
> "पॉलिसी में हर व्यक्ति के लिए 5% का साझा अनुमानित है। अगर आपका अमन रूप
> से दिन का राशि INR 8,000 अपने अधिकारित सीमा INR 5,000 से अधिक है, तो
> आपके संबंधित चिकित्सा खर्चों पर 16.8% का कार्यवायुमत घटाएंगे।"

("अमन रूप से" and "कार्यवायुमत" are not real Hindi words — the model
fabricated plausible-looking but meaningless tokens.)

**Gemini (gemini-3.6-flash) — fluent, natural, grammatically correct:**
> "पॉलिसी के अनुसार हर क्लेम पर 5% का को-पेमेंट लागू होगा। अगर आपके कमरे
> का किराया INR 8,000 प्रति दिन है, जो कि इसकी तय सीमा INR 5,000 प्रति
> दिन से अधिक है, तो इलाज से जुड़े आपके खर्चों पर 16.8% की आनुपातिक कटौती
> लागू होगी।"

Both preserved every numeric figure (5%, 8,000, 5,000, 16.8%) correctly —
translation quality is what differs, not number handling in this sample.
This is expected: `qwen2.5-coder:7b` is a code-specialized model, not
tuned for fluent natural-language generation in Indian languages; Gemini is
a large general-purpose multilingual model. **Conclusion: use Gemini for
this role specifically.** Every other LLM-dependent role in this codebase
(`decoder/verify/entailment.py`, `decoder/verify/decompose.py`,
`decoder/reason/ollama_drafter.py`) keeps using Ollama — this is not a
wholesale provider switch, just the one role where the local model's
weaknesses actually show up in the output quality that matters for that
role.

## Numeric-fidelity check — a translation-specific "trap"

Both sample translations above preserved figures correctly, but nothing
guarantees an LLM translator always will — a number silently dropped or
altered during translation is the same category of harm as a fabricated
quote in entailment (§7.2), just in a different pipeline stage.
`decoder.respond.translate.check_numeric_fidelity()` extracts every numeric
value from the source and confirms each has a matching value in the
translation (tolerant of cosmetic formatting differences like comma
grouping, since the underlying value is what matters); a mismatch raises
`NumericFidelityError` rather than silently showing a corrupted
translation. This mirrors `decoder.verify.span_containment`'s hallucination
trap — same principle (never trust unverified model output with something
that matters), applied to translation instead of entailment.

## Operational note: free-tier reliability

Two transient `503 UNAVAILABLE` ("high demand") responses were observed
from the Gemini API across roughly a dozen manual test calls in this
session, and the user separately flagged a concern about free-tier rate
limits (`429`). `decoder/llm/gemini_client.py` now retries `5xx` errors
with short exponential backoff (a few seconds total, 3 attempts) since
those are transient, but raises `GeminiRateLimitError` immediately on `429`
without retrying — hammering an exhausted quota would only make that worse.
This is a real, observed characteristic of the free tier, not a
hypothetical concern, and it's worth keeping in mind if translation (or any
Gemini-backed role) becomes latency-sensitive in the UI — a fallback path
(e.g. showing the untranslated English while a retry/queue happens in the
background, or falling back to Ollama for non-translation roles) may be
worth designing once the frontend exists.

## Still open ("when")

- No UI exists yet to decide when/how a Hindi toggle appears — that's a
  frontend design question, not a translation-mechanism one.
- Static UI strings (state labels like "Stated in your policy," button
  text) are a *different* problem from the dynamic generated prose this
  spike covers — those are a small, fixed, known vocabulary and deserve a
  reviewed, consistent locale dictionary (e.g. a simple JSON string table),
  not fresh LLM translation on every render. Not built yet; noted here so
  the two translation paths (static i18n dictionary vs. dynamic
  `GeminiHindiTranslator`) aren't conflated when the frontend is built.
