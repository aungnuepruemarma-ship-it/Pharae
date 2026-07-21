import unittest

from nexus.cog import RewardShaper
from nexus.schemas.core import Evidence


def evidence(confidence=1.0, attempts=1, retries=0, cost=None):
    report = {"attempts": attempts, "retries": retries}
    if cost is not None:
        report["cost"] = cost
    return Evidence(
        id="ev", run_id="run", verified=True, confidence=confidence, cost_report=report
    )


class TestRewardShaper(unittest.TestCase):
    def setUp(self):
        self.shaper = RewardShaper()

    def test_failure_is_zero(self):
        self.assertEqual(self.shaper.reward(evidence(confidence=0.9), success=False), 0.0)

    def test_clean_high_confidence_success_is_near_one(self):
        self.assertGreater(self.shaper.reward(evidence(confidence=1.0), success=True), 0.95)

    def test_bounded_in_unit_interval(self):
        for conf in (0.0, 0.3, 0.7, 1.0):
            for retries in (0, 1, 5):
                r = self.shaper.reward(
                    evidence(confidence=conf, attempts=retries + 1, retries=retries),
                    success=True,
                )
                self.assertGreaterEqual(r, 0.0)
                self.assertLessEqual(r, 1.0)

    def test_cost_reduces_reward(self):
        clean = self.shaper.reward(evidence(confidence=0.9, attempts=1, retries=0), True)
        retried = self.shaper.reward(evidence(confidence=0.9, attempts=2, retries=1), True)
        self.assertLess(retried, clean)  # same confidence, friction costs trust

    def test_explicit_cost_field_penalizes(self):
        cheap = self.shaper.reward(evidence(confidence=0.9, cost=0.0), True)
        pricey = self.shaper.reward(evidence(confidence=0.9, cost=1.0), True)
        self.assertLess(pricey, cheap)

    def test_higher_confidence_scores_higher(self):
        low = self.shaper.reward(evidence(confidence=0.4), True)
        high = self.shaper.reward(evidence(confidence=0.9), True)
        self.assertLess(low, high)

    def test_deterministic(self):
        e = evidence(confidence=0.7, attempts=3, retries=2)
        self.assertEqual(self.shaper.reward(e, True), self.shaper.reward(e, True))

    def test_cost_free_shaper_reduces_to_confidence(self):
        plain = RewardShaper(confidence_weight=1.0, outcome_weight=0.0, cost_weight=0.0)
        self.assertAlmostEqual(plain.reward(evidence(confidence=0.73), True), 0.73)

    def test_missing_cost_report_is_safe(self):
        bare = Evidence(id="e", run_id="r", verified=True, confidence=0.8)
        r = self.shaper.reward(bare, success=True)
        self.assertGreater(r, 0.0)
        self.assertLessEqual(r, 1.0)


if __name__ == "__main__":
    unittest.main()
