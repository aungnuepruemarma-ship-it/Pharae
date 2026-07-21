import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.cog import Cog, CogError, PolicyEngine, to_routing_policy
from nexus.executor import Executor
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime
from nexus.memory import MemoryLayer, MemorySystem
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, Run, RunStatus, Task
from nexus.verify import VerificationEngine


def manifest(name, ctype="code", trust=0.2, reliability=0.5):
    return CapabilityManifest(
        name=name, capability_type=ctype, version="1.0.0",
        trust_score=trust, reliability=reliability,
    )


class CogTestCase(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.memory = MemorySystem(bus=self.bus)
        self.addCleanup(self.memory.close)
        self.registry = CapabilityRegistry(bus=self.bus)
        self.rt = Runtime(bus=self.bus)
        self.rt.start()
        self.verifier = VerificationEngine(bus=self.bus)
        self.cog = Cog(self.memory, registry=self.registry, bus=self.bus)

    def run_and_verify(self, tasks, plan_id="plan-c"):
        plan = Plan(id=plan_id, tasks=tasks)
        run = Executor(self.rt).execute(plan)
        evidence = self.verifier.verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        return run, plan, evidence

    def ok_task(self, tid="a", ctype="code", binding=None):
        self.rt.register_handler(ctype, lambda task, ctx: {"done": task.id})
        return Task(id=tid, capability_type=ctype, capability_binding=binding)

    def bad_task(self, tid="a", ctype="boom", binding=None):
        def fail(task, ctx):
            raise ValueError("kaput")

        self.rt.register_handler(ctype, fail)
        return Task(id=tid, capability_type=ctype, capability_binding=binding)


class TestLearnGate(CogTestCase):
    def test_unverified_evidence_rejected_nothing_written(self):
        run = Run(id="r", plan_id="p", session_id="s", status=RunStatus.RUNNING)
        evidence = VerificationEngine().verify(run)  # unverifiable
        with self.assertRaises(CogError):
            self.cog.learn(run, evidence)
        self.assertEqual(self.memory.read(MemoryLayer.EPISODIC), [])
        self.assertEqual(self.memory.read(MemoryLayer.FAILURE), [])


class TestReflection(CogTestCase):
    def test_success_learn_promotes_episodic_with_provenance(self):
        run, plan, evidence = self.run_and_verify([self.ok_task()])
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertTrue(result.success)
        self.assertEqual(result.signature, "code")
        items = self.memory.read(MemoryLayer.EPISODIC)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, result.episodic_id)
        self.assertEqual(items[0].content["run_id"], run.id)
        self.assertTrue(items[0].content["success"])
        self.assertEqual(items[0].provenance["evidence_id"], evidence.id)
        self.assertEqual(result.failure_ids, [])

    def test_failure_learn_promotes_failure_items(self):
        run, plan, evidence = self.run_and_verify(
            [
                self.ok_task("good", ctype="code"),
                self.bad_task("bad", binding="broken.local@1.0.0"),
            ]
        )
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertFalse(result.success)
        failures = self.memory.read(MemoryLayer.FAILURE)
        self.assertEqual(len(failures), 1)
        content = failures[0].content
        self.assertEqual(content["task_id"], "bad")
        self.assertEqual(content["capability"], "broken.local@1.0.0")
        self.assertIn("kaput", content["error"])
        episodic = self.memory.read(MemoryLayer.EPISODIC)[0]
        self.assertFalse(episodic.content["success"])


