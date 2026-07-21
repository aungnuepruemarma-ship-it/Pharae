import unittest

from nexus.capabilities import CapabilityRegistry, RegistryError
from nexus.executor import Executor, RetryPolicy
from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime
from nexus.memory import MemoryError_, MemoryLayer, MemorySystem
from nexus.planner import Planner
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, Run, RunStatus, Task, TaskResult, TaskStatus
from nexus.verify import VerificationEngine


def executed_run(handlers=None, tasks=None, retry=RetryPolicy()):
    """Run a real plan through the runtime and return (run, plan, runtime)."""
    rt = Runtime()
    rt.start()
    rt.register_handler("echo", lambda task, ctx: {"echo": task.id})
    for ctype, fn in (handlers or {}).items():
        rt.register_handler(ctype, fn)
    plan = Plan(id="plan-v", tasks=tasks or [Task(id="a", capability_type="echo")])
    run = Executor(rt, retry=retry).execute(plan)
    return run, plan, rt


class TestVerifiedSuccess(unittest.TestCase):
    def setUp(self):
        self.run, self.plan, self.rt = executed_run(
            tasks=[
                Task(id="a", capability_type="echo"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
            ]
        )
        self.engine = VerificationEngine(bus=self.rt.bus)

    def test_completed_run_verifies_with_full_confidence(self):
        evidence = self.engine.verify(self.run, plan=self.plan)
        self.assertTrue(evidence.verified)
        self.assertEqual(evidence.confidence, 1.0)
        self.assertTrue(evidence.test_results["success"])
        self.assertTrue(evidence.reproducible)
        events = self.rt.bus.log("run.verified")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["evidence_id"], evidence.id)

    def test_evidence_id_is_deterministic(self):
        e1 = self.engine.verify(self.run, plan=self.plan)
        e2 = self.engine.verify(self.run, plan=self.plan)
        self.assertEqual(e1.id, e2.id)

    def test_cost_report(self):
        evidence = self.engine.verify(self.run, plan=self.plan)
        report = evidence.cost_report
        self.assertEqual(report["tasks"], 2)
        self.assertEqual(report["attempts"], 2)
        self.assertEqual(report["retries"], 0)
        self.assertGreaterEqual(report["duration_s"], 0.0)

    def test_scoring_inputs_are_recorded(self):
        evidence = self.engine.verify(self.run, plan=self.plan)
        scoring = evidence.test_results["scoring"]
        self.assertEqual(scoring["task_completion"], 1.0)
        self.assertEqual(scoring["check_pass_rate"], 1.0)
        self.assertEqual(scoring["first_attempt_rate"], 1.0)
        self.assertEqual(scoring["trace_consistent"], 1.0)


class TestUnverifiable(unittest.TestCase):
    def test_non_terminal_run_is_unverified(self):
        bus = EventBus()
        engine = VerificationEngine(bus=bus)
        run = Run(id="run-live", plan_id="p", session_id="s", status=RunStatus.RUNNING)
        evidence = engine.verify(run)
        self.assertFalse(evidence.verified)
        self.assertEqual(evidence.confidence, 0.0)
        events = bus.log("run.unverified")
        self.assertEqual(len(events), 1)
        self.assertIn("not terminal", " ".join(events[0].payload["reasons"]))

    def test_missing_task_results_is_unverified(self):
        run, plan, rt = executed_run()
        del run.task_results["a"]
        evidence = VerificationEngine(bus=rt.bus).verify(run, plan=plan)
        self.assertFalse(evidence.verified)

    def test_inconsistent_trace_is_unverified(self):
        # A terminal-looking run whose event trace was never produced.
        bus = EventBus()
        engine = VerificationEngine(bus=bus)
        run = Run(id="run-ghost", plan_id="p", session_id="s", status=RunStatus.COMPLETED)
        run.task_results["a"] = TaskResult(task_id="a", status=TaskStatus.COMPLETED)
        evidence = engine.verify(run)
        self.assertFalse(evidence.verified)
        self.assertEqual(len(bus.log("run.unverified")), 1)

    def test_engine_without_bus_skips_trace_check(self):
        run, plan, _ = executed_run()
        evidence = VerificationEngine().verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertNotIn("trace_consistent", evidence.test_results["scoring"])


class TestFailedRunEvidence(unittest.TestCase):
    def test_failure_evidence_is_verified_but_not_success(self):
        def boom(task, ctx):
            raise ValueError("kaput")

        run, plan, rt = executed_run(
            handlers={"boom": boom},
            tasks=[
                Task(id="ok", capability_type="echo"),
                Task(id="bad", capability_type="boom"),
            ],
        )
        self.assertIs(run.status, RunStatus.PARTIAL)
        evidence = VerificationEngine(bus=rt.bus).verify(run, plan=plan)
        self.assertTrue(evidence.verified)  # trustworthy evidence OF a failure
        self.assertFalse(evidence.test_results["success"])
        self.assertLess(evidence.confidence, 1.0)
        self.assertGreater(evidence.confidence, 0.0)


