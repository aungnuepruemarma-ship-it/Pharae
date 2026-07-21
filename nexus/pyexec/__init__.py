"""A real, safe, offline code capability: arithmetic evaluation.

Spec: docs/volume-2-modules/pyexec.md. The first *failable* built-in — it does
genuine work (evaluates an expression) and genuinely fails on anything it
can't compute. That failure is the point: it lets verification grade real
outcomes, so the benchmark's confidence metric measures capability quality
instead of harness determinism. No `eval`, no names/calls/attributes — an AST
whitelist over numeric operators only.
"""

from nexus.pyexec.pyexec import (
    PyexecError,
    make_pyexec_handler,
    pyexec_check,
    pyexec_manifest,
    safe_eval,
)

__all__ = [
    "PyexecError",
    "make_pyexec_handler",
    "pyexec_check",
    "pyexec_manifest",
    "safe_eval",
]
