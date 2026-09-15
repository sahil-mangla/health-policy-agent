"""User-facing strings, kept separate from the logic that chooses them —
docs/HANDOVER.md §9.4.

"Keep all user-facing strings and generated explanations separable from
logic so Hindi output can be added without a rewrite." Everything a reader
sees that this codebase *generates* lives here; the modules that decide
what to say import these rather than phrasing anything inline.

Quoted clause text is deliberately NOT here and never should be: §9.4
forbids translating a quoted span ("show the original and the translation
together"), so span text stays in the Span it came from and is rendered
verbatim beside these strings, never folded into them.
"""

from __future__ import annotations

from decoder.intake.interfaces import DocumentType
from decoder.schema import SupportState

# §8's UI mapping table, verbatim. Never paraphrase these in a caller —
# the label IS the contract with the reader about how much the system is
# claiming, and §3 forbids inventing synonyms for support states.
SUPPORT_STATE_LABELS: dict[SupportState, str] = {
    SupportState.WELL_SUPPORTED: "Stated in your policy",
    SupportState.NEEDS_CONFIRMATION: "Verify before proceeding",
    SupportState.NEEDS_INFORMATION: "Depends on information we don't have",
    SupportState.INSUFFICIENT_EVIDENCE: "Not found in these documents",
    SupportState.CONFLICTING: "Your documents disagree",
}

# Question phrasing per state (§2 F3: "specific, answerable questions for
# the insurer, derived from the gaps the analysis actually found"). The
# templates are phrasing; decoder.respond.question_generation supplies the
# specifics from the real claim, so these never become a generic template
# list divorced from what was actually found. WELL_SUPPORTED has no entry
# on purpose — a supported claim generates no question.
QUESTION_TEMPLATES: dict[SupportState, str] = {
    SupportState.NEEDS_CONFIRMATION: "Confirm with your insurer: {claim}",
    SupportState.NEEDS_INFORMATION: (
        "We need this from you before this can be answered — {input_name} ({input_description})"
    ),
    SupportState.INSUFFICIENT_EVIDENCE: (
        "These documents do not state this. Ask your insurer: {claim}"
    ),
    SupportState.CONFLICTING: (
        "Your documents disagree on this. Ask your insurer which one governs: {claim}"
    ),
}

# Shown when decomposition produced nothing checkable. §8: "Never refuse
# outright. Every state produces an answer" — so this is still an answer
# about what happened, not an error message.
NO_CHECKABLE_CLAIMS_TEXT = (
    "Nothing in these documents could be turned into a statement we are able to "
    "check against them for this situation."
)

EVIDENCE_PREFIX_SUPPORTS = "Supported by"
EVIDENCE_PREFIX_CONTRADICTS = "Contradicted by"

# §9.1: "Refuse politely and specifically for the wrong type." Specific
# per type — a generic "unsupported document" message is what makes a
# wrong upload feel like a broken product rather than a caught mistake.
UNUSABLE_DOCUMENT_MESSAGES: dict[DocumentType, str] = {
    DocumentType.MOTOR_OR_LIFE_POLICY: (
        "This looks like a motor or life insurance policy. This tool only reads "
        "health insurance policies."
    ),
    DocumentType.HOSPITAL_BILL: (
        "This looks like a hospital bill, not an insurance policy. Please upload the "
        "policy wording or the Customer Information Sheet instead."
    ),
    DocumentType.UNREADABLE_SCAN: (
        "No readable text could be extracted from this file — it may be a scanned "
        "image. Please upload a text-based PDF of the policy."
    ),
    DocumentType.EXPIRED_POLICY: (
        "This policy appears to have expired. Analysing a lapsed policy would be "
        "misleading, so please upload the current one."
    ),
    DocumentType.NOT_INSURANCE_DOCUMENT: (
        "This does not appear to be an insurance document. Please upload your health "
        "policy wording or Customer Information Sheet."
    ),
}
