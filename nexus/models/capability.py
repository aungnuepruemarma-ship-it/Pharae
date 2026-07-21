"""Model packaged as a capability: manifest, handler, verification check.

The manifest carries a ``tier`` (small/mid/frontier/local) in constraints —
the signal the Economist (L5) reasons over. The handler writes only working
memory; durable use of a model's output goes through the evidence gate.
"""

from __future__ import annotations

from typing import Any, Callable

from nexus.kernel.runtime import RunContext
from nexus.models.adapter import ModelAdapter
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Task, TaskResult


def model_manifest(
    name: str,
    tier: str = "mid",
    version: str = "0.1.0",
    cost: float = 1.0,
    latency_ms: float = 200.0,
    trust: float = 0.2,
    reliability: float = 0.6,
) -> CapabilityManifest:
    return CapabilityManifest(
        name=name,
        capability_type="model",
        version=version,
        description=f"Reasoning via a model ({tier} tier)",
        input_schema={"prompt": "str"},
        output_schema={"model": "str", "output": "str"},
        permissions=["net.fetch"],
        constraints={"tier": tier},
        cost=cost,
        latency_ms=latency_ms,
        reliability=reliability,
        trust_score=trust,
        evidence_score=0.4,
        confidence=0.2,
        strengths=["reasoning", tier],
    )


def make_model_handler(
    adapter: ModelAdapter,
) -> Callable[[Task, RunContext], dict[str, Any]]:
    def handler(task: Task, ctx: RunContext) -> dict[str, Any]:
        prompt = task.payload.get("prompt") or task.payload.get("description", "")
        output = {"model": adapter.name, "output": adapter.complete(prompt)}
        ctx.set(f"model:{task.id}", output)
        return output

    return handler


def model_output_check(result: TaskResult, task: Task) -> tuple[bool, str]:
    output = result.output
    if not isinstance(output, dict) or "output" not in output:
        return False, "output is not a model response"
    if not str(output.get("output", "")).strip():
        return False, "model produced empty output"
    return True, f"model {output.get('model', '?')} produced {len(output['output'])} chars"
