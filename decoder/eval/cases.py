"""The annotated eval set — docs/HANDOVER.md §11/§12, M0's DoD.

Grading checks a SPECIFIC matching claim's state (decoder.eval.runner.
_find_claim, matched by topic keyword), not `answer.overall_state`, for
every case except `correctly_abstain` ones — because
`decoder.extract.room_rent_limit.analyze_room_rent` runs unconditionally
alongside every question (mirroring web/app.py), so a document with no
room-rent cap at all (Easy Health, Star Comprehensive) always contributes
an INSUFFICIENT_EVIDENCE claim to the answer regardless of what else was
asked — that would make `overall_state` a false failure signal for an
unrelated, perfectly-answered question on the same document. This is a
real, worth-knowing property of the live system's behavior, not a defect
introduced here.

Room-rent cases are graded deterministically (decoder.extract.
room_rent_limit is pure code, no LLM call). Co-payment/waiting-period cases
depend on a live local model's drafted wording containing the expected
keyword — verified by hand against the real corpus and a live model before
being written here, per this project's own standing practice
(docs/HANDOVER.md's M1/M3 status notes), but inherently less deterministic
than the room-rent cases.
"""

from __future__ import annotations

from decoder.eval.schema import EvalCase, ExpectedOutcome
from decoder.schema import SupportState

_WS = SupportState.WELL_SUPPORTED
_NI = SupportState.NEEDS_INFORMATION
_IE = SupportState.INSUFFICIENT_EVIDENCE