class TestScoreUpdates(CogTestCase):
    def test_outcomes_move_registry_scores(self):
        self.registry.register(manifest("solid.local"))
        self.registry.register(manifest("shaky.local"))
        before_solid = self.registry.get("solid.local").manifest.trust_score
        before_shaky = self.registry.get("shaky.local").manifest.reliability

        run, plan, evidence = self.run_and_verify(
            [
                self.ok_task("a", ctype="code", binding="solid.local@1.0.0"),
                self.bad_task("b", binding="shaky.local@1.0.0"),
            ]
        )
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertIn(("solid.local@1.0.0", True), result.score_updates)
        self.assertIn(("shaky.local@1.0.0", False), result.score_updates)
        self.assertGreater(
            self.registry.get("solid.local").manifest.trust_score, before_solid
        )
        self.assertLess(
            self.registry.get("shaky.local").manifest.reliability, before_shaky
        )

    def test_reward_shaping_makes_cheaper_success_build_more_trust(self):
        # Two capabilities, identical starting trust. Same verified success,
        # but one run needed a retry — reward shaping should reward the clean
        # one more. Cog passes a reward derived from the run's own evidence,
        # so we drive two runs with different retry cost.
        from nexus.executor import RetryPolicy

        self.registry.register(manifest("clean.local", trust=0.2))
        self.registry.register(manifest("retry.local", trust=0.2))

        # clean capability: succeeds first try
        clean_run, clean_plan, clean_ev = self.run_and_verify(
            [self.ok_task("a", ctype="code", binding="clean.local@1.0.0")],
            plan_id="p-clean",
        )
        self.cog.learn(clean_run, clean_ev, plan=clean_plan)

        # retry capability: fails once then succeeds (needs its own runtime path)
        calls = {"n": 0}

        def flaky(task, ctx):
            calls["n"] += 1
            if calls["n"] < 2:
                raise ConnectionError("transient")
            return {"done": task.id}

        self.rt.register_handler("flaky", flaky)
        from nexus.schemas.core import Plan as _Plan

        plan = _Plan(
            id="p-retry",
            tasks=[Task(id="a", capability_type="flaky", capability_binding="retry.local@1.0.0")],
        )
        run = Executor(self.rt, retry=RetryPolicy(max_attempts=2)).execute(plan)
        evidence = self.verifier.verify(run, plan=plan)
        self.cog.learn(run, evidence, plan=plan)

        clean_trust = self.registry.get("clean.local").manifest.trust_score
        retry_trust = self.registry.get("retry.local").manifest.trust_score
        self.assertGreater(clean_trust, retry_trust)  # friction cost trust

    def test_unknown_binding_is_noted_not_fatal(self):
        run, plan, evidence = self.run_and_verify(
            [self.ok_task("a", binding="ghost.local@9.9.9")]
        )
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertEqual(result.score_updates, [])
        self.assertTrue(any("ghost.local" in note for note in result.notes))


class TestSkills(CogTestCase):
    def test_three_verified_successes_promote_a_skill_once(self):
        skill_ids = []
        for i in range(4):
            run, plan, evidence = self.run_and_verify(
                [self.ok_task()], plan_id=f"plan-{i}"
            )
            result = self.cog.learn(run, evidence, plan=plan)
            skill_ids.append(result.skill_id)
        self.assertEqual(skill_ids[:2], [None, None])
        self.assertIsNotNone(skill_ids[2])  # third success crosses the threshold
        self.assertIsNone(skill_ids[3])  # no duplicate skill
        skills = self.memory.read(MemoryLayer.PROCEDURAL)
        self.assertEqual(len(skills), 1)
        content = skills[0].content
        self.assertEqual(content["signature"], "code")
        self.assertEqual(len(content["source_runs"]), 3)
        self.assertEqual(content["task_chain"], [{"capability_type": "code", "description": ""}])
        self.assertEqual(len(self.bus.log("skill.promoted")), 1)

    def test_different_signatures_do_not_cross_count(self):
        for i in range(2):
            run, plan, evidence = self.run_and_verify(
                [self.ok_task()], plan_id=f"plan-a{i}"
            )
            self.cog.learn(run, evidence, plan=plan)
        run, plan, evidence = self.run_and_verify(
            [self.ok_task("r", ctype="research")], plan_id="plan-b"
        )
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertIsNone(result.skill_id)
        self.assertEqual(self.memory.read(MemoryLayer.PROCEDURAL), [])

    def test_verified_failure_deprecates_the_skill(self):
        for i in range(3):
            run, plan, evidence = self.run_and_verify(
                [self.ok_task()], plan_id=f"plan-{i}"
            )
            self.cog.learn(run, evidence, plan=plan)
        self.assertEqual(len(self.memory.read(MemoryLayer.PROCEDURAL)), 1)

        run, plan, evidence = self.run_and_verify(
            [self.bad_task("a", ctype="code")], plan_id="plan-fail"
        )
        result = self.cog.learn(run, evidence, plan=plan)
        self.assertIsNotNone(result.deprecated_skill_id)
        self.assertEqual(self.memory.read(MemoryLayer.PROCEDURAL), [])  # gone by default
        self.assertEqual(len(self.bus.log("skill.deprecated")), 1)


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.memory = MemorySystem()
        self.addCleanup(self.memory.close)
        self.engine = PolicyEngine(bus=self.bus, sink=self.memory.record_policy_event)

    def test_propose_activate_supersede(self):
        v1 = self.engine.propose("routing", {"denied": []}, reason="baseline")
        self.assertIsNone(self.engine.active("routing"))
        self.engine.activate("routing", v1.version)
        self.assertEqual(self.engine.active("routing").version, 1)

        v2 = self.engine.propose("routing", {"denied": ["bad.cap"]}, reason="failures")
        self.engine.activate("routing", v2.version)
        active = self.engine.active("routing")
        self.assertEqual(active.version, 2)
        self.assertEqual(active.payload["denied"], ["bad.cap"])
        history = self.engine.history("routing")
        self.assertEqual([p.status.value for p in history], ["deprecated", "active"])
        self.assertEqual(len(self.bus.log("policy.activated")), 2)

    def test_rollback_restores_previous_active(self):
        v1 = self.engine.propose("routing", {"denied": []}, reason="baseline")
        self.engine.activate("routing", v1.version)
        v2 = self.engine.propose("routing", {"denied": ["bad.cap"]}, reason="failures")
        self.engine.activate("routing", v2.version)

        restored = self.engine.rollback("routing", reason="regression")
        self.assertEqual(restored.version, 1)
        self.assertEqual(self.engine.active("routing").version, 1)
        self.assertEqual(len(self.bus.log("policy.rolled_back")), 1)
        with self.assertRaises(CogError):
            self.engine.rollback("routing", reason="nothing left")

    def test_journal_is_durable_in_memory(self):
        v1 = self.engine.propose("routing", {"denied": []}, reason="baseline")
        self.engine.activate("routing", v1.version)
        events = self.memory.policy_events("routing")
        self.assertGreaterEqual(len(events), 2)  # proposed + activated
        self.assertEqual(events[0]["status"], "proposed")
        self.assertEqual(events[-1]["status"], "active")
        self.assertEqual(events[-1]["payload"], {"denied": []})


