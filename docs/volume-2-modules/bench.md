# Module Spec — Benchmark Harness

**Status:** Implemented. Code: `nexus/bench/`. Tests: `tests/test_bench.py`.
CLI: `nexus bench`. Realizes Volume 1 §18; first recorded result:
`docs/volume-4-research/benchmarks/baseline-0.1.0.md`.

## Purpose

Measure the runtime against itself, reproducibly. Runs a fixed suite of
objectives through the real loop and reports the metrics Volume 1 §18 names.
Supplies the data source the research agenda's open questions all require and
the Experiment Manager (L8) was built to consume.

## Design

- **Fixed suite** (`suite.py`): 12 objectives spanning reflex / code /
  research / multi-goal, plus a **deliberate unroutable case** (a browser
  objective with no built-in browser) — the gate and honest routing failure
  are part of what is measured, not excluded.
- **Runner** (`runner.py`): one shared `AppContext` across the suite so
  learning accumulates and is observable (episodic memory growth). A small
  fixed corpus is written into the data dir and used as the research root, so
  research cases are deterministic regardless of the caller's cwd. No network.
- **Report**: `summary()` → success rate, verified rate, unroutable rate, mean
  confidence (over verified), mean tasks, learning-observed.
  `deterministic_summary()` rounds for use as a regression fixture — identical
  across runs and data dirs. `as_dict()` serializes.

## Boundary

**Owns:** the suite, the run loop, aggregation. **Must never:** change runtime
behavior, or assert per-case *correctness* beyond completion — it *measures*;
it does not grade individual outputs (that is verification's job).

## Recorded limits

With built-in reference handlers, verified runs are clean by construction, so
`mean_confidence` currently reflects harness determinism, not capability
quality — it becomes meaningful when real capabilities that can fail are
installed. The suite is small and hand-written; generator-based suites (the
`cog` repo's approach) and Holm-corrected multi-config comparison are future
work.

## Verification

7 tests: suite spans kinds incl. unroutable; report metrics in range;
failures included (unroutable rate > 0); learning observed across the suite;
deterministic summary across separate data dirs; JSON-serializable; and the
`nexus bench` CLI verb runs and prints the summary.
