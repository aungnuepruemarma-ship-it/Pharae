# Module Spec — Capability Registry

**Status:** Spec (Stage 2). Not yet implemented. Manifest schema is already
canonical in `nexus/schemas/capability.py` and Volume 3.

## Purpose

The single source of truth about what the runtime can do. Capabilities register
themselves; the kernel knows only the manifest schema, never implementations.

## Boundary

**Owns:** registration, discovery, health checking, metadata, versioning,
trust/reliability bookkeeping.

**Must never:** execute capabilities, route (Router's job), or special-case any
vendor. A capability for Claude and a capability for a local script are the
same kind of object.

## Behavior

- **Register:** validate manifest (schema, version, permissions) → store →
  emit `capability.registered`.
- **Discover:** query by capability *type* (`browser`, `code`, `research`),
  returning manifests with current health and trust.
- **Health:** periodic or on-demand checks; unhealthy capabilities remain
  registered but are flagged; the router decides whether to use them.
- **Versioning:** multiple versions may coexist; retirement emits
  `capability.retired`.
- Trust and reliability scores are *written by the learning pipeline* from
  verified run history, never self-reported past registration defaults
  (Invariant I2).

## Interfaces

- `CapabilityManifest` schema: Volume 3 (`capability-manifest.md`).
- Registry API: register / deregister / find(type, constraints) / health(id).

## Verification

Manifest validation tests (reject malformed/overpermissioned), discovery
filtering tests, health-flag behavior, version coexistence.
