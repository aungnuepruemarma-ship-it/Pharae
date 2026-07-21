"""Rule-based intent parsing: Objective → Intent.

The rules are ordered and transparent so parsing stays deterministic and
auditable. Identical objective text and context refs produce a structurally
identical Intent, including its id (content-derived, not random). Ambiguity is
represented explicitly as open questions, never silently resolved.

Classification per clause, in order:

1. Ends with ``?``                        → open question
2. Contains ``so that``                   → split; right side is an outcome,
                                            left side re-enters classification
3. Starts with a constraint marker        → constraint
4. Starts with an outcome marker          → desired outcome
5. Otherwise                              → goal; ``and then`` splits compound
                                            goals; embedded phrases
                                            (``using …``, ``without …``,
                                            budget/limit phrases) are also
                                            extracted as constraints
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from nexus.kernel.events import EventBus
from nexus.schemas.core import Intent, Objective

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!])\s+")
_SO_THAT = re.compile(r"\bso that\b", re.IGNORECASE)
_AND_THEN = re.compile(r"\s*,?\s*\band then\b\s*|\s*,\s*then\s+", re.IGNORECASE)

_CONSTRAINT_START = re.compile(
    r"^(?:must\b|should(?:\s+not|n't)?\b|do\s+not\b|don't\b|never\b|avoid\b|"
    r"only\b|without\b|use\b|using\b|keep\b|ensure\b|stay\b|limit\b|"
    r"no\s+more\s+than\b|at\s+most\b|at\s+least\b|within\b|under\s|"
    r"budget\b|deadline\b|no\s)",
    re.IGNORECASE,
)
_OUTCOME_START = re.compile(
    r"^(?:deliver\b|the\s+result\b|end\s+result\b|end\s+up\s+with\b|"
    r"the\s+final\b|output\s+should\b|result\s+should\b)",
    re.IGNORECASE,
)
_EMBEDDED_CONSTRAINT = re.compile(
    r"\b(?:using|without|no more than|at most|at least|within)\s[^,;.]+",
    re.IGNORECASE,
)

# Context refs: URLs, paths with a directory component, or bare filenames with
# a documentation/data extension. Extension list deliberately excludes js/ts/
# html so dotted product names ("Node.js") are not mistaken for files.
_REF = re.compile(
    r"https?://[^\s)\]}>,;]+"
    r"|(?:[\w.~-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6}"
    r"|\b[\w-]+\.(?:md|py|txt|json|ya?ml|toml|csv|pdf|rst|ipynb)\b"
)


def _content_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:12]}"


def make_objective(text: str, context_refs: list[str] | None = None) -> Objective:
    """Wrap raw user text into an Objective with a content-derived id."""
    refs = list(context_refs or [])
    return Objective(
        id=_content_id("obj", text, *refs),
        text=text,
        context_refs=refs,
    )


@dataclass
class _Buckets:
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


def _clauses(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = _BULLET.sub("", line.strip())
        if not line:
            continue
        for part in _SENTENCE_SPLIT.split(line):
            part = part.strip().rstrip(".;:!").strip()
            if part:
                out.append(part)
    return out


def _extract_refs(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;:!?") for m in _REF.finditer(text)]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _classify(clause: str, buckets: _Buckets) -> None:
    if clause.endswith("?"):
        buckets.questions.append(clause)
        return
    parts = _SO_THAT.split(clause, maxsplit=1)
    if len(parts) == 2:
        left, right = parts[0].strip().rstrip(","), parts[1].strip()
        if left:
            _classify(left, buckets)
        if right:
            buckets.outcomes.append(right)
        return
    if _CONSTRAINT_START.match(clause):
        buckets.constraints.append(clause)
        return
    if _OUTCOME_START.match(clause):
        buckets.outcomes.append(clause)
        return
    for goal in _AND_THEN.split(clause):
        goal = goal.strip()
        if not goal:
            continue
        buckets.goals.append(goal)
        for embedded in _EMBEDDED_CONSTRAINT.finditer(goal):
            buckets.constraints.append(embedded.group(0).strip())


class IntentEngine:
    """Parses objectives. Holds no execution machinery by construction."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus

    def parse(self, objective: Objective) -> Intent:
        buckets = _Buckets()
        for clause in _clauses(objective.text):
            _classify(clause, buckets)
        if not buckets.goals and not buckets.questions:
            buckets.questions.append(
                "No actionable goal identified in the objective; clarification needed."
            )
        intent = Intent(
            id=_content_id("int", objective.id, objective.text),
            objective_id=objective.id,
            goals=_dedupe(buckets.goals),
            constraints=_dedupe(buckets.constraints),
            desired_outcomes=_dedupe(buckets.outcomes),
            open_questions=_dedupe(buckets.questions),
            context_refs=_dedupe(objective.context_refs + _extract_refs(objective.text)),
        )
        if self._bus is not None:
            self._bus.publish(
                "intent.parsed",
                {"intent_id": intent.id, "objective_id": objective.id},
            )
        return intent
