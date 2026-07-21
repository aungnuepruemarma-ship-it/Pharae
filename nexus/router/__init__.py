"""Stage 3 — Capability Router.

Spec: docs/volume-2-modules/router.md. Chooses which registered capability
executes each task. Decides; never executes. Rule-based and deterministic in
V1; every decision is recorded (Kernel Invariant I6) and the router never
guesses — unroutable tasks fail explicitly.
"""

from nexus.router.router import Router, RoutingPolicy, UnroutableError

__all__ = ["Router", "RoutingPolicy", "UnroutableError"]
