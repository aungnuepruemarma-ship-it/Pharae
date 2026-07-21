import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.kernel.events import EventBus
from nexus.router import Router, RoutingPolicy, UnroutableError
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, Task


def manifest(name, ctype="browser", version="1.0.0", **overrides):
    base = dict(
        name=name,
        capability_type=ctype,
        version=version,
        cost=1.0,
        latency_ms=100.0,
        reliability=0.5,
        trust_score=0.5,
    )
    base.update(overrides)
    return CapabilityManifest(**base)


def task(tid="t1", ctype="browser"):
    return Task(id=tid, capability_type=ctype)


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry(bus=self.bus)
        self.router = Router(self.registry, bus=self.bus)

    def test_routes_to_only_candidate(self):
        self.registry.register(manifest("browser.playwright"))
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.playwright@1.0.0")

    def test_prefers_higher_trust_and_reliability(self):
        self.registry.register(manifest("browser.weak", reliability=0.3, trust_score=0.2))
        self.registry.register(manifest("browser.strong", reliability=0.9, trust_score=0.8))
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.strong@1.0.0")

    def test_cheaper_wins_when_quality_is_equal(self):
        self.registry.register(manifest("browser.pricey", cost=10.0))
        self.registry.register(manifest("browser.cheap", cost=1.0))
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.cheap@1.0.0")

    def test_faster_wins_when_all_else_equal(self):
        self.registry.register(manifest("browser.slow", latency_ms=5000.0))
        self.registry.register(manifest("browser.fast", latency_ms=50.0))
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.fast@1.0.0")

    def test_tie_breaks_by_name_deterministically(self):
        self.registry.register(manifest("browser.zeta"))
        self.registry.register(manifest("browser.alpha"))
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.alpha@1.0.0")

    def test_determinism_same_state_same_choice(self):
        self.registry.register(manifest("browser.a", reliability=0.7))
        self.registry.register(manifest("browser.b", reliability=0.6))
        first = self.router.route(task())
        second = self.router.route(task())
        self.assertEqual(first.chosen, second.chosen)
        other = Router(self.registry)
        self.assertEqual(other.route(task()).chosen, first.chosen)


