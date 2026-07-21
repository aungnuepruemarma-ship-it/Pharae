# Volume 2 — Module Specifications

One specification per subsystem. Each module evolves independently, but every
spec must conform to Volume 1 and preserve the Kernel Invariants (Volume 0 §5).

A module spec defines: purpose, boundary (what it owns / must never know),
interfaces (referencing Volume 3), behavior, and its verification strategy.

| Spec | Module | Status |
|------|--------|--------|
| [kernel.md](kernel.md) | Runtime kernel: events, state, sessions, scheduler, runtime | **Implemented (Stage 0)** |
| [intent.md](intent.md) | Intent engine | **Implemented (Stage 1)** |
| [thinking.md](thinking.md) | Thinking (L4 reasoning budget) | **Implemented** |
| [economics.md](economics.md) | Economics (L5) + model capability | **Implemented** |
| [capability-registry.md](capability-registry.md) | Capability registry | **Implemented (Stage 2)** |
| [router.md](router.md) | Capability router | **Implemented (Stage 3)** |
| [planner.md](planner.md) | Planner | **Implemented (Stage 4)** |
| [executor.md](executor.md) | Runtime executor | **Implemented (Stage 5)** |
| [memory.md](memory.md) | Memory system | **Implemented (Stage 6)** |
| [verification.md](verification.md) | Verification engine | **Implemented (Stage 7)** |
| [research.md](research.md) | Research capability | **Implemented (Stage 8)** |
| [browser.md](browser.md) | Browser capability | **Implemented (Stage 9)** |
| [plugins.md](plugins.md) | Plugin system | **Implemented (Stage 10)** |
| [experiments.md](experiments.md) | Experiment Manager (L8, statistics) | **Implemented** |
| [cog.md](cog.md) | Cog learning system | **Implemented** |

Not yet specified (arrive as capabilities/plugins, per Invariant I5):
cloud, notebook, swarm. They get specs when their stage begins.
