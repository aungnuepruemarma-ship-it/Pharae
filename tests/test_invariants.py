"""Executable Kernel Invariants (Volume 0 §5).

These turn the constitution from prose into continuously-checked guarantees.
A failure here is a violation of the system's identity, not an ordinary bug.
"""

import ast
import os
import unittest

from nexus.capabilities import CapabilityRegistry, RegistryError
from nexus.cog import Cog, CogError
from nexus.memory import MemoryError_, MemoryLayer, MemorySystem
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Evidence, Run, RunStatus
from nexus.science import (
    OrganizationLibrary,
    RepresentationArena,
    ScienceError,
    TheoryLedger,
)

_NEXUS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nexus")
_VENDOR_PREFIXES = ("anthropic", "openai", "playwright", "requests", "httpx", "numpy", "scipy")


def _imported_roots(path: str) -> set[str]:
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module)
    return roots


def _py_files(subdir: str) -> list[str]:
    root = os.path.join(_NEXUS, subdir)
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


def unverified() -> Evidence:
    return Evidence(id="ev-bad", run_id="run", verified=False, confidence=0.9)


def verified() -> Evidence:
    return Evidence(id="ev-ok", run_id="run", verified=True, confidence=0.9)


class TestI1_ProviderAgnosticKernel(unittest.TestCase):
    """The kernel and schemas import only the stdlib and each other — never a
    vendor, never a higher layer."""

    def _assert_pure(self, subdir: str, allowed_nexus: tuple[str, ...]):
        for path in _py_files(subdir):
            for root in _imported_roots(path):
                base = root.split(".")[0]
                self.assertNotIn(
                    base, _VENDOR_PREFIXES,
                    f"{path} imports vendor {root!r} — violates I1",
                )
                if root.startswith("nexus"):
                    self.assertTrue(
                        any(root == a or root.startswith(a + ".") for a in allowed_nexus),
                        f"{path} imports {root!r}, outside {allowed_nexus} — violates layering",
                    )

    def test_kernel_is_pure(self):
        self._assert_pure("kernel", ("nexus.kernel", "nexus.schemas"))

    def test_schemas_are_pure(self):
        self._assert_pure("schemas", ("nexus.schemas",))


class TestI2_EvidenceGatedLearning(unittest.TestCase):
    """No learning path accepts unverified evidence — checked across every
    module that learns."""

    def test_memory_promote_rejects_unverified(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        with self.assertRaises(MemoryError_):
            mem.promote(unverified(), MemoryLayer.EPISODIC, {"x": 1}, policy_id="p@1")

    def test_registry_record_outcome_rejects_unverified(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="c", capability_type="code", version="1.0.0"))
        with self.assertRaises(RegistryError):
            reg.record_outcome("c", "1.0.0", evidence=unverified(), success=True)

    def test_cog_learn_rejects_unverified(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        run = Run(id="r", plan_id="p", session_id="s", status=RunStatus.COMPLETED)
        with self.assertRaises(CogError):
            Cog(mem).learn(run, unverified())

    def test_science_modules_reject_unverified(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        ledger = TheoryLedger(mem)
        t = ledger.propose("some theory")
        with self.assertRaises(ScienceError):
            ledger.observe(t.id, unverified(), supports=True)

        arena = RepresentationArena()
        arena.register("cot")
        with self.assertRaises(ScienceError):
            arena.record("cot", unverified(), success=True)

        lib = OrganizationLibrary()
        lib.define("o", ["code"])
        with self.assertRaises(ScienceError):
            lib.record("o", unverified(), success=True)


class TestI3_PolicyGatedMemory(unittest.TestCase):
    """Above working memory, the only write path is a gated promotion."""

    def test_no_ungated_write_method_exists(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        for forbidden in ("write", "insert", "add_item", "save_item", "write_layer", "put"):
            self.assertFalse(hasattr(mem, forbidden), f"ungated write {forbidden!r} exists")

    def test_promote_requires_policy_id(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        with self.assertRaises(MemoryError_):
            mem.promote(verified(), MemoryLayer.SEMANTIC, {"x": 1}, policy_id="")

    def test_promote_into_working_is_rejected(self):
        mem = MemorySystem()
        self.addCleanup(mem.close)
        with self.assertRaises(MemoryError_):
            mem.promote(verified(), MemoryLayer.WORKING, {"x": 1}, policy_id="p@1")


class TestI6_RecordedSideEffects(unittest.TestCase):
    """Promotions and score changes are evented; the event log is sequenced."""

    def test_promotion_and_scoring_emit_events(self):
        from nexus.kernel.events import EventBus

        bus = EventBus()
        mem = MemorySystem(bus=bus)
        self.addCleanup(mem.close)
        mem.promote(verified(), MemoryLayer.SEMANTIC, {"fact": "x"}, policy_id="p@1")
        self.assertEqual(len(bus.log("memory.promoted")), 1)

        reg = CapabilityRegistry(bus=bus)
        reg.register(CapabilityManifest(name="c", capability_type="code", version="1.0.0"))
        reg.record_outcome("c", "1.0.0", evidence=verified(), success=True)
        self.assertEqual(len(bus.log("capability.scored")), 1)

        seqs = [e.seq for e in bus.log()]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(seqs), len(set(seqs)))


class TestI7_HumanOverride(unittest.TestCase):
    """A human can override the security gate to release held work."""

    def test_approval_releases_blocked_task(self):
        from nexus.executor import Executor
        from nexus.kernel.runtime import Runtime
        from nexus.schemas.core import Plan, Task, TaskStatus
        from nexus.security import SecurityGuard, SecurityPolicy

        rt = Runtime()
        rt.start()
        rt.register_handler("risky@1.0.0", lambda t, c: {"ran": True})
        reg = CapabilityRegistry()
        reg.register(
            CapabilityManifest(name="risky", capability_type="code", version="1.0.0",
                               permissions=["proc.spawn"])
        )
        guard = SecurityGuard(reg, SecurityPolicy(approval_permissions={"proc.spawn"}))
        plan = Plan(id="p", tasks=[Task(id="a", capability_type="code", capability_binding="risky@1.0.0")])

        blocked = Executor(rt, security=guard).execute(plan)
        self.assertIs(blocked.task_results["a"].status, TaskStatus.FAILED)
        guard.approve("risky@1.0.0")
        released = Executor(rt, security=guard).execute(plan)
        self.assertIs(released.task_results["a"].status, TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
