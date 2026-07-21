# Module Spec — Kernel

**Status:** Implemented (Stage 0). Code: `nexus/kernel/`. Tests: `tests/`.

## Purpose

The minimal, provider-agnostic core: lifecycle, events, state, sessions, and
scheduling. Everything else in the system plugs into the kernel through the
interfaces in Volume 3; nothing else lives inside it.

## Boundary

**Owns:** runtime lifecycle, event loop, scheduling, session management, state,
context propagation.

**Must never know about:** models, vendors, browsers, cloud providers, HTTP,
prompts. (Invariant I1.) The kernel imports only the Python standard library and
`nexus.schemas`.

## Components

### Event Bus (`nexus/kernel/events.py`)

- Topic-based publish/subscribe. Topics are dot-separated strings
  (`task.completed`, `session.started`); subscriptions support a trailing
  wildcard (`task.*`, `*`).
- Synchronous, deterministic delivery in subscription order (V1). An async bus
  is a permitted future change behind the same interface.
- Every published event is appended to an in-memory **event log** with a
  monotonic sequence number and timestamp — the primitive for replay and
  observability (Invariant I6).
- Subscriber exceptions are captured and published to `bus.error`, never
  propagated to the publisher: one bad subscriber cannot break the loop.

### State Manager (`nexus/kernel/state.py`)

- Namespaced key-value state: `get/set/delete(namespace, key)`.
- **Snapshot/restore** of a namespace or the whole store — the checkpointing
  primitive used for recovery and resume.
- Snapshots are deep copies; mutating live state never corrupts a checkpoint.

### Session Manager (`nexus/kernel/sessions.py`)

- `create() → Session`, `get(id)`, `end(id)`; sessions are `ACTIVE` or `ENDED`.
- Each session owns an isolated state namespace (`session:<id>`) and its id is
  the correlation id stamped on session-scoped events.
- Ending a session emits `session.ended` and releases its namespace.

### Scheduler (`nexus/kernel/scheduler.py`)

- Dependency-aware (DAG): tasks are added with dependency edges; `ready()`
  returns tasks whose dependencies have all completed.
- Rejects dependency cycles and unknown dependencies at submission time.
- Priorities break ties among ready tasks; ordering is **deterministic**
  (priority, then insertion order).
- `complete(id)` / `fail(id)` transition tasks; failure marks all transitive
  dependents `BLOCKED`.
- The scheduler decides *what is ready*; it never executes anything.

### Runtime (`nexus/kernel/runtime.py`)

- Lifecycle: `start()` / `stop()`; emits `runtime.started` / `runtime.stopped`.
- Handlers register by **capability type string** (`"code"`, `"research"`) —
  this seam is where the Capability Layer will attach; the kernel neither knows
  nor cares what a handler does.
- `execute(plan)` runs a plan to completion: repeatedly asks the scheduler for
  ready tasks, dispatches to handlers, records results, emits
  `task.started` / `task.completed` / `task.failed` events, and returns a `Run`
  with per-task results and status.
- A handler exception fails the task (and blocks dependents); it never crashes
  the runtime.

## Verification

Every component has stdlib `unittest` coverage (`tests/`), including: wildcard
delivery, event-log ordering, subscriber-error isolation, snapshot isolation,
session lifecycle, cycle rejection, deterministic ready-ordering, failure
blocking, end-to-end plan execution with dependency ordering, and
recovery-relevant behaviors.

Run: `python3 -m unittest discover -s tests`.

## Non-Goals

No persistence (memory arrives in Stage 5 behind the Memory API), no async/
concurrency runtime (Stage 4 executor concern), no capability manifests
(Stage 2). Adding any of these *inside* the kernel requires an ADR.
