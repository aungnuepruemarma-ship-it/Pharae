"""L8 — Experiment Manager. Statistical comparison for evidence-justified
change.

Spec: docs/volume-2-modules/experiments.md. Gives the runtime the statistical
apparatus L24 governance already demands ("everything statistically
justified") and Cog's policy trials were missing: A/B comparison with
bootstrap confidence intervals, effect size, and Holm multiple-comparison
correction. Pure stdlib, deterministic under a seed.
"""

from nexus.experiments.manager import ExperimentManager, ExperimentResult
from nexus.experiments.stats import bootstrap_ci, cohens_d, holm_correction, mean

__all__ = [
    "ExperimentManager",
    "ExperimentResult",
    "bootstrap_ci",
    "cohens_d",
    "holm_correction",
    "mean",
]
