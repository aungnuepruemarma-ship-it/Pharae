# Module Spec — Science Layers (L9, L10, L12)

**Status:** Foundation implemented. Code: `nexus/science/`. Tests:
`tests/test_science.py`. Layers L9/L10/L12 of the CogOS v2.0 map. The deeper
science layers (L11 primitive discovery, L14–L17 organization discovery /
evolution / genome / math) are **staged, not built** — recorded honestly in
the Volume 4 layer map.

## Purpose

An evidence-first foundation for the blueprint's cognitive-science stack,
built behind Pharae's gates rather than ported wholesale from the sibling
`cog` repo. The through-line: **every learn path here refuses unverified
evidence** (Invariant I2) — the science layers are held to the same standard
as memory and capability scoring.

## L10 — Theory Ledger (`theory.py`)

Hypotheses earn their way into knowledge. A `Theory` is PENDING → accrues
verified observations (supporting / refuting) → ACTIVE on enough replications,
REJECTED on enough refutations. Only an ACTIVE theory may be **promoted**, and
promotion writes to **semantic memory through the gate** (verified evidence +
policy id, full provenance). Content-derived ids (`thy-…`) make proposal
idempotent and deterministic. Realizes L24's "no theory without replication."
Emits `theory.proposed/observed/rejected/promoted`.

## L9 — Representations (`representations.py`)

Competing reasoning strategies (chain-of-thought, graph, HTN, …) accrue
verified win/loss. `best()` returns the highest verified win-rate among those
with ≥ `min_trials` — a lucky single run cannot win; **only evidence
survives**. Deterministic tie-breaks (rate, trials, name). Emits
`representation.recorded`.

## L12 — Organizations (`organizations.py`)

Cognitive teams as **capability compositions**, consistent with ADR-0003
(*not* persistent agents): an `Organization` is a named ordered list of
capability *types* (e.g. `research→code→verify`). Organizations accrue
verified performance and `best_for(signature)` selects by success rate. Emits
`organization.defined/recorded`.

## Boundary

**Owns:** theory lifecycle, representation competition, organization
performance. **Must never:** learn from unverified evidence, write long-term
memory except through the promotion gate, or spawn persistent agents (orgs are
compositions).

## Recorded limits (the honest staging)

Not built here, deliberately: L11 primitive discovery; L14 organization
discovery from traces; L15 evolution/mutation; L16 genome encoding; L17
organization mathematics (performance prediction). These are the `cog` repo's
depth; integrating them behind Pharae's gates is future work, one layer at a
time, each with its own spec and tests. The Volume 4 layer map tracks status.

## Verification

14 tests: theory pending→active→promoted with gated semantic write and
provenance, refutation→rejected, unverified-evidence rejection on all three
modules, deterministic theory ids, representation competition (win-rate,
min-trials gating, only-evidence-survives), and organization
composition/selection by verified success.