CASES: tuple[EvalCase, ...] = (
    # --- Room-rent: compound %-of-SI-with-flat-cap (Arogya Sanjeevani) ---
    # Numbers inspired by Niraj Kajaria v. United India Insurance (W.B.
    # State Commission, 2017 — docs/corpus/ncdrc-feasibility.md): a real
    # entitled-vs-actual room rent mismatch, run here against the real
    # Arogya Sanjeevani compound clause already in this corpus (2% of SI,
    # max ₹5,000/day).
    EvalCase(
        id="room_rent_compound_exceeds",
        doc_id="arogya_sanjeevani",
        situation="My hospital room costs ₹8,000 per day and my sum insured is ₹1,00,000. "
        "Is my room rent within my policy's limit?",
        room_tariff_per_day=8000.0,
        sum_insured=100_000.0,
        expected=(
            ExpectedOutcome(concerns="room-rent eligibility", state=_WS),
            ExpectedOutcome(concerns="exceeds your eligible room-rent", state=_WS),
        ),
        note="2% of ₹1L = ₹2,000/day binds (below the ₹5,000 flat cap) — the exact "
        "compound-clause trap docs/HANDOVER.md §12 documents as this project's own "
        "headline confident-and-wrong catch.",
    ),
    EvalCase(
        id="room_rent_compound_within",
        doc_id="arogya_sanjeevani",
        situation="My hospital room costs ₹1,500 per day and my sum insured is ₹5,00,000. "
        "Is my room rent within my policy's limit?",
        room_tariff_per_day=1500.0,
        sum_insured=500_000.0,
        expected=(ExpectedOutcome(concerns="within your eligible room-rent", state=_WS),),
        note="2% of ₹5L = ₹10,000, but the ₹5,000 flat cap binds first — tariff is well "
        "within it either way.",
    ),
    # --- Room-rent: pure %-of-SI, no flat cap (Bajaj Health Guard Silver) ---
    EvalCase(
        id="room_rent_pure_percent_exceeds",
        doc_id="health_guard_silver",
        situation="My room costs ₹8,000 per day and my sum insured is ₹5,00,000. "
        "Does this exceed my room-rent entitlement?",
        room_tariff_per_day=8000.0,
        sum_insured=500_000.0,
        expected=(
            ExpectedOutcome(concerns="room-rent eligibility", state=_WS),
            ExpectedOutcome(concerns="exceeds your eligible room-rent", state=_WS),
        ),
        note="1% of ₹5L = ₹5,000/day, no flat cap component at all — corpus/README.md's "
        "verified Bajaj Health Guard Silver structure.",
    ),
    # --- Room-rent: no cap stated anywhere (two independent documents) ---
    EvalCase(
        id="room_rent_no_cap_easy_health",
        doc_id="easy_health",
        situation="What is my room rent limit per day?",
        expected=(ExpectedOutcome(concerns="room-rent eligibility", state=_IE),),
        correctly_abstain=True,
        note="Easy Health states no numeric room-rent restriction at all "
        "(corpus/README.md) — must read as INSUFFICIENT_EVIDENCE, never a fabricated "
        "'no limit' confirmation (§4/§6's own warning against inventing that "
        "distinction).",
    ),
    EvalCase(
        id="room_rent_no_cap_star_comprehensive",
        doc_id="star_comprehensive",
        situation="What is my room rent limit per day?",
        expected=(ExpectedOutcome(concerns="room-rent eligibility", state=_IE),),
        correctly_abstain=True,
        note="A second, independently-sourced no-cap document (corpus/README.md) — "
        "the same abstention must hold across insurers, not just one document.",
    ),
    # --- Room-rent: percent-of-SI stated, but SI not supplied ---
    EvalCase(
        id="room_rent_needs_sum_insured_arogya",
        doc_id="arogya_sanjeevani",
        situation="What is my room rent limit per day?",
        expected=(ExpectedOutcome(concerns="room-rent eligibility", state=_NI),),
        correctly_abstain=True,
        note="The %-of-SI component can't become a ₹ figure without a real sum "
        "insured, which is never in the generic wording (decoder.extract."
        "room_rent_limit's own module docstring) — must ask, never assume a "
        "market-typical SI.",
    ),
    EvalCase(
        id="room_rent_needs_sum_insured_bajaj",
        doc_id="health_guard_silver",
        situation="What is my room rent limit per day?",
        expected=(ExpectedOutcome(concerns="room-rent eligibility", state=_NI),),
        correctly_abstain=True,
        note="Same abstention on the pure-percent structure, confirming it isn't "
        "specific to the compound-clause document.",
    ),
    # --- Sum insured / policy period: confirmed absent from every document ---
    # in the corpus this session (regex-scanned directly against all 4 PDFs,
    # zero matches — see the room-rent session's own research). These
    # exercise the plain drafter/decompose/entailment path, not the
    # room-rent module, so the abstention has to come from real entailment
    # finding no supporting span, not from a modelled RequiredInput.
    EvalCase(
        id="sum_insured_not_in_wording",
        doc_id="arogya_sanjeevani",
        situation="What is my sum insured under this policy?",
        correctly_abstain=True,
        note="Sum insured is chosen at purchase and lives only on the personal "
        "Schedule — confirmed absent from every document in this corpus. The system "
        "must not guess a market-typical figure.",
    ),
    EvalCase(
        id="policy_period_not_in_wording",
        doc_id="easy_health",
        situation="What is my policy period — when does my coverage start and end?",
        correctly_abstain=True,
        note="Same structural absence as sum insured, confirmed by regex scan "
        "(decoder.intake.classify's own §9.2 status note: 'specimen wordings state "
        "no customer-specific dates at all, only a personal Schedule does').",
    ),
    # --- Room-category eligibility: confirmed absent from every document ---
    EvalCase(
        id="room_category_not_stated",
        doc_id="optima_restore_cis",
        situation="Am I entitled to a single private AC room, or a shared room?",
        correctly_abstain=True,
        note="docs/HANDOVER.md's M1 status: no document in the starter corpus states "
        "an explicit room-category eligibility clause — confirmed again during the "
        "NCDRC sampling pass (docs/corpus/ncdrc-feasibility.md), where this structure "
        "was searched for and not found either. A real, standing gap, not specific to "
        "this document.",
    ),
    # --- Co-payment: real, verified clauses (LLM-drafted, live-model-dependent) ---
    # Numbers/structure inspired by Star Health v. Mohinder Pal (Punjab
    # State Commission — a real two-tier PED/general co-payment clause) and
    # National Insurance v. Anil Kumar Jain (a real 10% co-payment
    # deduction) — run here against this project's own verified real
    # clauses, not the judgments' documents.
    EvalCase(
        id="copayment_arogya_sanjeevani",
        doc_id="arogya_sanjeevani",
        situation="What co-payment percentage applies to my claim?",
        expected=(ExpectedOutcome(concerns="co-payment", state=_WS),),
        note="Real verified clause: 'a Co-payment of 5%...' "
        "(tests/extract/test_llm_extractor.py's own confirmed extraction). "
        "REAL FINDING (2026-09-15, live run): this case genuinely fails "
        "intermittently — the drafter has been observed characterizing the "
        "correctly-grounded 5% figure as 'the policy has a 5% discount' "
        "rather than a co-payment. The number and the cited span are both "
        "right; the label is backwards (a co-payment is what the "
        "policyholder pays, not a price reduction). Left failing "
        "deliberately rather than loosened to accept 'discount' — this is a "
        "real drafting-quality gap worth its own investigation, not "
        "something the eval set should paper over.",
    ),
    EvalCase(
        id="copayment_star_comprehensive_senior",
        doc_id="star_comprehensive_cis",
        situation="I am 65 years old. What co-payment applies to my claim?",
        expected=(ExpectedOutcome(concerns="co-payment", state=_WS),),
        note="Real verified clause: 10% senior-citizen co-payment for entry age 61+ "
        "(tests/extract/test_llm_extractor.py).",
    ),
    # --- Waiting period: real, verified clauses ---
    # `continuity_date` is supplied on every one of these: §9.3 (decoder.
    # verify.continuity_requirement) attaches it as a RequiredInput to ANY
    # claim whose text discusses a waiting period, regardless of document —
    # without it, resolve() correctly downgrades to NEEDS_INFORMATION
    # rather than WELL_SUPPORTED (verified by hand 2026-09-15: an earlier
    # version of these cases omitted it and got exactly that downgrade,
    # which is the pipeline behaving correctly, not a bug — the eval case
    # was wrong, not the system).
    EvalCase(
        id="waiting_period_ped_arogya",
        doc_id="arogya_sanjeevani",
        situation="How long is the waiting period for pre-existing diseases?",
        provided_inputs={"continuity_date": "2018-01-01"},
        expected=(ExpectedOutcome(concerns="waiting period", state=_WS),),
        note="Real verified clause: 36-month PED waiting period "
        "(tests/extract/test_llm_extractor.py).",
    ),
    EvalCase(
        id="waiting_period_initial_star",
        doc_id="star_comprehensive",
        situation="What is the initial waiting period before any claim is payable?",
        provided_inputs={"continuity_date": "2018-01-01"},
        expected=(ExpectedOutcome(concerns="waiting period", state=_WS),),
        note="Real verified clause: 30-day initial waiting period "
        "(tests/extract/test_llm_extractor.py).",
    ),
    EvalCase(
        id="waiting_period_initial_optima",
        doc_id="optima_restore_cis",
        situation="What is the initial waiting period before any claim is payable?",
        provided_inputs={"continuity_date": "2018-01-01"},
        expected=(ExpectedOutcome(concerns="waiting period", state=_WS),),
        note="A second, independently-phrased 30-day initial waiting period "
        "(tests/extract/test_llm_extractor.py) — confirms the drafter isn't overfit "
        "to one document's wording.",
    ),
    EvalCase(
        id="waiting_period_specific_illness_easy_health",
        doc_id="easy_health_cis",
        situation="How long is the waiting period for specific listed illnesses or procedures?",
        provided_inputs={"continuity_date": "2018-01-01"},
        expected=(ExpectedOutcome(concerns="waiting period", state=_WS),),
        note="Real verified clause: 24-month specific-illness waiting period "
        "(tests/extract/test_llm_extractor.py) — from a two-column PDF layout that "
        "interleaves the clause's text, a real segmentation stress case.",
    ),
    # --- AYUSH sub-limit: confirmed absent from this project's own schema ---
    # (not necessarily the documents — Kewal Krishan Aggarwal v. New India
    # Assurance, docs/corpus/ncdrc-feasibility.md, shows this IS a real,
    # litigated clause type; this project simply has no extractor field for
    # it yet, so it must abstain rather than let the drafter free-hand a
    # number nothing verifies).
    EvalCase(
        id="ayush_sublimit_not_modelled",
        doc_id="arogya_sanjeevani",
        situation="What is the sub-limit for AYUSH (Ayurvedic/Homeopathic/Unani) "
        "treatment under my policy?",
        correctly_abstain=True,
        note="A real field type (AYUSH sub-limits are litigated — Kewal Krishan "
        "Aggarwal v. New India Assurance, Punjab State Commission, 2020 — see "
        "docs/corpus/ncdrc-feasibility.md) that this project's schema doesn't cover "
        "yet; the system must not fabricate a percentage nothing has verified.",
    ),
)
