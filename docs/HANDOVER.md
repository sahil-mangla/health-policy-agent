# Indian Health Insurance Policy Decoder — Engineering Handover (v2)

**Status:** pre-implementation spec. This supersedes the v1 concept document.
**Audience:** Claude Code (or any implementing agent), plus the human owner.
**Read this whole file before writing code.** Sections marked `LOCKED` are decisions;
do not relitigate them. Sections marked `SPIKE` are open and must be resolved by a
short, timeboxed investigation *before* the code that depends on them is written.

---

## 0. How to use this document

1. Start at §14 (Build Order). Each milestone lists its Definition of Done.
2. Before implementing a milestone, re-read the sections it references.
3. If a `SPIKE` blocks you, do the spike, write the answer into this file under
   the spike heading, and mark it `RESOLVED (date)`. Do not guess and proceed.
4. If you want to add a feature not listed here, apply the test in §16 first.

---

## 1. What changed from v1

The v1 concept doc was directionally right. This version closes gaps that would
have caused the system to fail under scrutiny. Deltas:

| # | Change | Reason |
|---|---|---|
| 1 | **Policy comparison cut from MVP** | Serves a different user (pre-purchase) at a different moment with different documents. Also imports a hard cross-insurer schema-normalisation problem the other features don't have. |
| 2 | **The 90% confidence threshold is deleted entirely** | v1 forbade fake precision in §18 while anchoring to a number in §17. Support state is now produced by deterministic rules over verification results, never by bucketing a float. |
| 3 | **Verification is now mechanical, not a judgment call** | "Verify the claim against evidence" is itself an LLM call and can hallucinate agreement. Replaced with atomic-claim decomposition + single-span binary entailment + exact-match numeric checks. See §7. |
| 4 | **Extraction is treated as a failure surface, not a pipe** | A wrong number with a correct-looking citation is worse than no answer: it manufactures trust and survives a user's spot-check. Extraction now carries provenance and its own accuracy metric. See §6. |
| 5 | **Hero scenario changed to room-rent limit / proportionate deduction** | Deterministic arithmetic once numbers are extracted, genuinely surprising consequence, and it demonstrates precision and humility on one screen. See §4. |
| 6 | **Evaluation switched to selective-prediction metrics** | The v1 A/B/C/D ablation would have shown System D (with abstention) as equal or *worse* on plain accuracy, i.e. the experiment would have argued against the central design decision. See §12. |
| 7 | **Ground truth sourced from adjudicated disputes** | Expert annotation at volume is the binding constraint. Published Insurance Ombudsman awards are effectively pre-labelled fact patterns. See §11 / SPIKE-2. |
| 8 | **Four previously-absent concerns added** | Language, wrong-document handling, policy versioning/continuity, PII. See §9. |

---

## 2. Product definition `LOCKED`

**One sentence:** Given an Indian consumer's health policy and a real situation,
identify which policy conditions actually matter, trace each conclusion to the
clause it came from, and state plainly where the documents are not sufficient to
answer without confirming with the insurer.

**The differentiator is not summarisation quality.** It is that the system knows
and says when it does not know, and is *right* about when it does not know.
Calibrated abstention is the product.

**North star test.** Every feature must make it easier for an ordinary Indian
consumer to understand what their health insurance means for a real situation,
while making clear what is evidence-backed and what still needs confirmation.

### In scope (MVP)

- **F1 — Structured policy understanding.** Policy + CIS → structured representation
  with span-level provenance for every extracted field.
- **F2 — Scenario analysis.** User situation → relevant conditions, evidence, support
  state, and what to verify.
- **F3 — Actionable questions.** Specific, answerable questions for the insurer,
  derived from the gaps the analysis actually found.

### Out of scope (MVP) — hard

Policy comparison · claim-outcome prediction · claim submission · insurer
communication · medical diagnosis or treatment advice · medical-necessity opinions ·
case law · legal opinions · lawyer marketplace · voice · non-health insurance lines ·
generic "chat with your PDF".

### Boundaries `LOCKED`

The system is a decision-support tool. It never says a claim will be approved or
rejected. It never diagnoses. Medical terms from the user are treated as **opaque
treatment category labels** used only to route to policy clauses — the system does
not reason about the medicine.

---

## 3. Vocabulary (use these exact terms in code and UI)

