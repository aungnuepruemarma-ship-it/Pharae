"""Science layers (L9, L10, L12) — the evidence-first cognitive-science core.

Spec: docs/volume-2-modules/science.md. A genuine, gate-preserving foundation
for the blueprint's science stack:

- **L10 Theory Ledger** — hypotheses with evidence, confidence, replications;
  promotion to long-term memory only through the verified-evidence gate.
- **L9 Representations** — competing reasoning strategies; only evidence
  survives (best by verified win-rate over a minimum trial count).
- **L12 Organizations** — named *capability compositions* (ADR-0003: not
  persistent agents), selected by verified success.

Every learn/observe path here refuses unverified evidence (Invariant I2) —
the same discipline the rest of Pharae enforces, extended to the science
layers. The deeper L11 (primitive discovery) and L14–L17 (organization
discovery/evolution/genome/math) are staged, not yet built (Volume 4 map).
"""

from nexus.science.organizations import Organization, OrganizationLibrary
from nexus.science.representations import RepresentationArena, RepresentationRecord
from nexus.science.theory import ScienceError, Theory, TheoryLedger, TheoryStatus

__all__ = [
    "Organization",
    "OrganizationLibrary",
    "RepresentationArena",
    "RepresentationRecord",
    "ScienceError",
    "Theory",
    "TheoryLedger",
    "TheoryStatus",
]
