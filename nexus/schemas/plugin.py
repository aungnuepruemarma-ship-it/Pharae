"""Plugin package schema.

Spec: docs/volume-3-protocols/plugin-api.md. A plugin contributes one or more
capabilities (each with a Capability Manifest) and nothing else — the only
way to add functionality outside the kernel (Invariant I5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from nexus.schemas.capability import CapabilityManifest

_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+].+)?$")


@dataclass
class PluginPackage:
    name: str
    version: str
    capabilities: list[CapabilityManifest]
    requested_permissions: list[str] = field(default_factory=list)
    entrypoint: str = ""  # "module.path:setup" → setup() -> {capability_name: handler}
    signature: str | None = None  # carried, not verified in V1 (recorded limit)

    def validate(self) -> list[str]:
        """Schema-level validation; empty list means valid. The manager adds
        environment checks (allowlist review, name collisions, entrypoint)."""
        errors: list[str] = []
        if not self.name.strip():
            errors.append("plugin name must be non-empty")
        if not _SEMVER.match(self.version):
            errors.append(f"plugin version {self.version!r} is not semver")
        if not self.capabilities:
            errors.append("a plugin must contribute at least one capability")
        if ":" not in self.entrypoint:
            errors.append(f"entrypoint {self.entrypoint!r} is not 'module:attr'")
        requested = set(self.requested_permissions)
        for manifest in self.capabilities:
            for error in manifest.validate():
                errors.append(f"capability {manifest.name!r}: {error}")
            hidden = set(manifest.permissions) - requested
            if hidden:
                errors.append(
                    f"capability {manifest.name!r} uses permissions not requested "
                    f"by the plugin: {sorted(hidden)}"
                )
        names = [m.name for m in self.capabilities]
        if len(names) != len(set(names)):
            errors.append("duplicate capability names within the plugin")
        return errors
