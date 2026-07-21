# Module Spec — Experiment Manager (L8)

**Status:** Implemented. Code: `nexus/experiments/`. Tests:
`tests/test_experiments.py`. Layer L8 of the CogOS v2.0 map. Supplies the
statistical justification L24 governance already demands and Cog's policy
trials were missing.

## Purpose

Decide whether a change is a real improvement, with recorded, reproducible
statistical evidence — not a single lucky run.

## Statistics (`stats.py`, pure stdlib)

- `mean`, `cohens_d` (standardized effect size, pooled SD),
- `bootstrap_ci` (percentile CI for the mean) and `bootstrap_p_greater`
  (one-sided 'no improvement' probability) — both **deterministic under a
  seed**, so a verdict is reproducible (Volume 0: auditable, reproducible),
- `holm_correction` (Holm–Bonferroni step-down) for multiple comparisons.

## ExperimentManager

`compare(baseline_id, treatment_id, baseline=[…], treatment=[…]) →
ExperimentResult`. An `improved` verdict requires **all three** to agree:
positive mean delta, effect size ≥ `min_effect` (0.5), and bootstrap
p(no-improvement) ≤ `alpha` (0.05). Any one failing → not improved — the
conservative default matching Pharae's gate-over-signal stance. Too few
samples per arm → inconclusive (not improved). Emits `experiment.completed`;
the result serializes to JSON.

## Governance wiring

`PolicyEngine.activate_if_improved(kind, version, result)` (Cog) activates a
candidate policy **only** if the experiment improved, recording the verdict
either way (`policy.trial_rejected` on failure). This is the opt-in trial
path that upgrades ADR-0006's recorded V1 shortcut (immediate activation):
the immediate `activate` remains for bootstrapping; trials gate on evidence.

## Boundary

**Owns:** statistical comparison and its verdict. **Must never:** execute,
mutate policies itself (it returns a verdict; Cog decides), or open any gate.

## Recorded limits

Bootstrap/effect-size thresholds are defaults, not tuned against a real
workload yet; the benchmark harness that will feed this with live metrics is
future work. Holm correction is available but not yet auto-applied across a
batch of concurrent policy trials (single-comparison path is what Cog uses
today).

## Verification

13 tests: mean/effect-size/CI/Holm correctness and determinism, clear
improvement vs noise vs regression vs insufficient-samples verdicts, JSON +
event emission, and the governance gate (improved → activate; flat →
rejected, active version unchanged, `policy.trial_rejected` emitted).
