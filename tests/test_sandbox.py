import os
import time
import unittest

from nexus.sandbox import SandboxLimits, run_sandboxed

posix_only = unittest.skipUnless(hasattr(os, "fork"), "sandbox needs POSIX fork")


# Module-level targets (fork inherits them; no pickling issues on POSIX).
def _add(a, b):
    return a + b


def _make_list(n):
    return list(range(n))


def _raise():
    raise ValueError("handler blew up")


def _sleep_forever():
    time.sleep(30)


def _spin():
    while True:
        pass


def _hog(mb):
    chunk = "x" * (1024 * 1024)
    keep = []
    for _ in range(mb):
        keep.append(chunk * 1)  # noqa: PLC0206
        keep.append("y" * (1024 * 1024))
    return len(keep)


@posix_only
class TestSandbox(unittest.TestCase):
    def test_ok_returns_value(self):
        r = run_sandboxed(_add, (2, 3))
        self.assertTrue(r.ok)
        self.assertEqual(r.value, 5)
        self.assertEqual(r.reason, "ok")

    def test_returns_picklable_structure(self):
        r = run_sandboxed(_make_list, (4,))
        self.assertTrue(r.ok)
        self.assertEqual(r.value, [0, 1, 2, 3])

    def test_exception_is_captured(self):
        r = run_sandboxed(_raise)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "error")
        self.assertIn("blew up", r.error)

    def test_wall_timeout_returns_promptly(self):
        start = time.monotonic()
        r = run_sandboxed(_sleep_forever, limits=SandboxLimits(wall_seconds=0.5))
        elapsed = time.monotonic() - start
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "timeout")
        self.assertLess(elapsed, 5.0)  # killed, not waited out

    def test_cpu_limit_stops_infinite_loop(self):
        r = run_sandboxed(_spin, limits=SandboxLimits(cpu_seconds=1, wall_seconds=8))
        self.assertFalse(r.ok)
        self.assertIn(r.reason, {"cpu", "crash", "timeout"})

    def test_memory_limit_contains_hog(self):
        r = run_sandboxed(_hog, (500,), limits=SandboxLimits(memory_mb=64, wall_seconds=8))
        self.assertFalse(r.ok)
        self.assertIn(r.reason, {"memory", "error", "crash"})

    def test_parent_survives_and_keeps_working(self):
        run_sandboxed(_spin, limits=SandboxLimits(cpu_seconds=1, wall_seconds=8))
        run_sandboxed(_hog, (500,), limits=SandboxLimits(memory_mb=64, wall_seconds=8))
        # the runtime (this process) is unharmed and can still run work
        r = run_sandboxed(_add, (10, 20))
        self.assertTrue(r.ok)
        self.assertEqual(r.value, 30)


@posix_only
class TestSandboxedPyexec(unittest.TestCase):
    def test_sandboxed_handler_still_computes(self):
        from nexus.kernel.runtime import RunContext, Runtime
        from nexus.pyexec import make_pyexec_handler
        from nexus.schemas.core import Task

        rt = Runtime()
        ctx = RunContext(run_id="r", session=rt.sessions.create(), state=rt.state, bus=rt.bus)
        handler = make_pyexec_handler(sandbox=True)
        out = handler(Task(id="t", capability_type="code", payload={"expression": "6 * 7"}), ctx)
        self.assertEqual(out["result"], 42)


if __name__ == "__main__":
    unittest.main()
