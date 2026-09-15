# SPIKE-2 (continued) — NCDRC / Consumer Commission judgment feasibility

**Status: PROMISING — first-pass sample done, not yet the full 20-case
classification (2026-09-15)**

This is the replacement candidate for the ombudsman-award archive
(`docs/corpus/ombudsman-feasibility.md`), which turned out not to be
licensed for this use — see that memo's "Licensing — resolved" section.
The question this memo answers: is there a *legally clean* source of real,
adjudicated Indian health-insurance disputes, as rich as the ombudsman
archive was, to build the annotated eval set on?

## Why this source, specifically

Health insurance disputes are not only decided by the Insurance Ombudsman —
plenty are litigated through India's consumer protection forums (District
Consumer Commissions → State Consumer Disputes Redressal Commissions →
NCDRC → Supreme Court on further appeal). These bodies are formal
adjudicatory tribunals under the Consumer Protection Act, and their
judgments are exactly the same shape of ground truth the ombudsman awards
were: a real fact pattern, a real clause dispute, and a reasoned, binding
outcome.

## Licensing — the actual legal basis, checked directly (not assumed)

**Section 52(1)(q)(iv) of the Copyright Act, 1957** exempts "the
publication in a newspaper of a report of a judicial proceeding" and,
separately under the same clause, the reproduction or publication of any
**judgment or order of a court, Tribunal or other judicial authority**,
unless that court/tribunal itself prohibits reproduction. This is a
statutory exception, not a website's discretionary grant — it exists
independent of whatever terms of use a hosting site publishes, because a
website cannot use its own terms of use to expand copyright protection
beyond what the Copyright Act itself grants over content it didn't
author. NCDRC and the State/District Consumer Commissions are
unambiguously tribunals under this provision — this is a materially
different, stronger position than the ombudsman question, where "is a
private council's award a tribunal order" was genuinely less clear-cut and
CIOINS had in any case asserted a blanket contrary claim over its own site.

Checked the two actual access points, not just assumed cleanliness:

- **`confonet.nic.in` / `ncdrc.nic.in`** — the official government (National
  Informatics Centre, Ministry of Electronics & IT) judgment-search portal
  for the consumer commission system. Its only disclaimer found is the
  standard "NIC is not responsible for the accuracy/completeness of the
  data" liability boilerplate — no reuse restriction.
- **`indiankanoon.org`** — a third-party aggregator that mirrors many of
  these judgments in cleaner, more consistently structured text. Its own
  Terms page (`indiankanoon.org/members/terms/`) has **no clause
  restricting copying, reproduction, or redistribution** of judgment
  content, and states outright that its data is "sourced through public
  websites including... government websites" — i.e. it does not itself
  claim an ownership layer over the judgments the way CIOINS did over the
  ombudsman archive.

**Caveat, stated plainly rather than glossed over:** Section 52(1)(q)(iv)'s
exception has an explicit carve-out — it doesn't apply if "reproduction or
publication of such judgment or order is prohibited by the court, the
Tribunal or other judicial authority" itself. This needs checking
per-judgment in practice (some sealed/in-camera matters carry such an
order; ordinary consumer-forum money disputes essentially never do, and
none of the cases read for this pass carried one), not assumed blanket-clear
forever. This is a genuine legal reading, not a substitute for actual legal
counsel if the project wants a fully authoritative answer before shipping —
but it is a real statutory basis checked against primary sources, which is
categorically different from "nobody said we couldn't."

## First-pass sample — read in full, not just found by search (2026-09-15)

Ten cases pulled via `indiankanoon.org` search and read in full to assess
quality, mirroring the ombudsman memo's own "read one book, classify what's
in it" method:

