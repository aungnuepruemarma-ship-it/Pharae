"""Process sandbox — resource-and-crash isolation for untrusted handler work.

Spec: docs/volume-2-modules/sandbox.md. Sits *beneath* the ADR-0007 dispatch
gate: the gate decides whether a task runs; the sandbox confines what a
running computation may consume. A callable is run in a child process under
CPU-time, memory, and wall-clock limits; the parent (the runtime) survives any
misbehavior — infinite loop, memory hog, or crash — and gets a structured
failure instead.

Honest boundary (also in the spec): this confines **resources and crashes**,
not **filesystem or network access**. A `resource`-limited subprocess is not a
namespace/container jail; true I/O isolation is future work that layers under
this same interface. POSIX-only (uses fork).
"""

from nexus.sandbox.sandbox import SandboxLimits, SandboxResult, run_sandboxed

__all__ = ["SandboxLimits", "SandboxResult", "run_sandboxed"]
