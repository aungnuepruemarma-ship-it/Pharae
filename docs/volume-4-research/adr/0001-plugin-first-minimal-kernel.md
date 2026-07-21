# ADR-0001: Plugin-first, minimal kernel

**Status:** Accepted
**Date:** 2026-07-21

## Context

Agent systems rot when vendor integrations, browser logic, and model quirks
leak into their core. The AI ecosystem churns fast: models, protocols, and
browser stacks are all replaceable on a 6–18 month horizon. The parts of large
systems that survive churn (Linux, Kubernetes, LLVM) are small kernels with
stable extension interfaces.

## Decision

The kernel contains only lifecycle, events, state, sessions, and scheduling.
Everything else — models, browsers, cloud, research, protocols — enters the
system as capabilities or plugins through the Volume 3 interfaces. The burden
of proof is always on adding code *to* the kernel.

## Alternatives Considered

- **Framework-style monolith** (integrations in-core): fastest to demo, but
  every vendor change becomes a core change; rejected as the known failure
  mode of current agent frameworks.
- **Microservices from day one:** maximum isolation, but massive operational
  cost before there is any user value; rejected for V1 (in-process plugins
  behind stable interfaces get the same boundary at near-zero cost).

## Consequences

Easier: swapping providers, testing the kernel in isolation, long-term
stability. Harder: the first capability costs more (registry + manifest before
any tool runs). Reopen trigger: none anticipated — this is identity-level
(Invariant I5 encodes it).

## Invariant Check

Establishes I1 and I5; consistent with all others.
