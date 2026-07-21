# Module Spec — Capability Router

**Status:** Implemented (Stage 3). Code: `nexus/router/`. Tests:
`tests/test_router.py`. Decision schema: `nexus/schemas/routing.py`.

## Purpose

For each task in a plan, choose which registered capability executes it.
Decides; never executes.

## Boundary

**Owns:** routing decisions and their recording.

**Must never:** execute tasks, mutate manifests, or contain vendor-specific
branches. Routing operates on manifest fields only (Invariant I1).

## Behavior

### Policy (`RoutingPolicy`, frozen)
A declarative rule set with an id: a policy id always names one exact
behavior — a changed policy is a new policy. Fields: `require_healthy`,
`min_reliability`, `min_trust`, `max_cost`, `max_latency_ms`,
`preferred`/`denied` capability names (user preferences), score weights, and
the preference bonus.

### Evaluation per task
1. Candidates: `registry.find(task.capability_type)` in the registry's
   deterministic order.
2. **Exclusion** with an explicit recorded reason, checked in order: denied by
   policy → unhealthy (always excluded) → health unknown when
   `require_healthy` → below `min_reliability`/`min_trust` → over
   `max_cost`/`max_latency_ms`. By default UNKNOWN health is admitted —
   unchecked capabilities are usable until proven unhealthy.
3. **Scoring** of the remaining candidates (deterministic):
   `w_reliability·reliability + w_trust·trust − w_cost·(cost/max_cost) −
   w_latency·(latency/max_latency) + preference_bonus·[name ∈ preferred]`,
   with cost/latency normalized within the eligible set. Default weights
   0.4/0.4/0.1/0.1, bonus 0.25.
4. **Choice:** highest score; ties break by name (ascending) then version
   (newest). Same registry state + same policy → same choice, always.

### Recording (Invariant I6)
Every `route()` call — routable or not — appends a `RoutingDecision`: task id,
capability type, policy id, the full per-candidate evaluation (score *or*
exclusion reason), the chosen capability id, and the reason. The log is
returned as copies and is complete enough to replay the choice. Wiring
`decision_sink` to `MemorySystem.record_routing_decision` (Stage 6) persists
every decision durably; the log is the raw material for benchmark-driven and
adaptive routing, which remain gated on this history.

### Unroutable tasks
The router never guesses. `route()` never raises: an unroutable task yields a
decision with `chosen=None` and a reason ("no registered capabilities of
type …" / "all candidates excluded by policy") plus a `route.unroutable`
event. `route_plan()` binds `task.capability_binding` for every routable task,
records every decision first, then raises `UnroutableError` naming the
unroutable tasks — so the planner or user acts on the full decision set.

## Events

`route.decided` (`{decision_id, task_id, capability}`), `route.unroutable`
(`{decision_id, task_id, reason}`).

## Verification

19 tests: single-candidate, quality/cost/latency dominance, preference-bonus
flip, name tie-break, cross-instance determinism, every exclusion rule with
its recorded reason, unknown-vs-unhealthy defaults, decision completeness,
unroutable recording + events, copy isolation of the log, plan binding, and
route-plan explicit failure after recording.
