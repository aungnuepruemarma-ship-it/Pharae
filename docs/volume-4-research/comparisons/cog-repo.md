# Comparison — `cog` repo vs. Pharae's Cog (`nexus/cog/`)

**Date:** 2026-07-21 · **Subject:** `aungnuepruemarma-ship-it/cog` @ `5a91c18`
(pushed 2026-07-16). Reviewed against Pharae's `nexus/cog/` (this repo).

## Headline

**Both repos contain a full Cog — but they are inverses of each other.**

- **Pharae** is a *kernel-first runtime* where Cog is **one module** (~430
  LOC) plugged into a larger system (intent → plan → route → execute →
  verify → learn). Cog is a consumer of the runtime's gates.
- **The `cog` repo** is a *learning-engine-first runtime* (~15,500 LOC, 132
  modules, imports clean, benchmark runs) where the **entire runtime is built
  around** the scientific learning loop. Here the runtime is a consumer of
  Cog, not the other way round.

They are two serious answers to the same constitution, weighted oppositely.
Neither is a copy of the other.

## What the `cog` repo actually contains

| Area | Modules | Notes |
|---|---|---|
| `runtime/` | core, adapter, **model_adapters (live Anthropic + OpenAI/local)**, session, hooks, trace, context | `CogRuntime.run(task) → Experience`; model-independent behind an adapter port — this is the model-agnostic pillar, realized with *real* providers |
| `execution/` | planner, executor, ordering, router, strategist, tools | its own execution stack |
| `experience/` | record, store, graph, emitter, benchmark_evidence | `Experience` with belief-state, reality-delta, causal graph, replay info, metrics, `validate()` |
| `learning/` | belief engine (contradiction, consolidation/decay, synthesis, lifecycle), **policy lifecycle (candidate→experimental→validated→active→challenged→retired)**, calibration, compression, corrections, curiosity, genome, primitives, representation competition/search, skill_compiler, organizations | the bulk of the system |
| `science/` | experiment, ledger, orchestrator, pipeline, **promotion (`promote_claim` + `PromotionDenied`)**, verification (`FormalVerifier`) | promotion requires provenance-verified experiment claims; denial → record a FINDING, never bypass |
| `verification/` | checks, corroboration, pipeline (`threshold=0.7`) | multi-check verification with corroboration |
| `memory/`, `research/`, `economics/`, `workspace/`, `experiment/` | stores+router; primitive discovery; reasoning-economics strategy; workspace builder; A/B experiment manager | breadth well beyond Pharae's Cog |
| `evaluation/` | epistemic suite (adversarial poisoning, contradiction, false-pattern, scope precision, replay…), stress/adversarial/real-trace versions, stats, baselines | a research-grade eval harness; Kaggle rollout notebooks |

Benchmark run (`python run.py bench`): gate accuracy 1.0, verified rate 0.64,
11/12 behavioral probes pass. **One self-reported regression:** belief
revision did not reconcile a self-contradiction (`belief_revision_observed:
false`). So it runs and largely works, with one known open defect.

## Concept mapping

| Pharae `nexus/cog/` | `cog` repo | Assessment |
|---|---|---|
| `learn(run, evidence)` → episodic/failure promotion | `CogRuntime.run` → `Experience` + emitter → stores/graph | cog repo is richer (causal graph, replay, belief state) |
| `PolicyEngine`: propose→activate→deprecate→rollback | `PolicyLifecycle`: candidate→experimental→validated→active→challenged→retired, **belief-linked** (`on_belief_challenged`) | cog repo's is a superset; belief-coupled transitions are genuinely more advanced |
| skills by plan signature, N successes | `skill_compiler`, primitives, representation competition | cog repo far deeper |
| routing revision denies failed capability | strategist + reasoning economics | different framing |
| evidence-gated `promote()` (verified + policy id) | `promote_claim` gated on provenance-verified experiment claims | **same principle, stronger enforcement** — provenance chain, not just a boolean |
| verification confidence + trace consistency | `VerificationPipeline` (checks, threshold) + `FormalVerifier` + corroboration | cog repo is a fuller verification subsystem |

## Assessment

Pharae's Cog is a **clean, minimal, gate-correct** learning module — the
right size for a kernel-first system, and everything it does is tested and
invariant-aligned. The `cog` repo is a **research-grade learning runtime** —
vastly more capable (belief revision, calibration, curiosity, representation
competition, formal verification, reasoning economics, real model adapters,
an epistemic eval suite) but heavier, with one open self-check regression and
a README whose described layout lags the real (deeper) tree.

The shared DNA is unmistakable and correct in both: **learning is gated on
verified evidence; promotion is the only sanctioned adoption path; bypassing
the gate is a FINDING, never a shortcut.** That invariant survived in both
independent implementations — strong signal it is load-bearing.

## Options (for the user to choose — not yet acted on)

1. **Keep both, cite the `cog` repo as the reference learning engine.** Treat
   Pharae's `nexus/cog/` as the compact in-kernel version; treat the `cog`
   repo as the advanced standalone one. Record the relationship (this doc).
2. **Port specific advances into Pharae's Cog**, each via Pharae's workflow
   (spec → tests → impl): belief-linked policy lifecycle, provenance-chain
   promotion (`promote_claim`), the corroboration verifier, calibration. High
   value, invariant-compatible.
3. **Adopt the `cog` repo's model adapters** (`AnthropicAdapter`,
   `OpenAIAdapter`) as Pharae's first real "model" capability — it is the
   piece Pharae has specced but never built, and it already exists and works.
4. **Fix the `cog` repo's open regression** (belief self-contradiction
   reconciliation) in place, if the goal is to advance that repo rather than
   Pharae.

No merging or code changes made yet — this is the assessment you asked for.
