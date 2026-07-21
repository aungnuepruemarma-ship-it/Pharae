"""Deterministic rule-based capability routing over manifest fields.

For each task: candidates come from the registry by capability type; each is
either excluded with an explicit recorded reason (denied by policy, unhealthy,
below quality thresholds, over cost/latency caps) or scored. The score is a
weighted sum of manifest fields — reliability and trust reward, cost and
latency (normalized within the eligible set) penalize, user preference adds a
bonus. Ties break by name then newest version, so identical registry state and
policy always produce the identical choice.

No vendor names appear in routing logic — only manifest fields (Invariant I1).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from nexus.capabilities.registry import (
    CapabilityRecord,
    CapabilityRegistry,
    HealthStatus,
)
from nexus.kernel.events import EventBus
from nexus.schemas.core import Plan, Task
from nexus.schemas.routing import CandidateEvaluation, RoutingDecision


class UnroutableError(Exception):
    pass


@dataclass(frozen=True)
class RoutingPolicy:
    """An ordered, declarative rule set. Frozen so a policy id always names
    one exact behavior; a changed policy is a new policy."""

    id: str = "default@1.0.0"
    require_healthy: bool = False  # True: only HEALTHY; default also admits UNKNOWN
    min_reliability: float = 0.0
    min_trust: float = 0.0
    max_cost: float | None = None
    max_latency_ms: float | None = None
    preferred: tuple[str, ...] = ()  # capability names granted the bonus
    denied: tuple[str, ...] = ()  # capability names never used
    w_reliability: float = 0.4
    w_trust: float = 0.4
    w_cost: float = 0.1
    w_latency: float = 0.1
    preference_bonus: float = 0.25


def _version_key(capability_id: str) -> tuple[int, ...]:
    version = capability_id.rsplit("@", 1)[1]
    return tuple(int(p) for p in version.split("-")[0].split("+")[0].split("."))


class Router:
    def __init__(
        self,
        registry: CapabilityRegistry,
        bus: EventBus | None = None,
        policy: RoutingPolicy | None = None,
        decision_sink: Callable[[RoutingDecision], None] | None = None,
    ) -> None:
        """``decision_sink`` receives a copy of every decision for durable
        persistence — wire it to ``MemorySystem.record_routing_decision``."""
        self._registry = registry
        self._bus = bus
        self._policy = policy or RoutingPolicy()
        self._sink = decision_sink
        self._decisions: list[RoutingDecision] = []
        self._counter = 0

    # -- single-task routing -------------------------------------------------

    def route(self, task: Task, policy: RoutingPolicy | None = None) -> RoutingDecision:
        """Evaluate all candidates for the task and record the decision.
        Never raises for an unroutable task: the decision carries
        ``chosen=None`` and the reason, and ``route.unroutable`` is emitted."""
        policy = policy or self._policy
        records = self._registry.find(task.capability_type)

        evaluations: dict[str, CandidateEvaluation] = {}
        eligible: list[CapabilityRecord] = []
        for record in records:
            reason = self._exclusion_reason(record, policy)
            if reason is not None:
                evaluations[record.capability_id] = CandidateEvaluation(
                    capability_id=record.capability_id, excluded=reason
                )
            else:
                eligible.append(record)

        for record, score in self._score(eligible, policy):
            evaluations[record.capability_id] = CandidateEvaluation(
                capability_id=record.capability_id, score=score
            )

        chosen, reason = self._choose(task, records, eligible, evaluations, policy)

        self._counter += 1
        decision = RoutingDecision(
            id=f"rd-{self._counter:06x}",
            task_id=task.id,
            capability_type=task.capability_type,
            policy_id=policy.id,
            candidates=[evaluations[r.capability_id] for r in records],
            chosen=chosen,
            reason=reason,
        )
        self._decisions.append(copy.deepcopy(decision))
        if self._sink is not None:
            self._sink(copy.deepcopy(decision))

        if self._bus is not None:
            if chosen is not None:
                self._bus.publish(
                    "route.decided",
                    {"decision_id": decision.id, "task_id": task.id, "capability": chosen},
                )
            else:
                self._bus.publish(
                    "route.unroutable",
                    {"decision_id": decision.id, "task_id": task.id, "reason": reason},
                )
        return decision

    # -- plan routing --------------------------------------------------------

    def route_plan(
        self, plan: Plan, policy: RoutingPolicy | None = None
    ) -> dict[str, RoutingDecision]:
        """Route and bind every task in a plan. Every decision is recorded
        first; then any unroutable task raises, so failures are explicit and
        the planner (or user) can act on the full decision set."""
        decisions: dict[str, RoutingDecision] = {}
        for task in plan.tasks:
            decision = self.route(task, policy=policy)
            decisions[task.id] = decision
            if decision.chosen is not None:
                task.capability_binding = decision.chosen
        unroutable = [tid for tid, d in decisions.items() if d.chosen is None]
        if unroutable:
            raise UnroutableError(
                f"plan {plan.id!r} has unroutable tasks: {', '.join(unroutable)}"
            )
        return decisions

    def decisions(self) -> list[RoutingDecision]:
        """The recorded decision log (copies). In-memory until the memory
        subsystem (Stage 5) persists it."""
        return copy.deepcopy(self._decisions)

    # -- rules ---------------------------------------------------------------

    @staticmethod
    def _exclusion_reason(record: CapabilityRecord, policy: RoutingPolicy) -> str | None:
        m = record.manifest
        if m.name in policy.denied:
            return "denied by policy"
        if record.health is HealthStatus.UNHEALTHY:
            return "unhealthy"
        if policy.require_healthy and record.health is not HealthStatus.HEALTHY:
            return f"health {record.health.value} (policy requires healthy)"
        if m.reliability < policy.min_reliability:
            return f"reliability {m.reliability:.2f} below minimum {policy.min_reliability:.2f}"
        if m.trust_score < policy.min_trust:
            return f"trust {m.trust_score:.2f} below minimum {policy.min_trust:.2f}"
        if policy.max_cost is not None and m.cost > policy.max_cost:
            return f"cost {m.cost:.2f} exceeds max {policy.max_cost:.2f}"
        if policy.max_latency_ms is not None and m.latency_ms > policy.max_latency_ms:
            return f"latency {m.latency_ms:.0f}ms exceeds max {policy.max_latency_ms:.0f}ms"
        return None

    @staticmethod
    def _score(
        eligible: list[CapabilityRecord], policy: RoutingPolicy
    ) -> list[tuple[CapabilityRecord, float]]:
        if not eligible:
            return []
        max_cost = max(r.manifest.cost for r in eligible)
        max_latency = max(r.manifest.latency_ms for r in eligible)
        out = []
        for record in eligible:
            m = record.manifest
            score = policy.w_reliability * m.reliability + policy.w_trust * m.trust_score
            score -= policy.w_cost * (m.cost / max_cost if max_cost > 0 else 0.0)
            score -= policy.w_latency * (m.latency_ms / max_latency if max_latency > 0 else 0.0)
            if m.name in policy.preferred:
                score += policy.preference_bonus
            out.append((record, score))
        return out

    def _choose(
        self,
        task: Task,
        records: list[CapabilityRecord],
        eligible: list[CapabilityRecord],
        evaluations: dict[str, CandidateEvaluation],
        policy: RoutingPolicy,
    ) -> tuple[str | None, str]:
        if not records:
            return None, (
                f"no registered capabilities of type {task.capability_type!r}"
            )
        if not eligible:
            return None, "all candidates excluded by policy"
        best = sorted(
            eligible,
            key=lambda r: (
                -evaluations[r.capability_id].score,
                r.manifest.name,
                tuple(-part for part in _version_key(r.capability_id)),
            ),
        )[0]
        return best.capability_id, "highest score under policy"
