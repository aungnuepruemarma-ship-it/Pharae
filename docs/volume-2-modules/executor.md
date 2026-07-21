# Module Spec — Runtime Executor

**Status:** Implemented (Stage 5). Code: `nexus/executor/`. Tests:
`tests/test_executor.py`. The kernel runtime's minimal `execute()` remains for
simple synchronous use; this executor is the real execution engine, built on
the same capability-type handler seam.

## Purpose

Run routed plans: interactive, background, parallel, long-running, resumable.

## Boundary

**Owns:** task dispatch, worker pool, retries, cancellation, checkpointing,
recovery.

**Must never:** choose capabilities (Router), reorder beyond scheduler
readiness (Scheduler decides *what is ready*; the executor decides *how it
runs*), write non-working memory (Invariant I3 — handlers receive only the
session's working-memory context), or swallow side effects unlogged
(Invariant I6 — every transition emits an event).

## Behavior

### Modes
- **Synchronous:** `execute(plan) → Run`.
- **Background:** `submit(plan, paused?) → Job` runs on a dispatcher thread.
- **Interactive:** the `Job` handle *is* the interactive surface —
  `pause()`/`unpause()` stop and restart new dispatch at task boundaries
  (in-flight tasks continue); `cancel()`; `wait()`. `paused=True` starts a job
  suspended before any dispatch.
- **Parallel:** independent DAG branches execute concurrently on a bounded
  worker pool (`max_workers`, default 4), verified by a barrier test that
  deadlocks unless truly parallel.
- **Scheduled runs:** deferred — requires a clock; trivially added atop
  `submit` when needed (recorded here rather than half-built).

### Plans stay immutable
The executor schedules fresh copies of the plan's tasks; the `Run` record, not
the plan, is the account of what happened. A plan can be executed, resumed,
or re-executed without state bleeding between runs.

### Retries
`RetryPolicy(max_attempts)` — bounded immediate retries; default 1 (no retry).
Each retry emits `task.retried` with the attempt number; final
`TaskResult.attempts` records the count. A missing handler fails without
retry (no attempt was ever possible). Backoff is deliberately absent in V1 —
it would put a clock in the logic path; an ADR adds it when a capability
needs it.

### Checkpointing and resume
At every task boundary (each settled task) the executor snapshots
`{completed task outputs, session working-memory namespace}` keyed by plan id
(`run.checkpointed`). `resume(plan)` replays completed results without
re-executing their handlers, restores working memory into a fresh session,
emits `run.resumed` with the restored task ids, and executes only what
remains. Resuming a plan with no checkpoint is an explicit error.
Checkpointing can be disabled (`checkpoints=False`).

### Cancellation (Invariant I7)
Cooperative for in-flight tasks — they finish and their real results are
recorded — and mandatory at task boundaries: nothing new dispatches, every
remaining task is marked CANCELLED, the run ends CANCELLED
(`run.cancelled`). Cancelling a paused job finalizes immediately.

### Run status
All completed → COMPLETED; mixed → PARTIAL; none completed → FAILED;
cancellation overrides → CANCELLED.

## Kernel notes (Stage 5 changes)

The event bus and state manager are now thread-safe (reentrant locks; a
publish is one critical section, so per-publish delivery order is unchanged) —
an implementation change explicitly permitted behind the same interfaces.
`Runtime.get_handler()` exposes the handler seam; `TaskResult.attempts` was
added to the schema.

## Events

`task.started/completed/failed/retried`, `run.started/completed/failed/
cancelled/checkpointed/resumed` — all in reserved namespaces.

## Verification

18 tests: dependency ordering, true parallelism (barrier), failure blocking,
missing-handler no-retry, plan immutability, runtime-not-started error, flaky
retry-to-success with recorded attempts/events, retry exhaustion, default
single attempt, checkpoint/resume (skip completed, restore working memory,
no-checkpoint error, disable switch), background submit/wait, mid-run cancel
(cooperative in-flight + boundary cancel), start-paused/unpause, cancel while
paused, and unique event sequencing under 8-way parallelism.
