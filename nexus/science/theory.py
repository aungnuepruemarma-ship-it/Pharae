"""L10 — Theory Ledger. Hypotheses earn their way into knowledge.

A theory is proposed as PENDING, accrues verified observations (supporting or
refuting), and transitions by evidence: enough replications → ACTIVE, enough
refutations → REJECTED. Only an ACTIVE theory can be PROMOTED, and promotion
writes to long-term (semantic) memory **through the gate** — verified evidence
+ policy id, full provenance (Invariants I2/I3). Governance L24 made literal:
"no theory without replication."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum

from nexus.kernel.events import EventBus
from nexus.memory import MemoryLayer, MemorySystem
from nexus.schemas.core import Evidence
from nexus.schemas.memory import MemoryItem


class ScienceError(Exception):
    pass


class TheoryStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    PROMOTED = "promoted"


@dataclass
class Theory:
    id: str
    statement: str
    status: TheoryStatus = TheoryStatus.PENDING
    supporting: list[str] = field(default_factory=list)  # evidence ids
    refuting: list[str] = field(default_factory=list)
    last_supporting_evidence: Evidence | None = None

    @property
    def replications(self) -> int:
        return len(self.supporting)

    @property
    def confidence(self) -> float:
        total = len(self.supporting) + len(self.refuting)
        return len(self.supporting) / total if total else 0.0


def _theory_id(statement: str) -> str:
    return f"thy-{hashlib.sha256(statement.encode('utf-8')).hexdigest()[:12]}"


class TheoryLedger:
    def __init__(
        self,
        memory: MemorySystem,
        bus: EventBus | None = None,
        replication_threshold: int = 3,
        refutation_threshold: int = 2,
    ) -> None:
        self._memory = memory
        self._bus = bus
        self._replication_threshold = replication_threshold
        self._refutation_threshold = refutation_threshold
        self._theories: dict[str, Theory] = {}

    def propose(self, statement: str) -> Theory:
        theory = self._theories.setdefault(
            _theory_id(statement), Theory(id=_theory_id(statement), statement=statement)
        )
        self._publish("theory.proposed", theory)
        return theory

    def get(self, theory_id: str) -> Theory | None:
        return self._theories.get(theory_id)

    def observe(self, theory_id: str, evidence: Evidence, *, supports: bool) -> Theory:
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise ScienceError(
                "theories learn only from verified evidence (Invariant I2)"
            )
        theory = self._require(theory_id)
        if theory.status in (TheoryStatus.REJECTED, TheoryStatus.PROMOTED):
            return theory
        if supports:
            theory.supporting.append(evidence.id)
            theory.last_supporting_evidence = evidence
        else:
            theory.refuting.append(evidence.id)
        self._publish("theory.observed", theory)

        if len(theory.refuting) >= self._refutation_threshold:
            theory.status = TheoryStatus.REJECTED
            self._publish("theory.rejected", theory)
        elif theory.replications >= self._replication_threshold:
            theory.status = TheoryStatus.ACTIVE
        return theory

    def promote(self, theory_id: str, *, policy_id: str) -> MemoryItem:
        theory = self._require(theory_id)
        if theory.status is not TheoryStatus.ACTIVE:
            raise ScienceError(
                f"only ACTIVE theories promote (theory {theory_id} is {theory.status.value})"
            )
        if theory.last_supporting_evidence is None:
            raise ScienceError("no supporting evidence to gate promotion")
        item = self._memory.promote(
            theory.last_supporting_evidence,
            MemoryLayer.SEMANTIC,
            {
                "theory": theory.statement,
                "replications": theory.replications,
                "confidence": theory.confidence,
                "supporting_evidence": list(theory.supporting),
            },
            policy_id=policy_id,
        )
        theory.status = TheoryStatus.PROMOTED
        self._publish("theory.promoted", theory)
        return item

    def _require(self, theory_id: str) -> Theory:
        theory = self._theories.get(theory_id)
        if theory is None:
            raise ScienceError(f"unknown theory {theory_id!r}")
        return theory

    def _publish(self, topic: str, theory: Theory) -> None:
        if self._bus is not None:
            self._bus.publish(
                topic,
                {
                    "theory_id": theory.id,
                    "status": theory.status.value,
                    "replications": theory.replications,
                },
            )
