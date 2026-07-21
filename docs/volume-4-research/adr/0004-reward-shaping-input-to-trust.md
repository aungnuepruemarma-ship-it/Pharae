# ADR-0004: Reward shaping as an input to trust scoring

**Status:** Accepted
**Date:** 2026-07-21

## Context

Reviewing sibling repositories (Volume 4 comparisons), Prue/NCP models
learning with a `RewardEngine` that turns an outcome plus verification into a
scalar reward (success ± confidence·weight − cost·weight, penalized when
verification is not approved). Pharae's trust score today moves on a simpler
target: `confidence` on success, `0` on failure. That target ignores the
*cost* of a success — a capability that succeeds only after retries, or at
high cost, builds trust exactly as fast as a clean, cheap one.

The question: can Pharae borrow reward shaping to enrich trust **without
weakening its hard evidence gate** (Invariant I2), which is the one place
Pharae is stricter than Prue (gate vs. signal)?

## Decision

Introduce `nexus.cog.RewardShaper`: a pure, deterministic function
`(verified Evidence, success) → reward ∈ [0, 1]`, blending confidence and
outcome and then discounting by a cost/friction signal (explicit normalized
cost if present, else the executor's retry fraction). Cog computes the reward
from a run's *own verified evidence* and passes it to
`CapabilityRegistry.record_outcome(..., reward=...)` as the **trust target
only**. Reliability remains the pure success rate.

The gate is untouched: `record_outcome` still refuses any evidence that is not
verified, before reward is ever consulted. Reward shaping affects only the
*magnitude* of a permitted trust update — it can never admit an unverified
outcome. With `reward=None` the registry falls back to the confidence target,
so prior behavior is a strict special case (and standalone registry use is
unchanged).

## Alternatives Considered

- **Adopt Prue's reward as a soft signal that can bypass the gate:** rejected
  — it would violate I2, the project's stricter and safer position.
- **Reward-shape reliability too:** rejected — reliability is defined as the
  observed success rate; shaping it by cost would conflate two distinct
  signals. Cost belongs in trust, which is already a judgment, not a rate.
- **Put the shaper in the registry:** rejected — reward weighting is a
  learning policy; Cog owns learning, the registry applies the number.

## Consequences

Easier: the runtime now learns to distrust chronically expensive/flaky
capabilities over time, complementing the router's per-decision cost penalty
with a durable one. Harder: one more (small, pure, defaulted) knob. Reopen
trigger: evidence that cost-shaped trust degrades routing quality on the
benchmark suite (Volume 4) — the weights, or the whole shaper, are then tuned
or removed.

## Invariant Check

- **I1** (provider-agnostic): reward is computed over evidence fields only —
  no vendor references. Preserved.
- **I2** (evidence-gated learning): the gate is unconditional and runs before
  reward; reward cannot admit unverified evidence. **Strengthened in intent,
  unweakened in fact.**
- **I3** (policy-gated memory): unaffected — this touches capability scoring,
  not memory promotion.
- Determinism: reward is a pure function of evidence fields; no clock, no
  randomness. Preserved.