| Term | Meaning |
|---|---|
| **Span** | A contiguous character range in a source document, with page and bbox. The atomic unit of evidence. Never cite a whole section. |
| **Extracted field** | A typed value (number, date, enum, bool) pulled from a span into the structured policy. |
| **Atomic claim** | A single, independently checkable assertion. One subject, one predicate, one value. |
| **Claim class** | `DOCUMENT_FACT` \| `REGULATORY_FACT` \| `DERIVED` \| `INTERPRETATION`. |
| **Entailment verdict** | Per (claim, span) pair: `SUPPORTS` \| `CONTRADICTS` \| `NEUTRAL`. |
| **Support state** | Per claim: `WELL_SUPPORTED` \| `NEEDS_CONFIRMATION` \| `NEEDS_INFORMATION` \| `INSUFFICIENT_EVIDENCE` \| `CONFLICTING`. Rule-derived. Never a rounded probability. |
| **Required input** | A user-supplied fact a claim depends on (e.g. continuity date). Named, typed, and requestable. |

Do not introduce synonyms. Do not use the word "confidence" anywhere in the codebase
or UI.

---

## 4. Hero scenario `LOCKED`

**Room-rent limit and proportionate deduction.**

The user has a policy with a room-rent cap. They are about to be admitted, or are
choosing a room. They believe a ₹10L sum insured means ₹10L of protection.

Why this scenario:

- Once the cap and the actual room tariff are extracted, the consequence is
  **arithmetic** — the system can be precise where it legitimately can be.
- The set of expense heads subject to proportionate deduction is **policy-specific**,
  so the system must be humble in the same answer. Precision and humility, one screen.
- The outcome genuinely surprises people, which makes the demo land.

**What the system must do:**

1. Extract the room-rent eligibility basis (flat ₹/day, % of SI/day, room *category*
   such as "single private AC", or none) with its span.
2. Extract which expense heads the policy subjects to proportionate deduction, and
   which it carves out. **Do not hardcode a default carve-out list.** If the policy
   does not enumerate it, that is `INSUFFICIENT_EVIDENCE` and becomes a question.
3. If the user supplies an actual room tariff, compute the deduction ratio and show
   the arithmetic explicitly, with the input numbers labelled and their spans linked.
4. State clearly which parts of the bill the computation does and does not cover.

> **SPIKE-1 — Regulatory position on proportionate deduction.**
> Determine the current IRDAI position (circulars, master guidelines, and any
> standardisation of exclusion/deduction wording), including effective dates and
> whether anything has been superseded. Also determine whether the position differs
> by product type or for policies where no room-rent limit exists.
> **Do not encode any regulatory rule until this is resolved and dated.**
> Output: a short memo in `/docs/regulatory/proportionate-deduction.md` with primary
> source URLs, effective dates, and an explicit "as of" line.
>
> **PARTIALLY RESOLVED (2026-09-14).** See `/docs/regulatory/proportionate-deduction.md`
> for the full memo. Summary: the primary source is IRDAI/HLT/REG/CIR/151/06/2020
> (11 June 2020), which fixes only a *floor* of mandatory exclusions from
> "associated medical expenses" (pharmacy/consumables, implants/medical devices,
> diagnostics, ICU charges) and leaves the insurer to define everything else in
> the policy T&C — there is no market-standard included list to hardcode. Whether
> this circular survived the 2024 Master Circular consolidation (its Annexure-6
> repeal list was not accessible) is the one open item still blocking full sign-off.

---

## 5. Architecture

```
                        User scenario + documents
                                   │
                    ┌──────────────┴──────────────┐
                    ↓                             ↓
            Document Intake                 Scenario Parse
         (§6: classify, OCR,            (opaque treatment label,
          segment, extract)              named required inputs)
                    │                             │
                    ↓                             │
        Structured Policy + Span Store            │
                    │                             │
                    └──────────────┬──────────────┘
                                   ↓
                          Clause Retrieval  (§10)
                                   ↓
                          Evidence Assembly
                                   ↓
                        Draft Reasoning (LLM)
                                   ↓
                    Atomic Claim Decomposition  (§7.1)
                                   ↓
                   Per-claim Span Verification  (§7.2)
                                   ↓
                  Support State Resolution (rules) (§8)
                                   ↓
              Response Assembly + Question Generation
```

**Hard rule:** nothing reaches the user that has not passed through claim
decomposition and support-state resolution. There is no "quick answer" path that
bypasses verification. If you find yourself adding one, the design has failed.

**Module boundaries** (keep these as separate packages with typed interfaces —
the ablation in §13 depends on being able to remove layers cleanly):

