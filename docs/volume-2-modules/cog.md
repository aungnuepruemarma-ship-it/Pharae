# Module Spec — Cog Learning System

**Status:** Implemented. Code: `nexus/cog/`. Tests: `tests/test_cog.py`.
The fifth pillar — with it, all five pillars of Volume 1 §2 are implemented.

## Purpose

Turn verified execution history into better policies and reusable behavior.
The system gets better over time without mutating itself randomly.

```
Run → Evidence → Evaluation → Failure analysis → Policy update → Skill promotion → Improved routing
```

## Boundary

**Owns:** reflection, the policy lifecycle, skill extraction, the memory
promotion pipeline — Cog is the intended holder of the promotion credential:
in the normal flow it is the only caller of `memory.promote` and
`registry.record_outcome`.

**Must never:** learn from unverified output (Invariant I2 — `learn()`
raises on unverified evidence, and both downstream gates enforce it again
independently), write memory outside the gated pipeline (I3), or modify
kernel/runtime code.

## Components

### Reflection (`learn(run, evidence, plan)`)
Every verified learn promotes an **episodic** record (run, signature,
success, confidence, failed tasks) and one **failure** record per failed
task (error, capability binding, signature) — evidence of failure is as
valuable as evidence of success. Capability score updates flow to the
registry per bound task outcome; unknown bindings are noted, never fatal.

**Reward shaping (ADR-0004).** The trust update sent to the registry is
shaped by a `RewardShaper`: a pure, deterministic
`(verified evidence, success) → reward ∈ [0,1]` that blends confidence and
outcome, then discounts by a cost/friction signal (explicit cost, else the
executor's retry fraction). Borrowed in spirit from Prue/NCP's reward engine
but placed *after* the hard gate — reward affects only the magnitude of a
permitted trust update, never whether learning happens (Invariant I2 intact).
Reliability stays the pure success rate.

### Policy Engine
Versioned, immutable policy records per kind: **propose → activate →
deprecate → rollback**, every transition evented (`policy.*`) and journaled
durably through the memory sink (`policy_events` — an operational record
like routing decisions). Rollback restores the previously active version and
records why. *V1 shortcut, recorded:* activation is immediate; benchmark-
gated trials arrive with the benchmark harness — rollback exists now, so a
bad policy is one call from gone.

### Skill Evolution
`skill_threshold` (default 3) verified successes of the same **plan
signature** (the capability-type chain, e.g. `research→code→verify`) promote
a skill into **procedural** memory: task chain, source-run provenance, mean
source confidence. One skill per signature; a later verified failure of the
signature deprecates it (`skill.promoted` / `skill.deprecated`). Thresholds
are counted from durable memory layers, not in-process state — learning
survives restarts.

### Routing Improvement
`failure_threshold` (default 3) verified failures of a capability propose
and activate a routing-policy revision adding it to `denied`.
`to_routing_policy(active_version)` materializes the record as the
`RoutingPolicy` the router consumes — closing the product loop's last arrow:
the capstone test shows a trusted-but-broken capability failing three
verified runs, Cog denying it, and the next routing choosing the working
alternative that succeeds.

## Verification

13 tests: the evidence gate (unverified → CogError, nothing written),
episodic/failure promotion with provenance, registry score movement in both
directions, unknown-binding resilience, skill threshold/uniqueness/
signature-isolation/deprecation, policy propose-activate-supersede,
rollback with journal durability, threshold-triggered denial consumed by a
real router, and the full improvement loop end to end.
