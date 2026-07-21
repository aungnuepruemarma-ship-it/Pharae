# Protocol — Plugin API (v1)

Implemented (Stage 10): `nexus/plugins/`, schema in `nexus/schemas/plugin.py`.

## Model

A **plugin** is an installable package that contributes one or more
capabilities (each with a Capability Manifest), and nothing else. Plugins are
the only way to add functionality outside the kernel (Invariant I5).

```
PluginPackage {
  name, version,                 # semver
  capabilities: [CapabilityManifest],
  requested_permissions: [str],  # must cover every capability's permissions
  entrypoint: str,               # "module.path:setup"
  signature?                     # carried, NOT verified in V1 (recorded limit)
}
```

## Entrypoint Contract

`setup()` returns `{capability_name: handler}` covering **exactly** the
package's capability names. Handlers are registered on the runtime under
capability ids (`name@version`), so multiple capabilities of one capability
*type* coexist — the router's binding decides which handler runs, and the
runtime resolves binding first, type as fallback.

## Lifecycle

```
install → validate everything (schema, permission review, cross-plugin
          capability-name collisions, entrypoint load) → register manifests
          + handlers. A rejected plugin leaves no trace.
update  → side-by-side: validate + load the new version fully, then retire
          old capability versions and wire the new; version history kept.
disable → capabilities retired (flagged, retained), handlers unwired;
enable  → capabilities reactivated, handlers rewired.
remove  → deregistered; registry records stay retired — durable history is
          never deleted. Reinstall after removal is permitted.
```

## Rules

- Installing a plugin never modifies kernel code or another plugin; a
  capability name owned by another plugin is a rejection.
- Permission grants are explicit at install time: a capability using
  permissions its plugin did not request is rejected, and the manager's
  `allowed_permissions` policy reviews the requested set. There is no
  escalation API; hard runtime enforcement arrives with the security layer.
- External protocol support (MCP, A2A, …) ships as adapter plugins that
  translate the external protocol into Volume 3 interfaces.

## Events

`plugin.installed`, `plugin.updated`, `plugin.disabled`, `plugin.enabled`,
`plugin.removed` — payload `{plugin, version, capabilities}`.