```
decoder/
  intake/        # classify, ocr, segment, span_store
  extract/       # field extractors + provenance
  retrieve/      # clause retrieval, regulatory retrieval
  reason/        # draft generation (the only creative LLM call)
  verify/        # decomposition, entailment, numeric checks
  resolve/       # support state rules (pure functions, no LLM, no I/O)
  respond/       # answer assembly, question generation
  eval/          # harness, metrics, ablation runner
  llm/           # provider-agnostic interface
```

`resolve/` must be pure and fully unit-testable without any model. This is
non-negotiable — it is the part a skeptic will interrogate hardest.

---

## 6. Extraction and provenance

Extraction errors propagate silently and arrive at the user wearing a citation.
Treat this as the highest-risk component.

**Every extracted field carries:**

```json
{
  "field": "room_rent_limit_per_day",
  "value": 5000,
  "unit": "INR_PER_DAY",
  "basis": "FLAT_AMOUNT",
  "spans": [
    {
      "doc_id": "policy_001",
      "page": 18,
      "char_start": 2041,
      "char_end": 2118,
      "text": "<verbatim source text>",
      "bbox": [72.0, 410.5, 523.0, 428.0]
    }
  ],
  "extraction_method": "LLM_STRUCTURED" ,
  "verbatim_match": true,
  "conflicting_candidates": []
}
```

**Rules:**

- `verbatim_match` is `true` only if the value's string form appears literally
  inside the span text. Numeric fields where this is `false` are **downgraded to
  `NEEDS_CONFIRMATION` automatically**, regardless of anything else.
- If the same field is extracted with different values from different spans (very
  common: CIS says one thing, policy schedule says another, endorsement says a
  third), record **all** candidates in `conflicting_candidates` and resolve to
  `CONFLICTING`. Never silently pick one. The CIS is a summary and **loses** to the
  policy wording — but the disagreement is itself information the user needs.
- A field that cannot be found is `null` with an empty span list. Absence is a valid,
  reportable state. Do not let the model invent a market-typical default.

**Extraction accuracy is a top-line metric**, tracked separately from answer
accuracy. See §12.

---

## 7. Verification `LOCKED`

This is the part that makes the project defensible. Get it right.

### 7.1 Atomic claim decomposition

The draft answer is split into atomic claims. A claim is atomic if it has one
subject, one predicate, one value, and could be marked right or wrong on its own.

Bad (compound): *"Your policy has a ₹5,000 room-rent cap, so a ₹8,000 room will
trigger proportionate deduction on your associated medical expenses."*

Good (three claims):
1. `DOCUMENT_FACT` — The policy specifies a room-rent limit of ₹5,000 per day.
2. `DOCUMENT_FACT` — The policy applies proportionate deduction to associated
   medical expenses when the room rent exceeds the eligible limit.
3. `DERIVED` — A room at ₹8,000/day exceeds the ₹5,000/day eligible limit.

Claim 3 is arithmetic and is checked by code, not by a model.

### 7.2 Per-claim verification

For each claim, run the **narrowest checkable question** against **one span at a
time**. Never ask a model "is this analysis correct?" — that is unfalsifiable and
will drift toward agreement.

| Claim class | Check |
|---|---|
| `DOCUMENT_FACT`, numeric | Exact string match of the value in the span. Code, not model. |
| `DOCUMENT_FACT`, non-numeric | Binary entailment: "Does this passage state that X? Answer SUPPORTS / CONTRADICTS / NEUTRAL and quote the words that decide it." |
| `REGULATORY_FACT` | Same binary entailment, against the regulatory corpus span. Must also carry an effective date. |
| `DERIVED` | Executed in code. The inputs must themselves be verified claims. |
| `INTERPRETATION` | Cannot be `WELL_SUPPORTED`, ever. Ceiling is `NEEDS_CONFIRMATION`. |

**Implementation constraints:**

- The verifier sees the claim and **one span**. It does not see the draft answer,
  the user's scenario, or the other claims. Isolation is what stops it rubber-stamping.
- The verifier must return the deciding words from the span. If those words are not
  actually present in the span, the verdict is discarded and treated as `NEUTRAL`.
  This is a cheap, effective hallucination trap — implement it.
- Run every claim against **all** retrieved spans, not just the one the drafter cited.
  Contradictions are found by looking, not by hoping.

---

## 8. Support state resolution `LOCKED`

Pure function. No model. No thresholds. No floats.

