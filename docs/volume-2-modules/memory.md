# Module Spec — Memory System

**Status:** Implemented (Stage 6). Code: `nexus/memory/`. Tests:
`tests/test_memory.py`. Storage: SQLite per ADR-0002. Protocol:
Volume 3 `memory-api.md` (normative gate rules).

## Purpose

Layered storage of knowledge and learned behavior. Memory is never one blob.

## Layers

| Layer | Contents | Write path |
|-------|----------|-----------|
| Working | Current run context | `write_working` — the only ungated write; session-scoped, cleared with the session |
| Episodic | What happened in past runs | `promote` only |
| Semantic | Stable facts, concepts, decisions | `promote` only |
| Procedural | Successful workflows (skills) | `promote` only |
| Failure | What went wrong, why, the fix | `promote` only |
| Project | Per-project state, goals, history | `promote` only |

## Gate Enforcement (Invariants I2, I3)

- `promote(evidence, layer, content, policy_id)` rejects: unverified or
  non-`Evidence` evidence, a missing policy id, promotion into the working
  layer, secret-like content, and non-JSON-serializable content — all before
  touching storage.
- **There is deliberately no generic `write(layer, …)` API.** The absence of
  an ungated write path is part of the contract, and a test asserts the
  methods do not exist.
- Every promoted item records full provenance (`run_id`, `evidence_id`,
  `policy_id`, `promoted_at`), queryable via `provenance(item_id)`.
- `deprecate(item_id, reason)` is reversible removal: excluded from default
  reads/searches, retained and queryable with `include_deprecated=True`.
  Idempotent; unknown ids error.
- Caller restriction (only Cog may call `promote`) remains organizational
  until the security layer lands — the evidence/policy gates are code.

## Secret Rejection

Every write path (working included) walks the payload and rejects:
credential-like key names (`password`, `api_key`, `token`, …) with non-empty
values, and value patterns (PEM private-key blocks, AWS access-key ids,
GitHub tokens, `sk-…` API-key shapes, bearer tokens). Recorded as policy:
false positives are acceptable; leaked credentials are not.

## Reads

`read(layer)` in insertion order; `search(text, layer?)` cross-layer LIKE
match; both exclude deprecated items by default. Layers accept enum or
string. Contents round-trip through JSON.

## Routing-Decision Record

Routing decisions persist here as an **operational record distinct from the
memory layers** — they are the router's replay log (Invariant I6), not
knowledge, so no gate applies. The router's `decision_sink` hook wires to
`record_routing_decision`; `routing_decisions()` reconstructs full
`RoutingDecision` objects across restarts.

## Storage

Single SQLite database (`:memory:` default, file path for durability),
thread-safe behind a lock, transactional writes. Items, working memory, and
routing decisions survive close/reopen. A knowledge graph is added only when
a recorded limitation justifies it — ADR superseding ADR-0002 required.

## Events

`memory.promoted` (`{item_id, layer, policy_id}`),
`memory.deprecated` (`{item_id, reason}`).

## Verification

23 tests: working-memory round-trip/isolation/clearing, secret rejection on
both write paths (key names and value patterns), the full promotion gate
(verified/unverified, missing policy, working-layer, unserializable),
absence-of-ungated-writes assertion, provenance completeness, ordered reads,
cross-layer and filtered search, deprecation semantics and events,
close/reopen persistence of items, working memory, and routing decisions,
and router→sink integration.
