# Benchmark Baseline — v0.1.0

**Date:** 2026-07-21 · **Command:** `nexus bench` / `run_suite(...)` ·
**Suite:** `nexus/bench/suite.py` default (12 cases). Reproduce from a clean
checkout — the harness is offline and deterministic.

## Result

```
n               : 12
success_rate    : 0.9167
verified_rate   : 0.9167
unroutable_rate : 0.0833
mean_confidence : 1.0
mean_tasks      : 2.1667
learning_observed: true
```

Per case: 11 of 12 route, execute, verify, and learn; case `b11`
("Scrape the pricing page") is **deliberately unroutable** — no built-in
browser capability — and is reported as such, not papered over. The one
unroutable case is the entire gap between success and 1.0.

## Honest reading

- `success_rate` / `verified_rate` measure that the **loop is sound** end to
  end (intent → thinking → plan → route → execute → verify → learn) and that
  the router fails honestly on missing capabilities. That is real signal.
- `mean_confidence = 1.0` is **not** a quality claim: the built-in `code`/
  `verify` handlers are deterministic reference no-ops, so their runs are
  clean by construction. This number becomes meaningful only once real
  capabilities (a model-backed `code`, a live browser) can *fail* — at which
  point confidence will spread and the metric will start measuring capability
  quality rather than harness determinism. Recorded so the number is never
  mistaken for more than it is.
- `learning_observed = true` confirms the promotion pipeline fires: episodic
  memory grew across the suite from verified runs.

## What this unlocks

This is the first reproducible measurement of Pharae against itself, and the
data source the research agenda's open questions all asked for. It feeds:

- the **Experiment Manager (L8)** — A/B two configurations over per-case
  confidence/outcome streams;
- **Cog policy trials** — `activate_if_improved` can now be driven by real
  benchmark deltas instead of hand-fed samples;
- **routing-algorithm research** (agenda Q1) and **trust-calibration** (Q3).

## Regression use

`deterministic_summary()` is the regression fixture: identical across runs and
data dirs. A change that moves these numbers must explain why in its PR — a
drop in `success_rate`/`verified_rate` without a matching suite change is a
regression; a spread in `mean_confidence` once real capabilities land is
progress.
