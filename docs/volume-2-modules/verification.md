# Module Spec — Verification Engine

**Status:** Implemented (Stage 7). Code: `nexus/verify/`. Tests:
`tests/test_verify.py`. This completes the Phase 1 core loop: the memory
promotion gate and capability score gate consume the Evidence produced here.

## Purpose

First-class subsystem that decides whether trustworthy evidence about a run
can be established, and how good the result looks. Nothing is trusted by
default; verification output is the *only* input to learning and long-term
memory (Invariant I2).

## The Central Semantic

**`verified` ≠ "the run succeeded."** They are separate judgments:

- **verified** — trustworthy evidence could be established: the run is
  terminal, every planned task has a result, and (when a bus is present) the
  event trace is consistent with the results. A verified record of a *failed*
  run is valid — it is exactly what failure memory and reliability scoring
  need. Unverifiable evidence carries `confidence 0.0` and provably cannot
  pass the downstream gates (tested against the real gates).
- **success** — the run completed and every check passed; carried in
  `test_results.success`.

## Boundary

**Owns:** evidence assembly, check execution, trace validation, confidence
scoring, reproducibility assessment.

**Must never:** repair results (that is re-planning), or be skippable for
runs that feed learning or memory — the gates enforce this from their side.

## Behavior

### Checks
- Structural (always): `all-tasks-completed` (run status).
- **Pluggable per capability type** via `register_check(type, name, fn)` —
  the seam where capability-specific verifiers attach as capabilities arrive
  (code → run tests; research → cross-check sources; browser → assert page
  state). Checks receive `(TaskResult, Task)`; a crashing checker records a
  failed check with the exception, never crashes verification. Type checks
  need the plan (for task types); without one they are skipped and noted in
  the logs.
- Failing checks lower confidence and negate success; they do not make
  evidence unverifiable — a bad result, verifiably observed, is still
  evidence.

### Trace consistency (Invariant I6)
With a bus attached: `run.started` and a terminal run event must exist, and
every `task.started` must have a settled counterpart. Completed-without-start
is permitted (checkpoint replays) — this is consistency, not completeness.
Inconsistency makes the run unverifiable.

### Confidence
Deterministic weighted score, every input recorded in
`test_results.scoring` so it can be audited and re-derived:
`0.5·task_completion + 0.3·check_pass_rate + 0.1·first_attempt_rate +
0.1·trace_consistent`, renormalized when the trace input is absent (no bus).
Retries surface honestly: a run that needed retries scores below a clean one.

### Evidence envelope
Content-derived id (`ev-<sha256[:12]>` over run id, statuses, attempts,
verdict) — verifying the same run twice yields identical evidence. Includes:
human-readable `logs`, `artifact_ids` (caller-supplied artifacts),
`test_results` (success, checks, scoring), `reproducible`
(plan-provided ∧ verified; `None` without a plan), and a `cost_report`
(duration, tasks, attempts, retries).

## Events

`run.verified` (`{run_id, evidence_id, confidence}`),
`run.unverified` (`{run_id, reasons}`).

## Verification (of the verifier)

17 tests: full-confidence verification of a clean run, deterministic evidence
ids, cost report, recorded scoring inputs, unverifiability (non-terminal,
missing results, inconsistent trace, no-bus trace skip), verified failure
evidence, custom checks (pass/fail/crash/no-plan skip), retry penalty, gate
integration (unverified evidence rejected by the real memory and registry
gates), and the V1 success-criteria test — all six steps of
Volume 0 §9 against real subsystems, ending in memory promotion and trust
movement.
