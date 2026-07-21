"""Kernel runtime: lifecycle + plan execution through capability-type handlers.

Spec: docs/volume-2-modules/kernel.md. Handlers register by capability *type*
string ("code", "research") — the seam where the Capability Layer attaches.
The kernel neither knows nor cares what a handler does (Kernel Invariant I1).
A handler exception fails its task (blocking dependents); it never crashes the
runtime.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from nexus.kernel.events import EventBus
from nexus.kernel.scheduler import Scheduler
from nexus.kernel.sessions import Session, SessionManager
from nexus.kernel.state import StateManager
from nexus.schemas.core import Plan, Run, RunStatus, Task, TaskResult, TaskStatus


@dataclass
class RunContext:
    """What a handler is given besides its task: the session's working-memory
    namespace and the event bus. Handlers get no path to any other state."""

    run_id: str
    session: Session
    state: StateManager
    bus: EventBus

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(self.session.namespace, key, default)

    def set(self, key: str, value: Any) -> None:
        self.state.set(self.session.namespace, key, value)


Handler = Callable[[Task, RunContext], Any]


class RuntimeError_(Exception):
    pass


class Runtime:
    def __init__(
        self,
        bus: EventBus | None = None,
        state: StateManager | None = None,
    ) -> None:
        self.bus = bus or EventBus()
        self.state = state or StateManager()
        self.sessions = SessionManager(self.bus, self.state)
        self._handlers: dict[str, Handler] = {}
        self._running = False
        self._run_counter = 0

    # -- lifecycle -----------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.bus.publish("runtime.started", {})

    def stop(self) -> None:
        if not self._running:
            return
        for session in self.sessions.active():
            self.sessions.end(session.id)
        self._running = False
        self.bus.publish("runtime.stopped", {})

    # -- handlers ------------------------------------------------------------

    def register_handler(self, key: str, handler: Handler) -> None:
        """Keys are capability type strings ("code") or capability ids
        ("calc.local@1.0.0") — plugins register under their ids so multiple
        capabilities of one type coexist."""
        if not key.strip():
            raise RuntimeError_("handler key must be non-empty")
        self._handlers[key] = handler

    def unregister_handler(self, key: str) -> bool:
        return self._handlers.pop(key, None) is not None

    def handler_types(self) -> list[str]:
        return sorted(self._handlers)

    def get_handler(self, key: str) -> Handler | None:
        return self._handlers.get(key)

    def resolve_handler(self, task: Task) -> Handler | None:
        """The router's binding wins; capability type is the fallback — the
        runtime honors routing decisions exactly."""
        if task.capability_binding and task.capability_binding in self._handlers:
            return self._handlers[task.capability_binding]
        return self._handlers.get(task.capability_type)

    # -- execution -----------------------------------------------------------

    def execute(self, plan: Plan, session: Session | None = None) -> Run:
        """Run a plan to completion (or until nothing more can run).

        Synchronous single-worker execution — the Stage 4 executor grows this
        behind the same interface."""
        if not self._running:
            raise RuntimeError_("runtime is not started")
        session = session or self.sessions.create()

        self._run_counter += 1
        run = Run(id=f"run-{self._run_counter:06x}", plan_id=plan.id, session_id=session.id)
        self.bus.publish("run.started", {"run_id": run.id, "plan_id": plan.id, "session_id": session.id})

        scheduler = Scheduler()
        scheduler.submit(plan.tasks)

        while not scheduler.done():
            ready = scheduler.ready()
            if not ready:
                break  # remaining tasks are unreachable (failed ancestors)
            for task in ready:
                self._execute_task(task, scheduler, run, session)

        for task_id, status in scheduler.statuses().items():
            if task_id not in run.task_results:
                run.task_results[task_id] = TaskResult(task_id=task_id, status=status)

        run.status = self._run_status(run)
        run.finished_at = time.time()
        topic = "run.completed" if run.status is RunStatus.COMPLETED else "run.failed"
        self.bus.publish(topic, {"run_id": run.id, "status": run.status.value})
        return run

    def _execute_task(self, task: Task, scheduler: Scheduler, run: Run, session: Session) -> None:
        scheduler.start(task.id)
        self.bus.publish(
            "task.started",
            {"task_id": task.id, "run_id": run.id, "session_id": session.id},
        )
        handler = self.resolve_handler(task)
        if handler is None:
            scheduler.fail(task.id)
            run.task_results[task.id] = TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"no handler registered for capability type {task.capability_type!r}",
            )
            self.bus.publish("task.failed", {"task_id": task.id, "run_id": run.id})
            return
        ctx = RunContext(run_id=run.id, session=session, state=self.state, bus=self.bus)
        try:
            output = handler(task, ctx)
        except Exception as exc:
            scheduler.fail(task.id)
            run.task_results[task.id] = TaskResult(
                task_id=task.id, status=TaskStatus.FAILED, error=repr(exc)
            )
            self.bus.publish("task.failed", {"task_id": task.id, "run_id": run.id})
            return
        scheduler.complete(task.id)
        run.task_results[task.id] = TaskResult(
            task_id=task.id, status=TaskStatus.COMPLETED, output=output
        )
        self.bus.publish("task.completed", {"task_id": task.id, "run_id": run.id})

    @staticmethod
    def _run_status(run: Run) -> RunStatus:
        statuses = {r.status for r in run.task_results.values()}
        if statuses <= {TaskStatus.COMPLETED}:
            return RunStatus.COMPLETED
        if TaskStatus.COMPLETED in statuses:
            return RunStatus.PARTIAL
        return RunStatus.FAILED
