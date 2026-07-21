"""Capability registry: registration, discovery, health, versioning, and
evidence-gated score bookkeeping.

Spec: docs/volume-2-modules/capability-registry.md. Two properties are
load-bearing here:

- The registry stores and returns *copies* of manifests, so no caller can
  mutate registered state — in particular trust/reliability — by aliasing.
- ``record_outcome`` is the only path that moves ``reliability`` and
  ``trust_score`` after registration, and it demands verified Evidence
  (Kernel Invariant I2). Unhealthy capabilities stay registered and are only
  flagged: the router, not the registry, decides whether to use them.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from nexus.kernel.events import EventBus
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Evidence

# Exponential-moving-average step sizes for verified outcomes. Trust moves
# slower than reliability and is additionally weighted by evidence confidence.
_RELIABILITY_ALPHA = 0.2
_TRUST_ALPHA = 0.1


class RegistryError(Exception):
    pass


class RegistrationStatus(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"


class HealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass
class CapabilityRecord:
    manifest: CapabilityManifest
    status: RegistrationStatus = RegistrationStatus.ACTIVE
    health: HealthStatus = HealthStatus.UNKNOWN
    registered_at: float = field(default_factory=time.time)
    health_checked_at: float | None = None

    @property
    def capability_id(self) -> str:
        return f"{self.manifest.name}@{self.manifest.version}"


def _version_key(version: str) -> tuple[int, ...]:
    numeric = version.split("-")[0].split("+")[0]
    return tuple(int(part) for part in numeric.split("."))


class CapabilityRegistry:
    def __init__(
        self,
        bus: EventBus | None = None,
        allowed_permissions: set[str] | None = None,
        known_types: set[str] | None = None,
    ) -> None:
        """``allowed_permissions``/``known_types`` of None mean open: any
        well-formed permission or type is accepted. Passing a set makes the
        registry reject manifests outside that vocabulary."""
        self._bus = bus
        self._allowed_permissions = allowed_permissions
        self._known_types = known_types
        self._records: dict[tuple[str, str], CapabilityRecord] = {}
        self._probes: dict[tuple[str, str], Callable[[], bool]] = {}

    # -- registration --------------------------------------------------------

    def register(
        self,
        manifest: CapabilityManifest,
        health_probe: Callable[[], bool] | None = None,
    ) -> str:
        errors = manifest.validate()
        if self._known_types is not None and manifest.capability_type not in self._known_types:
            errors.append(
                f"capability_type {manifest.capability_type!r} is not in the registry vocabulary"
            )
        if self._allowed_permissions is not None:
            for perm in manifest.permissions:
                if perm not in self._allowed_permissions:
                    errors.append(f"permission {perm!r} is not allowed by registry policy")
        if errors:
            raise RegistryError(f"manifest rejected: {'; '.join(errors)}")
        key = (manifest.name, manifest.version)
        existing = self._records.get(key)
        if existing is not None and existing.status is RegistrationStatus.ACTIVE:
            raise RegistryError(f"{manifest.name}@{manifest.version} is already registered")
        # A retired capability may be re-registered: reactivation (used by the
        # plugin lifecycle's disable→enable). Health resets to UNKNOWN.
        record = CapabilityRecord(manifest=copy.deepcopy(manifest))
        self._records[key] = record
        if health_probe is not None:
            self._probes[key] = health_probe
        self._publish(
            "capability.registered",
            {"capability": record.capability_id, "capability_type": manifest.capability_type},
        )
        return record.capability_id

    def retire(self, name: str, version: str) -> None:
        record = self._require(name, version)
        if record.status is RegistrationStatus.RETIRED:
            return
        record.status = RegistrationStatus.RETIRED
        self._publish("capability.retired", {"capability": record.capability_id})

    # -- discovery -----------------------------------------------------------

    def get(self, name: str, version: str | None = None) -> CapabilityRecord | None:
        """A specific version (any status), or the latest ACTIVE version."""
        if version is not None:
            record = self._records.get((name, version))
            return copy.deepcopy(record) if record else None
        candidates = [
            r
            for (n, _), r in self._records.items()
            if n == name and r.status is RegistrationStatus.ACTIVE
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda r: _version_key(r.manifest.version))
        return copy.deepcopy(latest)

    def find(
        self,
        capability_type: str,
        healthy_only: bool = False,
        include_retired: bool = False,
    ) -> list[CapabilityRecord]:
        out = [
            r
            for r in self._records.values()
            if r.manifest.capability_type == capability_type
            and (include_retired or r.status is RegistrationStatus.ACTIVE)
            and (not healthy_only or r.health is HealthStatus.HEALTHY)
        ]
        out.sort(key=lambda r: (r.manifest.name, _version_key(r.manifest.version)))
        return copy.deepcopy(out)

    def types(self) -> list[str]:
        return sorted(
            {
                r.manifest.capability_type
                for r in self._records.values()
                if r.status is RegistrationStatus.ACTIVE
            }
        )

    # -- health --------------------------------------------------------------

    def check_health(self, name: str, version: str) -> HealthStatus:
        record = self._require(name, version)
        probe = self._probes.get((name, version))
        if probe is None:
            return record.health
        try:
            healthy = bool(probe())
        except Exception:
            healthy = False  # a failing probe is an unhealthy capability, not a crash
        new = HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY
        record.health_checked_at = time.time()
        if new is not record.health:
            record.health = new
            self._publish(
                "capability.health",
                {"capability": record.capability_id, "health": new.value},
            )
        return record.health

    def check_all_health(self) -> dict[str, HealthStatus]:
        return {
            record.capability_id: self.check_health(name, version)
            for (name, version), record in sorted(self._records.items())
        }

    # -- evidence-gated scores (Invariant I2) --------------------------------

    def record_outcome(
        self,
        name: str,
        version: str,
        *,
        evidence: Evidence,
        success: bool,
        reward: float | None = None,
    ) -> None:
        """The only path that moves reliability/trust after registration.

        The evidence gate is unconditional (Invariant I2). ``reward`` is an
        optional reward-shaped trust target in [0, 1] (see ``nexus.cog.
        RewardShaper``), computed by the learning pipeline from this *same
        verified evidence* — it shapes only the magnitude of the trust update,
        never the gate. When omitted, trust falls back to the confidence
        target, preserving prior behavior. Reliability is always the pure
        success rate."""
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise RegistryError(
                "score updates require verified Evidence (Kernel Invariant I2)"
            )
        record = self._require(name, version)
        m = record.manifest
        reliability_target = 1.0 if success else 0.0
        if success:
            trust_target = _clamp(reward) if reward is not None else evidence.confidence
        else:
            trust_target = 0.0
        m.reliability = _clamp(
            m.reliability + _RELIABILITY_ALPHA * (reliability_target - m.reliability)
        )
        m.trust_score = _clamp(m.trust_score + _TRUST_ALPHA * (trust_target - m.trust_score))
        self._publish(
            "capability.scored",
            {
                "capability": record.capability_id,
                "reliability": m.reliability,
                "trust_score": m.trust_score,
                "evidence_id": evidence.id,
            },
        )

    # -- internals -----------------------------------------------------------

    def _require(self, name: str, version: str) -> CapabilityRecord:
        record = self._records.get((name, version))
        if record is None:
            raise RegistryError(f"unknown capability {name}@{version}")
        return record

    def _publish(self, topic: str, payload: dict) -> None:
        if self._bus is not None:
            self._bus.publish(topic, payload)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
