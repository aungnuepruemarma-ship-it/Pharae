# Module Spec — Capability Router

**Status:** Spec (Stage 3). Not yet implemented.

## Purpose

For each task in a plan, choose which registered capability executes it.
Decides; never executes.

## Boundary

**Owns:** routing decisions and their recording.

**Must never:** execute tasks, mutate manifests, or contain vendor-specific
branches. Routing operates on manifest fields only.

## Behavior

Inputs to a decision: task capability type, cost, latency, trust, context,
user preferences, historical performance (from recorded decisions + verified
outcomes).

- **V1 is rule-based and deterministic:** an ordered policy list evaluated over
  manifest fields. Same task + same registry snapshot + same policies → same
  choice.
- **Every decision is recorded** as a `RoutingDecision` (task, candidates
  considered, scores, chosen capability, policy version, timestamp). This
  record is the raw material for later benchmark-driven and adaptive routing —
  those upgrades are gated on having real decision history to evaluate.
- Emits `route.decided` events.
- If no capability satisfies the task, routing fails explicitly
  (`route.unroutable`) — the planner re-plans or the user is asked; the router
  never guesses.

## Interfaces

- Input: `Task` + registry query results + policy set.
- Output: capability binding on the task + persisted `RoutingDecision`.

## Verification

Determinism tests; policy-ordering tests; unroutable-task behavior; decision
records are complete enough to replay the choice.
