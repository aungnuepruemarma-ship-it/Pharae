import unittest

from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Plan, Task


def manifest(**overrides):
    base = dict(
        name="browser.playwright",
        capability_type="browser",
        version="1.0.0",
        permissions=["net.fetch", "fs.write"],
    )
    base.update(overrides)
    return CapabilityManifest(**base)


class TestCapabilityManifest(unittest.TestCase):
    def test_valid_manifest(self):
        self.assertEqual(manifest().validate(), [])

    def test_rejects_empty_identity(self):
        errors = manifest(name="  ", capability_type="").validate()
        self.assertEqual(len(errors), 2)

    def test_rejects_bad_version(self):
        self.assertTrue(manifest(version="1.0").validate())
        self.assertTrue(manifest(version="v1.0.0").validate())
        self.assertEqual(manifest(version="1.0.0-beta.1").validate(), [])

    def test_rejects_out_of_range_scores(self):
        errors = manifest(reliability=1.5, trust_score=-0.1).validate()
        self.assertEqual(len(errors), 2)

    def test_rejects_negative_cost_and_latency(self):
        errors = manifest(cost=-1, latency_ms=-5).validate()
        self.assertEqual(len(errors), 2)

    def test_rejects_malformed_permissions(self):
        errors = manifest(permissions=["net.fetch", "EVERYTHING", "fs"]).validate()
        self.assertEqual(len(errors), 2)


class TestPlan(unittest.TestCase):
    def test_task_ids(self):
        plan = Plan(
            id="p1",
            tasks=[Task(id="a", capability_type="x"), Task(id="b", capability_type="y")],
        )
        self.assertEqual(plan.task_ids(), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
