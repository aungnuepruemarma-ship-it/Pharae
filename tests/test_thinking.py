import unittest

from nexus.kernel.events import EventBus
from nexus.planner import Planner
from nexus.schemas.core import Intent
from nexus.thinking import ThinkingBudgeter, ThinkingMode


def intent(goals=(), constraints=(), questions=(), refs=()):
    return Intent(
        id="int-x",
        objective_id="obj-x",
        goals=list(goals),
        constraints=list(constraints),
        open_questions=list(questions),
        context_refs=list(refs),
    )


class TestModeClassification(unittest.TestCase):
    def setUp(self):
        self.b = ThinkingBudgeter()

    def test_single_simple_goal_is_reflex(self):
        budget = self.b.assess(intent(goals=["Rename the variable"]))
        self.assertIs(budget.mode, ThinkingMode.REFLEX)

    def test_refs_force_research(self):
        budget = self.b.assess(intent(goals=["Summarize the file"], refs=["a.md"]))
        self.assertIs(budget.mode, ThinkingMode.RESEARCH)

    def test_research_verb_forces_research(self):
        budget = self.b.assess(intent(goals=["Research solid-state batteries"]))
        self.assertIs(budget.mode, ThinkingMode.RESEARCH)

    def test_many_open_questions_force_research(self):
        budget = self.b.assess(
            intent(goals=["Build it"], questions=["A?", "B?"])
        )
        self.assertIs(budget.mode, ThinkingMode.RESEARCH)

    def test_multi_goal_is_deliberative(self):
        budget = self.b.assess(intent(goals=["Design the API", "Implement it"]))
        self.assertIs(budget.mode, ThinkingMode.DELIBERATIVE)

    def test_constraint_lifts_reflex_to_deliberative(self):
        budget = self.b.assess(
            intent(goals=["Rename the variable"], constraints=["Keep the public API"])
        )
        self.assertIs(budget.mode, ThinkingMode.DELIBERATIVE)


class TestBudgetShape(unittest.TestCase):
    def setUp(self):
        self.b = ThinkingBudgeter()

    def test_effort_is_monotonic_across_modes(self):
        reflex = self.b.assess(intent(goals=["Fix typo"]))
        delib = self.b.assess(intent(goals=["Design", "Build"]))
        research = self.b.assess(intent(goals=["Research options"], refs=["a.md"]))
        self.assertLessEqual(reflex.max_parallelism, delib.max_parallelism)
        self.assertLessEqual(delib.max_parallelism, research.max_parallelism)
        self.assertLessEqual(reflex.stopping_confidence, research.stopping_confidence)
        self.assertLessEqual(reflex.max_retries, research.max_retries)

    def test_reflex_is_minimal(self):
        b = self.b.assess(intent(goals=["Fix typo"]))
        self.assertFalse(b.gather_context)
        self.assertEqual(b.max_parallelism, 1)
        self.assertEqual(b.max_retries, 0)

    def test_research_gathers_context(self):
        b = self.b.assess(intent(goals=["Summarize"], refs=["a.md"]))
        self.assertTrue(b.gather_context)

    def test_budget_is_json_serializable_and_has_rationale(self):
        import json

        b = self.b.assess(intent(goals=["Design", "Build"]))
        json.dumps(b.as_dict())
        self.assertTrue(b.rationale)

    def test_deterministic(self):
        i = intent(goals=["Research X", "Build Y"], refs=["a.md"], constraints=["fast"])
        self.assertEqual(self.b.assess(i).as_dict(), self.b.assess(i).as_dict())


class TestEngineBehavior(unittest.TestCase):
    def test_emits_thinking_assessed(self):
        bus = EventBus()
        b = ThinkingBudgeter(bus=bus)
        budget = b.assess(intent(goals=["Build it"]))
        events = bus.log("thinking.assessed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["mode"], budget.mode.value)
        self.assertEqual(events[0].payload["intent_id"], "int-x")

    def test_works_without_bus(self):
        self.assertIsNotNone(ThinkingBudgeter().assess(intent(goals=["x"])))


class TestPlannerIntegration(unittest.TestCase):
    """The budget's gather_context knob steers the planner without weakening
    the structural verify step (Progressive Complexity, not gate removal)."""

    def setUp(self):
        self.planner = Planner()
        self.budgeter = ThinkingBudgeter()

    def test_default_planner_behavior_unchanged_without_budget(self):
        plan = self.planner.plan(intent(goals=["Build it"], refs=["spec.md"]))
        self.assertEqual(plan.tasks[0].id, "gather-context")  # legacy behavior

    def test_budget_can_suppress_gather_context(self):
        i = intent(goals=["Build it"], refs=["spec.md"])
        # A deliberate budget that opts out of gathering.
        from nexus.thinking import ThinkingBudget

        budget = ThinkingBudget(
            mode=ThinkingMode.DELIBERATIVE,
            max_plan_depth=2,
            gather_context=False,
            max_parallelism=2,
            stopping_confidence=0.75,
            max_retries=1,
            rationale="test",
        )
        plan = self.planner.plan(i, budget=budget)
        self.assertNotIn("gather-context", [t.id for t in plan.tasks])
        self.assertEqual(plan.tasks[-1].id, "verify")  # verify still structural

    def test_research_budget_keeps_gather_when_refs_present(self):
        i = intent(goals=["Summarize the spec"], refs=["spec.md"])
        budget = self.budgeter.assess(i)
        self.assertIs(budget.mode, ThinkingMode.RESEARCH)
        plan = self.planner.plan(i, budget=budget)
        self.assertEqual(plan.tasks[0].id, "gather-context")

    def test_verify_always_present_regardless_of_mode(self):
        for i in (
            intent(goals=["Fix typo"]),
            intent(goals=["Design", "Build"]),
            intent(goals=["Research X"], refs=["a.md"]),
        ):
            budget = self.budgeter.assess(i)
            plan = self.planner.plan(i, budget=budget)
            self.assertEqual(plan.tasks[-1].capability_type, "verify")


if __name__ == "__main__":
    unittest.main()
