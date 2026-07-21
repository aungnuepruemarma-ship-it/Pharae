"""Stage 2 — Capability Registry.

Spec: docs/volume-2-modules/capability-registry.md. The single source of
truth about what the runtime can do. The kernel knows only the manifest
schema, never implementations (Kernel Invariant I1).
"""

from nexus.capabilities.registry import (
    CapabilityRecord,
    CapabilityRegistry,
    HealthStatus,
    RegistrationStatus,
    RegistryError,
)

__all__ = [
    "CapabilityRecord",
    "CapabilityRegistry",
    "HealthStatus",
    "RegistrationStatus",
    "RegistryError",
]
