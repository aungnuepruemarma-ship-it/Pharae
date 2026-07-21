"""Stage 10 — Plugin system.

Spec: docs/volume-3-protocols/plugin-api.md and
docs/volume-2-modules/plugins.md. Plugins are installable packages that
contribute capabilities through the registry and handlers through the
runtime's seam — the only way to add functionality outside the kernel
(Invariant I5). Installing a plugin never modifies the kernel or another
plugin.
"""

from nexus.plugins.manager import PluginError, PluginManager, PluginRecord, PluginStatus
from nexus.schemas.plugin import PluginPackage

__all__ = [
    "PluginError",
    "PluginManager",
    "PluginPackage",
    "PluginRecord",
    "PluginStatus",
]
