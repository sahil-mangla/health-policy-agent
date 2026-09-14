"""Lexical + exact-phrase retrieval via SQLite FTS5.

See docs/spikes/retrieval-stack.md (SPIKE-3) for the decision rationale.
Stdlib-only (sqlite3), no extra dependency, fully local and reproducible.
"""

from __future__ import annotations

import sqlite3
from types import TracebackType

from decoder.schema import Span


class FTS5NotAvailableError(RuntimeError):
    """Raised if the local SQLite build lacks the FTS5 extension."""


class FTS5LexicalIndex:
    """A small wrapper around a SQLite FTS5 virtual table.

    `search()` always treats the query as an exact phrase (quoted and
    escaped before being sent to FTS5) rather than parsing it as FTS5 query
    syntax — this both satisfies the spec's "must support exact-phrase
    lookup" requirement and avoids surprising behavior or crashes if a
    caller's query string happens to contain FTS5 operators/punctuation.
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
        """Returns `[(span_id, bm25_score), ...]`, best match first. An empty
        index or a query with no matches returns `[]` without raising."""
        if not query.strip():
            return []
        phrase_query = '"' + query.replace('"', '""') + '"'
        rows = self._con.execute(
            "SELECT span_id, bm25(spans) FROM spans "
            "WHERE spans MATCH ? ORDER BY bm25(spans) LIMIT ?",
            (phrase_query, top_k),
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
