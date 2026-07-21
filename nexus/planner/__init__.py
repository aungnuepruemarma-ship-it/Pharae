"""Stage 4 — Planner.

Spec: docs/volume-2-modules/planner.md. Builds an execution DAG from a
structured intent. Emits plans; never executes, never binds vendors
(Kernel Invariant I1). Deterministic: the same intent produces the same
plan, ids included. Re-planning creates a successor plan — running plans
are immutable.
"""

from nexus.planner.planner import Planner, PlannerError

__all__ = ["Planner", "PlannerError"]
