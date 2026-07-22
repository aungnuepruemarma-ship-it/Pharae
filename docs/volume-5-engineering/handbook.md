# Volume 5 — Engineering Handbook

Practical guidance for building Pharae. This volume changes as needed; it never
overrides Volumes 0–3.

## Repository Layout

```
docs/                  Volumes 0–5 (this specification set)
nexus/                 The runtime
  kernel/              Stage 0 kernel (events, state, sessions, scheduler, runtime)
  schemas/             Canonical data objects (mirrors Volume 3)
tests/                 Unit tests (stdlib unittest)
```

Growth plan (added per stage, matching Volume 1 §17): `nexus/intent/`,
`nexus/planner/`, `nexus/capabilities/`, `nexus/router/`, `nexus/memory/`,
`nexus/verify/`, `nexus/plugins/`, `nexus/security/`, `nexus/telemetry/`,
`nexus/cli/`. A directory is created when its stage begins, never before.

## Development Workflow

Every feature, no exceptions:

1. **Design document** — a Volume 2 spec (new or updated section).
2. **Interfaces** — Volume 3 protocol + `nexus/schemas` types first.
3. **Tests** — written against the interface before the implementation.
4. **Implement.**
5. **Verify** — tests green, invariant check against Volume 0 §5.
6. **Benchmark** — where performance-relevant; record in Volume 4.
7. **Document** — update the module spec to match reality.
8. **Decide** — keep, revise, or remove. Removal is a first-class outcome.

## Coding Standards

- Python ≥ 3.11. The **kernel and schemas use the standard library only** —
  adding a dependency there requires an ADR. Capabilities and plugins may have
  dependencies, declared in their own packaging.
- Type hints everywhere; dataclasses for schemas; enums for statuses.
- No module reaches into another's internals: cross-module traffic goes
  through Volume 3 interfaces or the event bus (Invariant I4).
- Determinism is a feature: avoid wall-clock or randomness in logic paths;
  inject ids and time where practical.
- Comments state constraints the code can't express; specs carry the rationale.

## Testing Strategy

- Framework: stdlib `unittest` (keeps the zero-dependency property). Runner:
  `python3 -m unittest discover -s tests`.
- Every kernel behavior named in a Volume 2 spec has a test naming that
  behavior. Golden tests for intent/planner; property-style tests for
  scheduler (cycle rejection, deterministic ordering).
- Gate tests are mandatory for invariants I2/I3: attempts to bypass memory
  gating must fail in tests forever.

## CI / Release (to be stood up)

- CI: run the test suite on every push; no merge on red.
- Versioning: semver per protocol (Volume 3) and for the runtime package.
- Release notes must list any protocol version bumps and link the ADRs behind
  behavior changes.

## Executable Invariants

The Kernel Invariants (Volume 0 §5) are not only prose — `tests/test_invariants.py`
asserts them as continuously-checked guarantees: kernel/schemas import purity
(I1, by AST scan — no vendor, no higher-layer import), evidence-gating across
*every* learning path (I2 — memory, registry, cog, and all three science
modules reject unverified evidence), the absence of any ungated memory write
(I3), a sequenced event log (I6), and human-override release of gated work
(I7). A failure there is a constitutional violation, not an ordinary bug — the
fix is to restore the invariant, never to weaken the test.

## Contribution Rule of One Question

Every PR description answers: **which Kernel Invariants does this touch, and
how are they preserved?** A PR that can't answer cleanly needs an ADR first.
When in doubt, `tests/test_invariants.py` is the machine-checkable answer.
