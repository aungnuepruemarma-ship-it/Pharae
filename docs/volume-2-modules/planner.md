# Module Spec — Planner

**Status:** Implemented (Stage 4). Code: `nexus/planner/`. Tests:
`tests/test_planner.py`.

## Purpose

Build an execution DAG from a structured intent. Emits a plan; never executes.

```
Intent → Plan { tasks[], dependencies, capability-type requirements }
```

## Boundary

**Owns:** DAG construction, dependency analysis, capability-type assignment,
re-planning on failure, plan export.

**Must never:** call tools or capabilities, bind tasks to vendors (tasks
declare capability *types* only — binding is the Router's job), mutate a
running plan in place.

## Behavior (V1: rule-based, model-free)

### Plan shape

```
[gather-context]  →  goal-1  →  goal-2  →  …  →  goal-N
   (research,                                      │
    only when the intent                           ▼
    has context refs)              verify  (depends on every goal)
```

- Goals chain **sequentially in intent order** — order is meaningful; it came
  from numbered lists and "and then" decomposition upstream.
- A `verify` task is appended to **every** plan, depending on all goals and
  carrying the intent's desired outcomes: verification is structural, not
  optional (Volume 1 §13).
- Constraints attach to every task payload; goal payloads carry their goal
  text as `description`.

### Capability typing
Ordered keyword table over the goal text; first bucket wins; unmatched goals
default to `code` (the maker default): `verify` (test/verify/validate/
benchmark/audit) → `browser` (browse/scrape/visit/navigate/crawl) →
`research` (research/compare/analyze/summarize/…) → `code`. Verify outranks
browser so "Test the scraper" is a verify task. Tuning the table is routine
rule work against the golden tests, not an architecture change. Types are
never vendors (Invariant I1).

### Determinism and validity
- Same intent → same plan, **ids included** (`plan-<sha256[:12]>` over intent
  id, goals, constraints, outcomes, refs). No randomness, no clock.
- Every produced plan passes the kernel scheduler's closure/acyclicity
  validation by construction (tested).
- An intent with no goals is unplannable → `PlannerError`. Open questions on
  an intent with goals do **not** block planning — they remain on the intent
  for the user; the planner plans what is plannable.

### Re-planning
`replan(plan, evidence, completed) → Plan`: a **successor** plan — the
original is never mutated (running plans are immutable). Completed tasks are
dropped, dependencies on them released, statuses reset to PENDING, and router
bindings cleared so routing decides afresh under current registry state.
`provenance = "<old-plan-id>:<evidence-id>"` links the failure evidence.
Deterministic; replanning a fully-completed plan is an error. Emits
`plan.revised` with the dropped task ids.

## Events

`plan.created` (`{plan_id, intent_id, task_count}`),
`plan.revised` (`{plan_id, provenance, dropped}`).

## Verification

25 tests: plan shape (verify always appended, gather-context gating,
sequential chaining), typing table incl. precedence, payload propagation,
determinism (ids and structure), scheduler validity, no-goals error,
open-questions-still-plans, replan semantics (drop/filter/reset/immutability/
provenance/determinism/all-done error), and an end-to-end coordination test:
objective → intent → plan → route → completed run with all events observed.
