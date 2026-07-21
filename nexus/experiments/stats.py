"""Small, dependency-free statistics for evidence-justified decisions.

Deterministic where randomness is involved: the bootstrap takes an explicit
seed, so an experiment's verdict is reproducible (Volume 0 governance:
everything auditable and reproducible).
"""

from __future__ import annotations

import random
import statistics


def mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def cohens_d(treatment: list[float], baseline: list[float]) -> float:
    """Standardized effect size (positive → treatment higher). Uses pooled
    standard deviation; zero when there is no variance and no mean gap."""
    if len(treatment) < 2 or len(baseline) < 2:
        gap = mean(treatment) - mean(baseline)
        return 0.0 if gap == 0 else float("inf") * (1 if gap > 0 else -1)
    vt, vb = statistics.pvariance(treatment), statistics.pvariance(baseline)
    pooled = ((vt + vb) / 2.0) ** 0.5
    gap = mean(treatment) - mean(baseline)
    if pooled == 0:
        return 0.0 if gap == 0 else float("inf") * (1 if gap > 0 else -1)
    return gap / pooled


def bootstrap_ci(
    data: list[float], confidence: float = 0.95, iterations: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. Deterministic under ``seed``."""
    if not data:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(data)
    means = sorted(
        mean([data[rng.randrange(n)] for _ in range(n)]) for _ in range(iterations)
    )
    lo_idx = int((1 - confidence) / 2 * iterations)
    hi_idx = min(iterations - 1, int((1 + confidence) / 2 * iterations))
    return (means[lo_idx], means[hi_idx])


def bootstrap_p_greater(
    treatment: list[float], baseline: list[float], iterations: int = 2000, seed: int = 0
) -> float:
    """Bootstrap estimate of P(treatment mean ≤ baseline mean) — a one-sided
    'no improvement' probability. Small values support improvement."""
    if len(treatment) < 2 or len(baseline) < 2:
        return 1.0
    rng = random.Random(seed)
    nt, nb = len(treatment), len(baseline)
    not_better = 0
    for _ in range(iterations):
        mt = mean([treatment[rng.randrange(nt)] for _ in range(nt)])
        mb = mean([baseline[rng.randrange(nb)] for _ in range(nb)])
        if mt <= mb:
            not_better += 1
    return not_better / iterations


def holm_correction(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm–Bonferroni step-down. Returns {name: rejected?}. Once a hypothesis
    fails to reject, all larger p-values also fail (step-down property)."""
    ordered = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(ordered)
    results: dict[str, bool] = {}
    still_rejecting = True
    for i, (name, p) in enumerate(ordered):
        threshold = alpha / (m - i)
        if still_rejecting and p <= threshold:
            results[name] = True
        else:
            still_rejecting = False
            results[name] = False
    return results
