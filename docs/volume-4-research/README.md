# Volume 4 — Research Book

Experiments, benchmarks, failure analyses, design alternatives, literature
reviews, and future ideas. **Never mixed with the architecture**: nothing here
is normative until it graduates into an ADR and a Volume 1/2/3 change.

## Contents

- [`adr/`](adr/) — Architecture Decision Records. Why key choices were made.
  Start with [the template](adr/template.md).
- [`research-agenda.md`](research-agenda.md) — open questions and the
  continuous research loop.
- `experiments/` — created per experiment as they run (hypothesis →
  measurement → analysis → conclusion, notebook-style).
- `benchmarks/` — created when the benchmark harness lands (Stage 7+): task
  success rate, correctness, speed, cost, recovery rate, memory usefulness,
  routing quality, verification quality, human intervention rate.

## Continuous Research Loop

Run continuously, reviewed periodically **before** any architectural change:

- Track new models and providers
- Track new protocols (MCP, A2A, successors)
- Track agent frameworks and runtimes
- Track benchmarks
- Track browser automation
- Track cloud platforms

Findings are recorded here; only reviewed findings can motivate an ADR.

## Phase A research foundations (to be written)

Comparative studies feeding the architecture: agent runtimes, operating
systems, distributed systems, workflow engines, knowledge graphs, the
scientific method, scheduling algorithms, human cognition, continuous learning.
Each becomes a literature-review document in this volume with explicit
takeaways for Pharae.
