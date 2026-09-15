"""The bundled corpus, exposed as pickable documents for the analysis view.

Lives outside `decoder/` on purpose: §5's module boundaries list the
decoder packages, and a demo's document catalogue is not one of them.

Documents are loaded and segmented once per process and cached — segmenting
a 350-span policy wording takes seconds, and re-doing it per request would
dominate the latency the user actually waits on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from decoder.orchestrator import LoadedDocument, load_document

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus" / "raw"


@dataclass(frozen=True)
class CatalogueEntry:
    doc_id: str
    insurer: str
    product: str
    relative_path: str
    # What makes this document worth demoing — surfaced in the picker so
    # the reader knows which room-rent structure they are looking at.
    note: str

    @property
    def path(self) -> Path:
        return CORPUS_DIR / self.relative_path


# Structures deliberately span the hero scenario's bases (§4): a compound
# %-of-SI-with-flat-cap, a pure %-of-SI, and two documents with no
# room-rent cap at all. corpus/README.md is the source for each claim here.
CATALOGUE: tuple[CatalogueEntry, ...] = (
    CatalogueEntry(
        doc_id="arogya_sanjeevani",
        insurer="HDFC ERGO",
        product="Arogya Sanjeevani",
        relative_path="hdfc_ergo/arogya_sanjeevani_retail_policy_wording.pdf",
        note="Room rent capped at 2% of sum insured, max ₹5,000/day. 5% co-payment.",
    ),
    CatalogueEntry(
        doc_id="easy_health",
        insurer="HDFC ERGO",
        product="Easy Health",
        relative_path="hdfc_ergo/easy_health_policy_wording.pdf",
        note="No room-rent cap stated anywhere in the document.",
    ),
    CatalogueEntry(
        doc_id="optima_restore",
        insurer="HDFC ERGO",
        product="Optima Restore",
        relative_path="hdfc_ergo/optima_restore_policy_wording.pdf",
        note="Flagship retail plan. 30-day initial waiting period.",
    ),
    CatalogueEntry(
        doc_id="star_comprehensive",
        insurer="Star Health",
        product="Star Comprehensive",
        relative_path="star_health/star_comprehensive_policy_wording.pdf",
        note="No room-rent restriction. 10% co-payment for entry age 61+.",
    ),
    CatalogueEntry(
        doc_id="health_guard_silver",
        insurer="Bajaj Allianz",
        product="Health Guard Silver",
        relative_path="bajaj_allianz/health_guard_silver_pw_cis.pdf",
        note="Room rent capped at 1% of sum insured per day, no flat cap.",
    ),
)

_BY_ID = {entry.doc_id: entry for entry in CATALOGUE}
_cache: dict[str, LoadedDocument] = {}
_cache_lock = Lock()


def available() -> tuple[CatalogueEntry, ...]:
    """Only entries whose file is actually present — the corpus is not
    committed in full everywhere, and a picker listing a document that
    cannot be opened is worse than a shorter list."""
    return tuple(entry for entry in CATALOGUE if entry.path.exists())


def get(doc_id: str) -> LoadedDocument:
    """Raises KeyError for an unknown id, and UnusableDocumentError (from
    load_document) if the file somehow isn't an analysable health policy."""
    entry = _BY_ID[doc_id]
    with _cache_lock:
        cached = _cache.get(doc_id)
        if cached is not None:
            return cached
    # Deliberately outside the lock: segmenting is slow and pure, so two
    # concurrent first-requests doing it twice is cheaper than making every
    # other request wait behind one of them.
    document = load_document(entry.doc_id, entry.path.read_bytes())
    with _cache_lock:
        return _cache.setdefault(doc_id, document)


def entry_for(doc_id: str) -> CatalogueEntry:
    return _BY_ID[doc_id]
