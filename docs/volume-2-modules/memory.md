# Module Spec — Memory System

**Status:** Spec (Stage 5). Not yet implemented. Storage decision: ADR-0002
(SQLite first).

## Purpose

Layered storage of knowledge and learned behavior. Memory is never one blob.

## Layers

| Layer | Contents | Write path |
|-------|----------|-----------|
| Working | Current run context | Executor, freely (session-scoped, ephemeral) |
| Episodic | What happened in past runs | Learning pipeline only |
| Semantic | Stable facts, concepts, decisions | Learning pipeline only |
| Procedural | Successful workflows (skills) | Skill promotion only |
| Failure | What went wrong, why, the fix | Learning pipeline only |
| Project | Per-project state, goals, history | Policy-gated |

## Promotion Rules (Invariants I2, I3)

1. Working memory is free to write and dies with the run (except what
   verification captures as evidence).
2. Nothing enters episodic/semantic/procedural/failure memory except through
   the Cog pipeline, and only backed by **verified** evidence.
3. Promotions record provenance: which run, which evidence, which policy
   version approved it.
4. Every promotion is reversible: deprecation and rollback are first-class.

## Boundary

**Owns:** the stores, the Memory API, promotion bookkeeping, search.

**Must never:** be written directly by capabilities or models; interpret
content (it stores; Cog decides).

## Storage

SQLite, one file per store or one file with per-layer tables (implementation
choice). A knowledge graph is added only when a recorded limitation justifies
it — that requires a new ADR superseding ADR-0002.

## Interfaces

Memory API (Volume 3): `read(layer, query)`, `write_working(...)`,
`promote(evidence_ref, layer, item, policy)`, `search(...)`, `deprecate(...)`.

## Verification

Gate tests: direct writes above working memory are rejected. Provenance tests:
every promoted item traces to verified evidence. Rollback tests.
