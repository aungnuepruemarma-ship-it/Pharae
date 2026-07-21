import unittest

from nexus.capabilities import CapabilityRegistry, RegistrationStatus
from nexus.executor import Executor
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime
from nexus.plugins import PluginError, PluginManager, PluginStatus
from nexus.router import Router, RoutingPolicy
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, RunStatus, Task
from nexus.schemas.plugin import PluginPackage
from tests import plugin_fixtures


def calc_manifest(name="calc.local", ctype="code", version="1.0.0", perms=("fs.read",)):
    return CapabilityManifest(
        name=name, capability_type=ctype, version=version,
        permissions=list(perms), reliability=0.8,
    )


def calc_package(version="1.0.0", entrypoint="tests.plugin_fixtures:setup_calc", **kw):
    caps = kw.pop("capabilities", [calc_manifest(version=version)])
    return PluginPackage(
        name="nexus-calc",
        version=version,
        capabilities=caps,
        requested_permissions=kw.pop("requested_permissions", ["fs.read"]),
        entrypoint=entrypoint,
        **kw,
    )


class PluginTestCase(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry(bus=self.bus)
        self.runtime = Runtime(bus=self.bus)
        self.manager = PluginManager(self.registry, self.runtime, bus=self.bus)
        plugin_fixtures.CALLS.clear()


class TestInstall(PluginTestCase):
    def test_install_registers_capabilities_and_handlers(self):
        record = self.manager.install(calc_package())
        self.assertIs(record.status, PluginStatus.INSTALLED)
        self.assertEqual(record.capability_ids, ["calc.local@1.0.0"])
        self.assertEqual(len(self.registry.find("code")), 1)
        task = Task(id="t", capability_type="code", capability_binding="calc.local@1.0.0")
        self.assertIsNotNone(self.runtime.resolve_handler(task))
        events = self.bus.log("plugin.installed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["plugin"], "nexus-calc")

    def test_invalid_manifest_rejected_nothing_registered(self):
        bad = calc_package(capabilities=[calc_manifest(version="not-semver")])
        with self.assertRaises(PluginError):
            self.manager.install(bad)
        self.assertEqual(self.registry.find("code"), [])
        self.assertEqual(self.manager.list(), [])

    def test_no_capabilities_rejected(self):
        with self.assertRaises(PluginError) as ctx:
            self.manager.install(calc_package(capabilities=[]))
        self.assertIn("at least one capability", str(ctx.exception))

    def test_manifest_permission_outside_requested_rejected(self):
        sneaky = calc_package(
            capabilities=[calc_manifest(perms=("fs.read", "net.fetch"))],
            requested_permissions=["fs.read"],
        )
        with self.assertRaises(PluginError) as ctx:
            self.manager.install(sneaky)
        self.assertIn("net.fetch", str(ctx.exception))

    def test_permission_review_against_allowlist(self):
        manager = PluginManager(
            self.registry, self.runtime, allowed_permissions={"fs.read"}
        )
        overreaching = calc_package(
            capabilities=[calc_manifest(perms=("fs.read", "proc.spawn"))],
            requested_permissions=["fs.read", "proc.spawn"],
        )
        with self.assertRaises(PluginError) as ctx:
            manager.install(overreaching)
        self.assertIn("proc.spawn", str(ctx.exception))

    def test_duplicate_plugin_name_rejected(self):
        self.manager.install(calc_package())
        with self.assertRaises(PluginError):
            self.manager.install(calc_package(version="2.0.0"))

    def test_capability_name_owned_by_other_plugin_rejected(self):
        self.manager.install(calc_package())
        thief = PluginPackage(
            name="nexus-thief",
            version="1.0.0",
            capabilities=[calc_manifest()],  # same capability name
            requested_permissions=["fs.read"],
            entrypoint="tests.plugin_fixtures:setup_calc",
        )
        with self.assertRaises(PluginError) as ctx:
            self.manager.install(thief)
        self.assertIn("calc.local", str(ctx.exception))
        self.assertEqual(len(self.manager.list()), 1)  # first plugin intact

    def test_broken_entrypoint_leaves_no_trace(self):
        with self.assertRaises(PluginError):
            self.manager.install(
                calc_package(entrypoint="tests.plugin_fixtures:setup_broken")
            )
        self.assertEqual(self.registry.find("code"), [])
        self.assertEqual(self.manager.list(), [])

    def test_entrypoint_key_mismatch_rejected(self):
        with self.assertRaises(PluginError) as ctx:
            self.manager.install(
                calc_package(entrypoint="tests.plugin_fixtures:setup_wrong_keys")
            )
        self.assertIn("calc.local", str(ctx.exception))

    def test_entrypoint_must_return_handler_mapping(self):
        with self.assertRaises(PluginError):
            self.manager.install(
                calc_package(entrypoint="tests.plugin_fixtures:setup_not_a_dict")
            )

    def test_missing_entrypoint_module(self):
        with self.assertRaises(PluginError):
            self.manager.install(calc_package(entrypoint="tests.no_such_module:setup"))


class TestLifecycle(PluginTestCase):
    def setUp(self):
        super().setUp()
        self.manager.install(calc_package())
        self.task = Task(
            id="t", capability_type="code", capability_binding="calc.local@1.0.0"
        )

    def test_disable_flags_and_unwires_but_retains_state(self):
        self.manager.disable("nexus-calc")
        record = self.manager.get("nexus-calc")
        self.assertIs(record.status, PluginStatus.DISABLED)
        self.assertEqual(self.registry.find("code"), [])  # excluded from discovery
        kept = self.registry.get("calc.local", "1.0.0")
        self.assertIs(kept.status, RegistrationStatus.RETIRED)  # retained, flagged
        self.assertIsNone(self.runtime.resolve_handler(self.task))
        self.assertEqual(len(self.bus.log("plugin.disabled")), 1)

    def test_enable_restores_capabilities_and_handlers(self):
        self.manager.disable("nexus-calc")
        self.manager.enable("nexus-calc")
        self.assertIs(self.manager.get("nexus-calc").status, PluginStatus.INSTALLED)
        self.assertEqual(len(self.registry.find("code")), 1)
        self.assertIsNotNone(self.runtime.resolve_handler(self.task))
        self.assertEqual(len(self.bus.log("plugin.enabled")), 1)

    def test_remove_deregisters_but_keeps_registry_history(self):
        self.manager.remove("nexus-calc")
        self.assertIs(self.manager.get("nexus-calc").status, PluginStatus.REMOVED)
        self.assertEqual(self.manager.list(), [])  # default listing excludes removed
        self.assertEqual(len(self.manager.list(include_removed=True)), 1)
        self.assertIsNone(self.runtime.resolve_handler(self.task))
        history = self.registry.get("calc.local", "1.0.0")
        self.assertIs(history.status, RegistrationStatus.RETIRED)  # never deleted
        self.assertEqual(len(self.bus.log("plugin.removed")), 1)

    def test_reinstall_after_remove(self):
        self.manager.remove("nexus-calc")
        record = self.manager.install(calc_package())
        self.assertIs(record.status, PluginStatus.INSTALLED)
        self.assertEqual(len(self.registry.find("code")), 1)

    def test_update_swaps_versions_and_records_history(self):
        new = PluginPackage(
            name="nexus-calc",
            version="2.0.0",
            capabilities=[
                calc_manifest(version="2.0.0"),
                calc_manifest(name="calc.stats", ctype="research", version="2.0.0"),
            ],
            requested_permissions=["fs.read"],
            entrypoint="tests.plugin_fixtures:setup_calc_v2",
        )
        record = self.manager.update(new)
        self.assertEqual(record.package.version, "2.0.0")
        self.assertEqual(record.previous_versions, ["1.0.0"])
        self.assertEqual(
            self.registry.get("calc.local").manifest.version, "2.0.0"
        )  # latest active
        self.assertIs(
            self.registry.get("calc.local", "1.0.0").status, RegistrationStatus.RETIRED
        )
        self.assertEqual(len(self.registry.find("research")), 1)
        old_bound = Task(id="t", capability_type="code", capability_binding="calc.local@1.0.0")
        new_bound = Task(id="t", capability_type="code", capability_binding="calc.local@2.0.0")
        self.assertIsNone(self.runtime.resolve_handler(old_bound))
        self.assertIsNotNone(self.runtime.resolve_handler(new_bound))
        self.assertEqual(len(self.bus.log("plugin.updated")), 1)

    def test_update_unknown_or_same_version_rejected(self):
        with self.assertRaises(PluginError):
            self.manager.update(
                PluginPackage(
                    name="ghost", version="1.0.0",
                    capabilities=[calc_manifest(name="g.x")],
                    requested_permissions=["fs.read"],
                    entrypoint="tests.plugin_fixtures:setup_calc",
                )
            )
        with self.assertRaises(PluginError):
            self.manager.update(calc_package(version="1.0.0"))


class TestDispatchByBinding(PluginTestCase):
    """Two plugins of the same capability type coexist; the router's binding
    decides which handler runs — the runtime honors it exactly."""

    def test_bound_capability_handler_runs(self):
        for suffix, entry in (("a", "setup_a"), ("b", "setup_b")):
            self.manager.install(
                PluginPackage(
                    name=f"nexus-{suffix}",
                    version="1.0.0",
                    capabilities=[calc_manifest(name=f"calc.{suffix}", ctype="math")],
                    requested_permissions=["fs.read"],
                    entrypoint=f"tests.plugin_fixtures:{entry}",
                )
            )
        router = Router(
            self.registry, policy=RoutingPolicy(id="p@1", preferred=("calc.b",))
        )
        plan = Plan(id="p", tasks=[Task(id="t1", capability_type="math")])
        router.route_plan(plan)
        self.assertEqual(plan.tasks[0].capability_binding, "calc.b@1.0.0")

        self.runtime.start()
        run = Executor(self.runtime).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.task_results["t1"].output["by"], "calc.b")
        self.assertEqual(plugin_fixtures.CALLS, [("calc.b", "t1")])


class TestFullLoop(PluginTestCase):
    def test_installed_plugin_serves_a_routed_run(self):
        self.manager.install(calc_package())
        router = Router(self.registry, bus=self.bus)
        plan = Plan(
            id="p",
            tasks=[
                Task(id="t1", capability_type="code", payload={"numbers": [1, 2, 3]})
            ],
        )
        router.route_plan(plan)
        self.runtime.start()
        run = Executor(self.runtime).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.task_results["t1"].output, {"sum": 6, "by": "calc.local"})


if __name__ == "__main__":
    unittest.main()
