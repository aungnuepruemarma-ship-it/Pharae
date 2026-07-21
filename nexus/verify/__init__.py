"""Stage 7 — Verification Engine.

Spec: docs/volume-2-modules/verification.md. Produces the Evidence that the
memory promotion gate and capability score gate demand. ``verified`` means
"verification was performed and this evidence is trustworthy" — a verified
record of a *failed* run is valid input to failure memory and reliability
scoring; success is a separate judgment carried in the check results.
"""

from nexus.verify.engine import VerificationEngine

__all__ = ["VerificationEngine"]
