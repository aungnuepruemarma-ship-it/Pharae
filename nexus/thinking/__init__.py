"""L4 — Thinking (reasoning budget).

Spec: docs/volume-2-modules/thinking.md. Decides *how much reasoning is
necessary* before the planner runs — the mechanism that realizes First
Principle #5 (Progressive Complexity: solve simple tasks directly; only use
orchestration when it provides measurable value). Deterministic and
vendor-free: it reasons over intent features, never model output.
"""

from nexus.thinking.budget import ThinkingBudget, ThinkingBudgeter, ThinkingMode

__all__ = ["ThinkingBudget", "ThinkingBudgeter", "ThinkingMode"]
