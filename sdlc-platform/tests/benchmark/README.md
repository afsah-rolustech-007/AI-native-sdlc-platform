# Section 06 retrieval benchmark

Phase 03's numeric completion criterion, and the baseline Phase 11 compares against
("within 5 points at scale").

```bash
make up && make migrate
make benchmark                                  # standalone
uv run pytest tests/integration/test_retrieval_benchmark.py -s   # in the suite
```

## What is frozen

- `corpus/` — 14 Python files across 5 services (`auth`, `billing`, `storage`, `shared`,
  `web`). Small on purpose, but structured like a real app: a config module everything
  imports, a connection pool, repositories, an auth flow, a billing flow, HTTP routes.
  It also contains deliberate semantic near-misses — `shared/validation.py` competes with
  token verification for the word "valid", and `shared/retry.py` says "database connection"
  in its docstring without opening one.
- `queries.json` — 29 labeled queries across five types.

Both are frozen. Gold answers were read off the corpus source, not off system output.
**Do not edit a label to make a run pass.** Fix retrieval, or record the miss.

## Metric: success@5

A query is a hit when at least one gold answer appears in the first 5 results.

We do not report classic precision@5. Most queries here have exactly one correct answer,
so precision@5 is capped at 0.20 and measures label cardinality rather than retrieval
quality. Success@5 answers the question that matters for an agent: did the right code
make it into the context window?

Graph queries return unranked sets; they are truncated to 5 for the same metric.

## Signals are scored separately

There is no fusion at this phase (RRF is Phase 12). Each query is routed to exactly one
signal — semantic, lexical, or graph — so a miss is attributable to that signal rather
than to a ranking formula.

Lexical queries are **skipped, not failed**, when Zoekt binaries are unavailable, and the
skip is printed. Read the per-signal table, not just the aggregate.

## Baseline

Deterministic `HashingAdapter` (no GLM key needed, so results are reproducible), Zoekt
not installed:

| Scope | success@5 |
|---|---|
| overall | 96.2% (25/26 scored) |
| semantic | 100% (19/19) |
| graph | 86% (6/7) |
| lexical | skipped (3 queries) |

Target: ≥ 90%.

### The one miss

`g06` asks for callers of `DatabasePool.acquire`. Both callers reach it through
`self.pool`, and Section 03 resolves direct-name calls only. The query is labeled
`"adversarial": true` and stays in the set: it is a real recall limit of attribute-call
resolution, and deleting it would hide that.

### What the benchmark caught

Header-only class chunks were suppressing their own methods during overlap dedup — a class
row spans the whole class, but its vector is signature + docstring only, so it never
actually contained the method body. Exempting class rows from suppression took semantic
success@5 from 94% to 100%.

## Adding queries

Write the query and its gold answer from reading the corpus, *before* running it. Keep the
adversarial ones. If you add a corpus file, every existing label must still be correct.
