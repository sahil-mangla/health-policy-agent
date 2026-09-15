# SPIKE-2 (continued) — NCDRC / Consumer Commission judgment feasibility

**Status: PROMISING — 18-case sample classified, close to but not yet the
full 20-case target; two specific structures still unfound (2026-09-15)**

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

## Sample — read in full, not just found by search (2026-09-15, extended)

Eighteen cases pulled via `indiankanoon.org` search and read in full to
assess quality, mirroring the ombudsman memo's own "read one book,
classify what's in it" method — extended across two further passes
specifically to chase broader category coverage and the two missing
structures below.

| Case | Forum | Issue | Numbers given | Usable? |
|---|---|---|---|---|
| Niraj Kajaria v. United India Insurance (W.B. State Commission, 2017) | State Commission | Room-rent proportionate deduction | Entitled ₹4,250/day, actual room ₹5,400–9,000/day, entitled total ₹21,250, deducted ₹12,950, plus a wrongly-computed OT-equipment deduction the Commission corrected (₹1,847 claimed vs. ₹745.15 correct) | **Usable — best case found, and better than the ombudsman example**: a real instance of the Commission catching wrong arithmetic, directly useful as an adversarial/verification eval case |
| Nic Ltd. (National Insurance) v. Chetan Krishan Bhuchar (Punjab State Commission, 2015) | State Commission | Compound room-rent + ICU sub-limit, plus an overall per-illness cap | "1% of SI per day subject to max ₹5,000" (room), "2% of SI per day subject to max ₹10,000" (ICU), **"overall limit under this head: 25% of sum insured per illness"**; bill ₹2,69,720, paid ₹1,62,500 | **Usable — near-identical clause structure to the Arogya Sanjeevani compound clause already in the policy corpus, PLUS a third component (overall per-illness cap) not yet modelled anywhere in this project's schema** |
| V. Rama Rao v. New India Assurance (Karnataka State Commission, 2022) | State Commission | Room-rent/proportionate deduction, but decided on procedural grounds (insurer changed terms without notice) | Sum insured ₹3,00,000; claimed ₹3,58,384; paid ₹1,23,971; awarded additional ₹1,76,029 | Usable as an adversarial "unilateral policy change" edge case; not a clean room-rent arithmetic example on its own |
| Star Health v. Mohinder Pal (Punjab State Commission, First Appeal 239/2020, decided 2023) | State Commission | Co-payment | "50% of each and every claim arising out of pre-existing diseases and 30% of each and every claim for all other claims" — quoted verbatim; claim 1 ₹2,82,988 (paid ₹1,20,064); claim 2 ₹3,33,700 (50% ordered paid) | **Usable — clean two-tier co-payment clause (PED vs. general) with real arithmetic on both** |
| National Insurance v. Anil Kumar Jain (Delhi State Commission, 2016) | State Commission | 10% co-payment clause | Sum insured ₹1,00,000; bill ₹1,89,000; 10% co-pay = ₹10,000 deducted; ₹90,000 sanctioned, then claim denied on a separate exclusion ground | Usable for the co-payment arithmetic; final outcome turns on an unrelated exclusion |
| New India Assurance v. Ria Ranjan Alimchandani (Maharashtra State Commission, 2014) | State Commission | Premium loading tied to claims experience, with co-payment brackets (15–25%) as part of the same clause | Premium ₹2,862 → ₹5,725 (100% loading); claimed compensation ₹4,00,000 | Usable but tangential — co-payment appears as one component of a renewal-loading clause, not the primary dispute |
| Care Health Insurance v. Harjinder Singh Sohal (NCDRC, 2024) | NCDRC | Pre-existing disease non-disclosure repudiation | Sum insured USD 50,000; bill AUD 31,499 (~₹17,26,546); full claim + ₹50,000 compensation + ₹25,000 costs + 12% interest awarded | **Usable — clean worked example of a repudiation reversed for improper underwriting** |
| Smt. Surilla Mathur v. Oriental Insurance (Delhi State Commission, 2024) | State Commission | Pre-existing condition exclusion, travel/health policy | Claim S$44,891.15 (~₹13,46,735); full award + ₹1,00,000 (mental agony) + ₹50,000 costs + 6% interest | Usable — real exclusion clause quoted verbatim, real numbers |
| Manmohan Singh v. United India Insurance (Delhi State Commission, 2021) | State Commission | 48-month pre-existing-disease waiting period, two-policy claim | Policy 1 ₹5,25,000, Policy 2 (top-up) ₹10,00,000; bill ₹6,87,477; ₹3,87,000 awarded under Policy 2 | Usable — continuity/waiting-period case with real numbers across two linked policies |
| Sukhdev Singh v. New India Assurance (Punjab State Commission, 2014) | State Commission | Pre-existing disease repudiation on "conjectures and surmises," no documentary evidence | Premium ₹6,309; expenses ₹28,694; awarded in full + 9% interest + ₹10,000 costs | Usable — a clean "insurer must actually prove PED, not assume it" precedent |
| Arun Kumar v. New India Assurance (NCDRC) | NCDRC | Pre-existing disease non-disclosure, *uberrima fides* argument rejected | Claim ₹38,240.50; awarded in full + 9% interest | Usable — smaller claim, but a clean disclosure-obligation precedent |
| Jacob Punnen v. United India Insurance (Supreme Court, on appeal from NCDRC) | Supreme Court | Insurer added a new sub-limit clause ("70% of SI or max ₹2 lacs" for angioplasty) at renewal without notice | Sum insured ₹8,00,000 total; claim ₹3,82,705.27; paid ₹2,00,000; final award ₹1,75,000 + ₹50,000 costs | Usable as the sharpest adversarial "silently changed term at renewal" case found across either archive — directly relevant to this project's own §9.3 continuity concerns |
| National Insurance v. Shyamal Mookerjee (W.B. State Commission, 2012) | State Commission | Exclusion clause (nebulisation charges) disallowed inconsistently with prior claim practice | Claim ₹12,297.48; allowed ₹5,976; disallowed ₹6,320 (ambulance ₹200, medicines ₹620, nebulisation ₹5,500) | Usable — small but a clean "insurer can't apply an exclusion inconsistently" precedent, and touches ambulance charges too |
| Simrit Kaur v. New India Assurance (Chandigarh State Commission, 2016) | State Commission | General deficiency-of-service (duplicate fee deduction), not a specific hero-scenario clause | Sum insured ₹5,00,000; awarded ₹81,138 + ₹10,000 + ₹7,500 | Usable as general corpus depth, not hero-scenario-specific |
| National Insurance v. Neeru Bhatia (Chandigarh State Commission, 2023) | State Commission | Billing dispute (pre-hospitalization disallowance, deduction reconciliation) | Sum insured ₹6.75 lakh; bill ₹2,08,741; paid ₹67,591; final award ₹1,09,660 + ₹15,000 + ₹10,000 | Usable as general corpus depth |
| Kewal Krishan Aggarwal v. New India Assurance (Punjab State Commission, 2020) | State Commission | AYUSH (Ayurvedic/Homeopathic/Unani) treatment sub-limit | Clause quoted verbatim: "expenses are admissible upto 25% of sum insured...provided treatment is taken in a Govt. Hospital or accredited institution"; sum insured ₹2,00,000; claim ₹98,507 | **Usable — the AYUSH sub-limit field this project's schema doesn't yet cover at all, with the clause quoted verbatim** |
| Oriental Insurance v. Agarwal Samaj (Chhattisgarh State Commission, 2026) | State Commission | Large group-mediclaim claim-processing/representative-standing dispute (not AYUSH despite search hit) | Group policy, 1,372 members, sum assured ₹15.19 crore; three linked claims totalling ~₹47.6 lakh, all ordered paid | Usable as general corpus depth — a group-policy scale example, a policy type not otherwise represented in this sample |
| Manmohan Nanda v. United India Insurance (Supreme Court) | Supreme Court | Pre-existing disease non-disclosure, overseas mediclaim | Treatment cost USD 2,29,719 (~₹1.09 crore); full indemnification ordered + ₹1,00,000 costs; Court explicitly reasons through what counts as "material fact suppression" | **Usable — the highest-value claim in the whole sample, and the clearest judicial articulation of the disclosure standard found across either archive** |

