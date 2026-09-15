# SPIKE-2 — Insurance Ombudsman corpus feasibility

**Status: RESOLVED — NOT CLEARED FOR USE (2026-09-15)**

This gates the entire evaluation plan (`docs/HANDOVER.md` §11/§12/§13). A
real, bulk-downloadable archive was found and spot-verified (2026-09-14) —
genuinely the best fact-pattern source identified for this project — but
the licensing question that was left open at that point has now been
checked directly against the source site's own published terms, and the
answer is a clear no. **Do not use this archive as an eval-set source.**
See "Licensing — resolved" below; everything above that heading is the
original 2026-09-14 feasibility write-up, kept for the record.

## Where the archive actually is

IRDAI's own site (`irdai.gov.in/awards-of-ombudsman`) is a dead end — a
single sentence pointing at the Council for Insurance Ombudsmen (CIOINS),
last touched 2019, no hosted content. CIOINS's own visible navigation
(`cioins.co.in`) has no "Awards" or case-law menu item either.

The real archive is an **unlisted, unindexed legacy directory** on the same
domain, found only via `site:cioins.co.in` search and by guessing
sequential filenames — there is no index page:

```
https://www.cioins.co.in/GIC/mediclaim/Mediclaim-Book1.pdf   ... Book20+
https://www.cioins.co.in/GIC/groupmediclaim/GroupMediclaim-Book1.pdf ... Book20+
https://www.cioins.co.in/GIC/overseasmediclaim/OverseasMediclaim-Book1.pdf ...
```

(Sibling folders exist for motor, fire, personal accident, and LIC life
lines — not explored, not relevant here.) The naming pattern is predictable
enough that a script can enumerate it the same way this research did.

## What's actually in one book (verified firsthand, not just described)

Downloaded and read `Mediclaim-Book17.pdf` in full (376 pages, real text
layer — `pdfplumber` extracts it cleanly, not a scanned-image PDF). Each
entry is a compact, structured case digest: ombudsman centre, case number,
parties, insurer, award date, dispute type, fact pattern, the specific
clause/ground invoked, and the outcome. This is real clause-level fact
pattern data, not bare pass/fail summaries.

**Best example found — a complete, numbers-and-all worked instance of this
project's own hero scenario** (Chennai Ombudsman Centre, Case No.
11.12.1782/2011-12, *Mrs. Paramdeep Kaur Ahuja v. ICICI Lombard General
Insurance Co Ltd*, Award No. IO(CHN)/G/025/2012-13):

> "the insured took treatment in the Hospital with a room rent of
> Rs.8900/- per day exceeding his entitled limit of Rs.1500/- per day.
> Therefore all Hospital charges are paid in proportion to his eligibility
> for room rent as per policy conditions... as per Special Condition
> No.XXV the expenses under different heads were restricted in proportion
> to the eligible room rent of Rs.1500/- per day... vis-à-vis the actual
> room rent of Rs.8900/- per day which works out to 16.8%..."

This is directly usable as an eval case: real numbers, a named clause
("Special Condition No.XXV"), the computed ratio, and a reasoned (partial —
ex-gratia ₹2,000) outcome.

### First-pass classification (partial sample, not yet the full 20)

Read closely enough to classify 8 cases from this one book while confirming
the archive's general quality — this is a start toward SPIKE-2's own
"sample of 20, hand-classified" requirement, not a completion of it:

| Case | Dispute | Clause detail | Usable? |
|---|---|---|---|
| 11-009-0160-12 (Murjani v. Reliance) | Repudiation, congenital-disease exclusion | Clause number referenced, not quoted | Marginal — outcome clear, clause text absent |
| 11-004-0538-12 (Patel v. United India) | Repudiation on a documentation-name mismatch | Procedural, not a clause-interpretation dispute | Usable as an adversarial/procedural edge case, not a clause-reading case |
| 11-002-0591-12 (Bhatt v. New India) | Partial settlement per numbered policy conditions | Condition numbers cited, full text absent | Marginal |
| Chennai 11.04.1714/2011-12 (Krishnamurthy v. United India) | Room-rent proportionate deduction, "condition No.1.2... 1% of sum insured" | Percentage and clause number both given | **Usable — directly on-topic** |
| Chennai 11.12.1782/2011-12 (Ahuja v. ICICI Lombard) | Room-rent proportionate deduction, full numbers | Complete worked example (see above) | **Usable — best case found, hero-scenario match** |
| Chennai 11.04.1759/2011-12 (James v. United India) | Sum-insured continuity across renewal for cataract surgery | Underwriting-guideline text quoted | Usable — continuity/waiting-period-adjacent |
| Chennai 11.17.1036/2012-13 (Patwary v. Star Health) | Sub-limits + room-rent proportionate deduction | "Reasonable and Necessary" clause + proportionate deduction discussed | Usable |
| Chennai 11.02.1090/2012-13 (Bhansalai v. New India) | Not fully read this pass | — | Not yet classified |