```python
def resolve(claim, verdicts, required_inputs, provided_inputs) -> SupportState:
    supports    = [v for v in verdicts if v.verdict == "SUPPORTS"]
    contradicts = [v for v in verdicts if v.verdict == "CONTRADICTS"]

    if supports and contradicts:
        return CONFLICTING
    if contradicts and not supports:
        return CONFLICTING          # drafter asserted the opposite of the document
    if not supports:
        return INSUFFICIENT_EVIDENCE

    missing = [r for r in required_inputs if r not in provided_inputs]
    if missing:
        return NEEDS_INFORMATION

    if claim.claim_class == "INTERPRETATION":
        return NEEDS_CONFIRMATION
    if claim.claim_class == "DOCUMENT_FACT" and claim.is_numeric \
       and not claim.verbatim_match:
        return NEEDS_CONFIRMATION
    if claim.claim_class == "DERIVED" and any(
            i.state != WELL_SUPPORTED for i in claim.input_claims):
        return NEEDS_CONFIRMATION   # derived results inherit the weakest input

    return WELL_SUPPORTED
```

**Answer-level state = the weakest state among its claims.** A single
`CONFLICTING` claim makes the whole answer `CONFLICTING`. No averaging.

**Never refuse outright.** Every state produces an answer. `INSUFFICIENT_EVIDENCE`
means "here is what we could and could not find, here is what to ask" — not
"I cannot help."

### UI mapping

| State | Label | Required accompanying content |
|---|---|---|
| `WELL_SUPPORTED` | Stated in your policy | Clickable span |
| `NEEDS_CONFIRMATION` | Verify before proceeding | What is uncertain, why, exact question to ask |
| `NEEDS_INFORMATION` | Depends on information we don't have | Named the missing input, offer to accept it |
| `INSUFFICIENT_EVIDENCE` | Not found in these documents | Where we looked, what to ask |
| `CONFLICTING` | Your documents disagree | Both spans, side by side, with which document each came from |

Warnings are **contextual and specific**. A generic "AI can make mistakes" banner is
forbidden — it trains users to ignore the one warning that matters.

Every claim supports the path **Answer → Why → Evidence**, ending at the highlighted
span in the rendered page image. Do not ship a citation that is only a section number.

---

## 9. Edge cases the v1 doc missed — all must be handled in MVP

**9.1 Wrong or unusable document.** Classify on intake before anything else:
health policy wording / CIS / motor or life policy / expired policy / hospital bill /
unreadable scan / not an insurance document. Refuse politely and specifically for
the wrong type. Silently analysing a motor policy as health is a catastrophic
first impression.

**9.2 Expired or superseded policy.** Extract policy period. If the period has
lapsed or a renewal endorsement is present, say so **before** any analysis. Analysis
of a lapsed policy is misinformation.

**9.3 Policy versioning and continuity.** The hero scenario and every waiting-period
question depend on **continuous coverage across renewals**, which a single uploaded
PDF usually cannot establish. Model continuity date as a first-class **required
input**, not an assumption. If it is absent, waiting-period claims are
`NEEDS_INFORMATION` — never `WELL_SUPPORTED`. Design the data model to accept
multiple policy years from day one, even if the UI accepts one.

**9.4 Language.** The doc claims "ordinary Indian consumer" while assuming English
literacy. MVP decision: **input documents English-only** (real policy wordings are),
but **output must be translatable**. Keep all user-facing strings and generated
explanations separable from logic so Hindi output can be added without a rewrite.
Do not translate quoted clause text — show the original and the translation together.
`SPIKE-4` decides which second language ships first.

**9.5 PII.** Real uploaded policies contain names, addresses, DOBs, policy numbers,
sometimes health history. Rules: no document content in logs, ever. Redact before
any telemetry. Documents used for the eval corpus must be explicitly consented or
synthetic. Write this into the code as a lint-enforced boundary, not a policy doc.

---

## 10. Retrieval

Three layers, strict precedence:

1. **User policy wording** — primary authority, always.
2. **User CIS** — consumer summary. Used for cross-checking and for locating topics
   quickly. **Loses to the policy wording on any disagreement**, but the
   disagreement is surfaced as `CONFLICTING`, not hidden.
3. **Regulatory corpus (IRDAI)** — only for standardised definitions and regulatory
   requirements. Every regulatory span carries an effective date and a
   superseded-by field.

