"""The experience pipeline: verified (Run, Evidence) pairs in, memory
promotions, score updates, skills, and routing-policy revisions out.

Cog is the intended holder of the promotion credential: it is the only
module that calls ``memory.promote`` and ``registry.record_outcome`` in the
normal flow. Both gates additionally enforce verified evidence themselves,
so even a misused Cog cannot launder unverified output into memory.

Skill and failure thresholds are counted from durable memory (episodic and
failure layers), not in-process state — learning survives restarts.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from nexus.capabilities.registry import CapabilityRegistry, RegistryError
from nexus.cog.policy import CogError, PolicyEngine, PolicyVersion
from nexus.cog.reward import RewardShaper
from nexus.kernel.events import EventBus
from nexus.memory import MemoryLayer, MemorySystem
from nexus.router import RoutingPolicy
from nexus.schemas.core import Evidence, Plan, Run, RunStatus, TaskStatus

_ROUTING_KIND = "routing"


@dataclass
class LearnResult:
    run_id: str
    success: bool
    signature: str
    episodic_id: str
    failure_ids: list[str] = field(default_factory=list)
    skill_id: str | None = None
    deprecated_skill_id: str | None = None
    score_updates: list[tuple[str, bool]] = field(default_factory=list)
    policy_changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def to_routing_policy(
    policy: PolicyVersion, base: RoutingPolicy | None = None
) -> RoutingPolicy:
    """Materialize an active Cog routing-policy version as the RoutingPolicy
    the router consumes."""
    return dataclasses.replace(
        base or RoutingPolicy(),
        id=policy.id,
        denied=tuple(policy.payload.get("denied", ())),
    )


class Cog:
    def __init__(
        self,
        memory: MemorySystem,
        registry: CapabilityRegistry | None = None,
        bus: EventBus | None = None,
        policies: PolicyEngine | None = None,
        skill_threshold: int = 3,
        failure_threshold: int = 3,
        promotion_policy_id: str = "cog.promotion@0.1.0",
        reward_shaper: RewardShaper | None = None,
    ) -> None:
        self._memory = memory
        self._registry = registry
        self._bus = bus
        self.policies = policies or PolicyEngine(
            bus=bus, sink=memory.record_policy_event
        )
        self._skill_threshold = skill_threshold
        self._failure_threshold = failure_threshold
        self._policy_id = promotion_policy_id
        self._reward = reward_shaper or RewardShaper()

    # -- the pipeline --------------------------------------------------------

    def learn(self, run: Run, evidence: Evidence, plan: Plan | None = None) -> LearnResult:
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise CogError(
                "Cog learns only from verified evidence (Kernel Invariant I2)"
            )
        success = bool(
            evidence.test_results.get("success", run.status is RunStatus.COMPLETED)
        )
        signature = (
            "→".join(t.capability_type for t in plan.tasks) if plan is not None else ""
        )
        bindings = (
            {t.id: t.capability_binding for t in plan.tasks} if plan is not None else {}
        )
        failed_tasks = [
            (task_id, result)
            for task_id, result in sorted(run.task_results.items())
            if result.status is TaskStatus.FAILED
        ]

        result = LearnResult(
            run_id=run.id,
            success=success,
            signature=signature,
            episodic_id=self._reflect(run, evidence, signature, success, failed_tasks),
        )
        result.failure_ids = self._record_failures(
            run, evidence, signature, failed_tasks, bindings
        )
        self._update_scores(run, evidence, bindings, result)
        if plan is not None and signature:
            if success:
                result.skill_id = self._maybe_promote_skill(signature, plan, evidence)
            else:
                result.deprecated_skill_id = self._maybe_deprecate_skill(signature, run)
        if not success:
            result.policy_changes = self._maybe_revise_routing(failed_tasks, bindings)
        return result

    # -- reflection ----------------------------------------------------------

    def _reflect(self, run, evidence, signature, success, failed_tasks) -> str:
        item = self._memory.promote(
            evidence,
            MemoryLayer.EPISODIC,
            {
                "run_id": run.id,
                "plan_id": run.plan_id,
                "signature": signature,
                "success": success,
                "confidence": evidence.confidence,
                "task_count": len(run.task_results),
                "failed_tasks": [task_id for task_id, _ in failed_tasks],
            },
            policy_id=self._policy_id,
        )
        return item.id

    def _record_failures(self, run, evidence, signature, failed_tasks, bindings):
        ids = []
        for task_id, task_result in failed_tasks:
            item = self._memory.promote(
                evidence,
                MemoryLayer.FAILURE,
                {
                    "run_id": run.id,
                    "task_id": task_id,
                    "capability": bindings.get(task_id),
                    "error": task_result.error or "",
                    "signature": signature,
                },
                policy_id=self._policy_id,
            )
            ids.append(item.id)
        return ids

    # -- capability scores ---------------------------------------------------

    def _update_scores(self, run, evidence, bindings, result: LearnResult) -> None:
        if self._registry is None:
            return
        for task_id, task_result in sorted(run.task_results.items()):
            binding = bindings.get(task_id)
            if not binding or task_result.status not in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ):
                continue
            task_success = task_result.status is TaskStatus.COMPLETED
            name, _, version = binding.rpartition("@")
            reward = self._reward.reward(evidence, task_success)
            try:
                self._registry.record_outcome(
                    name, version, evidence=evidence, success=task_success, reward=reward
                )
                result.score_updates.append((binding, task_success))
            except RegistryError as exc:
                result.notes.append(f"score update skipped for {binding}: {exc}")

    # -- skills --------------------------------------------------------------

    def _maybe_promote_skill(self, signature, plan: Plan, evidence) -> str | None:
        existing = [
            item
            for item in self._memory.read(MemoryLayer.PROCEDURAL)
            if item.content.get("signature") == signature
        ]
        if existing:
            return None
        successes = [
            item
            for item in self._memory.read(MemoryLayer.EPISODIC)
            if item.content.get("signature") == signature and item.content.get("success")
        ]
        if len(successes) < self._skill_threshold:
            return None
        sources = successes[: self._skill_threshold]
        item = self._memory.promote(
            evidence,
            MemoryLayer.PROCEDURAL,
            {
                "signature": signature,
                "task_chain": [
                    {
                        "capability_type": t.capability_type,
                        "description": t.payload.get("description", ""),
                    }
                    for t in plan.tasks
                ],
                "source_runs": [s.content["run_id"] for s in sources],
                "confidence": round(
                    sum(s.confidence for s in sources) / len(sources), 6
                ),
            },
            policy_id=self._policy_id,
        )
        if self._bus is not None:
            self._bus.publish(
                "skill.promoted", {"skill_id": item.id, "signature": signature}
            )
        return item.id

    def _maybe_deprecate_skill(self, signature, run) -> str | None:
        for item in self._memory.read(MemoryLayer.PROCEDURAL):
            if item.content.get("signature") == signature:
                self._memory.deprecate(
                    item.id, reason=f"verified failure in run {run.id}"
                )
                if self._bus is not None:
                    self._bus.publish(
                        "skill.deprecated",
                        {"skill_id": item.id, "signature": signature, "run_id": run.id},
                    )
                return item.id
        return None

    # -- routing revision ----------------------------------------------------

    def _maybe_revise_routing(self, failed_tasks, bindings) -> list[str]:
        changes = []
        failed_bindings = sorted(
            {bindings.get(task_id) for task_id, _ in failed_tasks} - {None}
        )
        for binding in failed_bindings:
            name = binding.rpartition("@")[0]
            active = self.policies.active(_ROUTING_KIND)
            denied = set(active.payload.get("denied", [])) if active else set()
            if name in denied:
                continue
            failures = [
                item
                for item in self._memory.read(MemoryLayer.FAILURE)
                if item.content.get("capability") == binding
            ]
            if len(failures) < self._failure_threshold:
                continue
            proposed = self.policies.propose(
                _ROUTING_KIND,
                {"denied": sorted(denied | {name})},
                reason=f"{len(failures)} verified failures of {binding}",
            )
            self.policies.activate(_ROUTING_KIND, proposed.version)
            changes.append(proposed.id)
        return changes
