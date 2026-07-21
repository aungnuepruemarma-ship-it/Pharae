"""Security policy and guard.

A policy classifies a capability manifest into allow / require-approval / deny
over its declared permissions and type. The guard resolves a task's bound
capability from the registry and applies the policy, tracking approvals. The
executor consults the guard before dispatch — a denied or unapproved task is
never run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from nexus.capabilities.registry import CapabilityRegistry
from nexus.kernel.events import EventBus
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Task


class Decision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class Judgment:
    verdict: Decision
    reason: str


@dataclass(frozen=True)
class SecurityPolicy:
    """Frozen, declarative. Deny wins over approval wins over allow."""

    denied_permissions: frozenset[str] = field(default_factory=frozenset)
    approval_permissions: frozenset[str] = field(default_factory=frozenset)
    approval_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # accept plain sets at construction
        object.__setattr__(self, "denied_permissions", frozenset(self.denied_permissions))
        object.__setattr__(self, "approval_permissions", frozenset(self.approval_permissions))
        object.__setattr__(self, "approval_types", frozenset(self.approval_types))

    def decide(self, manifest: CapabilityManifest) -> Judgment:
        perms = set(manifest.permissions)
        denied = perms & self.denied_permissions
        if denied:
            return Judgment(Decision.DENY, f"denied permissions: {sorted(denied)}")
        needs = perms & self.approval_permissions
        if needs or manifest.capability_type in self.approval_types:
            why = (
                f"permissions {sorted(needs)}" if needs
                else f"capability type {manifest.capability_type!r}"
            )
            return Judgment(Decision.REQUIRE_APPROVAL, f"approval required for {why}")
        return Judgment(Decision.ALLOW, "allowed by policy")


class SecurityGuard:
    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: SecurityPolicy | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy or SecurityPolicy()
        self._bus = bus
        self._approved: set[str] = set()

    def approve(self, capability_id: str) -> None:
        """Human override: grant a capability the approval its policy demands."""
        self._approved.add(capability_id)
        if self._bus is not None:
            self._bus.publish("security.approved", {"capability": capability_id})

    def check(self, task: Task) -> tuple[bool, str]:
        binding = task.capability_binding
        if not binding:
            return True, "no binding to judge"
        name, _, version = binding.rpartition("@")
        record = self._registry.get(name, version)
        if record is None:
            return True, "capability not found; nothing to judge"
        judgment = self._policy.decide(record.manifest)
        if judgment.verdict is Decision.ALLOW:
            return True, judgment.reason
        if judgment.verdict is Decision.REQUIRE_APPROVAL and binding in self._approved:
            return True, "approved"
        return False, judgment.reason
