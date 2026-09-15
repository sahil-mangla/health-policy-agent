"""doc_id -> corpus file registry for the eval set.

Deliberately separate from web/corpus_library.py rather than importing it:
docs/HANDOVER.md §5's module boundaries list web/ as depending on decoder/,
never the other way — a demo's document picker is not a decoder concern,
but decoder/eval genuinely needs to load the same real files, so this is a
small, independent registry using the same doc_ids for consistency rather
than a shared import.
"""

from __future__ import annotations

from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "raw"

# Same doc_ids as web/corpus_library.py's CATALOGUE, kept in sync by
# convention (both ultimately name the same five files) rather than a
# shared import — see this module's docstring.
DOC_PATHS: dict[str, str] = {
    "arogya_sanjeevani": "hdfc_ergo/arogya_sanjeevani_retail_policy_wording.pdf",
    "arogya_sanjeevani_cis": "hdfc_ergo/arogya_sanjeevani_retail_cis.pdf",
    "easy_health": "hdfc_ergo/easy_health_policy_wording.pdf",
    "easy_health_cis": "hdfc_ergo/easy_health_cis.pdf",
    "optima_restore_cis": "hdfc_ergo/optima_restore_cis.pdf",
    "star_comprehensive": "star_health/star_comprehensive_policy_wording.pdf",
    "star_comprehensive_cis": "star_health/star_comprehensive_cis.pdf",
    "health_guard_silver": "bajaj_allianz/health_guard_silver_pw_cis.pdf",
}


def raw_bytes(doc_id: str) -> bytes:
    return (CORPUS_DIR / DOC_PATHS[doc_id]).read_bytes()
