# SPIKE-1 — IRDAI position on proportionate deduction

**Status: PARTIALLY RESOLVED (as of 2026-09-14)**

This memo exists because the Engineering Handover spec (`docs/HANDOVER.md` §4)
forbids encoding any regulatory rule about proportionate deduction until this
spike is resolved and dated. It is not fully resolved — see "Open question"
below — and the code must not treat it as closed.

## Primary sources read in full this session

### 1. IRDAI/HLT/REG/CIR/151/06/2020 — 11 June 2020

*"Modified Guidelines on Product filing in Health Insurance Business – Norms
on Proportionate Deductions."* Amends Clause (4), Chapter II of
IRDA/HLT/REG/CIR/150/07/2016 (29 July 2016).

Verbatim key provisions:

> 3. Where as part of product design insurers propose proportionate deduction
> of the 'associated medical expenses' when a policyholder chooses a higher
> room category than the category that is eligible as per terms and
> conditions of the policy, insurers shall define 'associate medical
> expenses' in the terms and conditions of policy contract.
>
> 4. The following expenses are not allowed to be part of the definition of
> 'associate medical expenses'.
>    a. Cost of pharmacy and consumables;
>    b. Cost of implants and medical devices
>    c. Cost of diagnostics
>
> 5. Insurers shall not recover any expenses towards proportionate deductions
> other than the defined 'associate medical expenses' while processing claims.
>
> 6. Insurers shall ensure that proportionate deductions are not applied in
> respect of the hospitals which do not follow differential billing or for
> those expenses in respect of which differential billing is not adopted
> based on the room category. This shall be clearly specified in the policy
> terms and conditions.
>
> 7. Insurers are not permitted to apply proportionate deduction for 'ICU
> charges' as different categories of ICU are not there.
>
> 8. The provisions of these guidelines shall be applicable to the Health
> Insurance products filed ... on or after 01st October, 2020. All policy
> contracts of the existing health insurance products that are not in
> compliance with these guidelines shall be modified as and when they are due
> for renewal from 01st April, 2021 onwards.

**What this means, precisely:** the regulation does **not** hand down a
standard list of expense heads that *are* subject to proportionate deduction.
It only fixes a **floor of mandatory exclusions** — pharmacy/consumables,
implants/medical devices, diagnostics, and (via a separate clause) ICU
charges can never be part of "associated medical expenses," no matter what an
individual insurer's policy wording says. Room rent itself, doctor/surgeon
fees, nursing charges, OT charges, and everything else are left to each
insurer to define in their own policy T&C. There is no regulator-supplied
"typical" or "market-standard" included list.

**Effective dates:** new product filings from 1 Oct 2020; existing products
brought into compliance by renewal, from 1 Apr 2021 onward. Given how long ago
this took effect, essentially all in-force retail health policies today should
already reflect it — but that is an inference, not something the circular
itself states as a universal guarantee.

### 2. IRDAI/HLT/CIR/PRO/84/5/2024 — Master Circular on Health Insurance
Business, 29 May 2024 (read in full, all 17 pages)

This is the current consolidated master circular for health insurance
business generally. It covers CIS format, free-look period, cancellation,
nomination, grace period, renewal, migration/portability, the 60-month
moratorium, No Claim Bonus, cashless/discharge TATs, claims settlement,
grievance redressal, and Ombudsman award enforcement.

**It does not mention proportionate deduction, room rent, or "associated
medical expenses" anywhere.** Its final clause states: *"This Circular
supersedes all the Guidelines/Circulars listed in Annexure-6."*

## Open question — blocks full sign-off

Annexure-6 (the actual repeal list) was **not accessible** in this research
pass — only the 17-page body of the master circular was retrieved. It is
therefore unknown whether IRDAI/HLT/REG/CIR/151/06/2020 is among the
circulars repealed by the 2024 consolidation, and if so, whether its
substance (the exclusion floor above) was:
- carried forward unchanged into current product-filing requirements,
- superseded by some other, not-yet-located provision, or
- genuinely lapsed with no replacement (unlikely for a substantive consumer
  protection rule, but not ruled out without checking).

**Do not treat this circular's rules as certainly still in force** until
Annexure-6 (or a subsequent circular explicitly addressing proportionate
deduction) has been checked. This is the single concrete follow-up that would
let this spike move from `PARTIALLY RESOLVED` to `RESOLVED`.

## Secondary-source contradiction (recorded because it is itself instructive)

Several consumer-facing web sources were checked before the primary documents
were located, and they **contradict each other and the primary text**:

- One source claims proportionate deduction now applies only to "room rent,
  doctor fees, surgery charges, nursing charges, and other room-linked
  associated expenses," with ICU/pharmacy/implants/diagnostics excluded.
- Another claims proportionate deduction applies **only to room rent itself**,
  with doctor/surgeon/nursing/OT/investigation/pharmacy charges *all*
  excluded as "category-agnostic."

Neither matches IRDAI/HLT/REG/CIR/151/06/2020, which only fixes the four-item
exclusion floor above and otherwise leaves the included list to each
insurer's policy wording. This is a real-world instance of exactly the
problem this whole product exists to solve: secondary paraphrase drifts from
the primary source, and a system that trusted "how this usually works" over
the actual document would get it wrong in either direction depending on which
blog it echoed.

## Implication for the codebase

Consistent with `docs/HANDOVER.md` §4 and §6:

- **Never hardcode a default included/excluded list of expense heads**, other
  than the four confirmed regulatory floor exclusions above (pharmacy/
  consumables, implants/medical devices, diagnostics, ICU charges), which may
  be encoded as a hard override — no policy can lawfully include them in
  "associated medical expenses" regardless of what its wording says.
- Per-policy extraction (`decoder/extract/`) must read each policy's own
  definition of "associated medical expenses" from its actual wording. If a
  policy is silent on this, that is `INSUFFICIENT_EVIDENCE`, not a filled-in
  market-typical default — this is already the handover spec's explicit
  instruction (§4, point 2) and this research confirms there is no regulatory
  default to fall back on either.
- No finding here addresses whether the position differs by product type or
  for policies with no room-rent limit at all — treat that as unresolved too.
