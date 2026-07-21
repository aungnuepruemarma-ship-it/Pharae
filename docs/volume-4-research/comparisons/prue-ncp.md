# Comparison — Prue (NCP) vs. Pharae, and the cross-repo picture

**Date:** 2026-07-21 · **Subject:** `aungnuepruemarma-ship-it/Prue` @ `38b36b6`
(pushed 2026-07-19). Reviewed against Pharae's `nexus/cog/`.

## What Prue is

**NCP — Nexus Computing Platform**, self-described as an "AI operating
system": ~11,100 LOC, 41 subpackages, imports clean (`from ncp.kernel import
Kernel`), 293 tests claimed / 34 test files. Stdlib core with optional extras
(`[api]`, `[config]`, `[llm]` Anthropic reasoner). Far broader than a learning
engine — it is a whole runtime: kernel, planner/router/executor, constraint
gate (Φ), **7-tier memory**, knowledge graph, provenance, compression,
curiosity, research loop, world model, distributed workers, recovery,
security.

## Does it contain a "cog"?

**It contains a learning engine, but not one named Cog, and philosophically
different from both Pharae's and the `cog` repo's.** `ncp/learning/` is
**reinforcement-flavored**:

- `RewardEngine.compute(output, verification)` → scalar reward
  (success ± confidence·weight − cost·weight, −0.5 if verification not
  approved). Verification *feeds* the reward rather than *gating* a promotion.
- `ExperienceDB` records (provider, task_type, success, reward, duration).
- `RoutingOptimizer` / `PlannerOptimizer` learn from that experience;
  `TelemetryEngine` observes.
- Skills exist separately (`ncp/skills/`: evolution, extractor, library,
  benchmark) and memory is a 7-tier stack (`ncp/memory/`: working, episodic,
  semantic, procedural, skill, + consolidation/forgetting/replay/ranking).

So verification is present and influences learning — but as a **reward term**,
not as the **hard promotion gate** Pharae and the `cog` repo enforce.

## The cross-repo picture (four repos, three learning philosophies)

| Repo | What it is | Learning engine | Gate philosophy |
|---|---|---|---|
| **Pharae** (this) | Kernel-first runtime; Cog is one module | `nexus/cog/` (~430 LOC): reflection, policy versions+rollback, skills by signature, routing denial | **Hard evidence gate**: `promote()` needs verified evidence + policy id, or nothing |
| **`cog` repo** | Learning-engine-first runtime (~15.5K LOC) | The whole system: belief revision, policy lifecycle, calibration, curiosity, representation competition | **Provenance-chain gate**: `promote_claim` needs a verified experiment claim; denial → FINDING |
| **Prue / NCP** | AI-OS (~11.1K LOC) | `ncp/learning/`: reward engine + experience DB + routing/planner optimizers | **Soft/reward**: verification is a reward term, learning is RL-style |
| **Jog / Hermes** | Operational kernel + security/observability | **none** | n/a — no learning engine |

## Assessment

The user's framing ("cog repo, prue repo they both contain cog system") is
half right: the **`cog` repo literally is Cog**; **Prue has a learning engine
of a different kind** (reinforcement/reward, not evidence-gated promotion).
All three learning-bearing repos independently keep verification in the loop —
but they place it differently:

- Pharae & `cog` repo: verification is a **gate** (nothing learns from
  unverified evidence — Invariant I2).
- Prue: verification is a **signal** (an unapproved result costs reward but
  does not hard-block learning).

That difference is the single most important design fork among them. Pharae's
position — the hard gate — is the stricter, safer one and is the project's
stated invariant; Prue's reward-shaping is more permissive and more RL-native.

## Options (unchanged posture — no code merged)

1. **Keep Pharae's hard gate; borrow Prue's reward shaping as an *input* to
   Cog's confidence, never as a replacement for the gate.** A `RewardEngine`-
   style scalar could enrich `capability.record_outcome` scoring without
   weakening I2.
2. **Mine NCP's 7-tier memory and skills-evolution** for ideas when Pharae's
   memory/skills deepen — it is the most elaborate memory stack of the four.
3. Treat the `cog` repo (not Prue) as the reference *learning engine*, and
   NCP as the reference *AI-OS breadth* — they lead in different dimensions.

Assessment only; nothing merged.