class TestChecks(unittest.TestCase):
    def test_failing_custom_check_lowers_confidence_not_verified(self):
        run, plan, rt = executed_run()
        engine = VerificationEngine(bus=rt.bus)
        engine.register_check(
            "echo", "output-shape", lambda result, task: (False, "echo missing key")
        )
        evidence = engine.verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertFalse(evidence.test_results["success"])
        self.assertLess(evidence.confidence, 1.0)
        failing = [c for c in evidence.test_results["checks"] if not c["passed"]]
        self.assertEqual(failing[0]["name"], "output-shape")
        self.assertEqual(failing[0]["detail"], "echo missing key")

    def test_passing_custom_check_keeps_full_confidence(self):
        run, plan, rt = executed_run()
        engine = VerificationEngine(bus=rt.bus)
        engine.register_check(
            "echo", "output-shape", lambda result, task: "echo" in result.output
        )
        evidence = engine.verify(run, plan=plan)
        self.assertEqual(evidence.confidence, 1.0)
        self.assertTrue(evidence.test_results["success"])

    def test_crashing_check_records_failure_not_crash(self):
        run, plan, rt = executed_run()
        engine = VerificationEngine(bus=rt.bus)

        def bad_check(result, task):
            raise RuntimeError("checker bug")

        engine.register_check("echo", "buggy", bad_check)
        evidence = engine.verify(run, plan=plan)
        failing = [c for c in evidence.test_results["checks"] if not c["passed"]]
        self.assertEqual(len(failing), 1)
        self.assertIn("checker bug", failing[0]["detail"])

    def test_without_plan_type_checks_are_skipped_and_noted(self):
        run, _, rt = executed_run()
        engine = VerificationEngine(bus=rt.bus)
        engine.register_check("echo", "output-shape", lambda r, t: True)
        evidence = engine.verify(run)  # no plan
        self.assertTrue(any("no plan" in line for line in evidence.logs))
        self.assertIsNone(evidence.reproducible)


class TestRetryPenalty(unittest.TestCase):
    def test_retried_success_scores_below_first_attempt_success(self):
        calls = {"n": 0}

        def flaky(task, ctx):
            calls["n"] += 1
            if calls["n"] < 2:
                raise ConnectionError("transient")
            return "ok"

        run, plan, rt = executed_run(
            handlers={"flaky": flaky},
            tasks=[Task(id="a", capability_type="flaky")],
            retry=RetryPolicy(max_attempts=2),
        )
        self.assertIs(run.status, RunStatus.COMPLETED)
        evidence = VerificationEngine(bus=rt.bus).verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertTrue(evidence.test_results["success"])
        self.assertLess(evidence.confidence, 1.0)
        self.assertEqual(evidence.test_results["scoring"]["first_attempt_rate"], 0.0)


class TestGateIntegration(unittest.TestCase):
    """Unverified evidence is provably unable to reach learning or memory."""

    def setUp(self):
        run = Run(id="run-live", plan_id="p", session_id="s", status=RunStatus.RUNNING)
        self.unverified = VerificationEngine().verify(run)
        self.assertFalse(self.unverified.verified)

    def test_unverified_cannot_promote_memory(self):
        memory = MemorySystem()
        with self.assertRaises(MemoryError_):
            memory.promote(
                self.unverified, MemoryLayer.EPISODIC, {"note": "x"}, policy_id="p@1"
            )
        memory.close()

    def test_unverified_cannot_update_capability_scores(self):
        registry = CapabilityRegistry()
        registry.register(
            CapabilityManifest(name="python.local", capability_type="code", version="1.0.0")
        )
        with self.assertRaises(RegistryError):
            registry.record_outcome(
                "python.local", "1.0.0", evidence=self.unverified, success=True
            )


class TestV1SuccessCriteria(unittest.TestCase):
    """Volume 0 §9: understand → plan → select → execute → verify → learn."""

    def test_all_six_steps(self):
        bus = EventBus()
        registry = CapabilityRegistry(bus=bus)
        for name, ctype in [
            ("research.local", "research"),
            ("python.local", "code"),
            ("checks.local", "verify"),
        ]:
            registry.register(
                CapabilityManifest(
                    name=name, capability_type=ctype, version="1.0.0", reliability=0.6
                )
            )
        memory = MemorySystem(bus=bus)
        router = Router(registry, bus=bus, decision_sink=memory.record_routing_decision)
        rt = Runtime(bus=bus)
        for ctype in ("research", "code", "verify"):
            rt.register_handler(ctype, lambda task, ctx: {"done": task.id})
        rt.start()

        # 1. Understand the objective.
        intent = IntentEngine(bus=bus).parse(
            make_objective("Build a REST API from spec.md. Use SQLite")
        )
        # 2. Produce a plan.
        plan = Planner(bus=bus).plan(intent)
        # 3. Select capabilities automatically.
        decisions = router.route_plan(plan)
        # 4. Execute the work.
        run = Executor(rt).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        # 5. Verify the result.
        evidence = VerificationEngine(bus=bus).verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertEqual(evidence.confidence, 1.0)
        # 6. Save useful experience for future runs.
        item = memory.promote(
            evidence,
            MemoryLayer.EPISODIC,
            {"objective": intent.objective_id, "run": run.id, "outcome": "completed"},
            policy_id="promo@1.0.0",
        )
        before = registry.get("python.local").manifest.trust_score
        for task in plan.tasks:
            name = decisions[task.id].chosen.split("@")[0]
            registry.record_outcome(name, "1.0.0", evidence=evidence, success=True)
        after = registry.get("python.local").manifest.trust_score

        self.assertEqual(memory.read(MemoryLayer.EPISODIC)[0].id, item.id)
        self.assertGreater(after, before)
        self.assertEqual(len(memory.routing_decisions()), len(plan.tasks))
        topics = {e.topic for e in bus.log()}
        self.assertTrue(
            {
                "intent.parsed", "plan.created", "route.decided", "run.started",
                "run.completed", "run.verified", "memory.promoted",
                "capability.scored",
            }
            <= topics
        )
        memory.close()


if __name__ == "__main__":
    unittest.main()
