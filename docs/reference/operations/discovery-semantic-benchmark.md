# Discovery Semantic Benchmark

Use this benchmark before changing semantic discovery tuning such as
`SEMANTIC_HNSW_EF_SEARCH`.

The benchmark creates deterministic synthetic skills under a reserved
`benchmark.semantic.*` slug prefix, inserts deterministic `indexed` semantic
vectors, compares approximate HNSW results against an exact scan baseline, and
then removes the benchmark rows by default. It does not call OpenAI.

## Run

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python scripts/benchmark_discovery_search.py
```

Useful smaller local run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python scripts/benchmark_discovery_search.py \
  --skills 100 \
  --queries 5 \
  --iterations 2 \
  --limit 10 \
  --ef-search 40 100 200
```

The target database comes from normal app settings. For a Neon branch or other
non-default target, set `DATABASE_URL` or `APP_SETTINGS_ENV_FILE` before running
the command. The script defaults `SEMANTIC_DISCOVERY_MODE=off` for settings
loading so provider credentials are not required.

## Output

The command prints a concise table followed by one JSON object on the final
line. The JSON includes:

- `semantic_hnsw`: recall and latency for each `hnsw.ef_search` value compared
  with an exact semantic baseline
- `discovery`: end-to-end `off`, `shadow`, and `hybrid` discovery latency and
  benchmark-cluster recall
- `cleanup`: whether benchmark rows were deleted

Use the final JSON line for saved artifacts or automated comparisons.

## Interpreting Results

Exact baseline means the query disables index scans with
`SET LOCAL enable_indexscan = off`, then orders by cosine distance. HNSW recall
is the overlap between approximate top-k results and that exact top-k result
set.

Start with the checked-in values:

- `40`: fastest baseline, lower recall
- `100`: normal starting point
- `200`: higher recall at higher latency
- `400`: near-exact behavior, usually much slower

Only raise `SEMANTIC_HNSW_EF_SEARCH` when recall improves enough to justify
the p95/p99 latency increase on the target database shape.

## Cleanup

Rows are removed by default. Use `--keep-data` only when inspecting query plans
or database state manually. Cleanup is restricted to prefixes that start with
`benchmark.semantic.` and end with `.`.
