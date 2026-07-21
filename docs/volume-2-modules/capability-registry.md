# Module Spec — Capability Registry

**Status:** Implemented (Stage 2). Code: `nexus/capabilities/`. Tests:
`tests/test_registry.py`. Manifest schema: `nexus/schemas/capability.py` and
Volume 3 (`capability-manifest.md`).

## Purpose

The single source of truth about what the runtime can do. Capabilities register
themselves; the kernel knows only the manifest schema, never implementations.

## Boundary

**Owns:** registration, discovery, health checking, metadata, versioning,
trust/reliability bookkeeping.

**Must never:** execute capabilities, route (Router's job), or special-case any
vendor. A capability for a hosted model and one for a local script are the
same kind of object.

## Behavior

### Registration
- `register(manifest, health_probe?) → "name@version"`. Validates the manifest
  (schema errors, malformed permissions) and registry policy: an optional
  **permission allowlist** rejects overpermissioned manifests, and an optional
  **type vocabulary** rejects unknown capability types (both open when
  unconfigured). Rejections carry every reason. Emits `capability.registered`.
- Identity is `(name, version)`; duplicates are rejected; **versions coexist**.
- The registry stores a *deep copy* and returns *deep copies* from every query:
  no caller can mutate registered state — in particular scores — by aliasing.

### Discovery
- `find(type, healthy_only?, include_retired?)` returns records sorted
  deterministically (name, then numeric version). `get(name)` returns the
  latest ACTIVE version by numeric semver comparison (1.10.0 > 1.2.0);
  `get(name, version)` returns that exact version in any status.
- `types()` lists the active capability-type vocabulary.

### Health
- Statuses: `UNKNOWN` (never checked / no probe) → `HEALTHY`/`UNHEALTHY` via
  the registered probe. A probe exception means UNHEALTHY, never a crash.
- Unhealthy capabilities **remain registered and findable, only flagged** —
  the router decides whether to use them. `healthy_only=True` filters.
- `capability.health` is emitted once per transition, not per check.

### Retirement and reactivation
- `retire(name, version)` flags the record RETIRED (idempotent; unknown ids
  error), excludes it from default discovery and from latest-version
  resolution, keeps the record queryable, and emits `capability.retired`.
- Registering a retired `(name, version)` **reactivates** it (fresh record,
  health reset to UNKNOWN) — used by the plugin lifecycle's disable→enable.
  Active duplicates are still rejected.

### Evidence-gated scores (Invariant I2)
- `record_outcome(name, version, evidence, success)` is the **only** path that
  moves `reliability` and `trust_score` after registration, and it rejects
  unverified `Evidence`. There is no public setter.
- Update rule (deterministic EMA, clamped to [0,1]):
  `reliability += 0.2 · (target − reliability)` with target 1 on success, 0 on
  failure; `trust += 0.1 · (target − trust)`, trust moving slower. The trust
  target on success is an optional **reward** in [0,1]
  (`record_outcome(..., reward=…)`, ADR-0004) supplied by the learning
  pipeline from the *same verified evidence* — cost/friction-aware, so cheaper
  cleaner successes build trust faster. With `reward` omitted the target falls
  back to evidence confidence (prior behavior). The gate runs *before* reward
  is consulted, so shaping never admits unverified evidence. Emits
  `capability.scored`.
- The credential model (restricting *callers* of `record_outcome` to Cog) is
  enforced organizationally until the security layer lands; the evidence gate
  is enforced in code now.

## Events

`capability.registered`, `capability.retired`, `capability.health`,
`capability.scored` — all within the reserved `capability.*` namespace.

## Verification

26 tests: manifest/policy rejection with reasons, duplicate rejection, version
coexistence and numeric-latest resolution, copy-isolation both directions,
deterministic discovery order, retirement semantics, probe success/failure/
exception, flagged-not-hidden unhealthy behavior, transition-only health
events, and the score gate (verified success raises / failure lowers /
unverified rejected unchanged / clamped / deterministic).
