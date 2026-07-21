"""Pharae — a model-agnostic intelligence runtime.

Package layout mirrors the architecture (docs/volume-1-architecture.md):

- ``nexus.kernel``  — Stage 0 kernel: events, state, sessions, scheduler, runtime.
- ``nexus.schemas`` — canonical data objects (docs/volume-3-protocols/).

The kernel and schemas depend on the Python standard library only.
"""

__version__ = "0.1.0"
