"""Stage 8 — Research capability.

Spec: docs/volume-2-modules/research.md. The first Phase 2 capability: a
unified research interface over pluggable sources, packaged as a capability —
manifest for the registry, handler for the runtime's capability-type seam,
check for the verification engine. The kernel is untouched (Invariant I5).
"""

from nexus.research.capability import (
    make_research_handler,
    research_manifest,
    research_report_check,
)
from nexus.research.engine import Finding, ResearchEngine, ResearchReport
from nexus.research.sources import DocumentationSource, RepositorySource, WebSource

__all__ = [
    "DocumentationSource",
    "Finding",
    "RepositorySource",
    "ResearchEngine",
    "ResearchReport",
    "WebSource",
    "make_research_handler",
    "research_manifest",
    "research_report_check",
]
