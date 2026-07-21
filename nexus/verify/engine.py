"""Verification: run → Evidence with recorded scoring inputs.

Verifiability (the ``verified`` flag) and quality (``confidence``, check
results) are deliberately separate judgments:

- **verified** — could trustworthy evidence be established at all? Requires a
  terminal run, a result for every planned task, and (when a bus is present)
  an event trace consistent with the results. Anything else is unverifiable,
  and the gates downstream reject it.
- **confidence** — how good does the verified evidence look? A deterministic
  weighted score over task completion, check pass rate, first-attempt rate,
  and trace consistency; every input is recorded in the evidence so the score
  can be audited and re-derived.

Checks are pluggable per capability type — the seam where capability-specific
verifiers (code → run tests, research → cross-check sources, browser → assert
page state) attach as those capabilities arrive. A crashing checker records a
failed check; it never crashes verification.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from nexus.kernel.events import EventBus
from nexus.schemas.core import (
    Artifact,
    Evidence,
    Plan,
    Run,
    RunStatus,
    Task,
    TaskResult,
    TaskStatus,
)

Check = Callable[[TaskResult, Task], "bool | tuple[bool, str]"]

_TERMINAL_RUN_STATUSES = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.PARTIAL, RunStatus.CANCELLED}
)
_WEIGHTS = {
    "task_completion": 0.5,
    "check_pass_rate": 0.3,
    "first_attempt_rate": 0.1,
    "trace_consistent": 0.1,
}


class VerificationEngine:
    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus
        self._checks: dict[str, list[tuple[str, Check]]] = {}

    def register_check(self, capability_type: str, name: str, check: Check) -> None:
        """Register a per-capability-type check. The check receives the task's
        result and the task; it returns bool or (bool, detail)."""
        self._checks.setdefault(capability_type, []).append((name, check))

    # -- verification --------------------------------------------------------

    def verify(
        self, run: Run, plan: Plan | None = None, artifacts: list[Artifact] | None = None
    ) -> Evidence:
        logs: list[str] = [f"run {run.id} status {run.status.value}"]
        reasons: list[str] = []

        if run.status not in _TERMINAL_RUN_STATUSES:
            reasons.append(f"run is not terminal (status {run.status.value})")
        if plan is not None:
            missing = [t.id for t in plan.tasks if t.id not in run.task_results]
            if missing:
                reasons.append(f"tasks without results: {missing}")
        else:
            logs.append("no plan provided: capability-type checks and reproducibility skipped")

        trace_ok: bool | None = None
        if self._bus is not None:
            trace_ok, trace_problems = self._trace_consistent(run)
            if not trace_ok:
                reasons.append(f"event trace inconsistent: {'; '.join(trace_problems)}")

        verified = not reasons
        for reason in reasons:
            logs.append(f"unverified: {reason}")

        checks = self._run_checks(run, plan, logs)
        success = run.status is RunStatus.COMPLETED and all(c["passed"] for c in checks)

        scoring = self._scoring_inputs(run, checks, trace_ok)
        confidence = self._confidence(scoring) if verified else 0.0

        evidence = Evidence(
            id=self._evidence_id(run, plan, verified),
            run_id=run.id,
            verified=verified,
            confidence=confidence,
            logs=logs,
            artifact_ids=[a.id for a in (artifacts or [])],
            test_results={"success": success, "checks": checks, "scoring": scoring},
            reproducible=None if plan is None else verified,
            cost_report=self._cost_report(run),
        )

        if self._bus is not None:
            if verified:
                self._bus.publish(
                    "run.verified",
                    {"run_id": run.id, "evidence_id": evidence.id, "confidence": confidence},
                )
            else:
                self._bus.publish("run.unverified", {"run_id": run.id, "reasons": reasons})
        return evidence

    # -- checks --------------------------------------------------------------

    def _run_checks(
        self, run: Run, plan: Plan | None, logs: list[str]
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = [
            {
                "name": "all-tasks-completed",
                "task_id": None,
                "passed": run.status is RunStatus.COMPLETED,
                "detail": f"run status {run.status.value}",
            }
        ]
        if plan is not None:
            for task in plan.tasks:
                result = run.task_results.get(task.id)
                if result is None:
                    continue  # already an unverifiability reason
                for name, check in self._checks.get(task.capability_type, []):
                    checks.append(self._apply_check(name, check, result, task))
        for entry in checks:
            outcome = "pass" if entry["passed"] else "fail"
            logs.append(
                f"check {entry['name']}"
                + (f" [{entry['task_id']}]" if entry["task_id"] else "")
                + f": {outcome} ({entry['detail']})"
            )
        return checks

    @staticmethod
    def _apply_check(name: str, check: Check, result: TaskResult, task: Task) -> dict[str, Any]:
        try:
            outcome = check(result, task)
        except Exception as exc:
            return {"name": name, "task_id": task.id, "passed": False, "detail": repr(exc)}
        if isinstance(outcome, tuple):
            passed, detail = outcome
        else:
            passed, detail = bool(outcome), ""
        return {"name": name, "task_id": task.id, "passed": passed, "detail": detail}

    # -- trace consistency (Invariant I6) ------------------------------------

    def _trace_consistent(self, run: Run) -> tuple[bool, list[str]]:
        """The run's event trace must agree with its recorded results:
        run.started and a terminal run event present; every task.started has a
        terminal task event. Tasks completed without a start (checkpoint
        replays) are permitted — this is consistency, not completeness."""
        events = [e for e in self._bus.log() if e.payload.get("run_id") == run.id]
        problems = []
        if not any(e.topic == "run.started" for e in events):
            problems.append("run.started missing")
        if not any(
            e.topic in ("run.completed", "run.failed", "run.cancelled") for e in events
        ):
            problems.append("terminal run event missing")
        started = {e.payload.get("task_id") for e in events if e.topic == "task.started"}
        settled = {
            e.payload.get("task_id")
            for e in events
            if e.topic in ("task.completed", "task.failed")
        }
        orphans = sorted(started - settled)
        if orphans:
            problems.append(f"tasks started but never settled: {orphans}")
        return (not problems), problems

    # -- scoring -------------------------------------------------------------

    @staticmethod
    def _scoring_inputs(
        run: Run, checks: list[dict[str, Any]], trace_ok: bool | None
    ) -> dict[str, float]:
        results = list(run.task_results.values())
        completed = [r for r in results if r.status is TaskStatus.COMPLETED]
        inputs = {
            "task_completion": len(completed) / len(results) if results else 1.0,
            "check_pass_rate": (
                sum(1 for c in checks if c["passed"]) / len(checks) if checks else 1.0
            ),
            "first_attempt_rate": (
                sum(1 for r in completed if r.attempts == 1) / len(completed)
                if completed
                else 1.0
            ),
        }
        if trace_ok is not None:
            inputs["trace_consistent"] = 1.0 if trace_ok else 0.0
        return inputs

    @staticmethod
    def _confidence(scoring: dict[str, float]) -> float:
        total_weight = sum(_WEIGHTS[name] for name in scoring)
        weighted = sum(_WEIGHTS[name] * value for name, value in scoring.items())
        return round(weighted / total_weight, 6)

    # -- bookkeeping ---------------------------------------------------------

    @staticmethod
    def _evidence_id(run: Run, plan: Plan | None, verified: bool) -> str:
        fingerprint = "\x00".join(
            [
                run.id,
                run.status.value,
                str(verified),
                plan.id if plan is not None else "",
                repr(
                    sorted(
                        (r.task_id, r.status.value, r.attempts)
                        for r in run.task_results.values()
                    )
                ),
            ]
        )
        return f"ev-{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:12]}"

    @staticmethod
    def _cost_report(run: Run) -> dict[str, Any]:
        results = list(run.task_results.values())
        attempts = sum(r.attempts for r in results)
        return {
            "duration_s": max(0.0, (run.finished_at or run.started_at) - run.started_at),
            "tasks": len(results),
            "attempts": attempts,
            "retries": sum(max(0, r.attempts - 1) for r in results),
        }
