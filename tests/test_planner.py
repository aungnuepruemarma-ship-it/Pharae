import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime
from nexus.kernel.scheduler import Scheduler
from nexus.planner import Planner, PlannerError
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Evidence, Intent, RunStatus, TaskStatus


def intent(goals=(), constraints=(), outcomes=(), refs=(), questions=()):
    return Intent(
        id="int-abc",
        objective_id="obj-abc",
        goals=list(goals),
        constraints=list(constraints),
        desired_outcomes=list(outcomes),
        open_questions=list(questions),
        context_refs=list(refs),
    )


class TestPlanShape(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def test_single_goal_yields_goal_and_verify_tasks(self):
        plan = self.planner.plan(intent(goals=["Implement the API"]))
        ids = [t.id for t in plan.tasks]
        self.assertEqual(ids, ["goal-1", "verify"])
        verify = plan.tasks[1]
        self.assertEqual(verify.capability_type, "verify")
        self.assertEqual(verify.depends_on, ["goal-1"])

    def test_goals_are_chained_sequentially(self):
        plan = self.planner.plan(
            intent(goals=["Research options", "Design the schema", "Implement the API"])
        )
        by_id = {t.id: t for t in plan.tasks}
        self.assertEqual(by_id["goal-1"].depends_on, [])
        self.assertEqual(by_id["goal-2"].depends_on, ["goal-1"])
        self.assertEqual(by_id["goal-3"].depends_on, ["goal-2"])
        self.assertEqual(sorted(by_id["verify"].depends_on), ["goal-1", "goal-2", "goal-3"])

    def test_context_refs_prepend_gather_task(self):
        plan = self.planner.plan(intent(goals=["Implement the API"], refs=["spec.md"]))
        by_id = {t.id: t for t in plan.tasks}
        self.assertIn("gather-context", by_id)
        gather = by_id["gather-context"]
        self.assertEqual(gather.capability_type, "research")
        self.assertEqual(gather.payload["context_refs"], ["spec.md"])
        self.assertEqual(by_id["goal-1"].depends_on, ["gather-context"])

    def test_constraints_attached_to_every_goal_task(self):
        plan = self.planner.plan(
            intent(goals=["Build the CLI"], constraints=["Use Python 3.11"])
        )
        by_id = {t.id: t for t in plan.tasks}
        self.assertEqual(by_id["goal-1"].payload["constraints"], ["Use Python 3.11"])

    def test_verify_task_carries_desired_outcomes(self):
        plan = self.planner.plan(
            intent(goals=["Build the API"], outcomes=["clients can generate SDKs"])
        )
        verify = next(t for t in plan.tasks if t.id == "verify")
        self.assertEqual(verify.payload["desired_outcomes"], ["clients can generate SDKs"])

    def test_goal_description_in_payload(self):
        plan = self.planner.plan(intent(goals=["Implement the API"]))
        self.assertEqual(plan.tasks[0].payload["description"], "Implement the API")

    def test_plan_records_intent_id(self):
        plan = self.planner.plan(intent(goals=["Build it"]))
        self.assertEqual(plan.intent_id, "int-abc")


class TestCapabilityTyping(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def classify(self, goal):
        plan = self.planner.plan(intent(goals=[goal]))
        return plan.tasks[0].capability_type

    def test_research_verbs(self):
        self.assertEqual(self.classify("Research existing solutions"), "research")
        self.assertEqual(self.classify("Compare storage engines"), "research")
        self.assertEqual(self.classify("Summarize the findings"), "research")

    def test_browser_verbs(self):
        self.assertEqual(self.classify("Scrape the pricing pages"), "browser")
        self.assertEqual(self.classify("Visit the vendor portal"), "browser")

    def test_verify_verbs_win_over_browser(self):
        self.assertEqual(self.classify("Test the scraper"), "verify")
        self.assertEqual(self.classify("Benchmark the parser"), "verify")

    def test_maker_default_is_code(self):
        self.assertEqual(self.classify("Implement the API"), "code")
        self.assertEqual(self.classify("Design the schema"), "code")

    def test_no_vendor_ever_appears(self):
        plan = self.planner.plan(intent(goals=["Research models", "Build the app"]))
        for task in plan.tasks:
            self.assertNotIn("@", task.capability_type)
            self.assertIsNone(task.capability_binding)


class TestDeterminismAndValidity(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def test_same_intent_same_plan(self):
        i = intent(goals=["Research", "Build it"], constraints=["Use SQLite"], refs=["a.md"])
        p1, p2 = self.planner.plan(i), self.planner.plan(i)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(p1.tasks, p2.tasks)

    def test_different_intents_different_plan_ids(self):
        p1 = self.planner.plan(intent(goals=["Build an API"]))
        i2 = intent(goals=["Build a CLI"])
        i2 = Intent(**{**i2.__dict__, "id": "int-other"})
        p2 = self.planner.plan(i2)
        self.assertNotEqual(p1.id, p2.id)

    def test_plan_is_scheduler_valid(self):
        plan = self.planner.plan(
            intent(goals=["Research", "Design", "Implement"], refs=["spec.md"])
        )
        Scheduler().submit(plan.tasks)  # closed + acyclic or it raises

    def test_no_goals_raises(self):
        with self.assertRaises(PlannerError):
            self.planner.plan(intent(questions=["What should we build?"]))

    def test_open_questions_with_goals_still_plans(self):
        plan = self.planner.plan(
            intent(goals=["Build it"], questions=["Should promotion be automatic?"])
        )
        self.assertEqual([t.id for t in plan.tasks], ["goal-1", "verify"])

    def test_plan_created_event(self):
        bus = EventBus()
        plan = Planner(bus=bus).plan(intent(goals=["Build it"]))
        events = bus.log("plan.created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["plan_id"], plan.id)
        self.assertEqual(events[0].payload["intent_id"], "int-abc")


class TestReplanning(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.planner = Planner(bus=self.bus)
        self.plan = self.planner.plan(intent(goals=["Research", "Design", "Implement"]))
        self.evidence = Evidence(id="ev-9", run_id="run-1", verified=True, confidence=0.3)

    def test_replan_is_a_new_plan_with_provenance(self):
        successor = self.planner.replan(self.plan, self.evidence, completed={"goal-1"})
        self.assertNotEqual(successor.id, self.plan.id)
        self.assertIn(self.plan.id, successor.provenance)
        self.assertIn("ev-9", successor.provenance)

    def test_replan_drops_completed_and_filters_deps(self):
        successor = self.planner.replan(self.plan, self.evidence, completed={"goal-1"})
        ids = [t.id for t in successor.tasks]
        self.assertNotIn("goal-1", ids)
        by_id = {t.id: t for t in successor.tasks}
        self.assertEqual(by_id["goal-2"].depends_on, [])  # dep on completed dropped
        self.assertEqual(sorted(by_id["verify"].depends_on), ["goal-2", "goal-3"])

    def test_replan_resets_status_and_bindings(self):
        self.plan.tasks[1].status = TaskStatus.FAILED
        self.plan.tasks[1].capability_binding = "python.local@1.0.0"
        successor = self.planner.replan(self.plan, self.evidence)
        for task in successor.tasks:
            self.assertIs(task.status, TaskStatus.PENDING)
            self.assertIsNone(task.capability_binding)

    def test_replan_does_not_mutate_original(self):
        before = [t.id for t in self.plan.tasks]
        self.planner.replan(self.plan, self.evidence, completed={"goal-1"})
        self.assertEqual([t.id for t in self.plan.tasks], before)

    def test_replan_is_deterministic_and_emits(self):
        s1 = self.planner.replan(self.plan, self.evidence, completed={"goal-1"})
        s2 = self.planner.replan(self.plan, self.evidence, completed={"goal-1"})
        self.assertEqual(s1.id, s2.id)
        self.assertEqual(s1.tasks, s2.tasks)
        events = self.bus.log("plan.revised")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].payload["provenance"], s1.provenance)

    def test_replan_everything_completed_raises(self):
        with self.assertRaises(PlannerError):
            self.planner.replan(
                self.plan, self.evidence, completed={t.id for t in self.plan.tasks}
            )


class TestEndToEndCoordination(unittest.TestCase):
    """Objective → intent → plan → route → execute: the core loop chain
    (minus memory/verification subsystems, which are later stages)."""

    def test_objective_to_completed_run(self):
        bus = EventBus()
        registry = CapabilityRegistry(bus=bus)
        for name, ctype in [
            ("research.local", "research"),
            ("python.local", "code"),
            ("checks.local", "verify"),
        ]:
            registry.register(
                CapabilityManifest(
                    name=name, capability_type=ctype, version="1.0.0", reliability=0.9
                )
            )
        router = Router(registry, bus=bus)
        runtime = Runtime(bus=bus)
        for ctype in ("research", "code", "verify"):
            runtime.register_handler(ctype, lambda task, ctx: {"done": task.id})
        runtime.start()

        engine = IntentEngine(bus=bus)
        parsed = engine.parse(
            make_objective("Research storage options and then implement the API. Use SQLite")
        )
        plan = Planner(bus=bus).plan(parsed)
        decisions = router.route_plan(plan)
        run = runtime.execute(plan)

        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(len(decisions), len(plan.tasks))
        for task in plan.tasks:
            self.assertIsNotNone(task.capability_binding)
        topics = {e.topic for e in bus.log()}
        self.assertTrue(
            {"intent.parsed", "plan.created", "route.decided", "run.completed"} <= topics
        )


if __name__ == "__main__":
    unittest.main()
