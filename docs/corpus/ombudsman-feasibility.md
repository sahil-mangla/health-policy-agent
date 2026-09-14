# SPIKE-2 — Insurance Ombudsman corpus feasibility

**Status: PARTIALLY RESOLVED (2026-09-14)**

This gates the entire evaluation plan (`docs/HANDOVER.md` §11/§12/§13). A
real, bulk-downloadable archive has been found and spot-verified — this is
the single most important finding of this pass — but the full 20-award
hand-classified sample and the licensing question are not both closed yet.
Do not build the eval harness on this archive until the open item below is
resolved.

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

## Open item — blocks full sign-off

**No explicit reuse/licensing terms were found anywhere on cioins.co.in** —
only a generic "© CIO. All Rights Reserved 2021" footer, no research-use,
fair-use, or public-domain statement. Government/quasi-regulatory
adjudication records are often treated as public record in practice, and
these awards are already being reproduced in secondary sources (see below),
but nothing on the source site explicitly grants reuse rights. **Do not
bulk-scrape or redistribute this archive without resolving this** — a
single sample file has been pulled locally for feasibility assessment only
(`corpus/raw/ombudsman_awards/cioins_mediclaim_book17.pdf`); whether to
commit it to this (public) repository, and whether to build the eval corpus
on this source at scale, is a decision for the project owner, not something
to proceed on unilaterally.

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

**Usable, with real caveats.** This is a genuine, bulk-downloadable,
clause-level adjudicated-dispute archive — far better than "nothing exists"
— but it is unlisted (must be crawled by pattern-guessing), skews toward
older cases from specific centres, has no stated reuse license, and needs a
real extraction pass (not just this spot-check) to turn into the 30-case
annotated eval set (§11's "of which ≥8 are correctly-abstain cases" still
needs cases where the documents genuinely can't answer — worth watching for
those specifically while extending this sample). Recommended next step:
resolve the licensing question with the project owner, then (if cleared)
write a small script to enumerate and pull the `Mediclaim-Book*.pdf` and
`GroupMediclaim-Book*.pdf` series and extend this classification to a real
20-case sample.
