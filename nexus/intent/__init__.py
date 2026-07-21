"""Stage 1 — Intent Engine.

Spec: docs/volume-2-modules/intent.md. Converts an Objective into a
structured Intent. Rule-based and deterministic in V1; no execution, no
tool calls, no vendors (Kernel Invariant I1).
"""

from nexus.intent.engine import IntentEngine, make_objective

__all__ = ["IntentEngine", "make_objective"]
