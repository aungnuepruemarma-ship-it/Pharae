"""Full plan executor over the kernel primitives.

Division of labor: the kernel scheduler decides *what is ready*; this module
decides *how it runs* — worker pool, retries, checkpoints, pause/cancel.
Handlers still register on the kernel runtime by capability type; the executor
never chooses capabilities (Router's job) and hands handlers only their task
and the session's working-memory context (Invariant I3).

Cancellation semantics (Invariant I7): cooperative for in-flight tasks — they
are allowed to finish and their real results are recorded — and mandatory at
task boundaries: nothing new is dispatched, every remaining task is CANCELLED.

Checkpoints are state-manager snapshots taken at task boundaries: completed
outputs plus the session's working-memory namespace, keyed by plan id.
``resume`` replays completed results without re-executing them and restores
the working memory the original run had built up.
"""

from __future__ import annotations

import copy
import threading
import time
from concurrent import futures as cf
from dataclasses import dataclass

from nexus.kernel.runtime import RunContext, Runtime
from nexus.kernel.scheduler import Scheduler
from nexus.kernel.sessions import Session
from nexus.schemas.core import (
    Plan,
    Run,
    RunStatus,
    Task,
    TaskResult,
    TaskStatus,
    TERMINAL_TASK_STATUSES,
)

_POLL_S = 0.05  # responsiveness bound for pause/cancel at task boundaries
_CHECKPOINT_NS = "checkpoints"


