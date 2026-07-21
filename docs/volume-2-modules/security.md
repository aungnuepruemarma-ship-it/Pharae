# Module Spec — Security Layer

**Status:** Implemented (V1: policy-enforced dispatch gate). Code:
`nexus/security/`. Tests: `tests/test_security.py`. Realizes the enforceable
part of Volume 1 §14 and Invariant I7 (human override); converts several
session-long "enforced organizationally" caveats into a real mechanism.

## Purpose

Give the runtime a single enforced choke point over what may execute:
allow / require-approval / deny, decided by policy over a capability's declared
permissions and type. Dangerous work is held for human approval (progressive
autonomy); forbidden work never runs.

## Behavior

- **`SecurityPolicy`** (frozen, declarative): `denied_permissions`,
  `approval_permissions`, `approval_types`. `decide(manifest) → Judgment`
  with deny > require-approval > allow precedence. Default is fully
  permissive.
- **`SecurityGuard`**: resolves a task's bound capability from the registry,
  applies the policy, and tracks approvals. `check(task) → (ok, reason)`;
  `approve(capability_id)` is the human-override grant (emits
  `security.approved`). An unknown/unbound task is allowed — the router
  already bound it; security judges known capabilities, not routing.
- **Enforcement point**: the **executor** consults the guard before
  dispatching each task (attempt 1). A blocked task fails with
  `blocked by security policy: <reason>`, emits `security.blocked`, and its
  dependents block — the run ends PARTIAL/FAILED. Wiring a guard with the
  default policy changes nothing (everything allowed), so it is on by default
  in the CLI with zero behavior change; `status` shows `permissive` or the
  rule count.

## Boundary

**Owns:** the allow/approve/deny decision and the dispatch gate. **Must
never:** execute, mutate capabilities, or weaken another gate.

## Recorded limits (honest)

- **No process sandboxing.** Handlers run in-process; the guard enforces
  *whether* a task dispatches, not what a running handler may then do. True
  isolation (subprocess/container, syscall limits) is future work — the
  permission model above the gate is declarative, not confined.
- **Promotion-caller restriction stays organizational.** The guard governs
  task dispatch, not who may call `memory.promote` / `registry.record_outcome`;
  those remain evidence-gated (I2) but not caller-restricted in code. A
  promotion credential is future work.

These limits are stated so the layer is not mistaken for more than it is: it
is a real policy gate at the dispatch choke point, not a sandbox.

## Verification

11 tests: policy decisions (allow/deny/approval by permission and type), guard
over the registry (permissive allow, deny, approval-then-grant, unknown-binding
allow), and executor enforcement (denied task never runs while siblings
complete; approval gate holds then releases after `approve`; no-guard behavior
unchanged).
