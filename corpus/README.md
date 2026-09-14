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

### `raw/hdfc_ergo/` — HDFC ERGO
Downloaded from https://www.hdfcergo.com/download/policy-wordings and
`/download/cis/health` (no login).

| Product | Policy Wording | CIS | Notes |
|---|---|---|---|
| Easy Health | `easy_health_policy_wording.pdf` | `easy_health_cis.pdf` | Base retail plan. Confirmed (spot-read 2026-09-14): **no explicit room-rent sub-limit clause** — Section B covers "Hospital room rent or boarding" without a stated ₹/day or %-of-SI cap. Useful as the hero scenario's "no cap" test case (§4 DoD). |
| Optima Restore | `optima_restore_policy_wording.pdf` | `optima_restore_cis.pdf` | Flagship "Restore" product line. Room-rent structure not yet reviewed — check during M1. |
| Arogya Sanjeevani (Retail) | `arogya_sanjeevani_retail_policy_wording.pdf` | `arogya_sanjeevani_retail_cis.pdf` | IRDAI's standardized product template across all insurers. **Verified (regex extractor, 2026-09-14): 2% of SI per day, capped at ₹5,000/day** — a compound %-of-SI-with-flat-cap structure. See `decoder/extract/regex_extractor.py`'s module docstring for the extraction details. |

### `raw/star_health/` — Star Health
Downloaded from Star's CloudFront CDN (`d28c6jni2fmamz.cloudfront.net`) —
their own site (starhealth.in) blocks automated fetches, but the same PDFs
are served unprotected from this CDN, discoverable via search indexing.

| Product | Policy Wording | CIS | Notes |
|---|---|---|---|
| Star Comprehensive | `star_comprehensive_policy_wording.pdf` | `star_comprehensive_cis.pdf` | **Verified (regex extractor + manual span search, 2026-09-14): no numeric or room-category room-rent restriction found anywhere in the document** — a second, independently-sourced "no cap" example alongside HDFC ERGO's Easy Health. |

### `raw/bajaj_allianz/` — Bajaj Allianz
Downloaded from https://www.bajajgeneralinsurance.com/health-insurance-plans/health-insurance-documents.html
(no login).

| Product | Policy Wording + CIS | Notes |
|---|---|---|
| Health Guard Silver | `health_guard_silver_pw_cis.pdf` (combined file) | **Verified (regex extractor, 2026-09-14): 1% of SI per day**, no flat-amount cap component — a simpler, pure %-of-SI structure distinct from Arogya Sanjeevani's compound percent+flat-cap formula. |

## Still needed (per the roadmap)

- **Room-category eligibility** (e.g. "single private AC room" phrasing) —
  still the one hero-scenario basis (§4) with no real example in hand.
  ICICI Lombard's "Elevate" product is the best known candidate (confirmed
  via public product descriptions, not yet pulled — both `icicilombard.com`
  and its CDN return 403/Access-Denied to automated fetch; needs a manual
  browser download) — see research notes, 2026-09-14.
- **Niva Bupa**: confirmed clean product list (ReAssure 2.0, Health
  Companion, Health Premia, Senior First) but the download host
  (`nivabupa.com`) sits behind a bot-protection WAF that blocked both a
  default and a browser-spoofed `curl` — needs a real browser session.
- **Care Health**: policy wordings reachable via `cms.careinsurance.com`
  and a third-party mirror, but CIS documents appear to sit behind a login
  portal (`confirm.careinsurance.com`) — not resolved.
- A flat-₹/day-only room-rent cap (no percent component) — none of the six
  documents currently in hand have this exact structure; all are either
  compound (Arogya Sanjeevani), pure-percent (Bajaj Health Guard Silver),
  or no-cap (Easy Health, Star Comprehensive).
- The adversarial cases (§11): CIS contradicting wording, a term buried in
  an endorsement, etc. — none of these documents were chosen for that yet.
- SPIKE-2's ombudsman award corpus — see
  `docs/corpus/ombudsman-feasibility.md`. A real archive has been found and
  one sample book pulled into `raw/ombudsman_awards/` (**not yet confirmed
  clear to redistribute — no license found on the source site; see that
  memo before committing more of this archive or relying on it for eval
  data**).
