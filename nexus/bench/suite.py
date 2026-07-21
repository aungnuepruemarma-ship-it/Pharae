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
    return [
        BenchCase("b01", "Implement a helper function", "code"),
        BenchCase("b02", "Fix the typo", "reflex"),
        BenchCase("b03", "Design the schema and then implement the API", "multi"),
        BenchCase("b04", "Research how routing scores capabilities", "research"),
        BenchCase("b05", "Compare SQLite and Postgres for the memory store", "research"),
        BenchCase("b06", "Add a validation check to the parser", "code"),
        BenchCase("b07", "Refactor the executor and then add tests", "multi"),
        BenchCase("b08", "Summarize the router design", "research"),
        BenchCase("b09", "Rename the variable", "reflex"),
        BenchCase("b10", "Build a CLI command. Use only the standard library", "code"),
        # Deliberate failure: no builtin browser capability → honest unroutable.
        BenchCase("b11", "Scrape the pricing page", "unroutable"),
        BenchCase("b12", "Investigate the memory promotion gate", "research"),
    ]
