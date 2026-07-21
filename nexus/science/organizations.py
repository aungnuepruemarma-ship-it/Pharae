"""L12 — Organizations. Cognitive teams as *capability compositions*.

Consistent with ADR-0003 (capability-centered, not agent-centered): an
Organization is a named, ordered composition of capability *types* (e.g.
research→code→verify) — a reusable team shape, not a roster of persistent
agents. Organizations accrue verified performance and are selected per plan
signature by success rate. Every record requires verified evidence
(Invariant I2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus.kernel.events import EventBus
from nexus.schemas.core import Evidence
from nexus.science.theory import ScienceError


@dataclass
class Organization:
    name: str
    capability_types: list[str]
    successes: int = 0
    trials: int = 0

    @property
    def signature(self) -> str:
        return "→".join(self.capability_types)

    @property
    def success_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0


class OrganizationLibrary:
    def __init__(self, bus: EventBus | None = None, min_trials: int = 3) -> None:
        self._bus = bus
        self._min_trials = min_trials
        self._orgs: dict[str, Organization] = {}

    def define(self, name: str, capability_types: list[str]) -> Organization:
        org = Organization(name=name, capability_types=list(capability_types))
        self._orgs[name] = org
        if self._bus is not None:
            self._bus.publish(
                "organization.defined", {"name": name, "signature": org.signature}
            )
        return org

    def record(self, name: str, evidence: Evidence, *, success: bool) -> Organization:
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise ScienceError(
                "organizations learn only from verified evidence (Invariant I2)"
            )
        org = self._orgs.get(name)
        if org is None:
            raise ScienceError(f"unknown organization {name!r}")
        org.trials += 1
        if success:
            org.successes += 1
        if self._bus is not None:
            self._bus.publish(
                "organization.recorded",
                {"name": name, "success_rate": org.success_rate, "trials": org.trials},
            )
        return org

    def best_for(self, capability_types: list[str]) -> Organization | None:
        """Best organization whose composition matches the given signature.
        Untried organizations are eligible (rate 0) only if nothing has trials;
        proven ones win by success rate, ties by more trials then name."""
        signature = "→".join(capability_types)
        matches = [o for o in self._orgs.values() if o.signature == signature]
        if not matches:
            return None
        return sorted(matches, key=lambda o: (-o.success_rate, -o.trials, o.name))[0]

    def all(self) -> list[Organization]:
        return sorted(self._orgs.values(), key=lambda o: o.name)
