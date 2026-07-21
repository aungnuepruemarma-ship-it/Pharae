"""Reasoning-budget assessment: Intent → ThinkingBudget.

Three modes, matching the blueprint's L4 (Reflex / Deliberative / Research):

- **REFLEX** — a single simple goal, no constraints, refs, or open questions:
  solve it directly. Minimal orchestration, no context gathering, no retries.
- **RESEARCH** — the objective needs information gathering: a research-shaped
  goal, context refs to read, or several open questions. Widest budget.
- **DELIBERATIVE** — everything in between (the safe default).

The policy is a transparent, ordered rule set over intent *features* only —
deterministic, no model, no vendor (Invariant I1). The budget is advice for
downstream layers (planner depth, context gathering, executor parallelism,
retry and stopping thresholds); it never overrides a structural invariant such
as the always-appended verify step.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from nexus.kernel.events import EventBus
from nexus.schemas.core import Intent

# Light, local research-signal vocabulary — kept independent of the planner's
# capability-typing table on purpose (layers stay decoupled).
_RESEARCH_HINT = re.compile(
    r"\b(research|investigate|study|compare|survey|explore|analyze|analyse|"
    r"review|summari[sz]e|find|gather|read|search|literature)",
    re.IGNORECASE,
)
_TRIVIAL_HINT = re.compile(
    r"\b(rename|fix|typo|format|print|echo|add|remove|delete|bump|tweak)",
    re.IGNORECASE,
)


class ThinkingMode(str, Enum):
    REFLEX = "reflex"
    DELIBERATIVE = "deliberative"
    RESEARCH = "research"


@dataclass(frozen=True)
class ThinkingBudget:
    mode: ThinkingMode
    max_plan_depth: int      # goal-decomposition depth hint
    gather_context: bool     # include a context-gathering step
    max_parallelism: int     # executor width hint
    stopping_confidence: float  # verification confidence deemed "good enough"
    max_retries: int         # retry-budget hint
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


class ThinkingBudgeter:
    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus

    def assess(self, intent: Intent) -> ThinkingBudget:
        n_goals = len(intent.goals)
        n_constraints = len(intent.constraints)
        n_questions = len(intent.open_questions)
        n_refs = len(intent.context_refs)
        research_signal = (
            n_refs > 0
            or n_questions >= 2
            or any(_RESEARCH_HINT.search(g) for g in intent.goals)
        )

        if research_signal:
            budget = ThinkingBudget(
                mode=ThinkingMode.RESEARCH,
                max_plan_depth=n_goals + 1,
                gather_context=n_refs > 0,
                max_parallelism=4,
                stopping_confidence=0.85,
                max_retries=2,
                rationale=self._why_research(n_refs, n_questions, intent.goals),
            )
        elif self._is_reflex(n_goals, n_constraints, n_questions, n_refs, intent.goals):
            budget = ThinkingBudget(
                mode=ThinkingMode.REFLEX,
                max_plan_depth=1,
                gather_context=False,
                max_parallelism=1,
                stopping_confidence=0.6,
                max_retries=0,
                rationale="single simple goal, no constraints/refs/questions",
            )
        else:
            budget = ThinkingBudget(
                mode=ThinkingMode.DELIBERATIVE,
                max_plan_depth=max(n_goals, 2),
                gather_context=n_refs > 0,
                max_parallelism=2,
                stopping_confidence=0.75,
                max_retries=1,
                rationale=f"{n_goals} goal(s), {n_constraints} constraint(s)",
            )

        if self._bus is not None:
            self._bus.publish(
                "thinking.assessed",
                {"intent_id": intent.id, "mode": budget.mode.value},
            )
        return budget

    @staticmethod
    def _is_reflex(n_goals, n_constraints, n_questions, n_refs, goals) -> bool:
        if not (n_goals == 1 and n_constraints == 0 and n_questions == 0 and n_refs == 0):
            return False
        goal = goals[0]
        # A short, trivially-shaped goal — otherwise deliberate.
        return bool(_TRIVIAL_HINT.search(goal)) or len(goal.split()) <= 4

    @staticmethod
    def _why_research(n_refs, n_questions, goals) -> str:
        if n_refs:
            return f"{n_refs} context ref(s) to gather"
        if any(_RESEARCH_HINT.search(g) for g in goals):
            return "research-shaped goal"
        return f"{n_questions} open questions"
