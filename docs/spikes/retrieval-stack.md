# SPIKE-3 — Retrieval stack

**Status: RESOLVED (2026-09-14)**

Constraints from `docs/HANDOVER.md` §10: must run locally for eval
reproducibility, must support exact-phrase lookup, half-day timebox, retrieval
is explicitly *not* the differentiator — do not over-engineer it.

## Decision

**Hybrid lexical + dense retrieval, unioned via Reciprocal Rank Fusion (RRF).
Never reranked.**

- **Lexical + exact-phrase: SQLite FTS5.** Uses the stdlib `sqlite3` module —
  zero extra dependency. `CREATE VIRTUAL TABLE ... USING fts5(...)` gives
  exact-phrase queries and BM25-based ranking (`bm25(table)`) for free.
  Confirmed working locally against this project's Python/SQLite build
  (sqlite 3.53.4 supports `fts5`). This alone satisfies the spec's hard
  requirement that the index "must support exact-phrase lookup" — insurance
  wording turns on exact terms and numbers ("₹5,000 per day," "single private
  AC room") that need literal matching, not just semantic similarity.
- **Dense:** a small local `sentence-transformers` embedding model (candidates:
  `bge-small-en-v1.5` or `e5-small-v2` — either is fine, pick one when corpus
  work starts; not decided further here since no corpus exists yet to tune
  against). Similarity computed as brute-force numpy cosine similarity for
  now, since expected corpus size in early milestones (a handful of policy +
  CIS documents at a time) doesn't warrant an approximate-nearest-neighbor
  index. FAISS or Chroma are the natural swap-in once/if corpus size grows
  past brute-force feasibility — deliberately **not** added now, to avoid
  building infrastructure for a scale problem that doesn't exist yet.
- **Fusion: Reciprocal Rank Fusion**, not a weighted-sum blend and not a
  reranker. `score(doc) = Σ 1 / (k + rank_in_list)` across the lexical and
  dense ranked lists, summed and re-sorted. Chosen over weighted-sum fusion
  because BM25 scores and cosine similarities live on incompatible numeric
  scales — weighted normalization between them is fragile and corpus-
  dependent, whereas RRF only needs rank order, which is stable across query
  types. Chosen over any cross-encoder/LLM reranking step specifically
  because §10 forbids "reranking that can drop a contradicting span" — RRF is
  a union/merge over both candidate sets, so nothing either retrieval method
  found is ever discarded before verification gets to see it.

## Why not something heavier

Elasticsearch/OpenSearch, a managed vector DB, or a cross-encoder reranker
would all work, but none are justified yet: the spec explicitly timeboxes
this spike and says retrieval is not the product's differentiator (§10), and
every one of those options adds either external infrastructure (breaks local
eval reproducibility) or a dependency footprint with no current corpus to
validate it against. FTS5 + a small local embedding model can be swapped for
something heavier later without touching anything upstream, since both sit
behind the same `Retriever` interface (`decoder/retrieve/interfaces.py`).

## What this unblocks vs. what it doesn't

- The FTS5 lexical path is fully implementable today with zero corpus
  dependency (`decoder/retrieve/lexical_fts5.py` — real code, not a stub, in
  this same commit).
- **Update (2026-09-14), caught by a real end-to-end test:** the original
  `search()` treated the *entire* query as one exact phrase, which is right
  for re-finding a span by a known quote but wrong for retrieving evidence
  from a free-text question — a real query ("co-payment percentage claim")
  against a real clause ("...Co-payment of 5% applicable to claim
  amount...") returned zero results, because the word "percentage" never
  appears in the clause at all and phrase matching requires every query
  word to co-occur verbatim. Split into `search()` (tokenized, OR-of-terms,
  BM25-ranked — the actual retrieval method) and `search_phrase()` (the
  original exact-phrase behavior, kept for verbatim-citation lookup). The
  "must support exact-phrase lookup" requirement is satisfied by
  `search_phrase()`; it was never meant to be the default retrieval mode.
- The dense path (`decoder/retrieve/dense.py`) stays a stub: it needs an
  actual embedding model download and a real corpus to be meaningfully
  tested, and the corpus is blocked on SPIKE-2 (still not started — see
  `docs/HANDOVER.md` §11/§15). Implementing it against zero documents would
  produce no signal, so it's left as `NotImplementedError` with a clear TODO
  rather than built to look done.
- RRF fusion (`decoder/retrieve/fusion.py`) is pure and dependency-free, so it
  is also implemented for real now even though nothing calls it end-to-end
  yet — a `HybridRetriever` wiring both `lexical_fts5` and `dense` together is
  the next milestone's job, once `dense.py` is real.