**The model's general knowledge is never evidence.** If a claim's only support is
"this is how Indian health insurance usually works", it is `INSUFFICIENT_EVIDENCE`.
Test for this explicitly: put a policy with an unusual, non-market-standard term in
the eval set and check the system reports the document's term, not the typical one.

Retrieval must be hybrid — insurance wording is full of exact terms and numbers that
pure dense retrieval misses. Lexical + dense, union of results, no reranking that
can drop a contradicting span.

> **SPIKE-3 — Retrieval stack.** Choose the index and embedding approach.
> Constraint: must run locally for eval reproducibility, must support exact-phrase
> lookup. Timebox: half a day. Do not over-engineer; the retrieval layer is not the
> differentiator.
>
> **RESOLVED (2026-09-14).** See `/docs/spikes/retrieval-stack.md`. Decision:
> lexical retrieval via SQLite FTS5 (stdlib, exact-phrase + BM25 ranking, no extra
> dependency) plus dense retrieval via a small local sentence-transformers model
> (brute-force numpy cosine for now), unioned via Reciprocal Rank Fusion — never
> reranked, so a contradicting span found by either method is never dropped.

---

## 11. Ground truth and corpus

The binding constraint on this project is labelled data, not model quality.

**Three sources, in priority order:**

**A. Adjudicated disputes.** Published Insurance Ombudsman awards contain a real
fact pattern, the disputed clause, the insurer's position, and a reasoned outcome.
This is effectively expert-labelled data that already exists.

> **SPIKE-2 — Ombudsman corpus feasibility.** Determine: volume of published awards
> for health insurance; format (HTML/PDF/scanned); whether the underlying policy
> wording is identifiable or quoted sufficiently; licensing/terms for research use;
> and how many awards turn on clause interpretation vs. procedural issues.
> **This spike gates the entire evaluation plan.** Do it first.
> Output: `/docs/corpus/ombudsman-feasibility.md` with a sample of 20 awards
> hand-classified by usable / not usable and why.
>
> **PARTIALLY RESOLVED (2026-09-14).** See `/docs/corpus/ombudsman-feasibility.md`.
> A real, bulk-downloadable archive was found (an unlisted directory on
> cioins.co.in, `GIC/mediclaim/Mediclaim-Book*.pdf` and siblings) — clause-level
> fact patterns confirmed, including a complete numbers-and-all worked example
> of this project's own hero scenario. Still open: no reuse license found on
> the source site (do not redistribute or build the eval corpus on this at
> scale until that's resolved with the project owner), and only 8 of the
> required 20 sample awards have been hand-classified so far. This still gates
> the evaluation plan (§12/§13) and M0 is not done until both are closed.

**B. Real policy wordings.** Insurers publish policy wordings and CIS documents.
Determine what may be used for development and evaluation.

**C. Synthetic controlled variants.** Generated to isolate specific reasoning:
identical policies differing in exactly one term (waiting period 2y vs 4y; room
cap present vs absent; co-pay 10% vs 20%). These give clean, unambiguous labels and
are the only practical way to measure whether the system reads *this* document
rather than the market norm. **Synthetic data complements real documents; it never
replaces them.** Report metrics on real and synthetic splits separately, always.

**Adversarial split (build this deliberately).** Cases designed to break the system:
CIS contradicting the wording; a term buried in an endorsement that overrides the
main document; an unusual non-market-standard limit; a required input that is absent;
a scenario the documents genuinely cannot answer. The correct output for several of
these is **not an answer** — it is the right abstention. That is what you are testing.

---

## 12. Metrics

Track separately. Do not collapse into a single score.

**Extraction**
- Field accuracy (exact match against annotated fields), per field type.
- Span accuracy: does the cited span actually contain the value.
- Hallucinated-field rate: fields returned that do not exist in the document.

**Retrieval**
- Recall@k for the clause a human annotator marked as decisive.
- **Contradiction recall**: when a contradicting span exists, how often is it
  retrieved. Under-measured everywhere, and it is what makes `CONFLICTING` work.

**Verification and calibration** — the headline metrics
- **Unsupported claim rate**: claims marked `WELL_SUPPORTED` whose cited span does
  not actually support them, per human annotation. **Target: near zero. This is the
  number the project lives or dies on.**
- **Risk–coverage curve**: accuracy on answered items as a function of the fraction
  answered. Report the full curve, not one point.
- **Appropriate abstention**: on cases annotated as genuinely undeterminable from the
  documents, how often the system reaches `NEEDS_INFORMATION` /
  `INSUFFICIENT_EVIDENCE` rather than answering.
- **Confident-and-wrong rate**: `WELL_SUPPORTED` and factually wrong. Weight this
  heavily — it is the harm case.
- **Over-abstention**: `INSUFFICIENT_EVIDENCE` on cases that were answerable. The
  failure mode on the other side; a system that abstains on everything is useless
  and must not be able to score well.

**Usefulness**
- Can a non-expert reader, given the output, state what they would do next?
  Small-n, qualitative, still worth running.

---

## 13. Ablation design

The v1 ablation would have made the abstention layer look bad, because a system that
declines some questions scores lower on plain accuracy. Fix the metric, not the system.

| Arm | Configuration |
|---|---|
| A | LLM only, no documents |
| B | LLM + naive RAG over raw chunks |
| C | B + structured extraction with provenance |
| D | C + claim decomposition and span verification |
| E | D + support-state resolution (full system) |

**Primary comparison:** risk–coverage curves for C, D, E, plus **accuracy at matched
coverage** — hold the answered fraction constant across arms and compare accuracy.
This is the only comparison that can show what the uncertainty layer actually buys.

**Secondary:** unsupported claim rate across arms at full coverage. Expect this to
be the cleanest, most dramatic result — and it is the one that supports the thesis
that RAG alone does not eliminate ungrounded claims.

Report A and B honestly even where they look competitive on easy extraction
questions. They will lose badly on the adversarial split, which is the point.

---

## 14. Build order

Each milestone ships something runnable. Do not proceed past a Definition of Done.

**M0 — Corpus and spikes.** *(Blocks everything.)*
Run SPIKE-2 (ombudsman), SPIKE-1 (proportionate deduction regulation), SPIKE-3
(retrieval stack). Assemble ≥15 real policy+CIS pairs and the adversarial case list.
**DoD:** three spike memos written and dated; corpus inventoried; 30 annotated eval
cases exist, of which ≥8 are correctly-abstain cases.

*Status as of 2026-09-14: SPIKE-1 and SPIKE-2 both partially resolved,
SPIKE-3 resolved, repo scaffold committed. The corpus has grown to 5 real
policy+CIS/CIS-bundle pairs across 3 insurers (HDFC ERGO, Star Health,
Bajaj Allianz — see `corpus/README.md`), verified to cover 3 of the 4
hero-scenario room-rent bases (compound %+flat cap, pure %-of-SI, no cap)
— still short of the ≥15-pair target, still missing room-category
eligibility and a pure flat-₹/day cap. A real ombudsman award archive has
been found for SPIKE-2 (`docs/corpus/ombudsman-feasibility.md`) with one
sample book pulled locally, including a complete worked example of the
hero scenario — but its reuse license is unresolved, so it has not been
built into the annotated eval set. M0 is not yet done: the corpus and
eval-set targets remain open, and the licensing question needs the
project owner's input. M1 (intake/extraction) and M3 (reasoning/
verification) work has proceeded ahead of M0's full completion regardless,
since neither depends on SPIKE-2 or the eval set.*

