# ADR-0002: SQLite-first memory

**Status:** Accepted
**Date:** 2026-07-21

## Context

The memory architecture calls for six layered stores with gated promotion
(Volume 1 §11). It is tempting to reach for a graph or vector database
immediately, but no recorded workload justifies one yet, and the Memory API
(Volume 3) is the stable surface — the backend is an implementation detail.

## Decision

V1 memory is SQLite: zero-dependency, transactional, file-based, trivially
snapshottable. Layers are tables; provenance is foreign keys to runs and
evidence. Richer stores are added only when a limitation is *recorded* (a
failing query pattern, a scale wall) in Volume 4, via a superseding ADR.

## Alternatives Considered

- **Graph database first:** matches the long-term knowledge-graph vision, but
  adds an operational dependency before any promotion pipeline exists to fill
  it; rejected as premature (violates progressive complexity).
- **Vector store first:** semantic search is useful but is a *feature of* a
  layer, not the storage foundation; can be added behind `search()` later.
- **Plain JSON files:** simplest, but no transactions — promotion gating wants
  atomicity.

## Consequences

Easier: setup, testing, checkpoint/backup (copy a file). Harder: graph
traversals and similarity search need application-level code until upgraded.
Reopen trigger: a recorded query pattern that SQLite cannot serve within
performance targets.

## Invariant Check

Supports I2/I3 (transactional gates), I6 (durable provenance). Touches no
kernel code (I1, I5 preserved — memory is a subsystem behind an API).
