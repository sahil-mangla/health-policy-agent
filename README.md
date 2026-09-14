# Indian Health Insurance Policy Decoder

Given a consumer's health policy + CIS and a real situation, identify which
policy conditions matter, trace each conclusion to the clause it came from,
and say plainly where the documents aren't sufficient to answer. Calibrated
abstention is the product, not summarization quality.

Full spec: [`docs/HANDOVER.md`](docs/HANDOVER.md) — read it before writing code.

## Quickstart

```bash
uv sync --group dev        # install
uv run pytest               # test
uv run ruff check .         # lint
uv run mypy .                # type check
```

Dense (embedding-based) retrieval needs an additional extra, not installed by
default:

```bash
uv sync --group dev --extra dense
```

## Status

Scaffold + SPIKE-1 (partial) + SPIKE-3 (resolved). See `docs/HANDOVER.md` §14–15
for build order and open decisions.