**18 of 18 read and classified as usable in some form** (14 directly on a
hero-scenario field or a schema-relevant sub-limit, 4 as general corpus
depth) — a stronger ratio than the ombudsman archive's own first pass (5
of 8). Two cases are worth flagging beyond the hero scenario itself: the
Nic Ltd. case is essentially the same compound room-rent clause already
verified in this project's real corpus
(`corpus/raw/hdfc_ergo/arogya_sanjeevani_retail_policy_wording.pdf`), now
with a real litigated dispute and a *third* component — an overall
per-illness cap — that neither the current corpus nor
`decoder/extract/room_rent_limit.py`'s schema models yet; and the Kewal
Krishan Aggarwal case is a real, quoted AYUSH sub-limit clause, a field
this project's schema doesn't cover at all yet.

## What was specifically searched for and NOT found

Two structures were deliberately hunted for, since they're the same two
gaps `corpus/README.md` already flags as missing from the policy-document
corpus itself — worth knowing whether litigation would fill that gap even
if the documents don't:

- **Room-category eligibility** (a clause like "entitled to a single
  private AC room," as opposed to a numeric ₹/day or %-of-SI cap). Several
  searches for "single room"/"room category" phrasing returned cases that
  merely *mention* a single room in a billing line item, not a genuine
  category-eligibility dispute — the same pattern HANDOVER.md already
  flagged from the LLM-extractor work (a room-rent field extractor
  mismatching a definitional or incidental mention for the real clause).
  **Still not found, in either archive.**
- **A pure flat-₹/day-only room-rent cap** (no percent-of-SI component at
  all). Direct-phrase searches returned zero matches; broader searches
  surfaced only compound (%+flat) or pure-percent structures. **Still not
  found, in either archive.**

Both remain open gaps regardless of which eval-data source this project
uses — worth treating as a standing "still needed" item, not something
this source happened to miss where the ombudsman archive would have had
it.

## What this doesn't establish yet

- 18 cases, not yet a full 20 — two more, focused on rounding out breadth
  (maternity/day-care, critical-illness-specific sub-limits, both searched
  for but not yet successfully pulled) rather than the two categories
  above (already searched hard and came up empty twice), would close this
  out.
- No systematic date-range/forum-coverage check yet (the ombudsman memo's
  own "skews toward 2012, Chennai/Ahmedabad" gap-finding exercise hasn't
  been repeated here) — this sample spans 2012–2026 and at least 7
  states/UTs (Punjab, Karnataka, Delhi, Maharashtra, West Bengal,
  Chandigarh, Chhattisgarh) plus NCDRC and the Supreme Court, which is a
  good sign, but wasn't tallied systematically.
- The per-judgment "not prohibited by the tribunal" check (Section
  52(1)(q)(iv)'s own carve-out) has been spot-checked, not exhaustively
  verified across every case that would go into a real 20+ case set.

## Verdict

**Usable, and meaningfully stronger on licensing than the archive it
replaces** — a real statutory basis (Section 52(1)(q)(iv)) rather than an
absence-of-prohibition argument, verified against two actual access points
that themselves impose no reuse restriction. Quality and volume both look
at least as good as the ombudsman archive, across every hero-scenario
category this project needs, plus one entirely new sub-limit structure
(the overall per-illness cap in the Nic Ltd. case) worth folding into the
schema regardless of which eval source ships. Recommended next step: two
more cases to round out to 20 (breadth categories, not the two confirmed-
absent structures above), then this can support the ≥15-pair corpus target
and the 30-case annotated eval set (§11/§15) that SPIKE-2's original
ombudsman path was meant to unblock.