| Case | Forum | Issue | Numbers given | Usable? |
|---|---|---|---|---|
| Niraj Kajaria v. United India Insurance (W.B. State Commission, 2017) | State Commission | Room-rent proportionate deduction | Entitled ₹4,250/day, actual room ₹5,400–9,000/day, entitled total ₹21,250, deducted ₹12,950, plus a wrongly-computed OT-equipment deduction the Commission corrected (₹1,847 claimed vs. ₹745.15 correct) | **Usable — best case found, and better than the ombudsman example**: a real instance of the Commission catching wrong arithmetic, directly useful as an adversarial/verification eval case |
| V. Rama Rao v. New India Assurance (Karnataka State Commission, 2022) | State Commission | Room-rent/proportionate deduction, but decided on procedural grounds (insurer changed terms without notice) | Sum insured ₹3,00,000; claimed ₹3,58,384; paid ₹1,23,971; awarded additional ₹1,76,029 | Usable as an adversarial "unilateral policy change" edge case; not a clean room-rent arithmetic example on its own |
| National Insurance v. Anil Kumar Jain (Delhi State Commission, 2016) | State Commission | 10% co-payment clause | Sum insured ₹1,00,000; bill ₹1,89,000; 10% co-pay = ₹10,000 deducted; ₹90,000 sanctioned, then claim denied on a separate exclusion ground | Usable for the co-payment arithmetic; final outcome turns on an unrelated exclusion, so pair with a cleaner co-pay case if the eval set wants a "claim succeeds" example too |
| Care Health Insurance v. Harjinder Singh Sohal (NCDRC, 2024) | NCDRC | Pre-existing disease non-disclosure repudiation | Sum insured USD 50,000; bill AUD 31,499 (~₹17,26,546); full claim + ₹50,000 compensation + ₹25,000 costs + 12% interest awarded | **Usable — clean worked example of a repudiation reversed for improper underwriting** |
| Smt. Surilla Mathur v. Oriental Insurance (Delhi State Commission, 2024) | State Commission | Pre-existing condition exclusion, travel/health policy | Claim S$44,891.15 (~₹13,46,735); full award + ₹1,00,000 (mental agony) + ₹50,000 costs + 6% interest | Usable — real exclusion clause quoted verbatim, real numbers |
| Manmohan Singh v. United India Insurance (Delhi State Commission, 2021) | State Commission | 48-month pre-existing-disease waiting period, two-policy claim | Policy 1 ₹5,25,000, Policy 2 (top-up) ₹10,00,000; bill ₹6,87,477; ₹3,87,000 awarded under Policy 2 | Usable — continuity/waiting-period case with real numbers across two linked policies |
| Arun Kumar v. New India Assurance (NCDRC) | NCDRC | Pre-existing disease non-disclosure, *uberrima fides* argument rejected | Claim ₹38,240.50; awarded in full + 9% interest | Usable — smaller claim, but a clean disclosure-obligation precedent |
| Jacob Punnen v. United India Insurance (Supreme Court, on appeal from NCDRC) | Supreme Court | Insurer added a new sub-limit clause ("70% of SI or max ₹2 lacs" for angioplasty) at renewal without notice | Sum insured ₹8,00,000 total; claim ₹3,82,705.27; paid ₹2,00,000; final award ₹1,75,000 + ₹50,000 costs | Usable as the sharpest adversarial "silently changed term at renewal" case found across either archive — directly relevant to this project's own §9.3 continuity concerns |
| Star Health v. Mohinder Pal (State Commission, 2023) | State Commission | Co-payment, not yet read in full | — | Found, not yet classified |
| The New India Assurance v. Ria Ranjan Alimchandani (State Commission, 2014) | State Commission | Co-payment/excess terms, not yet read in full | — | Found, not yet classified |

**8 of 10 fully read and classified as usable, 2 found but not yet read** —
a stronger ratio than the ombudsman archive's own first pass (5 of 8), on a
sample pulled from generic keyword search rather than even a curated
starting point. Every hero-scenario category this project needs
(room-rent/proportionate-deduction, co-payment, pre-existing-
disease/waiting-period, plus a real continuity/renewal adversarial case)
has at least one real, numbers-and-all example already in hand from just
two search passes — search results suggest dozens more per category are
available on `indiankanoon.org` alone, not counting the primary
`confonet.nic.in`/`ncdrc.nic.in` government source directly.

## What this doesn't establish yet

- Not yet a real 20-case classification at the depth SPIKE-2 originally
  asked for — this is a first pass proving the source is viable, the same
  status the ombudsman archive had before its licensing problem surfaced.
- No systematic date-range/forum-coverage check yet (the ombudsman memo's
  own "skews toward 2012, Chennai/Ahmedabad" gap-finding exercise hasn't
  been repeated here).
- Room-category-eligibility and pure-flat-₹/day-cap cases (the two gaps
  `corpus/README.md` already flags as missing from the policy-document
  corpus itself) weren't specifically searched for yet — worth a targeted
  pass if this becomes the eval source.
- The per-judgment "not prohibited by the tribunal" check (Section
  52(1)(q)(iv)'s own carve-out) has been spot-checked, not exhaustively
  verified across every case that would go into a real 20+ case set.

## Verdict

**Usable, and meaningfully stronger on licensing than the archive it
replaces** — a real statutory basis (Section 52(1)(q)(iv)) rather than an
absence-of-prohibition argument, verified against two actual access points
that themselves impose no reuse restriction. Quality and volume both look
at least as good as the ombudsman archive on this first pass, across every
category this project's hero scenario and field list need. Recommended
next step: extend this classification to a real 20-case sample (pulling
directly from `confonet.nic.in`/`ncdrc.nic.in` where possible, using
`indiankanoon.org` as a faster-to-read mirror), specifically hunting for
the two still-missing structures (room-category eligibility, pure flat-cap)
along the way — then this can support the ≥15-pair corpus target and the
30-case annotated eval set (§11/§15) that SPIKE-2's original ombudsman path
was meant to unblock.
