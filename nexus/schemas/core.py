"""Core data objects: Objective, Intent, Task, Plan, Run, Evidence, Artifact.

Spec: docs/volume-3-protocols/task-api.md. Tasks declare a capability *type*
(never a vendor) — Kernel Invariant I1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED}
)


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class Objective:
    """The user's goal, as given. Input to the intent engine (Stage 1)."""

    id: str
    text: str
    context_refs: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class Intent:
    """Structured parse of an objective. Output of the intent engine."""

    id: str
    objective_id: str
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    desired_outcomes: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)


@dataclass
class Task:
    """A unit of work; a node in a plan.

    ``capability_type`` is authored by the planner and is always a type
    string, never a vendor. ``capability_binding`` ("name@version") is the
    router's output, attached at routing time — never authored in a plan."""

    id: str
    capability_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    capability_binding: str | None = None


@dataclass
class Plan:
    """An execution DAG. Immutable once execution starts; re-planning creates
    a successor plan whose ``provenance`` links back to the failed plan."""

    id: str
    tasks: list[Task]
    intent_id: str | None = None
    provenance: str | None = None
    created_at: float = field(default_factory=time.time)

    def task_ids(self) -> list[str]:
        return [t.id for t in self.tasks]


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    attempts: int = 1


@dataclass
class Run:
    """One complete attempt at an objective — the unit of verification and
    learning."""

    id: str
    plan_id: str
    session_id: str
    status: RunStatus = RunStatus.RUNNING
    task_results: dict[str, TaskResult] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


@dataclass
class Artifact:
    """A produced object: code, docs, datasets, reports, screenshots."""

    id: str
    run_id: str
    kind: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """What proves a result. The only permitted input to learning and
    long-term memory (Kernel Invariant I2)."""

    id: str
    run_id: str
    verified: bool
    confidence: float
    logs: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    reproducible: bool | None = None
    cost_report: dict[str, Any] = field(default_factory=dict)
