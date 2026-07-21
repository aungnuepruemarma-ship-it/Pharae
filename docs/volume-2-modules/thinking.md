# Module Spec — Thinking (L4, reasoning budget)

**Status:** Implemented. Code: `nexus/thinking/`. Tests:
`tests/test_thinking.py`. Realizes First Principle #5 (Progressive Complexity)
and layer L4 of the CogOS v2.0 vision (Volume 4 layer map).

## Purpose

Decide *how much reasoning is necessary* before planning — so simple tasks are
solved directly and orchestration is spent only where it earns its cost. Sits
between the Intent Engine and the Planner in the core loop.

```
Intent → ThinkingBudgeter.assess → ThinkingBudget → Planner (and downstream)
```

## Boundary

**Owns:** reasoning-effort assessment (mode, depth, gathering, parallelism,
retry and stopping thresholds).

**Must never:** execute, call capabilities, choose vendors, or override a
structural invariant. The budget is *advice*; it cannot remove the
always-appended verify step or open any gate.

## Behavior (deterministic, model-free)

Three modes (blueprint L4):

| Mode | When | Budget character |
|------|------|------------------|
| **REFLEX** | one short/trivial goal; no constraints, refs, or open questions | depth 1, no gather, parallelism 1, 0 retries, stop @0.60 |
| **RESEARCH** | a research-shaped goal, ≥1 context ref, or ≥2 open questions | depth n+1, gather if refs, parallelism 4, 2 retries, stop @0.85 |
| **DELIBERATIVE** | everything else (safe default) | depth max(n,2), gather if refs, parallelism 2, 1 retry, stop @0.75 |

Ordered rule set over intent *features only* (goal count, constraints, open
questions, refs, a local research/trivial keyword check kept independent of
the planner's capability table so layers stay decoupled). Deterministic: same
intent → same budget (`as_dict` is stable and JSON-serializable). Emits
`thinking.assessed` (`{intent_id, mode}`) when a bus is attached; works
without one.

## Consumption (backward-compatible)

- **Planner** `plan(intent, budget=None)`: the budget's `gather_context`
  steers whether a context-gathering task is included. `budget=None` preserves
  prior behavior exactly. **The verify step is always appended regardless of
  mode** — a tested invariant, not a budget line.
- **Forward consumers** (documented, not yet wired to avoid churn):
  `max_parallelism` → executor worker width; `max_retries` → executor retry
  policy; `stopping_confidence` → verification "good enough" threshold;
  `max_plan_depth` → future goal decomposition.

## Recorded limits

Modes are heuristic and English-keyword based (same honest caveat as the
intent engine); tuning is routine rule-work against the golden tests. Model-
assisted uncertainty/confidence estimation (blueprint L4's richer form) is a
future capability behind the same `ThinkingBudget` schema.

## Verification

17 tests: mode classification (reflex/deliberative/research incl.
constraint-lifts-reflex, refs/verbs/questions forcing research), monotonic
effort across modes, reflex minimality, JSON/rationale, determinism, event
emission, no-bus operation, and planner integration proving the gather knob
works while verify stays structural in every mode.
