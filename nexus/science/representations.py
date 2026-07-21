"""L9 — Representations. Competing internal reasoning models; only evidence
survives.

Representations (chain-of-thought, graph reasoning, HTN, state machine, …)
accrue verified win/loss records. `best()` returns the highest verified
win-rate among those with enough trials — a representation that merely *looks*
good with one lucky run cannot win. Every record requires verified evidence
(Invariant I2).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.kernel.events import EventBus
from nexus.schemas.core import Evidence
from nexus.science.theory import ScienceError


@dataclass
class RepresentationRecord:
    name: str
    wins: int = 0
    trials: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.trials if self.trials else 0.0


class RepresentationArena:
    def __init__(self, bus: EventBus | None = None, min_trials: int = 3) -> None:
        self._bus = bus
        self._min_trials = min_trials
        self._records: dict[str, RepresentationRecord] = {}

    def register(self, name: str) -> RepresentationRecord:
        return self._records.setdefault(name, RepresentationRecord(name=name))

    def record(self, name: str, evidence: Evidence, *, success: bool) -> RepresentationRecord:
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise ScienceError(
                "representations learn only from verified evidence (Invariant I2)"
            )
        rec = self.register(name)
        rec.trials += 1
        if success:
            rec.wins += 1
        if self._bus is not None:
            self._bus.publish(
                "representation.recorded",
                {"name": name, "win_rate": rec.win_rate, "trials": rec.trials},
            )
        return rec

    def best(self) -> RepresentationRecord | None:
        qualified = [r for r in self._records.values() if r.trials >= self._min_trials]
        if not qualified:
            return None
        # Highest win-rate; ties broken by more trials, then name — deterministic.
        return sorted(qualified, key=lambda r: (-r.win_rate, -r.trials, r.name))[0]

    def standings(self) -> list[RepresentationRecord]:
        return sorted(self._records.values(), key=lambda r: (-r.win_rate, r.name))
