# Module Spec — Runtime Executor

**Status:** Spec (Stage 4). A minimal synchronous executor exists inside the
kernel runtime (`nexus/kernel/runtime.py`); Stage 4 grows it into a full
executor behind the same interface.

## Purpose

Run routed plans: interactive, background, parallel, long-running, resumable.

## Boundary

**Owns:** task dispatch, retries, timeouts, cancellation, checkpointing,
recovery, queues.

**Must never:** choose capabilities (Router), reorder beyond scheduler
readiness (Scheduler), write non-working memory (Invariant I3), or swallow
side effects unlogged (Invariant I6).

## Behavior

- **Modes:** interactive (user can pause/intervene), background jobs,
  parallel execution of independent DAG branches, scheduled runs.
- **Checkpointing:** state-manager snapshots at task boundaries; a run can be
  resumed from its last checkpoint after a crash or stop.
- **Failure:** per-task retry policy (bounded, recorded); on exhaustion the
  task fails, dependents block, and failure evidence is captured for
  re-planning and failure memory.
- **Cancellation:** any run can be cancelled at any time; cancellation is
  cooperative for capabilities but mandatory at task boundaries (Invariant I7).
- Every transition emits events (`task.started/completed/failed/retried`,
  `run.checkpointed/resumed/cancelled`).

## Non-Goals

Distributed swarms and remote workers (Phase 3). The executor's interface must
not preclude them, but V1 executes locally.

## Verification

Resume-from-checkpoint tests; retry-bounding tests; parallel-branch ordering
tests; cancellation-mid-run tests; event-trace completeness.
