# Module Spec — Cog Learning System

**Status:** Spec (post-V1 core loop; minimal version lands with Stage 6–7).

## Purpose

Turn verified execution history into better policies and reusable behavior.
The system gets better over time without mutating itself randomly.

```
Run → Evidence → Evaluation → Failure analysis → Policy update → Skill promotion → Improved routing
```

## Boundary

**Owns:** reflection, policy lifecycle, skill extraction, the memory promotion
pipeline.

**Must never:** learn from unverified output (Invariant I2), write memory
outside the gated pipeline (Invariant I3), or modify kernel/runtime code.

## Components

### Reflection Engine
Success analysis, failure analysis, pattern extraction across runs. Input is
strictly `(Run, Evidence)` pairs with `verified` status.

### Policy Engine
Policies (routing rules, retry budgets, memory promotion criteria) are
versioned objects with confidence tracking. Lifecycle: **propose → trial →
promote → deprecate → rollback**. A policy that regresses benchmarks is rolled
back automatically; every transition is recorded.

### Skill Evolution
Repeated verified successes of the same task shape are extracted into
**skills**: reusable procedures (capability compositions) registered in
procedural memory with provenance to their source runs. Skills carry their own
confidence and are deprecated when they start failing.

## Interfaces

- Input: verified `(Run, Evidence)` pairs; recorded `RoutingDecision`s.
- Output: policy versions, skill entries (via Memory API `promote`), routing
  weight updates.

## Verification

Regression harness: a policy update must not reduce benchmark success rate;
rollback restores prior behavior exactly; every promoted skill traces to ≥N
verified runs.
