"""L5 — Economics. Decides how much compute to spend on reasoning.

Spec: docs/volume-2-modules/economics.md. Given a Thinking budget (L4) and
candidate model capabilities, choose the compute tier that fits the required
reasoning effort: cheap for reflex, capable for research. Distinct from the
router (which binds a task to a capability of a given type); the Economist
selects *which model tier* to reason with, then the router/executor use it.
"""

from nexus.economics.economist import EconomicsError, Economist

__all__ = ["EconomicsError", "Economist"]
