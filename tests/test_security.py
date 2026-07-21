import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.executor import Executor
from nexus.kernel.runtime import Runtime
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, RunStatus, Task, TaskStatus
from nexus.security import Decision, SecurityGuard, SecurityPolicy


def manifest(name, ctype="code", perms=("proc.compute",)):
    return CapabilityManifest(
        name=name, capability_type=ctype, version="1.0.0", permissions=list(perms)
    )


class TestPolicy(unittest.TestCase):
    def test_default_allows(self):
        d = SecurityPolicy().decide(manifest("x"))
        self.assertIs(d.verdict, Decision.ALLOW)

    def test_denied_permission(self):
        p = SecurityPolicy(denied_permissions={"fs.write"})
        d = p.decide(manifest("x", perms=("fs.read", "fs.write")))
        self.assertIs(d.verdict, Decision.DENY)
        self.assertIn("fs.write", d.reason)

    def test_permission_requires_approval(self):
        p = SecurityPolicy(approval_permissions={"proc.spawn"})
        self.assertIs(p.decide(manifest("x", perms=("proc.spawn",))).verdict, Decision.REQUIRE_APPROVAL)

    def test_type_requires_approval(self):
        p = SecurityPolicy(approval_types={"browser"})
        self.assertIs(p.decide(manifest("x", ctype="browser")).verdict, Decision.REQUIRE_APPROVAL)


class TestGuard(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.registry.register(manifest("safe.local", perms=("proc.compute",)))
        self.registry.register(manifest("risky.local", perms=("proc.spawn",)))

    def task(self, binding):
        return Task(id="t", capability_type="code", capability_binding=binding)

    def test_allows_when_permissive(self):
        guard = SecurityGuard(self.registry, SecurityPolicy())
        ok, _ = guard.check(self.task("safe.local@1.0.0"))
        self.assertTrue(ok)

    def test_denies_forbidden(self):
        guard = SecurityGuard(self.registry, SecurityPolicy(denied_permissions={"proc.spawn"}))
        ok, reason = guard.check(self.task("risky.local@1.0.0"))
        self.assertFalse(ok)
        self.assertIn("deni", reason.lower())

    def test_approval_flow(self):
        guard = SecurityGuard(self.registry, SecurityPolicy(approval_permissions={"proc.spawn"}))
        ok, reason = guard.check(self.task("risky.local@1.0.0"))
        self.assertFalse(ok)
        self.assertIn("approval", reason.lower())
        guard.approve("risky.local@1.0.0")
        ok, _ = guard.check(self.task("risky.local@1.0.0"))
        self.assertTrue(ok)

    def test_unknown_binding_allowed(self):
        guard = SecurityGuard(self.registry, SecurityPolicy(denied_permissions={"x.y"}))
        ok, _ = guard.check(self.task("ghost@9.9.9"))
        self.assertTrue(ok)  # nothing to judge; router already bound it


class TestExecutorEnforcement(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()
        self.rt.start()
        self.rt.register_handler("risky.local@1.0.0", lambda t, c: {"ran": True})
        self.rt.register_handler("safe.local@1.0.0", lambda t, c: {"ran": True})
        self.registry = CapabilityRegistry()
        self.registry.register(manifest("safe.local", perms=("proc.compute",)))
        self.registry.register(manifest("risky.local", perms=("proc.spawn",)))

    def plan(self):
        return Plan(id="p", tasks=[
            Task(id="a", capability_type="code", capability_binding="risky.local@1.0.0"),
            Task(id="b", capability_type="code", capability_binding="safe.local@1.0.0"),
        ])

    def test_denied_task_never_runs(self):
        guard = SecurityGuard(self.registry, SecurityPolicy(denied_permissions={"proc.spawn"}))
        run = Executor(self.rt, security=guard).execute(self.plan())
        self.assertIs(run.task_results["a"].status, TaskStatus.FAILED)
        self.assertIn("security", (run.task_results["a"].error or "").lower())
        self.assertIs(run.task_results["b"].status, TaskStatus.COMPLETED)
        self.assertEqual(len(self.rt.bus.log("security.blocked")), 1)

    def test_approval_gate_holds_then_releases(self):
        guard = SecurityGuard(self.registry, SecurityPolicy(approval_permissions={"proc.spawn"}))
        blocked = Executor(self.rt, security=guard).execute(self.plan())
        self.assertIs(blocked.task_results["a"].status, TaskStatus.FAILED)

        guard.approve("risky.local@1.0.0")
        released = Executor(self.rt, security=guard).execute(self.plan())
        self.assertIs(released.task_results["a"].status, TaskStatus.COMPLETED)
        self.assertIs(released.status, RunStatus.COMPLETED)

    def test_no_guard_is_unchanged(self):
        run = Executor(self.rt).execute(self.plan())
        self.assertIs(run.status, RunStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
