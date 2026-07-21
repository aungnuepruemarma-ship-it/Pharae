"""Run the suite through the real loop and aggregate metrics.

One shared AppContext across the suite, so learning accumulates and can be
observed (episodic memory grows). A small fixed corpus is written into the
data dir and used as the research root, making research cases deterministic
regardless of the caller's working directory.
"""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from typing import Any

from nexus.bench.suite import BenchCase, default_suite
from nexus.cli.app import AppContext
from nexus.memory import MemoryLayer
from nexus.planner import PlannerError
from nexus.router import UnroutableError
from nexus.schemas.core import RunStatus

_CORPUS = {
    "routing.md": (
        "# Routing\n\nThe router scores capability manifests: reliability and "
        "trust are rewarded, cost and latency penalized. Unroutable tasks fail "
        "explicitly.\n"
    ),
    "memory.md": (
        "# Memory\n\nSix layered stores on SQLite. The promotion gate requires "
        "verified evidence and a policy id; nothing enters long-term memory "
        "otherwise.\n"
    ),
    "storage.md": (
        "# Storage\n\nSQLite is the V1 store. Postgres was considered and "
        "deferred; the router and executor are storage-agnostic.\n"
    ),
}


@dataclass
class BenchRow:
    id: str
    kind: str
    routable: bool
    run_status: str
    verified: bool
    confidence: float
    tasks: int


@dataclass
class BenchReport:
    rows: list[BenchRow] = field(default_factory=list)
    episodic_before: int = 0
    episodic_after: int = 0

    def summary(self) -> dict[str, float]:
        n = len(self.rows)
        routable = [r for r in self.rows if r.routable]
        completed = [r for r in routable if r.run_status == RunStatus.COMPLETED.value]
        verified = [r for r in self.rows if r.verified]
        return {
            "n": n,
            "success_rate": len(completed) / n if n else 0.0,
            "verified_rate": len(verified) / n if n else 0.0,
            "unroutable_rate": sum(1 for r in self.rows if not r.routable) / n if n else 0.0,
            "mean_confidence": statistics.fmean([r.confidence for r in verified]) if verified else 0.0,
            "mean_tasks": statistics.fmean([r.tasks for r in self.rows]) if n else 0.0,
            "learning_observed": self.episodic_after > self.episodic_before,
        }

    def deterministic_summary(self) -> dict[str, Any]:
        s = self.summary()
        return {
            k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.deterministic_summary(),
            "rows": [r.__dict__ for r in self.rows],
        }


def run_suite(data_dir: str, cases: list[BenchCase] | None = None) -> BenchReport:
    cases = cases or default_suite()
    corpus_dir = os.path.join(os.path.abspath(data_dir), "corpus")
    os.makedirs(corpus_dir, exist_ok=True)
    for name, text in _CORPUS.items():
        with open(os.path.join(corpus_dir, name), "w") as f:
            f.write(text)

    ctx = AppContext(data_dir=data_dir, research_root=corpus_dir)
    report = BenchReport(episodic_before=len(ctx.memory.read(MemoryLayer.EPISODIC)))
    try:
        for case in cases:
            report.rows.append(_run_case(ctx, case))
        report.episodic_after = len(ctx.memory.read(MemoryLayer.EPISODIC))
    finally:
        ctx.close()
    return report


def _run_case(ctx: AppContext, case: BenchCase) -> BenchRow:
    intent = ctx.parse(case.objective)
    budget = ctx.thinking.assess(intent)
    try:
        plan = ctx.planner.plan(intent, budget=budget)
    except PlannerError:
        return BenchRow(case.id, case.kind, False, "no-plan", False, 0.0, 0)

    try:
        ctx.router.route_plan(plan)
    except UnroutableError:
        return BenchRow(case.id, case.kind, False, "unroutable", False, 0.0, len(plan.tasks))

    run_ = ctx.executor.execute(plan)
    evidence = ctx.verifier.verify(run_, plan=plan)
    if evidence.verified:
        ctx.cog.learn(run_, evidence, plan=plan)
    return BenchRow(
        id=case.id,
        kind=case.kind,
        routable=True,
        run_status=run_.status.value,
        verified=evidence.verified,
        confidence=evidence.confidence,
        tasks=len(plan.tasks),
    )
