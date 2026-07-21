# Module Spec — Planner

**Status:** Spec (Stage 1). Not yet implemented.

## Purpose

Build an execution DAG from a structured intent. Emits a plan; never executes.

```
Intent → Plan { tasks[], dependencies, capability-type requirements }
```

## Boundary

**Owns:** DAG construction, dependency analysis, plan optimization,
re-planning on failure, plan export.

**Must never:** call tools or capabilities, bind tasks to vendors (tasks
declare capability *types* only — routing is the Router's job), mutate a
running plan in place.

## Behavior

- Deterministic: the same intent and the same registry snapshot produce the
  same plan.
- Independent branches are structurally identifiable so the executor can
  parallelize without re-analysis.
- **Re-planning:** on failure, the planner receives the failed plan plus
  failure evidence and produces a *new* plan (new id, provenance link to the
  old one). Running plans are immutable.
- Plans are exportable artifacts (JSON), diffable and replayable.
- Emits `plan.created` / `plan.revised` events.

## Interfaces

- Input: `Intent`; failure evidence on re-plan.
- Output: `Plan` (Volume 3 / `nexus/schemas`) — consumed by Router + Executor,
  validated by the kernel scheduler (cycle rejection).

## Verification

Golden tests intent → plan; cycle-freeness property test; determinism test;
re-planning produces a valid successor plan referencing the failure evidence.
