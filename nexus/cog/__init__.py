"""Cog — the learning engine (the fifth pillar).

Spec: docs/volume-2-modules/cog.md. Turns verified execution history into
better policies and reusable behavior:

    Run → Evidence → Evaluation → Failure analysis → Policy update
        → Skill promotion → Improved future routing

Cog learns only from verified evidence (Invariant I2), writes long-term
memory only through the gated promotion path it was built to hold
(Invariant I3), and never mutates the kernel.
"""

from nexus.cog.cog import Cog, LearnResult, to_routing_policy
from nexus.cog.policy import CogError, PolicyEngine, PolicyStatus, PolicyVersion
from nexus.cog.reward import RewardShaper

__all__ = [
    "Cog",
    "CogError",
    "LearnResult",
    "PolicyEngine",
    "PolicyStatus",
    "PolicyVersion",
    "RewardShaper",
    "to_routing_policy",
]
