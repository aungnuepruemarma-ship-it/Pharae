"""The `nexus` CLI — the runtime's front door.

Spec: docs/volume-2-modules/cli.md. Cognition verbs, not tool names
(Volume 1 §16). Realizes the Volume 0 §9 success criterion as a runnable
command: `nexus do "…"` drives the full loop — intent → thinking → plan →
route → execute → verify → learn — against real subsystems.
"""

from nexus.cli.main import run

__all__ = ["run"]
