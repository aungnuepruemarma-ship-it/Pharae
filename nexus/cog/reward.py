"""Reward shaping — a bounded, deterministic learning signal derived from
*verified* evidence.

Borrowed in spirit from Prue/NCP's RewardEngine (ADR-0004), but placed to
respect Pharae's hard gate: reward shaping happens **after** the evidence
gate, never around it. Cog computes a reward from verified evidence and hands
it to the registry as the trust target; the registry still refuses to score
anything unverified (Invariant I2). Reliability stays a pure success rate —
only trust is reward-shaped.

Over today's confidence-only trust target, the new ingredient is
**cost/friction awareness**: among equally-confident successes, the cheaper,
cleaner one (fewer retries, lower reported cost) earns trust faster — so the
runtime learns, over time, to distrust chronically expensive capabilities,
complementing the router's per-decision cost penalty.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.schemas.core import Evidence


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class RewardShaper:
    """Maps (verified Evidence, success) → reward in [0, 1].

    Defaults blend outcome and confidence, then discount by a cost signal.
    Setting ``outcome_weight=0`` and ``cost_weight=0`` reduces the reward to
    the raw confidence — i.e. exactly the legacy trust target — so the shaper
    is a strict generalization of prior behavior."""

    confidence_weight: float = 0.8
    outcome_weight: float = 0.2
    cost_weight: float = 0.15

    def reward(self, evidence: Evidence, success: bool) -> float:
        if not success:
            return 0.0
        confidence = _clamp(evidence.confidence)
        weight_sum = self.confidence_weight + self.outcome_weight
        if weight_sum <= 0:
            base = confidence
        else:
            base = (self.confidence_weight * confidence + self.outcome_weight) / weight_sum
        return _clamp(base * (1.0 - self.cost_weight * self._cost_signal(evidence)))

    @staticmethod
    def _cost_signal(evidence: Evidence) -> float:
        """A friction proxy in [0, 1]. Prefers an explicit normalized ``cost``
        in the evidence's cost report; otherwise uses the retry fraction
        (retries / attempts) that the executor records."""
        report = evidence.cost_report or {}
        if "cost" in report:
            try:
                return _clamp(float(report["cost"]))
            except (TypeError, ValueError):
                return 0.0
        attempts = report.get("attempts", 1) or 1
        retries = report.get("retries", 0) or 0
        try:
            return _clamp(float(retries) / float(attempts))
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0
