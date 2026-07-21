# Comparison — Jog (Hermes Core) vs. Pharae

**Date:** 2026-07-21 · **Subject:** `aungnuepruemarma-ship-it/Jog` @ `d68bf39`
(last pushed 2026-07-17, "Phase 8: certification review — certified for
limited release only"). Reviewed against Pharae as of Stage 10 + Cog.

## Headline finding

**Jog does not contain Cog.** There is no learning engine in the repository:
no reflection over outcomes, no skills, no experience-driven policy
versioning, no evidence-gated promotion pipeline, and the string "cog"
appears nowhere. What Jog *is*: **Hermes Core**, a sibling implementation of
the same architectural vision's kernel/state/policy layers — Sprint 1 of a
"local-first autonomous engineering workspace", stdlib-only, offline-tested,
with unusually strong operational-engineering discipline.

Near-misses that explain the recollection:

- `scheduler.promote_pending()` — task-state promotion (pending → ready),
  not memory promotion.
- Six memory stores behind one facade (ADR-006) — but a *different* six
  (see below), with an "explicit and audited" working→semantic promotion
  that is manual, not evidence-driven.
- ADR-010's circuit breaker denies failing providers — reactive health
  failover, not verified learning.
- `state/verify.py` — at-rest database invariant checking, not outcome
  verification.

## Architecture mapping

| Concern | Pharae | Jog / Hermes | Verdict |
|---|---|---|---|
| Kernel (events, scheduler, state) | Stage 0; event bus + replayable log | Event spine + durable log **+ dead-letter queue**; task state machine (pure); lease-based scheduler | Equivalent cores; Hermes' DLQ and leases are ideas worth stealing |
| Memory | Working/Episodic/Semantic/**Procedural/Failure/Project**; promotion gated on verified evidence + policy id | Working/Episodic/Semantic/ExecutionHistory(read model)/VectorIndex(lexical fallback)/KnowledgeGraph(placeholder); single-writer ingesters + watermarks; manual audited promotion | Different decompositions. Pharae's is learning-oriented; Hermes' is retrieval-oriented. Complementary, not competing |
| Verification | Run → Evidence engine (confidence, trace consistency, checks) | At-rest DB invariant checks only | **Pharae only** — this is the layer Cog depends on |
| Learning (Cog) | Implemented: reflection, policy versions + rollback, skills, routing revision | **Absent** | Pharae only |
| Routing | Manifest-scored, recorded decisions, learned denial via Cog | Provider registry with capability match, health probes, **circuit breaker**, null-provider floor, degraded plans | Complementary timescales: Hermes' breaker is fast/reactive; Cog's denial is slow/verified. Both belong in a mature router |
| Security | Organizational caveats, pending layer | **Permission gate with a non-bypass ADR (012)**, capability taxonomy, **effect ledger** (gate → ledger → execute → ledger) | **Hermes is ahead** — this is Pharae's missing security layer, designed |
| Observability | Event log | Structured JSON logging, trace context, metrics, health reporting (ADR-011) | Hermes ahead |
| Surfaces | None yet | CLI + local HTTP API + config system (defaults → TOML → env) | Hermes ahead |
| Plugins | Atomic install, permission review, dispatch by binding | Manifest discovery/registration; sandbox stubbed | Pharae ahead on lifecycle; Hermes' isolation ADR (007) worth reading before Pharae builds sandboxing |
| Governance | Six volumes, ADRs, invariants | Frozen baseline → change sets → ADRs → sprint log → `ledger.json` → certification review; "claims without artifacts don't count" evidence policy | Different styles, same spirit; Hermes' machine-readable ledger is a nice practice |

## Assessment

Jog and Pharae are two runs at the same constitution. Pharae went **deep on
the intelligence loop** (intent → plan → route → execute → verify → learn)
and has the only Cog. Hermes went **deep on operational hardening** (effect
ledger, permission non-bypass, observability, degraded-mode routing,
surfaces) and stops exactly where Pharae's distinctive layers begin.

The overlap (kernel, scheduler, SQLite state, checkpoints, plugins, events)
is real but neither side's port is obviously better wholesale — and porting
kernels is churn, not value.

## Recommendation

1. **Cog stays in Pharae.** There is nothing in Jog to replace or merge into
   `nexus/cog/` — it exists only here.
2. **Treat Jog as the design donor for Pharae's next layers**, in order of
   leverage: the **permission gate + effect ledger** (ADR-012's non-bypass
   discipline maps directly onto Pharae's two "organizational until the
   security layer lands" caveats), the **observability spine** (ADR-011),
   and the router's **circuit breaker + null floor** (ADR-010) as the fast
   reactive complement to Cog's slow verified denial.
3. **Adopt ideas, not code**: each arrives through Pharae's own workflow
   (spec → interfaces → tests → implementation) citing the Hermes ADR as
   prior art — no wholesale porting of a second kernel.
4. Longer term, decide whether Hermes continues as a separate product or is
   absorbed; nothing in this comparison forces that decision now.
