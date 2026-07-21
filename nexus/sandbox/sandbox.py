"""Resource-limited subprocess execution.

The child applies `setrlimit` (CPU, address space, output file size), runs the
target, and sends the result back over a pipe. The parent enforces a wall-clock
timeout by killing a child that overruns. Failures are classified so callers
can react (timeout / cpu / memory / error / crash).
"""

from __future__ import annotations

import multiprocessing as mp
import signal
from dataclasses import dataclass
from typing import Any, Callable

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX
    resource = None  # type: ignore


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 2
    memory_mb: int = 512
    wall_seconds: float = 5.0
    output_bytes: int = 8 * 1024 * 1024


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    value: Any = None
    error: str | None = None
    reason: str = "ok"  # ok | timeout | cpu | memory | error | crash | unsupported


def _apply_limits(limits: SandboxLimits) -> None:
    if resource is None:
        return
    if limits.cpu_seconds:
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 1))
    if limits.memory_mb:
        nbytes = limits.memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (nbytes, nbytes))
        except (ValueError, OSError):  # some platforms disallow RLIMIT_AS
            pass
    if limits.output_bytes:
        try:
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (limits.output_bytes, limits.output_bytes)
            )
        except (ValueError, OSError):
            pass


def _child(func, args, kwargs, limits, conn) -> None:  # pragma: no cover - child process
    try:
        _apply_limits(limits)
        value = func(*args, **kwargs)
        conn.send(("ok", value))
    except MemoryError:
        conn.send(("memory", "memory limit exceeded"))
    except Exception as exc:  # noqa: BLE001 - report anything the handler raises
        conn.send(("error", repr(exc)))
    finally:
        conn.close()


def run_sandboxed(
    func: Callable[..., Any],
    args: tuple = (),
    kwargs: dict | None = None,
    limits: SandboxLimits | None = None,
) -> SandboxResult:
    """Run ``func(*args, **kwargs)`` in a resource-limited child process.

    POSIX-only (fork). On a platform without fork, returns an ``unsupported``
    result so callers can fall back to in-process execution."""
    if not hasattr(mp, "get_context") or resource is None:
        return SandboxResult(False, reason="unsupported", error="no POSIX sandbox")
    limits = limits or SandboxLimits()
    kwargs = kwargs or {}
    ctx = mp.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(func, args, kwargs, limits, child_conn))
    proc.start()
    child_conn.close()

    proc.join(limits.wall_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(0.5)
        if proc.is_alive():
            proc.kill()
            proc.join(0.5)
        parent_conn.close()
        return SandboxResult(False, reason="timeout", error="wall-clock limit exceeded")

    payload = None
    if parent_conn.poll():
        try:
            payload = parent_conn.recv()
        except EOFError:
            payload = None
    parent_conn.close()

    if payload is not None:
        tag, data = payload
        if tag == "ok":
            return SandboxResult(True, value=data, reason="ok")
        if tag == "memory":
            return SandboxResult(False, reason="memory", error=data)
        return SandboxResult(False, reason="error", error=data)

    # No payload: the child died before reporting — classify by exit signal.
    code = proc.exitcode
    if code is not None and code < 0:
        sig = -code
        if sig in (getattr(signal, "SIGXCPU", -1), signal.SIGKILL):
            return SandboxResult(False, reason="cpu", error=f"killed by signal {sig}")
        return SandboxResult(False, reason="crash", error=f"killed by signal {sig}")
    return SandboxResult(False, reason="crash", error=f"exited with code {code}")
