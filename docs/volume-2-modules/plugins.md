# Module Spec — Plugin System

**Status:** Implemented (Stage 10). Code: `nexus/plugins/`. Tests:
`tests/test_plugins.py`. Protocol: Volume 3 `plugin-api.md` (v1).

## Purpose

Everything becomes installable. A plugin contributes capabilities through
the registry and handlers through the runtime's seam — the only way to add
functionality outside the kernel (Invariant I5).

## Boundary

**Owns:** plugin validation, permission review, lifecycle
(install/update/disable/enable/remove), the entrypoint contract, plugin
records and version history.

**Must never:** modify the kernel or another plugin, grant permissions
beyond the reviewed request, delete durable registry history, or bypass the
registry/runtime seams — a plugin's capabilities are ordinary registry
entries and its handlers ordinary handlers.

## Behavior

- **Atomic install:** schema validation, allowlist permission review,
  cross-plugin capability-name collision checks, and entrypoint loading all
  complete *before* any registration — a rejected plugin leaves no trace
  (tested for every rejection path).
- **Dispatch by binding:** handlers register under capability ids, so two
  plugins of the same capability type coexist; the router's binding selects
  the handler and the runtime honors it exactly (`resolve_handler`: binding
  first, type fallback — a Stage 10 kernel refinement closing the binding
  loop).
- **Lifecycle:** disable retires capabilities (flagged and retained in the
  registry, per its reactivation support) and unwires handlers; enable
  reactivates and rewires; update swaps versions side-by-side with history
  in `previous_versions`; remove keeps registry records retired forever.
- **Events** on every transition; `plugin.*` is a reserved namespace.

## Recorded V1 Limits

Signatures are carried, not verified. Entrypoints load in-process (no
sandbox) — the permission model is structural (handlers receive only their
RunContext) until the security layer lands. Both are Volume 4 agenda items.

## Verification

19 tests: install wiring and events, every rejection path leaves no trace
(bad manifest, no capabilities, hidden permissions, allowlist excess,
duplicate plugin, capability-name theft, broken/mismatched/malformed/missing
entrypoints), disable/enable round-trip, remove with retained history,
reinstall after removal, versioned update with handler swap, same-type
coexistence with binding-directed dispatch, and a routed full loop served
by an installed plugin.
