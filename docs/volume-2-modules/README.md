# Volume 2 — Module Specifications

One specification per subsystem. Each module evolves independently, but every
spec must conform to Volume 1 and preserve the Kernel Invariants (Volume 0 §5).

A module spec defines: purpose, boundary (what it owns / must never know),
interfaces (referencing Volume 3), behavior, and its verification strategy.

| Spec | Module | Status |
|------|--------|--------|
| [kernel.md](kernel.md) | Runtime kernel: events, state, sessions, scheduler, runtime | **Implemented (Stage 0)** |
| [intent.md](intent.md) | Intent engine | **Implemented (Stage 1)** |
| [planner.md](planner.md) | Planner | Spec (Stage 1) |
| [capability-registry.md](capability-registry.md) | Capability registry | Spec (Stage 2) |
| [router.md](router.md) | Capability router | Spec (Stage 3) |
| [executor.md](executor.md) | Runtime executor | Spec (Stage 4) |
| [memory.md](memory.md) | Memory system | Spec (Stage 5) |
| [verification.md](verification.md) | Verification engine | Spec (Stage 6) |
| [cog.md](cog.md) | Cog learning system | Spec (post-V1 core loop) |

Not yet specified (arrive as capabilities/plugins, per Invariant I5): research,
browser, cloud, notebook, swarm. They get specs when their stage begins.
