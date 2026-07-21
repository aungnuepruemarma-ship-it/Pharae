"""Security layer — the enforcement point for Volume 1 §14.

Converts the session's recurring "enforced organizationally until the security
layer lands" caveats into a real, consulted mechanism: a `SecurityGuard` the
executor checks before dispatching any task. A capability whose declared
permissions the policy forbids never runs (hard boundary); one that needs
approval holds until a human grants it (progressive autonomy, Invariant I7
human override). Default policy is permissive, so wiring it changes nothing
until rules are set.

This does not (yet) provide process-level sandboxing — handlers run in-process
— which is recorded as a limit. What it provides is a policy-enforced
allow/approve/deny gate at the single choke point where work is dispatched.
"""

from nexus.security.policy import Decision, Judgment, SecurityGuard, SecurityPolicy

__all__ = ["Decision", "Judgment", "SecurityGuard", "SecurityPolicy"]
