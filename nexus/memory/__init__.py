"""Stage 6 — Memory System (SQLite, per ADR-0002).

Spec: docs/volume-2-modules/memory.md and the normative gate rules in
docs/volume-3-protocols/memory-api.md. Layered storage; never one blob.
``write_working`` is the only ungated write path — everything above working
memory enters solely through ``promote`` with verified evidence and a policy
id (Kernel Invariants I2/I3).
"""

from nexus.memory.store import MemoryError_, MemorySystem
from nexus.schemas.memory import MemoryItem, MemoryLayer

__all__ = ["MemoryError_", "MemoryItem", "MemoryLayer", "MemorySystem"]
