import os
import tempfile
import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.kernel.events import EventBus
from nexus.memory import MemoryError_, MemoryLayer, MemorySystem
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Evidence, Task


def evidence(verified=True, confidence=0.9, eid="ev-1", run_id="run-1"):
    return Evidence(id=eid, run_id=run_id, verified=verified, confidence=confidence)


class MemoryTestCase(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.memory = MemorySystem(bus=self.bus)  # in-memory SQLite

    def tearDown(self):
        self.memory.close()


class TestWorkingMemory(MemoryTestCase):
    def test_write_read_overwrite(self):
        self.memory.write_working("ses-1", "cursor", {"line": 4})
        self.assertEqual(self.memory.read_working("ses-1", "cursor"), {"line": 4})
        self.memory.write_working("ses-1", "cursor", {"line": 9})
        self.assertEqual(self.memory.read_working("ses-1", "cursor"), {"line": 9})

    def test_read_all_and_session_isolation(self):
        self.memory.write_working("ses-1", "a", 1)
        self.memory.write_working("ses-1", "b", 2)
        self.memory.write_working("ses-2", "a", 99)
        self.assertEqual(self.memory.read_working("ses-1"), {"a": 1, "b": 2})
        self.assertEqual(self.memory.read_working("ses-2"), {"a": 99})

    def test_clear_session(self):
        self.memory.write_working("ses-1", "a", 1)
        self.memory.clear_session("ses-1")
        self.assertEqual(self.memory.read_working("ses-1"), {})
        self.assertIsNone(self.memory.read_working("ses-1", "a"))

    def test_secretlike_key_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.write_working("ses-1", "password", "hunter2hunter2")

    def test_secret_pattern_in_value_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.write_working("ses-1", "note", "aws key AKIAABCDEFGHIJKLMNOP")


class TestPromotionGate(MemoryTestCase):
    """Invariants I2/I3: verified evidence + policy, or nothing."""

    def test_promote_with_verified_evidence(self):
        item = self.memory.promote(
            evidence(), MemoryLayer.SEMANTIC, {"fact": "SQLite is the V1 store"},
            policy_id="promo@1.0.0",
        )
        self.assertTrue(item.id.startswith("mem-"))
        self.assertIs(item.layer, MemoryLayer.SEMANTIC)
        self.assertEqual(item.confidence, 0.9)
        events = self.bus.log("memory.promoted")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["item_id"], item.id)

    def test_unverified_evidence_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.promote(
                evidence(verified=False), MemoryLayer.SEMANTIC, {"fact": "x"},
                policy_id="promo@1.0.0",
            )
        self.assertEqual(self.memory.read(MemoryLayer.SEMANTIC), [])

    def test_missing_policy_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.promote(evidence(), MemoryLayer.SEMANTIC, {"fact": "x"}, policy_id="")

    def test_promote_to_working_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.promote(
                evidence(), MemoryLayer.WORKING, {"fact": "x"}, policy_id="promo@1.0.0"
            )

    def test_secret_content_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.promote(
                evidence(), MemoryLayer.SEMANTIC,
                {"note": "use token ghp_" + "a" * 36}, policy_id="promo@1.0.0",
            )

    def test_unserializable_content_rejected(self):
        with self.assertRaises(MemoryError_):
            self.memory.promote(
                evidence(), MemoryLayer.SEMANTIC, {"obj": object()}, policy_id="promo@1.0.0"
            )

    def test_no_ungated_write_path_exists(self):
        for name in ("write", "insert", "add_item", "save_item", "write_layer"):
            self.assertFalse(hasattr(self.memory, name))

    def test_provenance_is_complete(self):
        item = self.memory.promote(
            evidence(eid="ev-42", run_id="run-7"), MemoryLayer.PROCEDURAL,
            {"workflow": "plan→route→execute"}, policy_id="promo@1.0.0",
        )
        prov = self.memory.provenance(item.id)
        self.assertEqual(prov["evidence_id"], "ev-42")
        self.assertEqual(prov["run_id"], "run-7")
        self.assertEqual(prov["policy_id"], "promo@1.0.0")
        self.assertIn("promoted_at", prov)


