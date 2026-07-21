# Pharae — Intelligence Runtime

> A model-agnostic intelligence runtime that coordinates capabilities, verifies outcomes, and learns from experience.

Pharae is **not** a chat app, a coding assistant, or a model wrapper. It is a runtime
that takes an *objective*, routes it across models, tools, browsers, cloud workers,
and memory, then verifies the results and learns from them.

The runtime coordinates intelligence rather than trying to become the intelligence.
It is designed to work with any future model, protocol, browser, cloud platform, or
execution engine.

```
Objective → Intent → Plan → Capability Routing → Execution → Verification → Learning → Memory
```

## First Principles

1. **Objectives, not prompts** — users express goals; the runtime decides how to achieve them.
2. **Capabilities, not products** — the runtime reasons about "browser", "code", "research", not vendors.
3. **Evidence before memory** — long-term memory is updated only from verified outcomes.
4. **Plugins over kernel** — the kernel stays minimal; everything else is replaceable.
5. **Progressive complexity** — simple tasks are solved directly; orchestration only when it earns its cost.
6. **Model-agnostic** — any model or provider can be added or removed.

See [`docs/volume-0-manifesto.md`](docs/volume-0-manifesto.md) for the full philosophy
and the **Kernel Invariants** that every change must preserve.

## Documentation

The project separates the stable architectural contract from implementation detail,
the way large systems (Linux, Kubernetes, LLVM) do.

| Volume | Purpose | Change rate |
|--------|---------|-------------|
| [Volume 0 — Manifesto](docs/volume-0-manifesto.md) | Why the system exists: vision, principles, invariants, non-goals | Rarely |
| [Volume 1 — Architecture Specification](docs/volume-1-architecture.md) | The constitution: abstractions, layers, models, boundaries | Slowly, by review |
| [Volume 2 — Module Specifications](docs/volume-2-modules/) | One spec per subsystem (kernel, planner, router, memory, …) | Per subsystem |
| [Volume 3 — Protocol Specifications](docs/volume-3-protocols/) | Every internal interface: manifests, APIs, event bus | Versioned |
| [Volume 4 — Research Book](docs/volume-4-research/) | ADRs, experiments, benchmarks, open questions | Continuously |
| [Volume 5 — Engineering Handbook](docs/volume-5-engineering/handbook.md) | Standards, testing, workflow, repo layout | As needed |

## Repository Layout

```
docs/        The six specification volumes (see table above)
nexus/       The runtime implementation
  kernel/    Stage 0: event bus, state, sessions, scheduler, runtime lifecycle
  intent/    Stage 1: deterministic objective → structured intent parsing
  schemas/   Canonical data objects: Objective, Intent, Task, Plan, Capability, Evidence, Run
tests/       Unit tests (stdlib unittest; no dependencies)
```

## Status

**Stage 0 — Kernel** is implemented: runtime lifecycle, scheduler (DAG-aware),
session manager, event bus, and state manager, with the canonical data schemas.
No browser. No agents. No cloud. Those arrive later as *capabilities and plugins*,
never as kernel code.

**Stage 1 — Intent Engine** is implemented: deterministic, rule-based parsing of
objectives into structured intent (goals, constraints, desired outcomes, open
questions, context refs) with content-derived ids. Ambiguity becomes explicit
open questions, never silent guesses.

The staged roadmap (Intent Engine → Capability Registry → Router → Runtime →
Memory → Verification → Research → Browser → Plugins) is defined in
[Volume 1 §17](docs/volume-1-architecture.md#17-roadmap).

## Development

The kernel is pure Python 3.11+ standard library. Run the tests:

```sh
python3 -m unittest discover -s tests -v
```

Every feature follows the workflow in the
[Engineering Handbook](docs/volume-5-engineering/handbook.md):
design doc → interfaces → tests → implementation → verification → benchmark →
documentation → keep/revise/remove decision.

## The One-Line Test for Every Proposal

> Does it preserve the Kernel Invariants?

If the answer is no, the proposal requires an explicit architecture review
(a new ADR in Volume 4) before any code is written.
