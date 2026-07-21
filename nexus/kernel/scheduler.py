"""Scheduler: dependency-aware (DAG) ready-set computation.

Spec: docs/volume-2-modules/kernel.md. The scheduler decides *what is ready*;
it never executes anything. Ordering is deterministic: priority (higher first),
then submission order. A failed task blocks all transitive dependents.
"""

from __future__ import annotations

from nexus.schemas.core import Task, TaskStatus, TERMINAL_TASK_STATUSES


class SchedulerError(Exception):
    pass


class Scheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._order: dict[str, int] = {}
        self._dependents: dict[str, list[str]] = {}

    def submit(self, tasks: list[Task]) -> None:
        """Add a task graph. Rejects duplicate ids, unknown dependencies
        (the graph must be closed), and dependency cycles."""
        known = set(self._tasks)
        incoming = {t.id for t in tasks}
        if len(incoming) != len(tasks):
            raise SchedulerError("duplicate task ids in submission")
        clash = incoming & known
        if clash:
            raise SchedulerError(f"task ids already scheduled: {sorted(clash)}")
        for task in tasks:
            for dep in task.depends_on:
                if dep not in incoming and dep not in known:
                    raise SchedulerError(f"task {task.id!r} depends on unknown task {dep!r}")
        self._check_acyclic(tasks)
        for task in tasks:
            self._tasks[task.id] = task
            self._order[task.id] = len(self._order)
            for dep in task.depends_on:
                self._dependents.setdefault(dep, []).append(task.id)

    def _check_acyclic(self, new_tasks: list[Task]) -> None:
        # Kahn's algorithm over the combined graph.
        graph = {t.id: list(t.depends_on) for t in self._tasks.values()}
        graph.update({t.id: list(t.depends_on) for t in new_tasks})
        indegree = {tid: len(deps) for tid, deps in graph.items()}
        queue = [tid for tid, deg in indegree.items() if deg == 0]
        visited = 0
        dependents: dict[str, list[str]] = {}
        for tid, deps in graph.items():
            for dep in deps:
                dependents.setdefault(dep, []).append(tid)
        while queue:
            tid = queue.pop()
            visited += 1
            for child in dependents.get(tid, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if visited != len(graph):
            raise SchedulerError("dependency cycle detected")

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise SchedulerError(f"unknown task {task_id!r}") from None

    def ready(self) -> list[Task]:
        """Pending tasks whose dependencies have all completed, ordered by
        (priority desc, submission order)."""
        out = [
            t
            for t in self._tasks.values()
            if t.status is TaskStatus.PENDING
            and all(self._tasks[d].status is TaskStatus.COMPLETED for d in t.depends_on)
        ]
        out.sort(key=lambda t: (-t.priority, self._order[t.id]))
        return out

    def start(self, task_id: str) -> None:
        task = self.get(task_id)
        if task.status not in (TaskStatus.PENDING, TaskStatus.READY):
            raise SchedulerError(f"task {task_id!r} cannot start from {task.status}")
        task.status = TaskStatus.RUNNING

    def complete(self, task_id: str) -> None:
        self._finish(task_id, TaskStatus.COMPLETED)

    def fail(self, task_id: str) -> None:
        self._finish(task_id, TaskStatus.FAILED)
        self._block_dependents(task_id)

    def cancel(self, task_id: str) -> None:
        task = self.get(task_id)
        if task.status not in TERMINAL_TASK_STATUSES:
            task.status = TaskStatus.CANCELLED

    def _finish(self, task_id: str, status: TaskStatus) -> None:
        task = self.get(task_id)
        if task.status is not TaskStatus.RUNNING:
            raise SchedulerError(f"task {task_id!r} is not running")
        task.status = status

    def _block_dependents(self, task_id: str) -> None:
        for child_id in self._dependents.get(task_id, []):
            child = self._tasks[child_id]
            if child.status not in TERMINAL_TASK_STATUSES:
                child.status = TaskStatus.BLOCKED
                self._block_dependents(child_id)

    def done(self) -> bool:
        """True when every task is in a terminal status."""
        return all(t.status in TERMINAL_TASK_STATUSES for t in self._tasks.values())

    def statuses(self) -> dict[str, TaskStatus]:
        return {tid: t.status for tid, t in self._tasks.items()}
