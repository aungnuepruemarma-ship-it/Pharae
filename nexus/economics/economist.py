"""Compute-tier selection over model capabilities, driven by the Thinking
budget. Deterministic; reasons over manifest fields only (Invariant I1).

Policy by mode:
- REFLEX      → minimize cost (cheapest capable-enough model).
- RESEARCH    → maximize capability (highest trust·reliability), cost secondary.
- DELIBERATIVE→ balance quality against normalized cost and latency.

Ties break by name for reproducibility.
"""

from __future__ import annotations

from nexus.kernel.events import EventBus
from nexus.schemas.capability import CapabilityManifest
from nexus.thinking import ThinkingBudget, ThinkingMode


class EconomicsError(Exception):
    pass


class Economist:
    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus

    def choose(
        self, budget: ThinkingBudget, candidates: list[CapabilityManifest]
    ) -> CapabilityManifest:
        if not candidates:
            raise EconomicsError("no model candidates to choose from")
        chosen = self._rank(budget.mode, candidates)[0]
        if self._bus is not None:
            self._bus.publish(
                "economics.chosen",
                {
                    "capability": chosen.name,
                    "mode": budget.mode.value,
                    "tier": chosen.constraints.get("tier", "?"),
                },
            )
        return chosen

    @staticmethod
    def _rank(
        mode: ThinkingMode, candidates: list[CapabilityManifest]
    ) -> list[CapabilityManifest]:
        max_cost = max(c.cost for c in candidates) or 1.0
        max_lat = max(c.latency_ms for c in candidates) or 1.0

        def capability(c: CapabilityManifest) -> float:
            return c.trust_score * 0.5 + c.reliability * 0.5

        if mode is ThinkingMode.REFLEX:
            key = lambda c: (c.cost, -capability(c), c.name)
        elif mode is ThinkingMode.RESEARCH:
            key = lambda c: (-capability(c), c.cost, c.name)
        else:  # DELIBERATIVE — balance
            key = lambda c: (
                -(capability(c) - 0.3 * (c.cost / max_cost) - 0.2 * (c.latency_ms / max_lat)),
                c.name,
            )
        return sorted(candidates, key=key)
