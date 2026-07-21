import unittest

from nexus.economics import Economist
from nexus.kernel.events import EventBus
from nexus.models import model_manifest
from nexus.thinking import ThinkingBudget, ThinkingMode


def budget(mode):
    return ThinkingBudget(
        mode=mode, max_plan_depth=1, gather_context=False, max_parallelism=1,
        stopping_confidence=0.6, max_retries=0, rationale="t",
    )


def candidates():
    return [
        model_manifest("model.small", tier="small", cost=0.1, latency_ms=40, trust=0.5, reliability=0.6),
        model_manifest("model.mid", tier="mid", cost=1.0, latency_ms=200, trust=0.7, reliability=0.75),
        model_manifest("model.frontier", tier="frontier", cost=8.0, latency_ms=1500, trust=0.9, reliability=0.9),
    ]


class TestEconomist(unittest.TestCase):
    def setUp(self):
        self.econ = Economist()

    def test_reflex_picks_cheapest(self):
        choice = self.econ.choose(budget(ThinkingMode.REFLEX), candidates())
        self.assertEqual(choice.name, "model.small")

    def test_research_picks_most_capable(self):
        choice = self.econ.choose(budget(ThinkingMode.RESEARCH), candidates())
        self.assertEqual(choice.name, "model.frontier")

    def test_deliberative_balances(self):
        choice = self.econ.choose(budget(ThinkingMode.DELIBERATIVE), candidates())
        self.assertEqual(choice.name, "model.mid")

    def test_deterministic(self):
        b, c = budget(ThinkingMode.DELIBERATIVE), candidates()
        self.assertEqual(self.econ.choose(b, c).name, self.econ.choose(b, c).name)

    def test_no_candidates_raises(self):
        from nexus.economics import EconomicsError

        with self.assertRaises(EconomicsError):
            self.econ.choose(budget(ThinkingMode.REFLEX), [])

    def test_single_candidate_always_chosen(self):
        only = [model_manifest("model.only", tier="mid", cost=5.0, latency_ms=900)]
        for mode in ThinkingMode:
            self.assertEqual(self.econ.choose(budget(mode), only).name, "model.only")

    def test_emits_event(self):
        bus = EventBus()
        econ = Economist(bus=bus)
        choice = econ.choose(budget(ThinkingMode.RESEARCH), candidates())
        events = bus.log("economics.chosen")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["capability"], choice.name)
        self.assertEqual(events[0].payload["mode"], "research")


if __name__ == "__main__":
    unittest.main()
