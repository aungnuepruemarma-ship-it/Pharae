"""Deterministic rule-based planning: Intent → Plan (task DAG).

Plan shape: an optional ``gather-context`` research task (when the intent
carries context refs) → goal tasks chained sequentially (goal order is
meaningful — it came from numbered lists and "and then" decomposition) → a
``verify`` task depending on every goal, so verification is a structural part
of every plan, not an afterthought.

Goals map to capability *types* through an ordered keyword table — never to
vendors; binding is the router's job. Unrecognized goals default to ``code``
(the maker default). Improving the table is routine rule-tuning against the
golden tests, not an architecture change.
"""

from __future__ import annotations

import hashlib
import re

from nexus.kernel.events import EventBus
from nexus.schemas.core import Evidence, Intent, Plan, Task, TaskStatus

# Ordered: first matching bucket wins. "Test the scraper" is a verify task,
# so verify outranks browser; browser outranks research.
_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("verify", ("test", "verify", "validate", "benchmark", "audit", "qa")),
    ("browser", ("browse", "scrape", "visit", "navigate", "crawl")),
    (
        "research",
        (
            "research", "investigate", "study", "compare", "survey", "explore",
            "analyze", "analyse", "review", "summarize", "summarise", "find",
            "gather", "read", "search",
        ),
    ),
]
_DEFAULT_TYPE = "code"


class PlannerError(Exception):
    pass


def _classify(goal: str) -> str:
    lowered = goal.lower()
    for capability_type, keywords in _TYPE_RULES:
        for keyword in keywords:
            if re.search(rf"\b{keyword}", lowered):
                return capability_type
    return _DEFAULT_TYPE


def _content_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:12]}"


class Planner:
    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus

    # -- planning ------------------------------------------------------------

    def plan(self, intent: Intent) -> Plan:
        """Build a plan from an intent. Open questions on the intent do not
        block planning of the goals that exist — they remain on the intent
        for the user; an intent with no goals at all is unplannable."""
        if not intent.goals:
            raise PlannerError(
                f"intent {intent.id!r} has no goals to plan"
                + (f" (open questions: {intent.open_questions})" if intent.open_questions else "")
            )
        constraints = list(intent.constraints)
        tasks: list[Task] = []

        gather_id: str | None = None
        if intent.context_refs:
            gather_id = "gather-context"
            tasks.append(
                Task(
                    id=gather_id,
                    capability_type="research",
                    payload={
                        "description": "Gather context from referenced sources",
                        "context_refs": list(intent.context_refs),
                        "constraints": constraints,
                    },
                )
            )

        goal_ids: list[str] = []
        for index, goal in enumerate(intent.goals, start=1):
            task_id = f"goal-{index}"
            previous = goal_ids[-1] if goal_ids else gather_id
            tasks.append(
                Task(
                    id=task_id,
                    capability_type=_classify(goal),
                    payload={"description": goal, "constraints": constraints},
                    depends_on=[previous] if previous else [],
                )
            )
            goal_ids.append(task_id)

        tasks.append(
            Task(
                id="verify",
                capability_type="verify",
                payload={
                    "description": "Verify results against the objective",
                    "desired_outcomes": list(intent.desired_outcomes),
                    "constraints": constraints,
                },
                depends_on=list(goal_ids),
            )
        )

        plan = Plan(
            id=_content_id(
                "plan",
                intent.id,
                "|".join(intent.goals),
                "|".join(intent.constraints),
                "|".join(intent.desired_outcomes),
                "|".join(intent.context_refs),
            ),
            tasks=tasks,
            intent_id=intent.id,
        )
        if self._bus is not None:
            self._bus.publish(
                "plan.created",
                {"plan_id": plan.id, "intent_id": intent.id, "task_count": len(tasks)},
            )
        return plan

    # -- re-planning ---------------------------------------------------------

    def replan(
        self,
        plan: Plan,
        evidence: Evidence,
        completed: set[str] = frozenset(),
    ) -> Plan:
        """Produce a successor plan after a failure. The original plan is
        never mutated: completed tasks are dropped, dependencies on them are
        released, statuses reset, and router bindings cleared so routing
        decides afresh. Provenance links the old plan and the failure
        evidence."""
        kept = [t for t in plan.tasks if t.id not in completed]
        if not kept:
            raise PlannerError(
                f"nothing to replan: every task of {plan.id!r} is completed"
            )
        kept_ids = {t.id for t in kept}
        tasks = [
            Task(
                id=t.id,
                capability_type=t.capability_type,
                payload=dict(t.payload),
                depends_on=[d for d in t.depends_on if d in kept_ids],
                priority=t.priority,
                status=TaskStatus.PENDING,
                capability_binding=None,
            )
            for t in kept
        ]
        successor = Plan(
            id=_content_id("plan", plan.id, evidence.id, ",".join(sorted(completed))),
            tasks=tasks,
            intent_id=plan.intent_id,
            provenance=f"{plan.id}:{evidence.id}",
        )
        if self._bus is not None:
            self._bus.publish(
                "plan.revised",
                {
                    "plan_id": successor.id,
                    "provenance": successor.provenance,
                    "dropped": sorted(set(completed) & {t.id for t in plan.tasks}),
                },
            )
        return successor
