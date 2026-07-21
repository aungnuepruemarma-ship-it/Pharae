"""Benchmark harness — the runtime measured against itself.

Spec: docs/volume-2-modules/bench.md. Realizes Volume 1 §18: runs a fixed
suite of objectives through the real loop and reports task success rate,
verified rate, mean confidence, tasks per run, unroutable rate, and whether
learning was observed. Deliberately includes failure and unroutable cases —
the verification gate and honest routing failure are part of what is measured.

Offline and deterministic: a fixed self-contained corpus, built-in
capabilities, no network — so results are reproducible artifacts (Volume 0
governance) and feed the Experiment Manager (L8) and Cog's policy trials.
"""

from nexus.bench.suite import BenchCase, default_suite
from nexus.bench.runner import BenchReport, run_suite

__all__ = ["BenchCase", "BenchReport", "default_suite", "run_suite"]
