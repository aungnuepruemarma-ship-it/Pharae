"""Research packaged as a capability: manifest, handler, verification check.

This is the pattern every future capability follows (Invariant I5): the
registry gets a manifest, the runtime gets a handler on the capability-type
seam, the verification engine gets a check — and the kernel is untouched.
"""

from __future__ import annotations

from typing import Any, Callable

from nexus.kernel.runtime import RunContext
from nexus.research.engine import ResearchEngine
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Task, TaskResult


def research_manifest(version: str = "0.1.0") -> CapabilityManifest:
    return CapabilityManifest(
        name="research.local",
        capability_type="research",
        version=version,
        description=(
            "Unified research over pluggable sources: documentation trees, "
            "repositories (files + git history), and given web refs"
        ),
        input_schema={"description": "str", "context_refs": "list[str]"},
        output_schema={
            "query": "str",
            "findings": "list[{source, location, excerpt, score}]",
            "sources_consulted": "list[str]",
            "stats": "dict",
        },
        permissions=["fs.read", "net.fetch"],
        cost=0.0,
        latency_ms=200.0,
        reliability=0.7,
        trust_score=0.2,
        evidence_score=0.6,
        confidence=0.2,
        strengths=["documentation", "repository", "web"],
    )


def make_research_handler(
    engine: ResearchEngine, top_k: int = 10
) -> Callable[[Task, RunContext], dict[str, Any]]:
    """Handler for the runtime's capability-type seam. Reads the task's
    description as the query and its context refs as source hints; writes the
    report to working memory only — long-term storage of findings goes
    through the verified-evidence promotion gate, never around it."""

    def handler(task: Task, ctx: RunContext) -> dict[str, Any]:
        report = engine.research(
            task.payload.get("description", ""),
            refs=task.payload.get("context_refs", []),
            top_k=top_k,
        )
        result = report.as_dict()
        ctx.set(f"research:{task.id}", result)
        return result

    return handler


def research_report_check(result: TaskResult, task: Task) -> tuple[bool, str]:
    """Verification check for research tasks: a report with zero findings is
    a failed research task, not a quietly empty success."""
    output = result.output
    if not isinstance(output, dict) or "findings" not in output:
        return False, "output is not a research report"
    findings = output.get("findings") or []
    if not findings:
        return False, f"no findings for query {output.get('query', '')!r}"
    sources = output.get("sources_consulted") or []
    return True, f"{len(findings)} findings from {len(sources)} sources"
