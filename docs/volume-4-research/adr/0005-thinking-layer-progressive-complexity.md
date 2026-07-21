# ADR-0005: Thinking layer (L4) for Progressive Complexity

**Status:** Accepted
**Date:** 2026-07-21

## Context

First Principle #5 (Volume 0) — *solve simple tasks directly; only use
orchestration when it provides measurable value* — was stated but never
mechanized. Every objective, trivial or vast, took the same planner path. The
CogOS v2.0 vision (Volume 4 layer map) makes this an explicit layer, L4
Thinking: assess how much reasoning an objective needs before planning.

## Decision

Add `nexus/thinking/`: a deterministic `ThinkingBudgeter.assess(intent) →
ThinkingBudget` that classifies an intent into REFLEX / DELIBERATIVE /
RESEARCH over intent features only, producing effort advice (plan depth,
context gathering, parallelism, retry and stopping thresholds). The planner
accepts an optional budget that steers `gather_context`; the budget can never
remove the structurally-appended verify step or open any gate.

## Alternatives Considered

- **Model-driven effort estimation now:** rejected — puts a vendor in a core
  reasoning path (I1) and loses determinism. The `ThinkingBudget` schema is
  the stable surface; a model-assisted estimator can arrive later as a
  capability behind it.
- **Let the planner infer effort implicitly:** rejected — effort assessment is
  a distinct concern (L4 above the planner); folding it in would entangle two
  layers and hide the decision from observation.
- **Have the budget drop verification for REFLEX tasks:** rejected outright —
  verification is a structural invariant (Volume 1 §13); progressive
  complexity reduces *orchestration*, never *evidence*.

## Consequences

Easier: simple objectives get minimal plans; research objectives declare wider
budgets up front; the effort decision is now observable (`thinking.assessed`)
and tunable. Harder: one more heuristic layer to maintain. Reopen trigger: a
model-assisted budgeter, or evidence that the mode thresholds mis-serve real
workloads (tune against golden tests / the future benchmark harness).

## Invariant Check

- **I1** (provider-agnostic): assessment is over intent features only, no
  vendor. Preserved.
- **I2/I3** (gates): the budget is advice; it cannot open the evidence or
  memory gates, and explicitly cannot remove the verify step. Preserved.
- Determinism: same intent → same budget. Preserved.