class TestReadAndSearch(MemoryTestCase):
    def setUp(self):
        super().setUp()
        self.memory.promote(
            evidence(eid="ev-1"), MemoryLayer.SEMANTIC,
            {"fact": "routing uses manifests"}, policy_id="p@1",
        )
        self.memory.promote(
            evidence(eid="ev-2"), MemoryLayer.FAILURE,
            {"lesson": "routing failed on empty registry"}, policy_id="p@1",
        )
        self.memory.promote(
            evidence(eid="ev-3"), MemoryLayer.SEMANTIC,
            {"fact": "plans are immutable"}, policy_id="p@1",
        )

    def test_read_layer_in_insertion_order(self):
        items = self.memory.read(MemoryLayer.SEMANTIC)
        self.assertEqual(
            [i.content["fact"] for i in items],
            ["routing uses manifests", "plans are immutable"],
        )

    def test_read_accepts_string_layer(self):
        self.assertEqual(len(self.memory.read("failure")), 1)

    def test_search_across_layers(self):
        hits = self.memory.search("routing")
        self.assertEqual(len(hits), 2)
        self.assertEqual({i.layer for i in hits}, {MemoryLayer.SEMANTIC, MemoryLayer.FAILURE})

    def test_search_with_layer_filter(self):
        hits = self.memory.search("routing", layer=MemoryLayer.FAILURE)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].content["lesson"], "routing failed on empty registry")


class TestDeprecation(MemoryTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.memory.promote(
            evidence(), MemoryLayer.SEMANTIC, {"fact": "old"}, policy_id="p@1"
        )

    def test_deprecate_excludes_from_read_but_keeps_record(self):
        self.memory.deprecate(self.item.id, reason="superseded")
        self.assertEqual(self.memory.read(MemoryLayer.SEMANTIC), [])
        kept = self.memory.read(MemoryLayer.SEMANTIC, include_deprecated=True)
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].deprecated)
        events = self.bus.log("memory.deprecated")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["reason"], "superseded")

    def test_deprecate_is_idempotent_but_unknown_errors(self):
        self.memory.deprecate(self.item.id, reason="superseded")
        self.memory.deprecate(self.item.id, reason="again")  # no-op
        self.assertEqual(len(self.bus.log("memory.deprecated")), 1)
        with self.assertRaises(MemoryError_):
            self.memory.deprecate("mem-ghost", reason="x")

    def test_search_excludes_deprecated_by_default(self):
        self.memory.deprecate(self.item.id, reason="superseded")
        self.assertEqual(self.memory.search("old"), [])
        self.assertEqual(len(self.memory.search("old", include_deprecated=True)), 1)


class TestPersistence(unittest.TestCase):
    def test_items_survive_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.sqlite")
            memory = MemorySystem(path=path)
            item = memory.promote(
                evidence(), MemoryLayer.PROJECT, {"goal": "ship V1"}, policy_id="p@1"
            )
            memory.write_working("ses-1", "scratch", "kept")
            memory.close()

            reopened = MemorySystem(path=path)
            items = reopened.read(MemoryLayer.PROJECT)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].id, item.id)
            self.assertEqual(items[0].content, {"goal": "ship V1"})
            self.assertEqual(reopened.read_working("ses-1", "scratch"), "kept")
            self.assertEqual(reopened.provenance(item.id)["policy_id"], "p@1")
            reopened.close()


class TestRoutingDecisionPersistence(unittest.TestCase):
    def test_router_sink_persists_decisions(self):
        memory = MemorySystem()
        registry = CapabilityRegistry()
        registry.register(
            CapabilityManifest(name="python.local", capability_type="code", version="1.0.0")
        )
        router = Router(registry, decision_sink=memory.record_routing_decision)
        router.route(Task(id="t1", capability_type="code"))
        router.route(Task(id="t2", capability_type="teleportation"))

        stored = memory.routing_decisions()
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0].task_id, "t1")
        self.assertEqual(stored[0].chosen, "python.local@1.0.0")
        self.assertEqual(len(stored[0].candidates), 1)
        self.assertIsNone(stored[1].chosen)
        memory.close()

    def test_decisions_survive_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.sqlite")
            memory = MemorySystem(path=path)
            registry = CapabilityRegistry()
            registry.register(
                CapabilityManifest(name="python.local", capability_type="code", version="1.0.0")
            )
            Router(registry, decision_sink=memory.record_routing_decision).route(
                Task(id="t1", capability_type="code")
            )
            memory.close()

            reopened = MemorySystem(path=path)
            stored = reopened.routing_decisions()
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].policy_id, "default@1.0.0")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
