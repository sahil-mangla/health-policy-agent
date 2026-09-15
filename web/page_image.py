"""Renders the page a span came from, with that span boxed.

docs/HANDOVER.md §8: "Every claim supports the path Answer -> Why ->
Evidence, ending at the highlighted span in the rendered page image. Do not
ship a citation that is only a section number." This module is the last
step of that path — without it the evidence trail stops at quoted text and
a page number, which is better than a section number but still asks the
reader to take our word for where it came from.

Uses pdfplumber's own renderer (Pillow, already a transitive dependency),
so this adds no new install surface.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

_RESOLUTION = 110
_HIGHLIGHT = (255, 214, 0)
_PAD = 2.0


class PageImageError(ValueError):
    """The requested page does not exist in this document."""


@dataclass(frozen=True)
class RenderedPage:
    png: bytes
    # Where the highlight sits down the page, 0.0 (top) to 1.0 (bottom).
    # The reader opens this view to see one specific passage, so the client
    # needs to scroll there; without this it lands at the top of the page
    # and has to hunt for the box, which is most of the way back to citing
    # a page number and leaving them to find it.
    highlight_fraction: float | None


def render_page_with_span(
    pdf_path: Path,
    page_number: int,
    bbox: tuple[float, float, float, float] | None,
) -> RenderedPage:
    """`page_number` is 1-indexed, matching Span.page. A None bbox renders
    the page unmarked rather than failing — a span without geometry is
    still worth showing the reader in context."""
    with pdfplumber.open(pdf_path) as pdf:
        if not 1 <= page_number <= len(pdf.pages):
            raise PageImageError(
                f"page {page_number} is outside this document's 1..{len(pdf.pages)}"
            )
        page = pdf.pages[page_number - 1]
        image = page.to_image(resolution=_RESOLUTION)
        fraction: float | None = None
        if bbox is not None:
            clamped = _clamped(bbox, page.width, page.height)
            image.draw_rect(clamped, stroke=_HIGHLIGHT, stroke_width=3)
            centre = (clamped[1] + clamped[3]) / 2
            fraction = min(1.0, max(0.0, centre / float(page.height)))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return RenderedPage(png=buffer.getvalue(), highlight_fraction=fraction)


def _clamped(
    bbox: tuple[float, float, float, float], width: float, height: float
) -> tuple[float, float, float, float]:
    """A bbox that spills past the page edge makes pdfplumber raise rather
    than draw; segmentation can produce one for a span that hugs a margin,
    and losing the whole highlight over a fraction of a point would be a
    poor trade."""
    x0, top, x1, bottom = bbox
    return (
        max(0.0, x0 - _PAD),
        max(0.0, top - _PAD),
        min(width, x1 + _PAD),
        min(height, bottom + _PAD),
    )
