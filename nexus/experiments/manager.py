"""A/B experiment comparison → an improvement verdict with recorded evidence.

An `improved` verdict requires three things to agree: a positive mean delta, a
meaningful effect size, and a bootstrap 'no improvement' probability below the
significance level. Any one failing yields no improvement — the conservative
default that matches Pharae's gate-over-signal stance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.experiments.stats import bootstrap_ci, bootstrap_p_greater, cohens_d, mean
from nexus.kernel.events import EventBus


@dataclass
class ExperimentResult:
    baseline_id: str
    treatment_id: str
    baseline_mean: float
    treatment_mean: float
    delta: float
    effect_size: float
    p_no_improvement: float
    treatment_ci: tuple[float, float]
    improved: bool
    rationale: str
    n_baseline: int = 0
    n_treatment: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentManager:
    def __init__(
        self,
        bus: EventBus | None = None,
        seed: int = 0,
        alpha: float = 0.05,
        min_effect: float = 0.5,
        min_samples: int = 3,
    ) -> None:
        self._bus = bus
        self._seed = seed
        self._alpha = alpha
        self._min_effect = min_effect
        self._min_samples = min_samples

    def compare(
        self,
        baseline_id: str,
        treatment_id: str,
        *,
        baseline: list[float],
        treatment: list[float],
    ) -> ExperimentResult:
        b_mean, t_mean = mean(baseline), mean(treatment)
        delta = t_mean - b_mean

        if len(baseline) < self._min_samples or len(treatment) < self._min_samples:
            result = ExperimentResult(
                baseline_id, treatment_id, b_mean, t_mean, delta,
                effect_size=0.0, p_no_improvement=1.0, treatment_ci=(t_mean, t_mean),
                improved=False,
                rationale=f"insufficient samples (need ≥{self._min_samples} per arm)",
                n_baseline=len(baseline), n_treatment=len(treatment),
            )
            return self._finish(result)

        effect = cohens_d(treatment, baseline)
        p_no_improvement = bootstrap_p_greater(
            treatment, baseline, seed=self._seed
        )
        ci = bootstrap_ci(treatment, seed=self._seed)
        improved = (
            delta > 0
            and effect >= self._min_effect
            and p_no_improvement <= self._alpha
        )
        rationale = (
            f"Δ={delta:+.3f}, d={effect:.2f}, p(no-improve)={p_no_improvement:.3f}"
            + (" → improvement" if improved else " → not significant")
        )
        result = ExperimentResult(
            baseline_id, treatment_id, b_mean, t_mean, delta,
            effect_size=effect if effect != float("inf") else 999.0,
            p_no_improvement=p_no_improvement, treatment_ci=ci,
            improved=improved, rationale=rationale,
            n_baseline=len(baseline), n_treatment=len(treatment),
        )
        return self._finish(result)

    def _finish(self, result: ExperimentResult) -> ExperimentResult:
        if self._bus is not None:
            self._bus.publish(
                "experiment.completed",
                {
                    "baseline": result.baseline_id,
                    "treatment": result.treatment_id,
                    "improved": result.improved,
                    "delta": result.delta,
                },
            )
        return result
