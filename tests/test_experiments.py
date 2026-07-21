import unittest

from nexus.experiments import (
    ExperimentManager,
    bootstrap_ci,
    cohens_d,
    holm_correction,
    mean,
)
from nexus.kernel.events import EventBus


class TestStats(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([1, 2, 3, 4]), 2.5)
        self.assertEqual(mean([]), 0.0)

    def test_bootstrap_ci_is_deterministic_with_seed(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        a = bootstrap_ci(data, seed=7)
        b = bootstrap_ci(data, seed=7)
        self.assertEqual(a, b)
        lo, hi = a
        self.assertLess(lo, hi)
        self.assertLessEqual(lo, mean(data))
        self.assertLessEqual(mean(data), hi)

    def test_cohens_d_sign_and_zero(self):
        self.assertGreater(cohens_d([5, 6, 7], [1, 2, 3]), 0)
        self.assertLess(cohens_d([1, 2, 3], [5, 6, 7]), 0)
        self.assertEqual(cohens_d([1, 1, 1], [1, 1, 1]), 0.0)

    def test_holm_correction_orders_and_flags(self):
        # smallest p first; Holm rejects in order until one fails.
        results = holm_correction({"a": 0.001, "b": 0.02, "c": 0.9}, alpha=0.05)
        self.assertTrue(results["a"])
        self.assertFalse(results["c"])
        # b threshold = 0.05/2 = 0.025 → 0.02 rejected
        self.assertTrue(results["b"])

    def test_holm_stops_at_first_non_reject(self):
        results = holm_correction({"a": 0.04, "b": 0.001}, alpha=0.05)
        # sorted: b(0.001) thresh 0.025 reject; a(0.04) thresh 0.05 → 0.04<0.05 reject
        self.assertTrue(results["b"])
        self.assertTrue(results["a"])
        results2 = holm_correction({"a": 0.03, "b": 0.001}, alpha=0.05)
        # b reject (thresh .025); a thresh .05 → .03 reject
        self.assertTrue(results2["a"])


class TestExperimentManager(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.mgr = ExperimentManager(bus=self.bus, seed=1)

    def test_clear_improvement_is_significant(self):
        result = self.mgr.compare(
            "baseline", "treatment",
            baseline=[0.4, 0.45, 0.5, 0.42, 0.48],
            treatment=[0.8, 0.85, 0.9, 0.82, 0.88],
        )
        self.assertTrue(result.improved)
        self.assertGreater(result.effect_size, 0.8)
        self.assertGreater(result.treatment_mean, result.baseline_mean)
        self.assertGreater(result.delta, 0)

    def test_noise_is_not_significant(self):
        result = self.mgr.compare(
            "baseline", "treatment",
            baseline=[0.5, 0.51, 0.49, 0.5, 0.5],
            treatment=[0.5, 0.49, 0.51, 0.5, 0.5],
        )
        self.assertFalse(result.improved)

    def test_regression_is_not_improvement(self):
        result = self.mgr.compare(
            "baseline", "treatment",
            baseline=[0.9, 0.9, 0.9, 0.9],
            treatment=[0.4, 0.4, 0.4, 0.4],
        )
        self.assertFalse(result.improved)
        self.assertLess(result.delta, 0)

    def test_insufficient_samples_is_inconclusive(self):
        result = self.mgr.compare("b", "t", baseline=[0.5], treatment=[0.9])
        self.assertFalse(result.improved)
        self.assertIn("insufficient", result.rationale)

    def test_deterministic(self):
        args = dict(baseline=[0.4, 0.5, 0.45, 0.42], treatment=[0.7, 0.75, 0.72, 0.71])
        r1 = self.mgr.compare("b", "t", **args)
        r2 = self.mgr.compare("b", "t", **args)
        self.assertEqual(r1.as_dict(), r2.as_dict())

    def test_emits_event_and_serializes(self):
        import json

        result = self.mgr.compare(
            "b", "t", baseline=[0.4, 0.45, 0.5, 0.42], treatment=[0.8, 0.85, 0.9, 0.82]
        )
        json.dumps(result.as_dict())
        events = self.bus.log("experiment.completed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["improved"], result.improved)


class TestPolicyGate(unittest.TestCase):
    """L8 supplies the statistical justification L24 governance asks for:
    a policy activates only if an experiment shows improvement."""

    def setUp(self):
        self.bus = EventBus()

    def test_activate_if_improved_promotes_only_on_evidence(self):
        from nexus.cog import PolicyEngine

        mgr = ExperimentManager(bus=self.bus, seed=3)
        engine = PolicyEngine(bus=self.bus)
        v1 = engine.propose("routing", {"denied": []}, reason="baseline")
        engine.activate("routing", v1.version)
        v2 = engine.propose("routing", {"denied": ["bad"]}, reason="candidate")

        improved = mgr.compare(
            "v1", "v2",
            baseline=[0.4, 0.42, 0.45, 0.43],
            treatment=[0.8, 0.82, 0.85, 0.83],
        )
        self.assertTrue(engine.activate_if_improved("routing", v2.version, improved))
        self.assertEqual(engine.active("routing").version, 2)

    def test_activate_if_improved_rejects_flat_trial(self):
        from nexus.cog import PolicyEngine

        mgr = ExperimentManager(bus=self.bus, seed=3)
        engine = PolicyEngine(bus=self.bus)
        w1 = engine.propose("routing", {}, reason="baseline")
        engine.activate("routing", w1.version)
        w2 = engine.propose("routing", {"denied": ["x"]}, reason="candidate")
        flat = mgr.compare(
            "w1", "w2", baseline=[0.5, 0.5, 0.5, 0.5], treatment=[0.5, 0.5, 0.5, 0.5]
        )
        self.assertFalse(engine.activate_if_improved("routing", w2.version, flat))
        self.assertEqual(engine.active("routing").version, 1)  # unchanged
        self.assertEqual(len(self.bus.log("policy.trial_rejected")), 1)


if __name__ == "__main__":
    unittest.main()
