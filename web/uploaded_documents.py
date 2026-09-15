"""In-memory store for a user's own uploaded policy document — a real
upload path alongside web/corpus_library.py's bundled demo picker.

This closes a real gap, not a cosmetic one: docs/HANDOVER.md's spec is
written throughout assuming a real uploaded policy (§9.1's refusal-for-
wrong-type, §9.2's expiry check, §9.3's continuity requirement, §9.5's PII
rules), but until this module existed the running app could only ever
analyse the 5 documents already bundled in corpus/raw/ — there was no way
to point it at a real policy at all.

PII (§9.5): raw bytes and the segmented LoadedDocument live in memory for
the life of the process only — never written to disk, never logged. This
mirrors web/app.py's own job-record policy exactly (see that module's
docstring).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock

from pdfplumber.utils.exceptions import PdfminerException

from decoder.intake.interfaces import DocumentType
from decoder.orchestrator import LoadedDocument, UnusableDocumentError, load_document
from decoder.respond.labels import UNUSABLE_DOCUMENT_MESSAGES

# Prefixed distinctly from corpus_library's plain doc_ids (e.g.
# "arogya_sanjeevani") so web/app.py can route a doc_id to the right store
# with a cheap string check rather than trying one store, catching
# KeyError, then trying the other.
_ID_PREFIX = "upload-"

# Real policy wordings run a few hundred KB to a few MB; this is generous
# headroom against an oversized upload without being a load-bearing limit
# anyone should expect to hit in normal use.
MAX_UPLOAD_BYTES = 20_000_000


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file exceeds MAX_UPLOAD_BYTES."""


@dataclass(frozen=True)
class UploadedEntry:
    doc_id: str
    filename: str
    raw_bytes: bytes
    document: LoadedDocument


_store: dict[str, UploadedEntry] = {}
_lock = Lock()


def is_upload_id(doc_id: str) -> bool:
    return doc_id.startswith(_ID_PREFIX)


def add(filename: str, raw_bytes: bytes) -> UploadedEntry:
    """Raises UploadTooLargeError for an oversized file, or
    UnusableDocumentError (from decoder.orchestrator.load_document, §9.1)
    for a wrong-type or unreadable one — the same refusal path the bundled
    corpus already uses, just reached from a real upload instead of a
    fixed file. Validation happens here, at upload time, so a bad document
    is refused before the reader has even typed a situation."""
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError(
            f"file is {len(raw_bytes):,} bytes, over the {MAX_UPLOAD_BYTES:,}-byte limit"
        )
    doc_id = f"{_ID_PREFIX}{uuid.uuid4().hex[:12]}"
    try:
        document = load_document(doc_id, raw_bytes)
    except PdfminerException:
        # A real upload can be anything a user drags in — a .docx renamed
        # to .pdf, a corrupt download, plain text — not just a badly
        # scanned-but-genuine PDF. pdfplumber raises its own exception type
        # for "this isn't a parseable PDF at all" rather than returning
        # empty text the way it does for a scanned image with no text
        # layer, so decoder.intake.classify never sees it and can't
        # produce its own UNREADABLE_SCAN classification — caught here
        # instead and mapped to the same §9.1 message, since from the
        # reader's side both failures mean the same thing: "we couldn't
        # get readable text out of this file."
        raise UnusableDocumentError(
            doc_id,
            DocumentType.UNREADABLE_SCAN,
            UNUSABLE_DOCUMENT_MESSAGES[DocumentType.UNREADABLE_SCAN],
        ) from None
    entry = UploadedEntry(doc_id=doc_id, filename=filename, raw_bytes=raw_bytes, document=document)
    with _lock:
        _store[doc_id] = entry
    return entry


def get(doc_id: str) -> UploadedEntry:
    """Raises KeyError for an unknown id — same contract as
    web.corpus_library.get()."""
    with _lock:
        return _store[doc_id]
