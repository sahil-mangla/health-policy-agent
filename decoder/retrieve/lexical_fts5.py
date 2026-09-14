"""Lexical retrieval via SQLite FTS5 — both natural-language term search and
exact-phrase lookup.

See docs/spikes/retrieval-stack.md (SPIKE-3) for the decision rationale.
Stdlib-only (sqlite3), no extra dependency, fully local and reproducible.
"""

from __future__ import annotations

import re
import sqlite3
from types import TracebackType

from decoder.schema import Span

_TOKEN_RE = re.compile(r"\w+")


class FTS5NotAvailableError(RuntimeError):
    """Raised if the local SQLite build lacks the FTS5 extension."""


class FTS5LexicalIndex:
    """A small wrapper around a SQLite FTS5 virtual table.

    Two distinct search modes, because they serve different callers:

    - `search()` tokenizes the query and matches spans containing ANY of
      the terms (OR), ranked by BM25 — this is what evidence retrieval over
      a free-text situation/question needs (docs/HANDOVER.md §10): a real
      question rarely repeats a clause's exact wording, so requiring every
      query word to literally co-occur (or worse, the whole query as one
      phrase) misses spans that use different words for the same fact.
      Caught by a real end-to-end test (2026-09-14): a query like
      "co-payment percentage claim" against a real clause reading
      "...Co-payment of 5% applicable to claim amount..." returned zero
      results under phrase-only matching, because the word "percentage"
      never appears in the clause at all.
    - `search_phrase()` is the original exact-phrase behavior — the whole
      query treated as one literal, quoted phrase. This is what "must
      support exact-phrase lookup" actually refers to: re-finding a span by
      a known verbatim citation, not general retrieval.

    Each individual token is quoted before being sent to FTS5 (in both
    methods) so query text is never parsed as FTS5 operator syntax — this
    avoids crashes/surprising behavior on punctuation-heavy input without
    needing a full FTS5 query-syntax escaper.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._con = sqlite3.connect(db_path)
        try:
            self._con.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS spans "
                "USING fts5(span_id UNINDEXED, doc_id UNINDEXED, text)"
            )
        except sqlite3.OperationalError as exc:
            raise FTS5NotAvailableError(
                "This SQLite build lacks FTS5 support; see "
                "docs/spikes/retrieval-stack.md for the retrieval stack decision."
            ) from exc

    def add_span(self, span: Span) -> None:
        self._con.execute(
            "INSERT INTO spans(span_id, doc_id, text) VALUES (?, ?, ?)",
            (span.id, span.doc_id, span.text),
        )

    def add_spans(self, spans: list[Span]) -> None:
        for span in spans:
            self.add_span(span)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Returns `[(span_id, bm25_score), ...]`, best match first, for
        spans containing any of the query's terms — natural-language
        retrieval, not exact matching. An empty query, an index with no
        matches, or a query with no usable tokens all return `[]` without
        raising."""
        tokens = _TOKEN_RE.findall(query)
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in tokens)
        return self._run(fts_query, top_k)

    def search_phrase(self, phrase: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Returns `[(span_id, bm25_score), ...]` for spans containing
        `phrase` as one literal, contiguous, exact substring (case- and
        punctuation-insensitive per FTS5's tokenizer, but not otherwise
        normalized) — for re-finding a span by a known verbatim quote."""
        if not phrase.strip():
            return []
        fts_query = '"' + phrase.replace('"', '""') + '"'
        return self._run(fts_query, top_k)

    def _run(self, fts_query: str, top_k: int) -> list[tuple[str, float]]:
        rows = self._con.execute(
            "SELECT span_id, bm25(spans) FROM spans "
            "WHERE spans MATCH ? ORDER BY bm25(spans) LIMIT ?",
            (fts_query, top_k),
        ).fetchall()
        return [(span_id, score) for span_id, score in rows]

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> FTS5LexicalIndex:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
