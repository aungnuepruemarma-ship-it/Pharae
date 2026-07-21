# ADR-0007: Security as a policy-enforced dispatch gate (V1)

**Status:** Accepted
**Date:** 2026-07-21

## Context

Volume 1 §14 promises sandboxing, permissions, and approval for dangerous
actions; Invariant I7 promises human override. Across the build these were
"enforced organizationally until the security layer lands" — real permission
*review* existed at registration/plugin-install, but nothing enforced policy at
*execution* time, and there was no approval mechanism. Full process sandboxing
is a large, platform-specific effort.

## Decision

Ship the enforceable core first: a `SecurityPolicy` (allow / require-approval /
deny over declared permissions and capability type) and a `SecurityGuard` the
**executor consults before dispatching each task**. Denied tasks never run;
approval-required tasks hold until `approve(capability_id)` (human override).
Default policy is permissive, so the gate is on by default with zero behavior
change until rules are set. Process-level sandboxing and promotion-caller
restriction are explicitly deferred and recorded as limits.

## Alternatives Considered

- **Full sandbox now (subprocess/container isolation):** rejected for V1 —
  large, platform-specific, and premature while all capabilities are trusted
  built-ins. The dispatch gate delivers the policy/approval value immediately;
  isolation slots beneath it later without changing the interface.
- **Enforce in the kernel runtime instead of the executor:** rejected — the
  executor is the single dispatch choke point and already owns "how it runs";
  the kernel stays provider- and policy-agnostic (I1).
- **A promotion credential to caller-restrict memory writes:** deferred —
  invasive (touches every promote call) for marginal gain over the existing
  evidence gate; recorded as a limit instead of half-built.

## Consequences

Easier: forbidden capabilities can be hard-denied; dangerous ones gated on
human approval; every block is evented (`security.blocked`) and auditable.
Harder: nothing yet — the default is permissive. Reopen trigger: the first
untrusted/third-party capability that actually needs process isolation, which
motivates the sandbox beneath this gate.

## Invariant Check

- **I1:** the guard lives in the executor and reasons over manifest fields;
  the kernel stays policy-agnostic. Preserved.
- **I6:** every block is logged as an event. Preserved.
- **I7:** approval is the human-override mechanism. **Realized.**
- I2/I3: unaffected — this gates task dispatch, not evidence or memory.
