"""PDF text + layout extraction, backing decoder.intake.segment.

Uses pdfplumber (stdlib-adjacent, MIT-licensed, pure Python — no AGPL/binary
dependency concerns). Deliberately no OCR fallback yet: the starter corpus
(corpus/README.md) is all clean, text-based PDFs. OCR for scanned documents
is a separate, not-yet-made decision — see decoder.intake.interfaces.DocumentType.UNREADABLE_SCAN.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import TypedDict

import pdfplumber


class _Word(TypedDict):
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


# A new paragraph/clause starts when a line's text matches one of these —
# derived from the actual structure observed in the starter corpus (real
# HDFC ERGO policy wordings use "Def. N", "SECTION X.", and numbered/lettered
# clause markers consistently). This is a heuristic tuned to this corpus,
# not a general-purpose PDF layout parser — revisit once more insurers'
# documents are added (corpus/README.md "still needed").
_CLAUSE_START_RE = re.compile(
    r"^(Def\.\s*\d+|SECTION\s+[A-Z]\.|Chapter\s+[IVXLC]+|\d+\)\s|\d+\.\s+[A-Z]|"
    r"[a-z]\)\s|[ivxlc]+\.\s)"
)

# A vertical gap this many times the page's median line height also starts a
# new paragraph, independent of clause markers (catches headings/whitespace
# breaks that don't use a numbering convention).
_GAP_MULTIPLE = 1.6


@dataclass(frozen=True)
class ExtractedLine:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass(frozen=True)
class ExtractedParagraph:
    text: str
    bbox: tuple[float, float, float, float]  # (x0, top, x1, bottom)


def _extract_lines(page: pdfplumber.page.Page) -> list[ExtractedLine]:
    words = page.extract_words()
    if not words:
        return []
    lines_by_top: dict[float, list[_Word]] = {}
    for raw_word in words:
        w: _Word = {
            "text": raw_word["text"],
            "x0": raw_word["x0"],
            "x1": raw_word["x1"],
            "top": raw_word["top"],
            "bottom": raw_word["bottom"],
        }
        # Round to the nearest pixel-ish bucket so words on the same visual
        # line (with tiny float jitter) group together.
        key = round(w["top"])
        lines_by_top.setdefault(key, []).append(w)

    lines: list[ExtractedLine] = []
    for top_key in sorted(lines_by_top):
        line_words = sorted(lines_by_top[top_key], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in line_words)
        x0 = min(w["x0"] for w in line_words)
        x1 = max(w["x1"] for w in line_words)
        top = min(w["top"] for w in line_words)
        bottom = max(w["bottom"] for w in line_words)
        lines.append(ExtractedLine(text=text, x0=x0, top=top, x1=x1, bottom=bottom))
    return lines


def extract_paragraphs(page: pdfplumber.page.Page) -> list[ExtractedParagraph]:
    """Groups a page's text into paragraph/clause-sized chunks, each with a
    tight bounding box, using the clause-marker + vertical-gap heuristics
    above."""
    lines = _extract_lines(page)
    if not lines:
        return []

    heights = [line.bottom - line.top for line in lines]
    median_height = sorted(heights)[len(heights) // 2] if heights else 10.0
    gap_threshold = median_height * _GAP_MULTIPLE

    paragraphs: list[ExtractedParagraph] = []
    current_lines: list[ExtractedLine] = [lines[0]]

    for prev, line in zip(lines, lines[1:], strict=False):
        gap = line.top - prev.bottom
        starts_new = gap > gap_threshold or bool(_CLAUSE_START_RE.match(line.text))
        if starts_new:
            paragraphs.append(_merge_lines(current_lines))
            current_lines = [line]
        else:
            current_lines.append(line)
    paragraphs.append(_merge_lines(current_lines))
    return paragraphs


def _merge_lines(lines: list[ExtractedLine]) -> ExtractedParagraph:
    text = " ".join(line.text for line in lines)
    x0 = min(line.x0 for line in lines)
    x1 = max(line.x1 for line in lines)
    top = min(line.top for line in lines)
    bottom = max(line.bottom for line in lines)
    return ExtractedParagraph(text=text, bbox=(x0, top, x1, bottom))


def extract_first_page_text(raw_bytes: bytes, max_pages: int = 2) -> str:
    """Fast, cheap text extraction for classification — doesn't need
    paragraph/bbox structure, just enough text to detect document type."""
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        pages = pdf.pages[:max_pages]
        return "\n".join(p.extract_text() or "" for p in pages)


def extract_all_paragraphs(raw_bytes: bytes) -> list[tuple[int, ExtractedParagraph]]:
    """Returns (page_number, paragraph) pairs for every page, 1-indexed pages."""
    result: list[tuple[int, ExtractedParagraph]] = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for paragraph in extract_paragraphs(page):
                result.append((page_number, paragraph))
    return result