**M1 — Intake and extraction with provenance.**
Classification (§9.1), segmentation, span store, field extraction for the hero
scenario's fields plus sum insured, policy period, waiting periods, co-pay,
sub-limits.
**DoD:** extraction metrics running in CI on the annotated set; every field has a
span; `verbatim_match` computed; conflicting candidates surfaced not resolved.

*Status as of 2026-09-14: classification and segmentation are real and
verified against the starter corpus (`decoder/intake/classify.py`,
`segment.py`) — a real 52-page policy wording segments into 424 precise
clause-level spans with page+bbox provenance. Field extraction has a real
deterministic (regex) implementation for the mechanically-safe fields only
(UIN, explicit numeric room-rent caps — `decoder/extract/regex_extractor.py`),
verified against all three real policy wordings, including a genuine
compound-formula case (Arogya Sanjeevani's "2% of SI, capped at ₹5000/day").

As of 2026-09-15, waiting periods (initial, PED, specific-illness) and
co-payment also have a real LLM-based implementation
(`decoder/extract/llm_extractor.py`), now that `decoder/reason`/
`decoder/verify` are wired against a real LLM client (M3 status, below).
It deliberately does not trust the model with the number itself: the model's
only job, isolated to ONE field definition and ONE span at a time (mirroring
`decoder/verify/entailment.py`'s isolation), is to say whether that span
states the field's value and quote the exact words that do; the quote must
be verbatim-in-span (`decoder/verify/span_containment.py`) or it's
discarded, and the actual number is then parsed out of that verified quote
by a field-specific regex in code — a hallucinated digit in the quote fails
the regex and the span is dropped, not trusted. Verified by hand against
live Ollama (qwen2.5-coder:7b) across four different real documents/insurers
(HDFC ERGO, Star Health): co-payment (5% and, separately, a 10%
senior-citizen co-pay), a 36-month PED waiting period, a 30-day initial
waiting period (two independently-phrased documents), a 24-month
specific-illness waiting period.

Room-category eligibility is also implemented, but with no real positive
example anywhere in the starter corpus to verify it against (confirmed:
none of the corpus documents state an explicit room-category eligibility
clause — corpus/README.md's own "still needed" list already flagged this
gap). Building it caught a real false-positive before it shipped: the
model first matched a *definition* clause ("Def. 17 Single occupancy ...
means a Hospital room with only one patient bed") as if it were an
eligibility statement. Fixed by tightening the field's prompt to explicitly
exclude definition-shaped clauses; a regression test for exactly this case
is in `tests/extract/test_llm_extractor.py`. Still needs a real corpus
document with a room-category clause before it can be called verified
rather than just implemented.

The proportionate-deduction carve-out list is still NOT implemented
anywhere — it's list-valued and `ExtractedField.value` is scalar
(`str | int | float | bool | None`); extending that is a schema decision
(SPIKE-6, still NOT STARTED) rather than one made unilaterally inside an
extractor module.

Extraction metrics/CI and the annotated set are not started (still blocked
on SPIKE-2).*

**M2 — Retrieval.**
Hybrid retrieval over policy and CIS. Regulatory corpus stubbed.
**DoD:** recall@k and contradiction recall reported on the eval set.

*Status as of 2026-09-14: `decoder/retrieve/lexical_fts5.py`'s FTS5 lexical
half is real and, as of this pass, split into two methods —
`search_phrase()` (exact-phrase, the original SPIKE-3 behavior) and
`search()` (OR-of-terms, ranked by BM25). The split exists because a real
end-to-end test caught `search()`'s original always-phrase behavior
returning zero results for a natural-language retrieval query whose words
didn't literally co-occur in the target clause — phrase search alone was
never going to serve free-text evidence retrieval. Dense retrieval
(`dense.py`) and a `HybridRetriever` combining both are still not built,
still blocked on SPIKE-2's corpus. No recall@k/contradiction-recall metrics
yet — blocked on the eval set (§11/§15).*

**M3 — Reasoning and verification.** *(The core.)*
Draft generation, atomic decomposition, isolated span entailment with the
deciding-words trap, code-executed derived claims.
**DoD:** unsupported claim rate measured; the deciding-words trap demonstrably
catches injected errors (write that test).

*Status as of 2026-09-14: `decoder/verify` is now complete. Draft generation
(`decoder/reason/ollama_drafter.py`), isolated single-span entailment
(`decoder/verify/entailment.py`), multi-claim decomposition
(`decoder/verify/decompose.py`), and code-executed DERIVED-claim arithmetic
(`decoder/verify/numeric_check.py`) are all real, with tests against the
starter corpus and (for decompose/entailment) a live local model. Full
retrieve → draft → verify → resolve chains have been run end-to-end for
both a nuanced document field (co-payment %) and the hero scenario's own
DERIVED comparison (₹8,000/day room vs. ₹5,000/day limit). The
deciding-words hallucination trap is demonstrably enforced (a fabricated
quote is caught; an off-label verdict word like "CONFLICTS" defaults
safely to NEUTRAL). Decompose deliberately does not attempt to extract
DERIVED-claim numeric operands from free text — tested by hand and found
unreliable — so a DERIVED claim's `derived_operation` must be constructed
by code that already has the real operand values, never parsed from a
model's draft (`decoder.schema.DerivedOperation`'s docstring has the
detail).

**A real "confident and wrong" instance was caught by the test suite
itself** (§12's headline harm case), not hypothesized: at Ollama's default
sampling temperature, `OllamaEntailer` intermittently returned SUPPORTS for
a fabricated co-payment percentage checked against a real clause stating
the correct one — the model's own quoted text contained the right number,
but its verdict ignored it. `decoder/llm/ollama_client.py` now defaults to
`temperature=0`, confirmed by hand to reproduce the correct verdict
consistently (15/15 trials) where the default temperature was not. This is
recorded here rather than quietly patched, because it's a concrete,
measured data point for exactly the metric §12 asks for — not proof the
failure mode is fully closed, only that this one reproduction is fixed.

No unsupported-claim-rate metric yet — needs the eval set (SPIKE-2,
§11/§15).*

**M4 — Resolution and response.**
`resolve/` as pure functions with exhaustive unit tests. Question generation derived
from actual gaps, not a template list.
**DoD:** 100% branch coverage on `resolve/`; every UI state renders with its required
accompanying content; no answer path bypasses verification (assert this in a test).

**M5 — Hero scenario end to end.**
Room-rent / proportionate deduction, with visible arithmetic and linked spans.
**DoD:** runs on ≥3 real policies with different room-rent structures, including one
with no cap and one where the carve-out list is absent from the document.

**M6 — Evaluation harness and ablation.**
**DoD:** all five arms runnable with one command; risk–coverage curves generated;
results written up.

**UI** is a structured analysis view, not a chat window. Chat exists only as a
secondary affordance for "why is this flagged" / "show me the clause" / "simpler
language". Build the analysis view first.

---

## 15. Open decisions `SPIKE`

| ID | Question | Gates | Status |
|---|---|---|---|
| SPIKE-1 | IRDAI position on proportionate deduction, with dates | M5 | PARTIALLY RESOLVED (2026-09-14) — see `/docs/regulatory/proportionate-deduction.md` |
| SPIKE-2 | Ombudsman corpus feasibility | M0, all evaluation | PARTIALLY RESOLVED (2026-09-14) — see `/docs/corpus/ombudsman-feasibility.md`; archive found, licensing unresolved |
| SPIKE-3 | Retrieval stack | M2 | RESOLVED (2026-09-14) — see `/docs/spikes/retrieval-stack.md` |
| SPIKE-4 | Second output language and when | Post-MVP | PARTIALLY RESOLVED (2026-09-14) — see `/docs/spikes/translation-language.md`. Language (Hindi) and mechanism (translate only the final verified answer text, via Gemini — tested against Ollama and found clearly better for this role) are decided; "when" (which milestone ships it in the UI) is still open since no frontend exists yet. |
| SPIKE-5 | Model choice per role — drafting and verification need not be the same model, and the verifier arguably should be cheaper and dumber | M3 | PARTIALLY RESOLVED (2026-09-14) — `decoder/llm/interface.py`'s `LLMClient` now has two real, working implementations (`ollama_client.py`, local, no key; `gemini_client.py`, cloud, needs `GEMINI_API_KEY`) plus two documented stubs (`anthropic_client.py`, `openai_client.py`, unwired pending keys) — any package can use any provider per role without changing its own code. Which specific model(s) to use per role (drafter vs. verifier, and which provider) is still open. |
| SPIKE-6 | Final policy schema beyond the hero fields | M1 extension | NOT STARTED |
| SPIKE-7 | Annotation protocol and inter-annotator agreement for the eval set | M0 | NOT STARTED |

Resolve, date, and record in this file.

---

## 16. Guardrails for future agents

Before adding anything, answer: **does this strengthen the core loop
(understand → retrieve → verify → resolve → act), or widen it?**

Priorities, in order of tie-breaking:

```
Depth            > breadth
Evidence         > fluency
Reliability      > impressive demos
Actionability    > summaries
Calibrated doubt > confident answers
Real user pain   > general AI capability
```

**Specific anti-patterns to refuse:**

- Adding a fast path that skips verification "just for simple questions".
- Reintroducing a numeric confidence score into the resolution logic.
- Letting the verifier see the draft answer or the user's question.
- Defaulting an absent field to a market-typical value.
- Adding policy comparison back in before the core loop is measured.
- A generic AI disclaimer banner.
- Expanding to another insurance line before the health MVP has published metrics.

The goal is not the largest legal AI system. It is a small, evidence-grounded
insurance reasoning product that survives hostile questioning about accuracy,
safety, and usefulness.

---

## 17. Post-completion checklist (added 2026-09-14)

Once the project reaches a genuinely complete/demoable state (hero scenario
working end-to-end, frontend live, deployed): **publish results/findings
and a raw working example to GitHub**, distinct from the routine commits
already going to github.com/sahil-mangla/health-policy-agent throughout
development — intended for hackathon judges to reference and validate the
submission. Confirm exact scope with the project owner at that point rather
than assuming (e.g. a results write-up, a judge-facing README pass, a
sample walkthrough/output) — not started yet, noted here so it isn't
dropped.
