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

## Run the analysis view

Needs a local [Ollama](https://ollama.com) with the model pulled — no API key,
nothing leaves the machine:

```bash
ollama pull qwen2.5-coder:7b
uv run uvicorn web.app:app --reload     # http://127.0.0.1:8000
```

Pick one of the bundled real policies, describe a situation, and every
statement comes back with its support state, the verbatim clause behind it,
and the page it came from with that passage boxed.

A full run is tens of seconds — each claim is checked against every retrieved
clause separately, which is the point. Progress is reported per stage.

To run the UI without a model (deterministic, for tests and for poking at the
interface), set `POLICY_AGENT_FAKE_LLM=1`.

### Tests

```bash
uv run pytest                    # everything; live-model tests skip if Ollama is down
uv run pytest tests/web          # API + browser tests, scripted model, ~20s
uv run playwright install chromium   # once, for the browser tests
```

Browser tests assert `docs/HANDOVER.md` §8's UI contract — that each support
state reaches the reader with the accompanying content it requires, that the
evidence path ends at a highlighted passage in the real page, and that the
forbidden generic AI disclaimer is absent.

## Status

Pipeline runs end to end (intake → retrieval → draft → verify → resolve →
response) behind a structured analysis view. See `docs/HANDOVER.md` §14–15 for
build order, what is verified, and what is still open — notably the hero
scenario's room-rent arithmetic and dense retrieval.
