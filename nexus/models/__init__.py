"""Model capability — reasoning via a model, as an ordinary capability.

Same pattern as research/browser (manifest + handler + check), so the runtime
stays model-agnostic (Invariant I1): a scripted adapter and a live Anthropic
adapter are the same kind of object behind `ModelAdapter`. Real adapters are
optional and import-safe; only *constructing/calling* them touches the network.
"""

from nexus.models.adapter import CallableAdapter, ModelAdapter, ScriptedAdapter
from nexus.models.capability import (
    make_model_handler,
    model_manifest,
    model_output_check,
)
from nexus.models.live import AnthropicAdapter, OpenAIAdapter

__all__ = [
    "AnthropicAdapter",
    "CallableAdapter",
    "ModelAdapter",
    "OpenAIAdapter",
    "ScriptedAdapter",
    "make_model_handler",
    "model_manifest",
    "model_output_check",
]
