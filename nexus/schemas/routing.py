"""Routing decision records.

Spec: docs/volume-2-modules/router.md. Every routing decision is recorded
with its full candidate evaluation — complete enough to replay the choice.
This log is the raw material for benchmark-driven and adaptive routing later.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CandidateEvaluation:
    """One candidate's fate in a routing decision: either a score, or an
    explicit exclusion reason. Never both, never neither."""

    capability_id: str
    score: float | None = None
    excluded: str | None = None


@dataclass
class RoutingDecision:
    id: str
    task_id: str
    capability_type: str
    policy_id: str
    candidates: list[CandidateEvaluation] = field(default_factory=list)
    chosen: str | None = None
    reason: str = ""
    created_at: float = field(default_factory=time.time)
