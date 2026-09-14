# Corpus

Real, publicly downloadable Indian health insurance documents used to unblock
M1 (intake/extraction) development. See `docs/HANDOVER.md` §11 for the
corpus strategy — this is a starter set, not the full ≥15-pair target.

## Provenance

All files in `raw/hdfc_ergo/` were downloaded directly from HDFC ERGO's
public, no-login-required document hub:
- Policy wordings: https://www.hdfcergo.com/download/policy-wordings
- CIS: https://www.hdfcergo.com/download/cis/health

Downloaded 2026-09-14. These are documents insurers are required by IRDAI to
publish openly for prospective customers to review before purchase — they
are consumer disclosure documents, not confidential materials. Each file's
UIN (Unique Identification Number) is printed on every page of the source
PDF for traceability back to the insurer's own regulatory filing.

## Contents

| Product | Policy Wording | CIS | Notes |
|---|---|---|---|
| Easy Health | `easy_health_policy_wording.pdf` | `easy_health_cis.pdf` | Base retail plan. Confirmed (spot-read 2026-09-14): **no explicit room-rent sub-limit clause** — Section B covers "Hospital room rent or boarding" without a stated ₹/day or %-of-SI cap. Useful as the hero scenario's "no cap" test case (§4 DoD). |
| Optima Restore | `optima_restore_policy_wording.pdf` | `optima_restore_cis.pdf` | Flagship "Restore" product line. Room-rent structure not yet reviewed — check during M1. |
| Arogya Sanjeevani (Retail) | `arogya_sanjeevani_retail_policy_wording.pdf` | `arogya_sanjeevani_retail_cis.pdf` | IRDAI's standardized product template across all insurers — by regulatory design this has a fixed room-rent/ICU-charge sub-limit (typically 1%/2% of SI per day). Not yet verified against this specific copy — check during M1. Useful as a cross-insurer regulatory-baseline comparison case. |

## Still needed (per the roadmap)

- CIS↔policy-wording pairs from 2-3 more insurers for diversity (Niva Bupa
  and Bajaj Allianz confirmed as clean no-login sources — see research notes
  from 2026-09-14).
- A product with an explicit flat ₹/day room-rent cap and one with a %-of-SI
  cap, to cover all three hero-scenario bases (§4: flat amount, % of SI,
  room category, none).
- The adversarial cases (§11): CIS contradicting wording, a term buried in
  an endorsement, etc. — none of these six documents were chosen for that
  yet.
- SPIKE-2's ombudsman award corpus — entirely separate, not started.