class TestPolicyFilters(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.router = Router(self.registry)

    def test_denied_capability_is_excluded_with_reason(self):
        self.registry.register(manifest("browser.banned", reliability=0.99, trust_score=0.99))
        self.registry.register(manifest("browser.ok"))
        policy = RoutingPolicy(id="p@1", denied=("browser.banned",))
        decision = self.router.route(task(), policy=policy)
        self.assertEqual(decision.chosen, "browser.ok@1.0.0")
        banned = self._eval(decision, "browser.banned@1.0.0")
        self.assertIn("denied", banned.excluded)

    def test_preference_bonus_flips_choice(self):
        self.registry.register(manifest("browser.better", reliability=0.6))
        self.registry.register(manifest("browser.liked", reliability=0.5))
        base = self.router.route(task())
        self.assertEqual(base.chosen, "browser.better@1.0.0")
        policy = RoutingPolicy(id="p@1", preferred=("browser.liked",))
        decision = self.router.route(task(), policy=policy)
        self.assertEqual(decision.chosen, "browser.liked@1.0.0")

    def test_min_reliability_threshold_excludes(self):
        self.registry.register(manifest("browser.flaky", reliability=0.2))
        policy = RoutingPolicy(id="p@1", min_reliability=0.5)
        decision = self.router.route(task(), policy=policy)
        self.assertIsNone(decision.chosen)
        self.assertIn("reliability", self._eval(decision, "browser.flaky@1.0.0").excluded)

    def test_max_cost_cap_excludes(self):
        self.registry.register(manifest("browser.pricey", cost=100.0))
        self.registry.register(manifest("browser.cheap", cost=1.0))
        policy = RoutingPolicy(id="p@1", max_cost=10.0)
        decision = self.router.route(task(), policy=policy)
        self.assertEqual(decision.chosen, "browser.cheap@1.0.0")
        self.assertIn("cost", self._eval(decision, "browser.pricey@1.0.0").excluded)

    def test_unhealthy_excluded_unknown_allowed_by_default(self):
        self.registry.register(manifest("browser.down"), health_probe=lambda: False)
        self.registry.check_health("browser.down", "1.0.0")
        self.registry.register(manifest("browser.unchecked"))  # health UNKNOWN
        decision = self.router.route(task())
        self.assertEqual(decision.chosen, "browser.unchecked@1.0.0")
        self.assertIn("unhealthy", self._eval(decision, "browser.down@1.0.0").excluded)

    def test_require_healthy_excludes_unknown(self):
        self.registry.register(manifest("browser.unchecked"))
        policy = RoutingPolicy(id="p@1", require_healthy=True)
        decision = self.router.route(task(), policy=policy)
        self.assertIsNone(decision.chosen)

    @staticmethod
    def _eval(decision, capability_id):
        return next(c for c in decision.candidates if c.capability_id == capability_id)


class TestDecisionRecording(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry()
        self.router = Router(self.registry, bus=self.bus, policy=RoutingPolicy(id="default@1.0.0"))

    def test_decision_records_candidates_scores_and_policy(self):
        self.registry.register(manifest("browser.a"))
        self.registry.register(manifest("browser.b"))
        decision = self.router.route(task("t42"))
        self.assertEqual(decision.task_id, "t42")
        self.assertEqual(decision.capability_type, "browser")
        self.assertEqual(decision.policy_id, "default@1.0.0")
        self.assertEqual(len(decision.candidates), 2)
        for candidate in decision.candidates:
            self.assertIsNotNone(candidate.score)
            self.assertIsNone(candidate.excluded)
        self.assertEqual(len(self.router.decisions()), 1)

    def test_every_route_call_is_recorded_including_unroutable(self):
        self.registry.register(manifest("browser.a"))
        self.router.route(task("t1"))
        self.router.route(task("t2", ctype="teleportation"))
        log = self.router.decisions()
        self.assertEqual(len(log), 2)
        self.assertIsNone(log[1].chosen)
        self.assertIn("no registered capabilities", log[1].reason)

    def test_decisions_returns_copies(self):
        self.registry.register(manifest("browser.a"))
        self.router.route(task())
        self.router.decisions()[0].chosen = "tampered"
        self.assertEqual(self.router.decisions()[0].chosen, "browser.a@1.0.0")

    def test_events_decided_and_unroutable(self):
        self.registry.register(manifest("browser.a"))
        d1 = self.router.route(task("t1"))
        d2 = self.router.route(task("t2", ctype="teleportation"))
        decided = self.bus.log("route.decided")
        unroutable = self.bus.log("route.unroutable")
        self.assertEqual(len(decided), 1)
        self.assertEqual(decided[0].payload["decision_id"], d1.id)
        self.assertEqual(decided[0].payload["capability"], "browser.a@1.0.0")
        self.assertEqual(len(unroutable), 1)
        self.assertEqual(unroutable[0].payload["task_id"], "t2")
        self.assertEqual(unroutable[0].payload["decision_id"], d2.id)

    def test_router_works_without_bus(self):
        registry = CapabilityRegistry()
        registry.register(manifest("browser.a"))
        decision = Router(registry).route(task())
        self.assertEqual(decision.chosen, "browser.a@1.0.0")


class TestRoutePlan(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.registry.register(manifest("browser.a", ctype="browser"))
        self.registry.register(manifest("python.local", ctype="code"))
        self.router = Router(self.registry)

    def test_route_plan_binds_every_task(self):
        plan = Plan(
            id="p1",
            tasks=[
                Task(id="t1", capability_type="browser"),
                Task(id="t2", capability_type="code", depends_on=["t1"]),
            ],
        )
        decisions = self.router.route_plan(plan)
        self.assertEqual(plan.tasks[0].capability_binding, "browser.a@1.0.0")
        self.assertEqual(plan.tasks[1].capability_binding, "python.local@1.0.0")
        self.assertEqual(set(decisions), {"t1", "t2"})

    def test_route_plan_raises_on_unroutable_after_recording(self):
        plan = Plan(
            id="p1",
            tasks=[
                Task(id="t1", capability_type="browser"),
                Task(id="t2", capability_type="teleportation"),
            ],
        )
        with self.assertRaises(UnroutableError) as ctx:
            self.router.route_plan(plan)
        self.assertIn("t2", str(ctx.exception))
        self.assertEqual(len(self.router.decisions()), 2)  # both recorded
        self.assertIsNone(plan.tasks[1].capability_binding)


if __name__ == "__main__":
    unittest.main()
