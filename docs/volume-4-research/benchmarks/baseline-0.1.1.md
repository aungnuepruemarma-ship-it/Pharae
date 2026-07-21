# Benchmark Baseline — v0.1.1 (real failable code capability)

**Date:** 2026-07-21 · **Command:** `nexus bench` · **Supersedes:**
[baseline-0.1.0](baseline-0.1.0.md). **Change:** the built-in `code`
capability is now `pyexec` — real, safe, offline arithmetic evaluation that
*genuinely fails* on anything it cannot compute — replacing the reference
no-op. The suite is reworked to a mix of computable tasks, one prose-code task
the builtin cannot do, research, and an unroutable case.

## Result

```
n               : 12
success_rate    : 0.8333    (was 0.9167 — b10 now fails honestly)
verified_rate   : 0.9167
unroutable_rate : 0.0833    (b11, the browser case)
mean_confidence : 0.9273    (was 1.0000 — the metric now spreads)
mean_tasks      : 2.0833
learning_observed: true
```

Per case: computable code (b01–b04, b09) and research (b06–b08, b12) complete
at confidence 1.00; the multi-goal compute (b05) completes; **b10
("Implement a helper function") genuinely fails at confidence 0.20** — the
arithmetic builtin cannot write prose code and does not pretend to; **b11
("Scrape the pricing page") is unroutable** (no browser capability).

## Why this baseline matters more than v0.1.0

v0.1.0's `mean_confidence = 1.0` measured harness determinism — the reference
handlers could not fail. This baseline is the first where **the confidence
metric measures capability quality**: it spreads across [0.20, 1.00] driven by
real verification of real outcomes. A capability that can fail is what makes
the number honest, and the number moved exactly where it should:

- computable work → verified success → high confidence;
- work beyond the builtin's ability → verified *failure* → low confidence
  (0.20), feeding failure memory and lowering the capability's trust;
- missing capability → unroutable, reported, excluded from success.

This is the movement the v0.1.0 caveat predicted. The remaining path to a
richer number is the same as before: install real, failable capabilities for
other types (a model-backed general coder, a live browser) and the spread will
widen further.

## Regression use

`deterministic_summary()` remains the fixture; this document is the required
explanation for the change from v0.1.0 (new capability + reworked suite, not a
regression). Future drops in `success_rate`/`verified_rate` without a suite or
capability change are regressions; a wider `mean_confidence` spread as real
capabilities land is progress.