class TestRoutingImprovement(CogTestCase):
    def test_repeated_failures_deny_the_capability(self):
        self.registry.register(manifest("broken.local"))
        cog = Cog(self.memory, registry=self.registry, bus=self.bus, failure_threshold=2)
        for i in range(2):
            run, plan, evidence = self.run_and_verify(
                [self.bad_task("a", binding="broken.local@1.0.0")], plan_id=f"p{i}"
            )
            result = cog.learn(run, evidence, plan=plan)
        self.assertEqual(len(result.policy_changes), 1)
        active = cog.policies.active("routing")
        self.assertEqual(active.payload["denied"], ["broken.local"])

        routing_policy = to_routing_policy(active)
        self.assertEqual(routing_policy.id, active.id)
        decision = Router(self.registry, policy=routing_policy).route(
            Task(id="t", capability_type="code")
        )
        self.assertIsNone(decision.chosen)  # only candidate is now denied


class TestImprovedFutureRouting(CogTestCase):
    """The last arrow of the product loop: verified failures teach the
    runtime to route away from a trusted-but-broken capability."""

    def test_full_improvement_loop(self):
        # flaky starts with the better scores — the router will prefer it.
        self.registry.register(manifest("flaky.local", trust=0.9, reliability=0.9))
        self.registry.register(manifest("solid.local", trust=0.2, reliability=0.5))

        def failing(task, ctx):
            raise ConnectionError("flaky backend down")

        self.rt.register_handler("flaky.local@1.0.0", failing)
        self.rt.register_handler("solid.local@1.0.0", lambda t, c: {"by": "solid"})

        router = Router(self.registry, bus=self.bus)
        for i in range(3):
            plan = Plan(id=f"p{i}", tasks=[Task(id="t", capability_type="code")])
            router.route_plan(plan)
            self.assertEqual(plan.tasks[0].capability_binding, "flaky.local@1.0.0")
            run = Executor(self.rt).execute(plan)
            self.assertIs(run.status, RunStatus.FAILED)
            evidence = self.verifier.verify(run, plan=plan)
            result = self.cog.learn(run, evidence, plan=plan)

        self.assertTrue(result.policy_changes)
        learned = to_routing_policy(self.cog.policies.active("routing"))

        plan = Plan(id="p-final", tasks=[Task(id="t", capability_type="code")])
        router.route_plan(plan, policy=learned)
        self.assertEqual(plan.tasks[0].capability_binding, "solid.local@1.0.0")
        run = Executor(self.rt).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.task_results["t"].output, {"by": "solid"})


if __name__ == "__main__":
    unittest.main()
