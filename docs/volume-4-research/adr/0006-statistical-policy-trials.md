# ADR-0006: Statistical gate for policy activation (L8)

**Status:** Accepted
**Date:** 2026-07-21

## Context

Cog's PolicyEngine (the Cog spec's "V1 shortcut, recorded") activated a
proposed policy immediately — rollback existed, but there was no *evidence*
that a new policy was better before it went live. L24 governance requires
"everything statistically justified"; the missing piece was the statistics.

## Decision

Add `nexus/experiments/` (L8): bootstrap CIs, effect size, Holm correction,
and an `ExperimentManager.compare` that returns an evidence-backed
improvement verdict (deterministic under a seed). Add
`PolicyEngine.activate_if_improved(kind, version, result)` that activates a
candidate **only** on an improved verdict, recording rejection otherwise. The
immediate `activate` remains as the explicit bootstrapping path.

## Alternatives Considered

- **Keep immediate activation only:** rejected — leaves policy changes
  unjustified, violating the governance principle once measurements exist to
  test against.
- **A dependency on scipy/numpy for stats:** rejected — the kernel/core stays
  stdlib-only (ADR-0001); a percentile bootstrap and Holm step-down are a few
  lines and keep the zero-dependency property.
- **Auto-gate every activation (remove immediate path):** rejected for V1 —
  bootstrapping the first policies needs an ungated path; trials become the
  norm once the benchmark harness produces metric streams.

## Consequences

Easier: policy evolution is now evidence-justified and reproducible; the
verdict is recorded (`experiment.completed`, `policy.trial_rejected`). Harder:
callers must supply metric samples — which the benchmark harness will produce.
Reopen trigger: real workloads showing the default thresholds (min effect 0.5,
alpha 0.05) mis-serve, or a need to Holm-correct concurrent trials.

## Invariant Check

- **I1/I2/I3:** unaffected — this gates policy *activation*, not memory or
  evidence; statistics run over metric samples, no vendor, no gate bypass.
- Determinism: the bootstrap is seeded; verdicts are reproducible. Preserved.
