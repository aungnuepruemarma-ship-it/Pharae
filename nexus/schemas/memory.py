"""Memory data objects.

Spec: docs/volume-3-protocols/memory-api.md. Everything above working memory
carries provenance: which run, which evidence, which policy approved the
promotion (Kernel Invariants I2/I3).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryLayer(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    FAILURE = "failure"
    PROJECT = "project"


PROMOTABLE_LAYERS = frozenset(
    {
        MemoryLayer.EPISODIC,
        MemoryLayer.SEMANTIC,
        MemoryLayer.PROCEDURAL,
        MemoryLayer.FAILURE,
        MemoryLayer.PROJECT,
    }
)


@dataclass
class MemoryItem:
    id: str
    layer: MemoryLayer
    content: dict[str, Any]
    provenance: dict[str, Any] | None = None
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)
    deprecated: bool = False
