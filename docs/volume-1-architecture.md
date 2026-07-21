# Volume 1 — Architecture Specification (IRAB v1.0)

**Intelligence Runtime Architecture Blueprint**

**Status:** Living architecture specification. This is the constitution: every
module must conform to this document. Changes require an ADR (Volume 4) and must
preserve the Kernel Invariants (Volume 0 §5).

---

## 1. Executive Summary

Pharae is a model-agnostic intelligence runtime. It accepts an **objective**,
parses it into structured **intent**, plans an execution **DAG**, routes each
task to the best available **capability**, executes with checkpointing and
recovery, **verifies** results with evidence, and **learns** from verified
outcomes to improve future routing and planning.

The system is capability-centered, not agent-centered. There is no "research
agent" or "browser agent" baked into the core; there are *capabilities*
(research, browser, code, memory, verification) from which temporary workers
are assembled as needed.

## 2. The Five Pillars

The architecture revolves around five immutable pillars. Everything else —
browser automation, notebooks, cloud providers, IDE integrations, protocols
like MCP and A2A, research connectors — is a capability or plugin built on top.

1. **Runtime** — executes work.
2. **Capability Fabric** — connects models, tools, services, and plugins through
   common interfaces.
3. **Knowledge Fabric** — represents goals, evidence, projects, memories, and
   relationships.
4. **Learning Engine (Cog)** — learns from verified experience and improves
   policies over time.
5. **Verification Engine** — ensures outputs are grounded, reproducible, and
   evidence-based.

## 3. Core Product Loop

```
Objective
  ↓
Intent parsing
  ↓
Thinking (reasoning budget — L4, Progressive Complexity)
  ↓
Planning
  ↓
Capability routing
  ↓
Execution
  ↓
Verification
  ↓
Learning
  ↓
Memory update
  ↓
Improved future routing
```

This loop *is* the product. Every subsystem exists to serve one stage of it.

## 4. Architectural Layers

```
┌─────────────────────────────────────────────────────┐
│ 1. Interfaces          CLI · API · TUI · (Web later)│
├─────────────────────────────────────────────────────┤
│ 2. Coordination        Intent · Planner · Router    │
├─────────────────────────────────────────────────────┤
│ 3. Runtime Kernel      Lifecycle · Events · Sessions│
│                        Scheduler · State            │
├─────────────────────────────────────────────────────┤
│ 4. Capability Layer    Registry · Manifests · Health│
│                        Providers · Plugins          │
├─────────────────────────────────────────────────────┤
│ 5. Knowledge Layer     Memory stores · Evidence     │
│                        Artifacts · (Graph later)    │
├─────────────────────────────────────────────────────┤
│ 6. Learning Layer      Cog: reflection · policies · │
│                        skill promotion              │
├─────────────────────────────────────────────────────┤
│ 7. Infrastructure      Storage · Sandbox · Telemetry│
│                        Security                     │
└─────────────────────────────────────────────────────┘
```

Dependencies point downward only. A lower layer never imports from a higher one.
The kernel (layer 3) knows only the schemas in Volume 3 — never implementations.

## 5. Core Concepts

The canonical nouns (schemas in `nexus/schemas/`, reference in Appendix C):

- **Objective** — user goal + constraints + desired outcomes.
- **Intent** — structured parse of an objective.
- **Plan** — DAG of tasks with dependencies.
- **Task** — unit of work; declares the *capability type* it needs, never a vendor.
- **Capability** — registered ability with a manifest (identity, I/O schemas,
  cost, latency, permissions, reliability, trust, version).
- **Worker** — temporary executor assembled from capabilities for a task.
- **Session** — live execution context with its own state namespace.
- **Run** — one complete attempt at an objective; the unit of learning.
- **Evidence** — logs, tests, artifacts, traces, confidence that prove a result.
- **Artifact** — produced object (code, docs, data, screenshots, reports).
- **Policy** — rule for choosing/acting (routing policy, memory policy, security policy).
- **Memory** — layered stores (see §11).
- **Skill** — promoted, reusable procedure extracted from verified runs.

## 6. Runtime Kernel

**Owns:** lifecycle, event loop, scheduling, sessions, state, context.

**Never contains:** browser logic, cloud logic, provider logic, model names,
vendor SDKs. (Invariant I1.)

Components (implemented in `nexus/kernel/`, spec in Volume 2):

- **Event Bus** — topic-based pub/sub with a replayable event log. All
  cross-module communication flows through events or the versioned APIs in
  Volume 3; modules never call each other's internals.
- **State Manager** — namespaced key-value state with snapshot/restore; the
  primitive underlying checkpointing and recovery.
- **Session Manager** — creates, tracks, and ends sessions; each session gets an
  isolated state namespace and event correlation id.
