# Protocol — Plugin API (draft)

Implemented in Stage 10. Draft status: shapes may change until Stage 2 (registry)
lands, since plugins are delivered *through* the registry.

## Model

A **plugin** is an installable package that contributes one or more
capabilities (each with a Capability Manifest), and nothing else. Plugins are
the only way to add functionality outside the kernel (Invariant I5).

```
PluginPackage {
  name, version,                 # semver
  capabilities: [CapabilityManifest],
  requested_permissions: [str],  # union of its capabilities' permissions
  entrypoint,                    # how the runtime loads it
  signature?                     # integrity/provenance
}
```

## Lifecycle

```
install → validate (schema + permission review) → register capabilities
update  → side-by-side install, re-validate, migrate registrations
disable → capabilities flagged unavailable, state retained
remove  → deregister capabilities; durable evidence/artifacts are never deleted
```

## Rules

- Installing a plugin never modifies kernel code or another plugin.
- Permission grants are explicit at install time; a plugin cannot escalate at
  runtime.
- External protocol support (MCP, A2A, …) ships as adapter plugins that
  translate the external protocol into Volume 3 interfaces.
- Events: `plugin.installed`, `plugin.updated`, `plugin.disabled`,
  `plugin.removed`.
