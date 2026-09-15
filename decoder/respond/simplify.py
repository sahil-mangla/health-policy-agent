"""Plain-language rephrasing of an already-resolved claim statement — one
of the three scoped uses docs/HANDOVER.md's M6 status names for chat as a
"secondary affordance" ("why is this flagged" / "show me the clause" /
"simpler language"), never a general-purpose chatbot (§2 rules that out
explicitly: "generic 'chat with your PDF'" is out of scope).

Rephrases ONLY a claim statement decoder.respond.answer_assembly already
built from a resolved claim — never a document span. A quoted clause is
shown verbatim per §8/§9.4 and never rewritten by this or anything else.

Reuses decoder.respond.translate's numeric-fidelity check rather than
inventing a second copy of it: rephrasing that drops or alters a figure is
exactly the same failure mode translation guards against (silently
changing a number while restating already-verified content), just
triggered by "simpler English" instead of "Hindi."
"""

from __future__ import annotations

from decoder.llm.interface import LLMClient
from decoder.respond.translate import check_numeric_fidelity

_SYSTEM_PROMPT = (
    "You rewrite a short factual statement about a health insurance policy "
    "in plain, simple English that an ordinary reader can follow "
    "immediately. Preserve every number, percentage, and currency figure "
    "EXACTLY as written in the original — do not reformat, round, or "
    "alter them in any way. Do not add any fact that is not already in "
    "the original statement. Output ONLY the rewritten statement, nothing "
    "else."
)


def simplify_claim_statement(llm: LLMClient, text: str, model: str = "qwen2.5-coder:7b") -> str:
    """Raises decoder.respond.translate.NumericFidelityError rather than
    returning a rewording that silently dropped or altered a figure —
    callers should treat that as "simplification unavailable for this
    text," e.g. by falling back to the original statement, not by
    retrying blindly."""
    simplified = llm.generate(prompt=text, system=_SYSTEM_PROMPT, model=model)
    check_numeric_fidelity(text, simplified)
    return simplified