Roughly **5 of 8** examined so far are directly usable for clause-level eval
cases, 2 are marginal (procedural/no clause quoted), 1 unclassified — a
promising ratio, but 8 is not 20; extending this classification across more
books (and more of this book) is the concrete next step.

## Volume, date range, and coverage gaps

Roughly 20 books each for individual mediclaim, group mediclaim, and
overseas mediclaim alone (other lines not counted) — very likely several
hundred to low-thousands of health-insurance case entries in total. Date
range for the sampled book skews **2012** (Ahmedabad and Chennai centres
both appear in this one book); the archive's overall span and per-region
completeness across all ~7-9 ombudsman centres and more recent years is
**not confirmed** — a real gap to close before treating this as
comprehensive ground truth.

## Licensing — resolved (2026-09-15): NOT CLEARED

The 2026-09-14 pass found no explicit terms and treated the question as
open. On follow-up, cioins.co.in does in fact publish both a Disclaimer
page and a "Terms and Conditions.pdf" (linked from the site footer,
`/Disclaimer` and `/notification/Terms and Conditions.pdf`) — they were
simply not checked directly the first time round. Both are unambiguous and
neither carries a research/fair-use/non-commercial carve-out:

> Disclaimer: "No material from this web site can be copied, reproduced,
> published, uploaded, posted, transmitted or distributed or dealt with in
> any manner." / "Users are not permitted to change, modify or prepare
> derivative works from the content of this site."
>
> Terms & Conditions §L (Intellectual Property): "All content and
> information ... available on the Website, are the property of CIO ...
> Any unauthorized copying, distribution, modification, or use of this
> content is expressly and strictly prohibited."

This is a real, explicit prohibition, not merely an absence of a granted
right — stronger than the 2026-09-14 memo's framing assumed. It applies to
the mediclaim award books exactly as much as to any other page on the
site; nothing distinguishes adjudication records as public-record content
exempt from this. **Conclusion: this archive must not be bulk-scraped,
committed to this (public) repository, or built into the eval set at
scale.** The single sample file pulled 2026-09-14 for feasibility
assessment (`corpus/raw/ombudsman_awards/cioins_mediclaim_book17.pdf`) was
never committed and should be deleted from local disk, not retained on the
theory it might still be useful later.

SPIKE-2 is now resolved in the sense that matters for planning purposes —
no more time should be spent extending the classification sample on this
source, and M0/M6 should route around it rather than waiting on further
licensing clarification. If a licensed path is wanted later, it would mean
contacting CIO directly (`inscoun@cioins.co.in`, the T&C's own listed
grievance contact — though that address is scoped to the ombudsman
complaint process, not licensing requests, so a real reuse inquiry may
need a different, more clearly commercial/legal contact than the one
published) and getting written permission before pulling anything beyond
this single already-deleted sample.

## Secondary source — indiankanoon.org (supplementary only)

Hosts High Court judgments that *review* ombudsman awards (a party
petitioning to set aside one). Quality is inconsistent and requires
case-by-case triage: one example (*Star Health v. Insurance Ombudsman*, 21
Nov 2024, indiankanoon.org/doc/182721591) quotes an award's reasoning
verbatim in useful depth; another (*Prasanna Narendran v. The Insurance
Ombudsman*, 14 Aug 2025, indiankanoon.org/doc/16315339) barely mentions the
underlying dispute at all. Also carries a selection bias toward awards
contested enough to reach a writ court — not representative of the typical
(uncontested) award. Useful as a supplement once the primary archive is
established, not as a primary source on its own.

## Verdict

**Not usable as an eval-set source — licensing forecloses it (see above).**
The archive itself is genuinely excellent — a bulk-downloadable,
clause-level adjudicated-dispute corpus, far better than "nothing exists"
— which makes this a real loss for the eval plan, not a formality. The
30-case annotated eval set (§11's "of which ≥8 are correctly-abstain
cases") needs a different source. `indiankanoon.org` (below) was not
itself checked for reuse terms and remains a secondary, supplementary
option at best given its own quality/selection-bias caveats — it has not
been vetted as a primary replacement. Recommended next step: decide the
eval set's real source with the project owner (candidates: hand-authored
cases grounded in the existing policy-wording/CIS corpus already in hand,
IRDAI circulars/regulations directly, or a licensing inquiry to CIO if the
project is willing to wait on a response) — see `docs/HANDOVER.md` M0/M6
for how this feeds the build order.
