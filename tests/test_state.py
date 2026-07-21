import unittest

from nexus.kernel.state import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.state = StateManager()

    def test_get_set_delete(self):
        self.state.set("ns", "k", 42)
        self.assertEqual(self.state.get("ns", "k"), 42)
        self.assertTrue(self.state.delete("ns", "k"))
        self.assertFalse(self.state.delete("ns", "k"))
        self.assertIsNone(self.state.get("ns", "k"))
        self.assertEqual(self.state.get("ns", "k", "fallback"), "fallback")

    def test_namespaces_are_isolated(self):
        self.state.set("a", "k", 1)
        self.state.set("b", "k", 2)
        self.assertEqual(self.state.get("a", "k"), 1)
        self.assertEqual(self.state.get("b", "k"), 2)
        self.state.clear_namespace("a")
        self.assertIsNone(self.state.get("a", "k"))
        self.assertEqual(self.state.get("b", "k"), 2)

    def test_snapshot_is_a_deep_copy(self):
        self.state.set("ns", "items", [1, 2])
        snap = self.state.snapshot("ns")
        self.state.get("ns", "items").append(3)  # mutate live state
        self.assertEqual(snap["items"], [1, 2])

    def test_restore_namespace_round_trip(self):
        self.state.set("ns", "k", "checkpoint")
        snap = self.state.snapshot("ns")
        self.state.set("ns", "k", "diverged")
        self.state.set("ns", "extra", True)
        self.state.restore(snap, "ns")
        self.assertEqual(self.state.get("ns", "k"), "checkpoint")
        self.assertIsNone(self.state.get("ns", "extra"))

    def test_restore_does_not_alias_snapshot(self):
        snap = {"k": [1]}
        self.state.restore(snap, "ns")
        self.state.get("ns", "k").append(2)
        self.assertEqual(snap["k"], [1])

    def test_full_store_snapshot_restore(self):
        self.state.set("a", "k", 1)
        snap = self.state.snapshot()
        self.state.set("b", "k", 2)
        self.state.restore(snap)
        self.assertEqual(self.state.namespaces(), ["a"])


if __name__ == "__main__":
    unittest.main()
