# Protocol — Event Bus (v1)

Implemented: `nexus/kernel/events.py`.

## Model

- An **event** is `{ topic, payload, seq, timestamp, correlation_id? }`.
  Payloads are plain dicts of JSON-serializable values; no live objects.
- **Topics** are dot-separated lowercase strings: `<noun>.<verb-past>` —
  `task.completed`, `session.started`, `capability.registered`.
- **Subscriptions** match an exact topic, a prefix wildcard (`task.*`), or
  everything (`*`).

## Delivery Semantics (v1)

- Synchronous, in-process, at-most-once, in subscription order. Deterministic:
  same publish sequence → same delivery sequence.
- A subscriber exception is captured and republished on `bus.error`
  (`{ topic, error, subscriber }`); it never propagates to the publisher.
  `bus.error` handler failures are swallowed (no error loops).
- Every event is appended to the **event log** with a monotonic `seq`. The log
  is the replay/observability primitive (Invariant I6).

A future async bus may change *timing* but not ordering guarantees per topic,
and never the envelope shape.

## Reserved Topic Namespaces

| Prefix | Emitter |
|--------|---------|
| `runtime.*` | Kernel runtime lifecycle |
| `session.*` | Session manager |
| `task.*` | Scheduler / executor |
| `plan.*` | Planner |
| `route.*` | Router |
| `run.*` | Executor / verification |
| `capability.*` | Registry |
| `memory.*` | Memory system |
| `policy.*`, `skill.*` | Cog |
| `bus.*` | The bus itself |

New namespaces require a spec update here.
