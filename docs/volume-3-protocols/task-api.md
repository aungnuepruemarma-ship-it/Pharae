# Protocol — Task API (v1)

Schema: `nexus/schemas/core.py` (`Task`, `Plan`, `Run`). Kernel scope
implemented in `nexus/kernel/scheduler.py` and `nexus/kernel/runtime.py`.

## Task

```
Task {
  id: str                    # unique within a plan
  capability_type: str       # e.g. "code", "research" — NEVER a vendor
  payload: dict              # capability-type-specific input
  depends_on: [str]          # task ids within the same plan
  priority: int              # higher runs earlier among ready tasks (default 0)
  status: PENDING | READY | RUNNING | COMPLETED | FAILED | BLOCKED | CANCELLED
  capability_binding: str?   # "name@version" — router output, attached at
                             # routing time, never authored in a plan
}
```

Rules:

- `capability_type` is a type string; binding to a concrete capability is the
  Router's output, attached at routing time, never authored in a plan.
- Dependency graphs must be acyclic and closed (all `depends_on` ids exist in
  the plan); the scheduler rejects violations at submission.
- Status transitions: `PENDING → READY → RUNNING → {COMPLETED | FAILED}`;
  `PENDING/READY → BLOCKED` when an ancestor fails; any non-terminal → `CANCELLED`.

## Plan

```
Plan { id, intent_id?, tasks: [Task], created_at, provenance? }
```

Plans are immutable once execution starts; re-planning creates a successor plan
with `provenance` linking to the failed plan and its evidence.

## Run

```
Run {
  id, plan_id, session_id,
  status: RUNNING | COMPLETED | FAILED | PARTIAL | CANCELLED,
  task_results: { task_id: { status, output?, error?, attempts } },
  started_at, finished_at?
}
```

A run is the unit of verification and learning. `PARTIAL` means some tasks
completed and some were blocked/failed.

## Events

`task.started`, `task.completed`, `task.failed`, `task.retried` (payload:
`task_id`, `run_id`, plus `attempt` on retry); `run.started`, `run.completed`,
`run.failed`, `run.cancelled`, `run.checkpointed`, `run.resumed` (payload:
`run_id` plus mode-specific fields).
