# Volume 0 — Manifesto

**Status:** Stable. This document should rarely change. Changes require an ADR.

---

## 1. Vision

An intelligence runtime that coordinates intelligence rather than trying to become
the intelligence. The user states an objective; the runtime decides which models,
tools, browsers, cloud workers, and memories to combine to achieve it — then
verifies the result and learns from the verified outcome.

The long-term identity of the system:

- **Linux** for intelligence — a stable kernel with everything else as modules.
- **Git** for objectives — every run is recorded, diffable, and replayable.
- **Kubernetes** for capabilities — declarative registration, health, scheduling.
- **A notebook** for evidence — results are reproducible and inspectable.
- **A brain** for coordination — layered memory and learning from experience.

The user does not manage models. The user manages outcomes.

## 2. Mission

Build a model-agnostic runtime with a minimal kernel that:

1. Understands objectives (not prompts).
2. Plans work as an explicit execution graph.
3. Routes work across registered capabilities (not hardcoded vendors).
4. Executes with checkpointing and recovery.
5. Verifies every serious result with evidence.
6. Learns from verified experience only.

## 3. Philosophy

- **Objectives over prompts.** The unit of interaction is a goal with constraints,
  not a string sent to a model.
- **Capabilities over products.** The runtime reasons about "browser",
  "code generation", "research", "vision" — never "vendor X's API".
- **Evidence over assumptions.** Claims about what worked come from verification,
  not from model output.
- **Verification before trust.** Nothing is trusted by default; confidence is earned
  per-run and per-capability.
- **Learning from experience.** Policies and skills improve from verified run
  history, never from raw, unverified model output.
- **Separation of execution and learning.** The executor never mutates long-term
  memory directly; learning is a distinct, gated pipeline.

## 4. First Principles

1. **Objectives, not prompts.**
2. **Capabilities, not products.**
3. **Evidence before memory.**
4. **Plugins over kernel.**
5. **Progressive complexity** — solve simple tasks directly; orchestrate only when
   it provides measurable value.
6. **Model-agnostic** — any model or provider can be added or removed.
7. **Deterministic orchestration where possible** — planning and routing should be
   reproducible given the same inputs and registry state.
8. **Progressive autonomy** — autonomy is granted as verification history justifies it.
9. **Human override** — a human can always inspect, pause, or cancel.
10. **Security by default** — side effects are sandboxed, logged, and replayable.

## 5. Kernel Invariants

These are the architectural rules that cannot be broken without intentionally
changing the system's identity. Every feature proposal is evaluated by one
question: **does it preserve the kernel invariants?** If not, it requires an
explicit architecture review (ADR) before acceptance.

- **I1 — Provider-agnostic kernel.** The kernel never references a specific model,
  vendor, browser, or cloud provider. It knows schemas, not implementations.
- **I2 — Evidence-gated learning.** Learning is driven by verified evidence, not
  raw model output.
- **I3 — Policy-gated memory.** Long-term memory updates pass through policy and
  verification. No capability writes persistent memory directly.
- **I4 — Stable interfaces.** Capabilities communicate through stable, versioned
  interfaces (Volume 3), never through direct dependencies on each other.
- **I5 — Plugins by default.** New functionality is added through plugins or
  capabilities unless it is fundamental to the kernel. The burden of proof is on
  putting code *in* the kernel.
- **I6 — Recorded side effects.** Every external side effect is logged and, where
  feasible, replayable.
- **I7 — Human override.** Every run can be inspected, paused, and cancelled by a
  human at any time.

## 6. Design Goals

- A new contributor — or an AI agent — can read the volumes and answer: what is
  this system, why does it exist, how is it organized, what are the invariants,
  how do modules communicate, what belongs in the kernel vs. plugins.
- The exterior is simple (10–12 verbs); the interior may contain dozens of modules.
- The architecture survives technology churn: models, protocols, and browsers are
  replaceable without touching the kernel.

## 7. Non-Goals (V1)

Explicitly out of scope for the first release:

- Multi-agent "civilizations" or autonomous code evolution
- Distributed clusters / swarms
- A knowledge-graph database (SQLite first; graphs only when justified)
- Mobile, desktop, or web dashboard applications
- A marketplace or economic agent system
- Custom model training
- Robotics

These may become future work; they must arrive as capabilities/plugins, not
kernel features.

## 8. Definitions

Canonical nouns of the system (full glossary in Volume 1 Appendix A):

| Term | Meaning |
|------|---------|
| **Objective** | The user's goal, with constraints and desired outcomes. |
| **Intent** | The structured representation of an objective after parsing. |
| **Plan** | An execution DAG derived from an intent. |
| **Task** | A unit of work; a node in a plan. |
| **Capability** | Something the runtime can use (browser, python, a model), described by a manifest. |
| **Worker** | A temporary executor assembled from capabilities for a task. |
| **Session** | A live execution context. |
| **Run** | One complete attempt to satisfy an objective. |
| **Evidence** | What proves a result: logs, tests, artifacts, traces. |
| **Artifact** | A produced object: code, docs, datasets, reports, screenshots. |
| **Policy** | A rule governing choice or action (routing, memory, security). |
| **Memory** | Stored knowledge or learned behavior, in layered stores. |
| **Skill** | A promoted, reusable procedure extracted from verified runs. |

## 9. Success Criteria

The V1 runtime is successful if a user can type:

```
nexus do "Build a REST API from this specification"
```

and the system can:

1. Understand the objective.
2. Produce a plan.
3. Select the right capabilities automatically.
4. Execute the work.
5. Verify the result.
6. Save useful experience for future runs.

If those six steps work reliably, the core architecture is validated. Everything
else — dashboards, cloud orchestration, swarms, capability exchange, advanced
learning — is added incrementally on top of the stable foundation.

**Status:** this criterion is met and runnable. `nexus do "…"` (see the CLI
spec) drives all six steps end to end against the real subsystems — understand,
plan, select, execute, verify, learn — with learning persisted across
invocations. What remains unproven is not the architecture but its behavior
under sustained real-world use.
