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
  capabilities/  Stage 2: capability registry — manifests, discovery, health, scores
  router/    Stage 3: deterministic policy routing with recorded decisions
  planner/   Stage 4: intent → task DAG with structural verification, re-planning
  executor/  Stage 5: parallel execution, jobs, retries, checkpoint/resume
  memory/    Stage 6: SQLite layered memory with gated promotion, decision log
  verify/    Stage 7: evidence assembly, checks, trace validation, confidence
  research/  Stage 8: research capability — docs, repos, web refs (manifest+handler+check)
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

**Stage 2 — Capability Registry** is implemented: registration with policy
validation (permission allowlist, type vocabulary), versioned coexistence,
health probes (unhealthy is flagged, never hidden), retirement, and
evidence-gated reliability/trust scoring — the only path that moves scores
after registration requires verified Evidence (Invariant I2).

**Stage 3 — Router** is implemented: deterministic rule-based selection over
manifest fields (quality rewarded, normalized cost/latency penalized, explicit
per-candidate exclusion reasons, preference bonus, name/version tie-breaks).
Every decision — routable or not — is recorded complete enough to replay;
unroutable tasks fail explicitly, the router never guesses.

**Stage 4 — Planner** is implemented: deterministic intent → task DAG with
capability-type assignment (never vendors), sequential goal chaining, an
optional context-gathering task, and a `verify` task appended to every plan —
verification is structural. Re-planning produces an immutable successor plan
with provenance to the failed plan and its evidence. The coordination chain
now runs end to end: objective → intent → plan → routed bindings → completed
run.

**Stage 5 — Executor** is implemented: parallel execution of independent DAG
branches on a bounded worker pool, background jobs whose handle is the
interactive surface (pause/unpause at task boundaries, cooperative cancel),
bounded recorded retries, and checkpoint/resume — completed outputs and
working memory are snapshotted at every task boundary, and resume replays
them without re-execution. Plans stay immutable; the Run record is the
account of what happened.

**Stage 6 — Memory** is implemented: SQLite-backed layered stores (working,
episodic, semantic, procedural, failure, project) where `write_working` is the
only ungated path and everything above enters solely through `promote` —
verified evidence plus policy id, full provenance, reversible deprecation.
Secret-like payloads are rejected at every write path. Routing decisions
persist as an operational replay log, durable across restarts.

**Stage 7 — Verification** is implemented, completing the Phase 1 core loop:
structural checks, pluggable per-capability-type checks, event-trace
consistency validation, deterministic confidence scoring with recorded
inputs, and content-derived evidence ids. `verified` means "trustworthy
evidence was established" — a verified record of a failure feeds failure
memory and reliability scoring; unverifiable evidence provably cannot pass
the gates.

**The V1 success criteria hold:** understand → plan → select → execute →
verify → learn runs end to end against real subsystems
(`tests/test_verify.py::TestV1SuccessCriteria`).

**Stage 8 — Research** is implemented as the first Phase 2 capability, and
the reference pattern for all that follow: a manifest for the registry, a
handler for the runtime's capability-type seam, a check for the verification
engine — zero kernel changes. Pluggable sources (documentation trees,
repositories with git history, given web refs with an injectable fetcher)
feed deterministic term-frequency ranking; findings reach long-term memory
only through the verified-evidence promotion gate.

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
