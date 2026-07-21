"""Canonical data objects. Prose spec: docs/volume-3-protocols/.

On conflict between this code and Volume 3, Volume 3 wins and the code
must be fixed.
"""

from nexus.schemas.core import (
    Artifact,
    Evidence,
    Intent,
    Objective,
    Plan,
    Run,
    RunStatus,
    Task,
    TaskResult,
    TaskStatus,
)
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.routing import CandidateEvaluation, RoutingDecision

__all__ = [
    "Artifact",
    "CandidateEvaluation",
    "CapabilityManifest",
    "Evidence",
    "Intent",
    "Objective",
    "Plan",
    "RoutingDecision",
    "Run",
    "RunStatus",
    "Task",
    "TaskResult",
    "TaskStatus",
]
