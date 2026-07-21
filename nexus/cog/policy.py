"""Versioned policies: propose → activate → deprecate → rollback.

A policy version is immutable once created; changing behavior means a new
version. Every transition is evented and journaled through the sink
(durable in memory's operational policy_events table), so the policy history
can be audited and replayed.

V1 shortcut, recorded: activation is immediate — benchmark-gated trial
periods arrive with the benchmark harness; rollback exists now, so a bad
policy is one call from gone.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from nexus.kernel.events import EventBus

if TYPE_CHECKING:  # avoid a runtime dependency; only duck-typed
    from nexus.experiments import ExperimentResult


class CogError(Exception):
    pass


class PolicyStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class PolicyVersion:
    kind: str  # e.g. "routing"
    version: int
    payload: dict[str, Any]
    status: PolicyStatus = PolicyStatus.PROPOSED
    reason: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def id(self) -> str:
        return f"{self.kind}@v{self.version}"


class PolicyEngine:
    def __init__(
        self,
        bus: EventBus | None = None,
        sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._bus = bus
        self._sink = sink
        self._versions: dict[str, list[PolicyVersion]] = {}
        self._activation_stack: dict[str, list[int]] = {}

    # -- lifecycle -----------------------------------------------------------

    def propose(self, kind: str, payload: dict[str, Any], reason: str) -> PolicyVersion:
        versions = self._versions.setdefault(kind, [])
        policy = PolicyVersion(
            kind=kind,
            version=len(versions) + 1,
            payload=copy.deepcopy(payload),
            reason=reason,
        )
        versions.append(policy)
        self._record(policy, "policy.proposed")
        return copy.deepcopy(policy)

    def activate(self, kind: str, version: int) -> PolicyVersion:
        policy = self._require(kind, version)
        if policy.status is PolicyStatus.ACTIVE:
            return copy.deepcopy(policy)
        current = self._active_version(kind)
        if current is not None:
            current.status = PolicyStatus.DEPRECATED
            current.reason = f"superseded by v{version}"
            self._record(current, "policy.deprecated")
        policy.status = PolicyStatus.ACTIVE
        self._activation_stack.setdefault(kind, []).append(version)
        self._record(policy, "policy.activated")
        return copy.deepcopy(policy)

    def rollback(self, kind: str, reason: str) -> PolicyVersion:
        """Restore the previously active version. The rolled-back version is
        deprecated with the reason recorded."""
        stack = self._activation_stack.get(kind, [])
        if len(stack) < 2:
            raise CogError(f"no previous active {kind!r} policy to roll back to")
        current_version = stack.pop()
        current = self._require(kind, current_version)
        current.status = PolicyStatus.DEPRECATED
        current.reason = f"rolled back: {reason}"
        self._record(current, "policy.deprecated")
        restored = self._require(kind, stack[-1])
        restored.status = PolicyStatus.ACTIVE
        self._record(restored, "policy.rolled_back")
        return copy.deepcopy(restored)

    def activate_if_improved(
        self, kind: str, version: int, experiment: "ExperimentResult"
    ) -> bool:
        """Statistically-gated activation (L8 + L24 governance: 'everything
        statistically justified'). Activates only if the experiment shows
        improvement; records the verdict either way. Returns whether it
        activated. This is the opt-in trial path; ``activate`` remains the
        immediate path (ADR-0006 records the V1 shortcut)."""
        if getattr(experiment, "improved", False):
            self.activate(kind, version)
            return True
        policy = self._require(kind, version)
        policy.reason = f"trial rejected: {getattr(experiment, 'rationale', 'no improvement')}"
        self._record(policy, "policy.trial_rejected")
        return False

    # -- queries -------------------------------------------------------------

    def active(self, kind: str) -> PolicyVersion | None:
        policy = self._active_version(kind)
        return copy.deepcopy(policy) if policy else None

    def history(self, kind: str) -> list[PolicyVersion]:
        return copy.deepcopy(self._versions.get(kind, []))

    # -- internals -----------------------------------------------------------

    def _active_version(self, kind: str) -> PolicyVersion | None:
        for policy in self._versions.get(kind, []):
            if policy.status is PolicyStatus.ACTIVE:
                return policy
        return None

    def _require(self, kind: str, version: int) -> PolicyVersion:
        for policy in self._versions.get(kind, []):
            if policy.version == version:
                return policy
        raise CogError(f"unknown policy {kind}@v{version}")

    def _record(self, policy: PolicyVersion, topic: str) -> None:
        if self._sink is not None:
            self._sink(
                {
                    "kind": policy.kind,
                    "version": policy.version,
                    "status": policy.status.value,
                    "payload": copy.deepcopy(policy.payload),
                    "reason": policy.reason,
                    "created_at": policy.created_at,
                }
            )
        if self._bus is not None:
            self._bus.publish(
                topic,
                {"policy_id": policy.id, "status": policy.status.value, "reason": policy.reason},
            )
