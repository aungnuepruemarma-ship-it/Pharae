# Protocol — Memory API (v1)

Implemented (Stage 6): `nexus/memory/`. The gate rules below are normative;
the implementation enforces them in code.

## Operations

```
read(layer, query) → [MemoryItem]
search(text | filters) → [MemoryItem]          # cross-layer, read-only
write_working(session_id, key, value)           # only free-write path
promote(evidence_ref, layer, item, policy_id) → MemoryItem   # gated
deprecate(item_id, reason)                      # reversible removal
provenance(item_id) → { run_id, evidence_id, policy_id, promoted_at }
```

## MemoryItem

```
MemoryItem {
  id, layer: working|episodic|semantic|procedural|failure|project,
  content: dict, provenance?, confidence, created_at, deprecated: bool
}
```

## Gate Rules (normative — Invariants I2, I3)

1. `write_working` is the **only** ungated write, and only into the caller's
   session namespace. Working memory is ephemeral.
2. `promote` requires an `evidence_ref` pointing at **verified** evidence and a
   `policy_id` naming the promotion policy that approved it. Calls without
   both are rejected.
3. Only the Cog pipeline holds the promotion credential. Capabilities, models,
   and the executor cannot call `promote`.
4. Every promotion records full provenance and is reversible via `deprecate`.
5. Secrets never enter any layer; the API rejects payloads matching the
   secret-detection policy.

## Events

`memory.promoted`, `memory.deprecated` (payload: item id, layer, policy id).

## Storage note

V1 backend is SQLite (ADR-0002). The API is the stable surface; the backend is
replaceable without a version bump as long as semantics hold.
