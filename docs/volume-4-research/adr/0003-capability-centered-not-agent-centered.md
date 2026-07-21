# ADR-0003: Capability-centered, not agent-centered

**Status:** Accepted
**Date:** 2026-07-21

## Context

Most agent frameworks ship a roster of named agents ("research agent",
"browser agent", "coding agent"). Rosters ossify: each agent accretes special
cases, agents overlap, and adding a use case means adding another hardcoded
agent. The runtime's product identity is coordination, and coordination wants
uniform units to reason over.

## Decision

The system's unit is the **capability** (research, browser, code, memory,
verification), described by a uniform manifest. Temporary **workers** are
assembled from capabilities per task and dissolved afterward. No named agents
exist in the core.

## Alternatives Considered

- **Agent roster:** familiar to users of existing frameworks, but hardcodes a
  million special agents and puts orchestration knowledge inside each agent
  instead of the router/planner; rejected.
- **Hybrid (agents as sugar over capabilities):** possible later as a UX layer
  or plugin, but not a core concept; deferred.

## Consequences

Easier: routing (uniform manifests are comparable), composition (plans mix
capability types freely), replacing any single ability. Harder: some user
familiarity ("where are the agents?") — addressed by the CLI's verb-based
surface. Reopen trigger: evidence that persistent-role workers materially beat
per-task assembly on the benchmark suite.

## Invariant Check

Reinforces I1 and I4 (uniform stable interfaces); consistent with all others.