- **Scheduler** — dependency-aware (DAG) ready-set computation, priorities,
  concurrency limits. Deterministic: identical inputs yield identical order.
- **Runtime** — ties the above together; executes plans through registered
  handlers keyed by capability *type* string. The handler seam is where the
  Capability Layer plugs in; the kernel itself performs no capability work.

## 7. Intent Engine

Transforms natural language into a structured objective:

```
Objective (text) → { goals[], constraints[], desired_outcomes[], context refs }
```

- No execution. No tool calls. Parsing and decomposition only.
- Deterministic where possible: the same objective text and context should
  produce the same intent structure.
- Output feeds the Planner; the intent representation is a stable schema
  (Volume 3), so the parsing implementation can be swapped freely.

## 8. Planner

Builds an execution DAG from intent:

- Task decomposition, dependency edges, and per-task capability *type*
  requirements (e.g. `research`, `code`, `verify` — never a vendor).
- Optimization (parallelizable branches identified structurally).
- Re-planning on failure: the planner receives failure evidence and produces a
  revised plan; it never patches a running plan in place.
- Plans are exportable, diffable artifacts.

No tool calls. The planner emits a plan; it never executes.

## 9. Capability Layer

### 9.1 Capability Model

Every capability registers a **manifest** (schema in Volume 3):

identity, type, input schema, output schema, cost, latency, permissions,
reliability, constraints, strengths, version, trust score, evidence score,
confidence.

The runtime reasons over manifests. It compares capabilities of the same *type*
and never binds to an implementation.

### 9.2 Capability Registry

Registration, discovery, health checks, metadata, versioning. The registry is
the only source of truth about what the runtime can do.

### 9.3 Capability Router

Chooses a capability for each task based on: task type, cost, latency, trust,
context, user preferences, and historical performance. Every routing decision is
**recorded** with its inputs so it can be evaluated later (this is the raw
material for Cog's routing improvements).

V1 routing is rule-based and deterministic. Benchmark-driven and adaptive
routing arrive later, gated on recorded decision history.

## 10. Execution Engine

Runs plans. Supports:

- Interactive execution (user watching, can intervene)
- Background jobs
- Parallel execution of independent DAG branches
- Checkpointing (via State Manager snapshots) and recovery/resume
- Cancellation at any time (Invariant I7)

Retries, timeouts, and failure propagation are executor concerns; the scheduler
only decides *what is ready*, the executor decides *how it runs*.

Distributed swarms are explicitly future work (§17, Phase 3).

## 11. Memory System

Memory is layered, never one blob:

| Layer | Contents | Written by |
|-------|----------|-----------|
| **Working** | Current run context | Executor (freely) |
| **Episodic** | What happened in past runs | Learning pipeline only |
| **Semantic** | Stable facts, concepts, decisions | Learning pipeline only |
| **Procedural** | Workflows that succeeded (skills) | Skill promotion only |
| **Failure** | What went wrong, why, how fixed | Learning pipeline only |
| **Project** | Per-project state, goals, history | Policy-gated writes |

**Promotion rules:** information moves upward (working → episodic → semantic /
procedural) only through the Cog pipeline, and only when backed by verified
evidence (Invariants I2, I3). The executor may write working memory freely;
everything above working memory is policy-gated.

**V1 storage:** SQLite. Richer stores (graph databases) only when a recorded
limitation justifies them (ADR required).

## 12. Cog Learning System

Cog learns **only from verified experience**:

```
Run → Evidence → Evaluation → Failure analysis → Policy update → Skill promotion → Improved routing
```

- **Reflection Engine** — success/failure analysis, pattern extraction.
- **Policy Engine** — promotion, deprecation, rollback, confidence tracking.
  Policies are versioned and can be rolled back.
- **Skill Evolution** — extracts reusable workflows from repeated verified
  successes and registers them as procedural memory.

Cog never mutates the kernel and never writes memory outside the gated pipeline.

## 13. Verification Engine

Verification is a first-class subsystem, not an afterthought. Every serious run
ends with:

- output + **evidence** (logs, artifacts, traces)
- tests where applicable
- a **confidence score**
- reproducibility status (can this be replayed?)
- cost report

Nothing is trusted by default. Verification results are the *only* input to
learning and long-term memory (Invariant I2).

## 14. Security Model

Hard boundaries between: **planning**, **execution**, **memory write**, and
**external side effects**.

- No capability writes persistent memory without passing policy + verification.
- Risky work runs sandboxed; cloud workers are isolated.
- Dangerous actions require approval (progressive autonomy).
- Every side effect is logged; replay is possible where feasible (Invariant I6).
- Secrets never enter memory stores or event payloads.

Threat model: Appendix E (Volume 4 as it develops).

## 15. Protocols

The runtime absorbs protocols rather than fighting them. All are *adapters* at
the capability layer — the kernel sees only Volume 3 interfaces.

- **Internal:** Event Bus, Task API, Session API, Memory API, Capability API
  (Volume 3 — versioned, stable).
- **External:** MCP (tool/context access), A2A (agent-to-agent), REST/WebSocket/
  gRPC, Git, SSH, filesystem, notebooks, browser sessions.

## 16. Interfaces

One brain, multiple faces. The user learns ~12 verbs; the runtime may contain
dozens of modules.

```
do · think · research · plan · run · verify · memory · learn · browse · status · config · plugin
```

- **CLI** — the main power surface (`nexus do "…"`). Commands are cognition
  verbs, not tool names.
- **API** — everything the runtime does is callable programmatically.
- **TUI** — long-running work and fast inspection.
- **Web dashboard** — later (non-goal for V1).

## 17. Roadmap

**Phase 1 — Kernel MVP: complete.** Runtime kernel ✅ (Stage 0), intent
engine ✅ (Stage 1), capability registry ✅ (Stage 2), router ✅ (Stage 3),
planner ✅ (Stage 4), executor ✅ (Stage 5), SQLite memory ✅ (Stage 6),
verification ✅ (Stage 7). The Volume 0 §9 success criteria — understand,
plan, select, execute, verify, learn — run end to end in
`tests/test_verify.py::TestV1SuccessCriteria`.

**Phase 2 — Knowledge:** research capability ✅ (Stage 8 — the reference
pattern for capabilities: manifest + handler + check, zero kernel changes),
browser capability ✅ (Stage 9 — Playwright behind the backend-agnostic
driver seam, optional dependency), plugin system ✅ (Stage 10 — installable
packages contributing capabilities; atomic install, permission review,
dispatch by binding), knowledge graph (if justified).

**Cog (the fifth pillar) ✅** — implemented beyond the staged roadmap:
reflection into episodic/failure memory, versioned policies with rollback
and a durable journal, skill promotion/deprecation by plan signature, and
routing revisions that close the product loop's last arrow (verified
failures teach the router away from broken capabilities). All five pillars
of §2 are now implemented.

