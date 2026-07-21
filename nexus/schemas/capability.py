"""Capability manifest — the contract that keeps the kernel provider-agnostic.

Spec: docs/volume-3-protocols/capability-manifest.md. The runtime routes over
these fields and nothing else; ``reliability`` and ``trust_score`` are owned by
the learning pipeline after registration (Kernel Invariant I2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+].+)?$")

_UNIT_INTERVAL_FIELDS = (
    "reliability",
    "trust_score",
    "evidence_score",
    "confidence",
)


@dataclass
class CapabilityManifest:
    # Identity
    name: str
    capability_type: str
    version: str
    description: str = ""

    # Contract
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)

    # Routing signals
    cost: float = 0.0
    latency_ms: float = 0.0
    reliability: float = 0.5
    trust_score: float = 0.0
    evidence_score: float = 0.0
    confidence: float = 0.0
    strengths: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Return a list of validation errors; empty means valid.

        Registration (Stage 2) must reject any manifest with errors."""
        errors: list[str] = []
        if not self.name.strip():
            errors.append("name must be non-empty")
        if not self.capability_type.strip():
            errors.append("capability_type must be non-empty")
        if not _SEMVER.match(self.version):
            errors.append(f"version {self.version!r} is not semver (MAJOR.MINOR.PATCH)")
        if self.cost < 0:
            errors.append("cost must be >= 0")
        if self.latency_ms < 0:
            errors.append("latency_ms must be >= 0")
        for name in _UNIT_INTERVAL_FIELDS:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                errors.append(f"{name} must be in [0, 1], got {value}")
        for perm in self.permissions:
            if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", perm):
                errors.append(f"permission {perm!r} must be dotted lowercase, e.g. 'fs.write'")
        return errors
