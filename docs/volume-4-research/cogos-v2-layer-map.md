# CogOS v2.0 — 24-Layer Vision, Mapped Honestly to Reality

**Status:** Research vision map (Volume 4), not the constitution. It records
the 24-layer "Cognitive Operating System" north-star and — per the governance
invariant *nothing promoted without evidence* — states plainly what is
**implemented and tested** vs. **described**, in Pharae and in the sibling
`cog` repo. A layer is 🟢 only where code runs and has tests.

## The invariant that governs even this document

The blueprint's own governance rules (L24) are the acceptance test for every
row below: *nothing promoted without evidence; everything reversible;
everything auditable; no permanent memory without verification.* Pharae
already enforces these as Kernel Invariants I2/I3 and its gates — so "complete"
here means *gate-backed and tested*, never *designed*.

## Layer map

Legend: 🟢 implemented+tested · 🟡 partial · ⚪ absent · N/A external.

| L | Layer | Pharae | `cog` repo | Note |
|---|-------|:--:|:--:|------|
| L0 | Hermes OS | N/A | N/A | host OS; out of scope for both |
| L1 | Runtime (plan→exec→verify) | 🟢 | 🟢 | Pharae: kernel + executor + verification engine |
| L2 | Workspace (temp cognition) | 🟢 | 🟢 | Pharae: per-session working memory, cleared on session end |
| L3 | Memory (persistent, gated) | 🟡 | 🟢 | Pharae has 6 gated layers; blueprint's 8 add Theory/Organization stores Pharae lacks |
| L4 | **Thinking (reasoning budget)** | 🟢* | 🟡 | *implemented this turn (`nexus/thinking/`); realizes First Principle #5 |
| L5 | Economics (compute/model choice) | 🟡 | 🟢 | Pharae: router scores cost/latency/trust; no model-tier selection (needs real model capabilities) |
| L6 | Skills (verified, replayable) | 🟢 | 🟢 | Pharae: Cog skills by plan signature, promote/deprecate |
| L7 | Reflection (post-verify) | 🟢 | 🟢 | Pharae: Cog reflection → episodic/failure memory |
| L8 | Experiment Manager (stats) | ⚪ | 🟢 | Holm/bootstrap/effect-size; Pharae's benchmark harness not yet built |
| L9 | Representations (competing) | ⚪ | 🟢 | `cog` repo: representation search + competition |
| L10 | Theory Ledger | ⚪ | 🟢 | `cog` repo: `science/ledger` |
| L11 | Primitive Discovery | ⚪ | 🟢 | `cog` repo: `research/primitive_discovery` |
| L12 | Organization Runtime | ⚪ | 🟢 | Pharae is capability-centered (temporary workers), not persistent orgs — a deliberate ADR-0003 choice |
| L13 | Organization Competition | ⚪ | 🟢 | `cog` repo |
| L14 | Organization Discovery | ⚪ | 🟡 | `cog` repo |
| L15 | Organization Evolution | ⚪ | 🟢 | `cog` repo |
| L16 | Genome + Org Math | ⚪ | 🟢 | `cog` repo: `learning/genome` |
| L17 | Autonomous Research (full loop) | 🟡 | 🟢 | Pharae Stage 8 = retrieval only; no hypothesis→experiment→theory loop |
| L18 | Knowledge Graph | 🟡 | 🟡 | Pharae: memory search, no graph (ADR-0002 defers it); NCP/Prue has a graph |
| L19 | Self Model | ⚪ | 🟡 | calibration/blind-spots; NCP has fragments |
| L20 | Curriculum | ⚪ | ⚪ | practice-task generation; nowhere yet |
| L21 | Autonomous Research Lab | 🟡 | 🟢 | see L17 |
| L22 | Distributed Cognition | ⚪ | ⚪ | Pharae Phase 3; NCP/Jog have worker/sync fragments |
| L23 | Deployment (daemon, doctor) | 🟡 | 🟡 | Pharae: state snapshot/restore primitives; Jog/Hermes strongest (runbooks, doctor) |
| L24 | Governance | 🟢 | 🟢 | **Pharae's strongest alignment**: evidence-gated promotion, reversible deprecation, recorded decisions, invariants |
| L25 | Executive Meta-Cognition | ⚪ | ⚪ | the "CEO" layer — nowhere yet; genuinely novel |

## What this map says

- **Pharae leads on the spine and the conscience:** L1–L2 runtime/workspace,
  L3 gated memory, L6–L7 skills/reflection, and above all **L24 governance** —
  the layer the blueprint calls the highest authority is the one Pharae was
  built around from Volume 0.
- **The `cog` repo leads on the science:** L8–L17 (experiments, statistics,
  representations, theories, organizations, genome). That is its whole design;
  Pharae deliberately does *not* have persistent organizations (ADR-0003).
- **Genuinely unbuilt everywhere:** L20 Curriculum, L25 Executive
  Meta-Cognition, and real L22 Distributed Cognition.

So the two codebases are **complementary halves of the 24-layer vision**, not
competitors: Pharae is the governed runtime + memory + learning core; the
`cog` repo is the cognitive-science engine. A unified CogOS is closer to
"integrate the two behind Pharae's gates" than "build 24 layers from zero."

## Honest maturity (Pharae only)

- **Architecture of the built layers:** high — every implemented layer is
  spec'd, tested, invariant-checked.
- **Coverage of the 24-layer vision:** ~8 of 25 green, ~5 partial. The
  ambition is real but most of L8–L23 is *described*, and in Pharae's case
  largely *unbuilt* (it lives in the `cog` repo or nowhere).
- **Field maturity:** unproven — no sustained real-world deployment, matching
  the blueprint's own Phase IV/V caveat. This is the true bottleneck.

## Recommended path (evidence-first, not layer-count-first)

1. **L4 Thinking — done this turn.** Realizes Progressive Complexity.
2. **L5 Economics** next, once real model capabilities exist (adopt the `cog`
   repo's model adapters) — then Thinking's modes can actually choose models.
3. **L8 Experiment Manager / benchmark harness** — unlocks the statistical
   justification L24 governance already asks for and Cog's policy trials need.
4. Treat L9–L17 as **integration from the `cog` repo behind Pharae's gates**,
   not a green-field rebuild.
5. L25 Executive Meta-Cognition only after L8 exists — it needs measurements
   to allocate against.