**Phase 3 — Distributed Intelligence:** swarms, cloud scheduler, capability
exchange, continuous learning.

Staged build order within Phase 1 (each stage follows the Volume 5 workflow):

| Stage | Deliverable |
|-------|-------------|
| 0 | Kernel: runtime, scheduler, sessions, event bus, state ✅ |
| 1 | Intent engine: objective → constraints → plan-ready intent ✅ |
| 2 | Capability registry + manifest loader + health ✅ |
| 3 | Router (rule-based, recorded decisions) ✅ |
| 4 | Planner: intent → task DAG, re-planning with provenance ✅ |
| 5 | Executor: interactive, background, parallel, checkpoint, resume ✅ |
| 6 | Memory (SQLite): working, project, history, skills ✅ |
| 7 | Verification: evidence, logs, artifacts, confidence ✅ |
| 8 | Research capability ✅ |
| 9 | Browser capability (Playwright) ✅ |
| 10 | Plugin system: install, update, manifests, permissions ✅ |

## 18. Benchmarks

The system benchmarks itself on: task success rate, correctness, speed, cost,
recovery rate, memory usefulness, routing quality, verification quality, and
human intervention rate. Benchmark results live in Volume 4.

---

## Appendix A — Glossary

See Volume 0 §8 for canonical definitions. Volume 0 wins on conflict.

## Appendix B — Decision Records

ADRs live in `docs/volume-4-research/adr/`. Key standing decisions:

- ADR-0001: plugin-first, minimal kernel
- ADR-0002: SQLite-first memory
- ADR-0003: capability-centered, not agent-centered
- ADR-0004: reward shaping as an input to trust scoring (gate preserved)
- ADR-0005: Thinking layer (L4) for Progressive Complexity
- ADR-0006: statistical gate for policy activation (L8)

## Appendix C — Data Schemas

Canonical schemas are code: `nexus/schemas/`. Prose descriptions in Volume 3.
On conflict, Volume 3 (the protocol spec) wins and code must be fixed.

## Appendix D — Sequence: one run, end to end

```
User → CLI: nexus do "objective"
CLI → Intent: parse(objective)            → Intent
Intent → Planner: plan(intent)            → Plan (DAG)
Planner → Router: route(task) per task    → capability bindings (recorded)
Router → Executor: execute(plan)
Executor ⇄ Kernel: schedule / events / checkpoints
Executor → Verification: verify(run)      → Evidence + confidence
Verification → Cog: learn(run, evidence)  → policy/skill updates (gated)
Cog → Memory: promote(...)                → episodic/semantic/procedural writes
Runtime → User: result + evidence + cost report
```
