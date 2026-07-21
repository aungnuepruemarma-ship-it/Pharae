# Module Spec — Process Sandbox

**Status:** Implemented (POSIX). Code: `nexus/sandbox/`. Tests:
`tests/test_sandbox.py`. Closes the isolation item ADR-0007 deferred beneath
the security dispatch gate.

## Purpose

Confine what a running handler may *consume*, so a misbehaving capability
cannot take down the runtime or exceed its resource budget. The dispatch gate
(security layer) decides *whether* a task runs; the sandbox bounds *how much*
a running computation may use.

## Behavior

`run_sandboxed(func, args, kwargs, limits) → SandboxResult` runs the callable
in a child process (POSIX fork) under:

- **CPU** seconds (`RLIMIT_CPU`),
- **memory** / address space (`RLIMIT_AS`),
- **output** file size (`RLIMIT_FSIZE`),
- a **wall-clock** timeout the parent enforces by killing an overrunning child.

The result is classified: `ok` (with the return value) or a failure reason —
`timeout`, `cpu`, `memory`, `error` (the handler raised), or `crash`. The
parent always survives; tests exercise an infinite loop, a memory hog, and a
crash and confirm the runtime keeps working afterward. On a platform without
fork, it returns `unsupported` so callers fall back to in-process execution.

## The honest boundary (normative)

This confines **resource consumption and crashes**. It is **not** a filesystem
or network jail: a `resource`-limited subprocess can still read files and open
sockets. True I/O isolation needs OS namespaces / containers / seccomp, which
layer *under* this same `run_sandboxed` interface as future work. The module
docstring and this section state it so the sandbox is never mistaken for a
security jail — it is resilience isolation.

## Integration

Opt-in, not default. `make_pyexec_handler(sandbox=True)` runs the evaluation in
the sandbox (defense in depth — `safe_eval` is already safe, but the sandbox
also caps CPU/memory/time). Default execution stays in-process: per-task
process spawn has real cost, and the built-ins are trusted. Untrusted or
third-party capabilities are the intended users; they opt in.

## Boundary

**Owns:** the resource-limited execution primitive and failure
classification. **Must never:** be assumed to provide I/O confinement, or be
required for trusted in-process capabilities.

## Verification

8 tests: ok/value, picklable structures, captured exceptions, wall-timeout
(returns promptly, not waited out), CPU-limited infinite loop, memory-limited
hog, parent-survives-and-keeps-working, and a sandboxed pyexec handler that
still computes correctly.
