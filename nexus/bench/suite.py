"""The fixed benchmark suite. Spans reasoning modes and outcome kinds,
including cases that *should* fail to route — measuring the gate, not just the
happy path."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchCase:
    id: str
    objective: str
    kind: str  # code | research | multi | reflex | unroutable


def default_suite() -> list[BenchCase]:
    """Honest mix: computable code tasks that genuinely succeed, a prose-code
    task the builtin genuinely cannot do (real failure), research, and a
    deliberately unroutable case. Outcomes really vary, so the confidence
    metric measures capability quality, not harness determinism."""
    return [
        BenchCase("b01", "Compute 6 * 7", "code"),
        BenchCase("b02", "Evaluate (12 + 8) / 4", "code"),
        BenchCase("b03", "Calculate 2 ** 10", "code"),
        BenchCase("b04", "Compute 100 - 37", "code"),
        BenchCase("b05", "Evaluate 15 % 4 and then compute 3 * 3", "multi"),
        BenchCase("b06", "Research how routing scores capabilities", "research"),
        BenchCase("b07", "Summarize the memory promotion gate", "research"),
        BenchCase("b08", "Investigate the router design", "research"),
        BenchCase("b09", "Compute (3 + 4) * (5 - 2)", "code"),
        # Prose-code the arithmetic builtin genuinely cannot do → real failure.
        BenchCase("b10", "Implement a helper function", "code-fail"),
        # No builtin browser capability → honest unroutable.
        BenchCase("b11", "Scrape the pricing page", "unroutable"),
        BenchCase("b12", "Compare SQLite and Postgres for the store", "research"),
    ]