class ExecutorError(Exception):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded immediate retries. ``max_attempts=1`` means no retry. Backoff
    is deliberately absent in V1 — it would put a clock in the logic path;
    an ADR can add it when a real capability needs it."""

    max_attempts: int = 1


class Job:
    """Handle for an interactive or background run: pause/unpause stop new
    dispatch at task boundaries; cancel ends the run (cooperatively for
    in-flight tasks). ``wait`` joins the run and returns the Run record."""

    def __init__(self, plan: Plan, start_paused: bool = False) -> None:
        self.plan = plan
        self.run: Run | None = None
        self._cancel = threading.Event()
        self._resume = threading.Event()
        if not start_paused:
            self._resume.set()
        self._thread: threading.Thread | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set() and not self._cancel.is_set()

    def pause(self) -> None:
        self._resume.clear()

    def unpause(self) -> None:
        self._resume.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()  # wake a paused dispatcher so it can finalize

    def wait(self, timeout: float | None = None) -> Run | None:
        if self._thread is not None:
            self._thread.join(timeout)
        return self.run


class Executor:
    def __init__(
        self,
        runtime: Runtime,
        max_workers: int = 4,
        retry: RetryPolicy = RetryPolicy(),
        checkpoints: bool = True,
    ) -> None:
        self._runtime = runtime
        self._bus = runtime.bus
        self._state = runtime.state
        self._max_workers = max_workers
        self._retry = retry
        self._checkpoints = checkpoints
        self._counter = 0
        self._lock = threading.Lock()

    # -- public API ----------------------------------------------------------

    def execute(self, plan: Plan, session: Session | None = None) -> Run:
        """Synchronous execution to a terminal state."""
        job = Job(plan)
        return self._run(plan, session, job, restored=None)

    def submit(self, plan: Plan, session: Session | None = None, paused: bool = False) -> Job:
        """Background execution; the returned Job is the interactive control
        surface (pause/unpause/cancel/wait)."""
        if not self._runtime.running:
            raise ExecutorError("runtime is not started")
        job = Job(plan, start_paused=paused)
        thread = threading.Thread(
            target=self._run, args=(plan, session, job, None), daemon=True
        )
        job._thread = thread
        thread.start()
        return job

    def resume(self, plan: Plan, session: Session | None = None) -> Run:
        """Resume a plan from its last checkpoint: completed tasks are
        replayed from recorded outputs, working memory is restored, and only
        unfinished tasks execute."""
        checkpoint = self._state.get(_CHECKPOINT_NS, plan.id)
        if checkpoint is None:
            raise ExecutorError(f"no checkpoint recorded for plan {plan.id!r}")
        job = Job(plan)
        return self._run(plan, session, job, restored=copy.deepcopy(checkpoint))

    # -- run loop ------------------------------------------------------------

    def _run(self, plan: Plan, session: Session | None, job: Job, restored: dict | None) -> Run:
        if not self._runtime.running:
            raise ExecutorError("runtime is not started")
        session = session or self._runtime.sessions.create()
        with self._lock:
            self._counter += 1
            run = Run(
                id=f"run-e{self._counter:05x}", plan_id=plan.id, session_id=session.id
            )

        # Fresh task copies: plans stay immutable and re-executable; the Run
        # record, not the plan, is the account of what happened.
        tasks = [
            Task(
                id=t.id,
                capability_type=t.capability_type,
                payload=copy.deepcopy(t.payload),
                depends_on=list(t.depends_on),
                priority=t.priority,
                capability_binding=t.capability_binding,
            )
            for t in plan.tasks
        ]
        scheduler = Scheduler()
        scheduler.submit(tasks)

        if restored is not None:
            self._state.restore(restored.get("session_state", {}), session.namespace)
            replayed = []
            for task_id, output in restored.get("completed", {}).items():
                if any(t.id == task_id for t in tasks):
                    scheduler.start(task_id)
                    scheduler.complete(task_id)
                    run.task_results[task_id] = TaskResult(
                        task_id=task_id, status=TaskStatus.COMPLETED, output=output
                    )
                    replayed.append(task_id)
            self._bus.publish(
                "run.resumed",
                {"run_id": run.id, "plan_id": plan.id, "restored": sorted(replayed)},
            )

        self._bus.publish(
            "run.started",
            {"run_id": run.id, "plan_id": plan.id, "session_id": session.id},
        )

        ctx = RunContext(run_id=run.id, session=session, state=self._state, bus=self._bus)
        inflight: dict[cf.Future, tuple[Task, int]] = {}

        with cf.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            while not job.cancelled:
                if not job.paused:
                    for task in scheduler.ready():
                        self._dispatch(task, 1, scheduler, run, ctx, pool, inflight)
                if not inflight:
                    if job.paused and not scheduler.done():
                        job._resume.wait(_POLL_S)
                        continue
                    break  # done, or blocked by failed ancestors
                done, _ = cf.wait(inflight, timeout=_POLL_S, return_when=cf.FIRST_COMPLETED)
                for future in done:
                    task, attempt = inflight.pop(future)
                    self._settle(
                        future, task, attempt, scheduler, run, ctx, pool, inflight,
                        allow_retry=not job.cancelled,
                    )
            if job.cancelled and inflight:
                cf.wait(inflight, return_when=cf.ALL_COMPLETED)  # cooperative finish
                for future, (task, attempt) in list(inflight.items()):
                    self._settle(
                        future, task, attempt, scheduler, run, ctx, pool, inflight,
                        allow_retry=False,
                    )
                inflight.clear()

        if job.cancelled:
            for task_id, status in scheduler.statuses().items():
                if status not in TERMINAL_TASK_STATUSES:
                    scheduler.cancel(task_id)

        for task_id, status in scheduler.statuses().items():
            if task_id not in run.task_results:
                run.task_results[task_id] = TaskResult(task_id=task_id, status=status)

        run.status = self._final_status(run, cancelled=job.cancelled)
        run.finished_at = time.time()
        topic = {
            RunStatus.COMPLETED: "run.completed",
            RunStatus.CANCELLED: "run.cancelled",
        }.get(run.status, "run.failed")
        self._bus.publish(topic, {"run_id": run.id, "status": run.status.value})
        job.run = run
        return run

    # -- task lifecycle ------------------------------------------------------

    def _dispatch(
        self,
        task: Task,
        attempt: int,
        scheduler: Scheduler,
        run: Run,
        ctx: RunContext,
        pool: cf.ThreadPoolExecutor,
        inflight: dict[cf.Future, tuple[Task, int]],
    ) -> None:
        handler = self._runtime.resolve_handler(task)
        if attempt == 1:
            scheduler.start(task.id)
            self._bus.publish("task.started", {"task_id": task.id, "run_id": run.id})
        if handler is None:  # not retryable: no attempt was ever possible
            scheduler.fail(task.id)
            run.task_results[task.id] = TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"no handler registered for capability type {task.capability_type!r}",
                attempts=attempt,
            )
            self._bus.publish("task.failed", {"task_id": task.id, "run_id": run.id})
            self._save_checkpoint(run, ctx)
            return
        future = pool.submit(self._invoke, handler, task, ctx)
        inflight[future] = (task, attempt)

    @staticmethod
    def _invoke(handler, task: Task, ctx: RunContext) -> tuple[object, str | None]:
        try:
            return handler(task, ctx), None
        except Exception as exc:
            return None, repr(exc)

    def _settle(
        self,
        future: cf.Future,
        task: Task,
        attempt: int,
        scheduler: Scheduler,
        run: Run,
        ctx: RunContext,
        pool: cf.ThreadPoolExecutor,
        inflight: dict[cf.Future, tuple[Task, int]],
        allow_retry: bool,
    ) -> None:
        output, error = future.result()
        if error is not None and allow_retry and attempt < self._retry.max_attempts:
            self._bus.publish(
                "task.retried",
                {"task_id": task.id, "run_id": run.id, "attempt": attempt + 1},
            )
            handler = self._runtime.resolve_handler(task)
            retry_future = pool.submit(self._invoke, handler, task, ctx)
            inflight[retry_future] = (task, attempt + 1)
            return
        if error is not None:
            scheduler.fail(task.id)
            run.task_results[task.id] = TaskResult(
                task_id=task.id, status=TaskStatus.FAILED, error=error, attempts=attempt
            )
            self._bus.publish("task.failed", {"task_id": task.id, "run_id": run.id})
        else:
            scheduler.complete(task.id)
            run.task_results[task.id] = TaskResult(
                task_id=task.id, status=TaskStatus.COMPLETED, output=output, attempts=attempt
            )
            self._bus.publish("task.completed", {"task_id": task.id, "run_id": run.id})
        self._save_checkpoint(run, ctx)

    # -- checkpointing -------------------------------------------------------

    def _save_checkpoint(self, run: Run, ctx: RunContext) -> None:
        if not self._checkpoints:
            return
        completed = {
            r.task_id: r.output
            for r in run.task_results.values()
            if r.status is TaskStatus.COMPLETED
        }
        self._state.set(
            _CHECKPOINT_NS,
            run.plan_id,
            copy.deepcopy(
                {
                    "run_id": run.id,
                    "completed": completed,
                    "session_state": self._state.snapshot(ctx.session.namespace),
                }
            ),
        )
        self._bus.publish(
            "run.checkpointed",
            {"run_id": run.id, "plan_id": run.plan_id, "completed_count": len(completed)},
        )

    @staticmethod
    def _final_status(run: Run, cancelled: bool) -> RunStatus:
        if cancelled:
            return RunStatus.CANCELLED
        statuses = {r.status for r in run.task_results.values()}
        if statuses <= {TaskStatus.COMPLETED}:
            return RunStatus.COMPLETED
        if TaskStatus.COMPLETED in statuses:
            return RunStatus.PARTIAL
        return RunStatus.FAILED
