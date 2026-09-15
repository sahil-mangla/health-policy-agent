"""Real DocumentClassifier implementation — docs/HANDOVER.md §9.1.

"Classify on intake before anything else ... Silently analysing a motor
policy as health is a catastrophic first impression." Deterministic,
keyword-based (no LLM call needed for this — a wrong document type is a
structural mismatch, not a nuanced judgment call). Tuned against the actual
starter corpus (corpus/README.md); expand the keyword sets as more insurers'
documents are added.

Not implemented with confidence: HOSPITAL_BILL and EXPIRED_POLICY detection.
HOSPITAL_BILL has a keyword heuristic below but is untested — the starter
corpus contains no real hospital bills. EXPIRED_POLICY is left to
decoder.extract (§9.2's actual policy-period extraction), since reliably
parsing a policy period needs more than a first-pass keyword scan and
guessing here risks exactly the false confidence §9.2 warns against.
"""

from __future__ import annotations

import re
from datetime import date

from decoder.intake.interfaces import DocumentType
from decoder.intake.pdf_extract import extract_first_page_text

_CIS_MARKERS = (
    "customer information sheet",
    "know your policy",
)

_HEALTH_KEYWORDS = (
    "health insurance",
    "hospitalisation",
    "hospitalization",
    "room rent",
    "sum insured",
    "pre-existing disease",
    "medical expenses",
    "ayush",
    "cashless",
)

_MOTOR_KEYWORDS = (
    "own damage",
    "third party liability",
    "insured vehicle",
    "registration number",
    "idv",
    "motor insurance",
)

_LIFE_KEYWORDS = (
    "sum assured",
    "maturity benefit",
    "death benefit",
    "life insured",
    "policy bond",
)

_HOSPITAL_BILL_KEYWORDS = (
    "itemized bill",
    "discharge summary",
    "invoice no",
    "bill no",
    "amount payable",
)

_MIN_READABLE_CHARS = 50
_MIN_CATEGORY_SCORE = 1


def _score(text: str, keywords: tuple[str, ...]) -> int:
    return sum(text.count(k) for k in keywords)


class HeuristicDocumentClassifier:
    def classify(self, doc_id: str, raw_bytes: bytes) -> DocumentType:
        raw_text = extract_first_page_text(raw_bytes, max_pages=2)
        text = raw_text.lower()

        if len(raw_text.strip()) < _MIN_READABLE_CHARS:
            return DocumentType.UNREADABLE_SCAN

        if any(marker in text for marker in _CIS_MARKERS):
            return DocumentType.CUSTOMER_INFORMATION_SHEET

        scores = {
            DocumentType.HEALTH_POLICY_WORDING: _score(text, _HEALTH_KEYWORDS),
            DocumentType.MOTOR_OR_LIFE_POLICY: max(
                _score(text, _MOTOR_KEYWORDS), _score(text, _LIFE_KEYWORDS)
            ),
            DocumentType.HOSPITAL_BILL: _score(text, _HOSPITAL_BILL_KEYWORDS),
        }
        best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
        if best_score < _MIN_CATEGORY_SCORE:
            return DocumentType.NOT_INSURANCE_DOCUMENT
        return best_type


_POLICY_PERIOD_RE = re.compile(
    r"policy period[^\d]{0,40}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})[^\d]{1,10}"
    r"(?:to|-)[^\d]{0,10}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)


def find_policy_period_dates_in_text(text: str) -> tuple[str, str] | None:
    """Best-effort regex scan for a "Policy Period <start> to <end>" pattern,
    returning the raw matched date strings (not parsed/validated) or None if
    no such pattern is found. Callers needing an actual expiry determination
    (§9.2) should treat a None result as INSUFFICIENT_EVIDENCE, not as
    "not expired" — this function only ever confirms a pattern was found, it
    never confirms one's absence means anything.

    Split out from find_policy_period_dates() so the regex itself is
    testable against plain strings, without needing a PDF fixture for
    every case — is_policy_expired() below is the same split for the same
    reason."""
    match = _POLICY_PERIOD_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2)


def find_policy_period_dates(raw_bytes: bytes) -> tuple[str, str] | None:
    text = extract_first_page_text(raw_bytes, max_pages=3)
    return find_policy_period_dates_in_text(text)


def _parse_indian_date(raw: str) -> date | None:
    """DD/MM/YYYY or DD-MM-YYYY, the convention _POLICY_PERIOD_RE's own
    dates are always written in. Returns None — never a guess — for
    anything it can't parse confidently: an out-of-range day/month, or a
    2-digit year, which is genuinely ambiguous (is "10" 1910 or 2010?) and
    not worth resolving by assumption for a check whose only job is
    deciding whether to block analysis."""
    for separator in ("/", "-"):
        parts = raw.split(separator)
        if len(parts) != 3:
            continue
        day_s, month_s, year_s = parts
        if len(year_s) != 4:
            return None
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError:
            return None
    return None


def is_expired_from_text(text: str, as_of: date | None = None) -> bool | None:
    """§9.2: "If the period has lapsed ... say so before any analysis."

    Returns True only when a policy-period end date was found AND parsed
    AND is unambiguously before `as_of` (default: today). Returns None —
    never a guess — when the period wasn't found or couldn't be parsed;
    the starter corpus's specimen wordings are the common real case for
    this (docs/HANDOVER.md §9.2's own test: no customer-specific dates
    exist in a downloadable specimen, only in a Schedule this system
    doesn't have). A None result must never be treated as "not expired" —
    it means this check could not be performed, which is a different fact.
    """
    period = find_policy_period_dates_in_text(text)
    if period is None:
        return None
    _, end_raw = period
    end_date = _parse_indian_date(end_raw)
    if end_date is None:
        return None
    return end_date < (as_of or date.today())


def is_policy_expired(raw_bytes: bytes, as_of: date | None = None) -> bool | None:
    text = extract_first_page_text(raw_bytes, max_pages=3)
    return is_expired_from_text(text, as_of)
