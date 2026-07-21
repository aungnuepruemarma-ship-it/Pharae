import unittest

from nexus.kernel.events import EventBus
from nexus.memory import MemoryLayer, MemorySystem
from nexus.schemas.core import Evidence
from nexus.science import (
    OrganizationLibrary,
    RepresentationArena,
    ScienceError,
    TheoryLedger,
    TheoryStatus,
)


def ev(verified=True, confidence=0.9, eid="ev-1"):
    return Evidence(id=eid, run_id="run", verified=verified, confidence=confidence)


class TestTheoryLedger(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.memory = MemorySystem(bus=self.bus)
        self.addCleanup(self.memory.close)
        self.ledger = TheoryLedger(self.memory, bus=self.bus, replication_threshold=2)

    def test_propose_is_pending(self):
        t = self.ledger.propose("Retry improves flaky-tool success")
        self.assertIs(t.status, TheoryStatus.PENDING)
        self.assertTrue(t.id.startswith("thy-"))
        self.assertEqual(len(self.bus.log("theory.proposed")), 1)

    def test_unverified_evidence_rejected(self):
        t = self.ledger.propose("X causes Y")
        with self.assertRaises(ScienceError):
            self.ledger.observe(t.id, ev(verified=False), supports=True)

    def test_replications_activate_theory(self):
        t = self.ledger.propose("Caching cuts latency")
        self.ledger.observe(t.id, ev(eid="e1"), supports=True)
        self.assertIs(self.ledger.get(t.id).status, TheoryStatus.PENDING)
        self.ledger.observe(t.id, ev(eid="e2"), supports=True)
        active = self.ledger.get(t.id)
        self.assertIs(active.status, TheoryStatus.ACTIVE)
        self.assertEqual(active.replications, 2)
        self.assertGreater(active.confidence, 0.5)

    def test_refutation_rejects_theory(self):
        t = self.ledger.propose("Bad hypothesis")
        self.ledger.observe(t.id, ev(eid="e1"), supports=False)
        self.ledger.observe(t.id, ev(eid="e2"), supports=False)
        self.assertIs(self.ledger.get(t.id).status, TheoryStatus.REJECTED)
        self.assertEqual(len(self.bus.log("theory.rejected")), 1)

    def test_promote_requires_active_and_gates_to_memory(self):
        t = self.ledger.propose("Verified pattern")
        with self.assertRaises(ScienceError):  # not yet active
            self.ledger.promote(t.id, policy_id="sci@1")
        self.ledger.observe(t.id, ev(eid="e1"), supports=True)
        self.ledger.observe(t.id, ev(eid="e2", confidence=0.95), supports=True)
        item = self.ledger.promote(t.id, policy_id="sci@1")
        self.assertIs(self.ledger.get(t.id).status, TheoryStatus.PROMOTED)
        # landed in semantic memory through the gate, with provenance
        semantic = self.memory.read(MemoryLayer.SEMANTIC)
        self.assertEqual(len(semantic), 1)
        self.assertEqual(semantic[0].id, item.id)
        self.assertEqual(semantic[0].content["theory"], "Verified pattern")
        self.assertEqual(self.memory.provenance(item.id)["policy_id"], "sci@1")

    def test_deterministic_ids(self):
        a = self.ledger.propose("same statement")
        b = TheoryLedger(self.memory).propose("same statement")
        self.assertEqual(a.id, b.id)


class TestRepresentationArena(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.arena = RepresentationArena(bus=self.bus, min_trials=3)

    def test_unverified_rejected(self):
        self.arena.register("chain-of-thought")
        with self.assertRaises(ScienceError):
            self.arena.record("chain-of-thought", ev(verified=False), success=True)

    def test_best_by_verified_win_rate(self):
        for name in ("cot", "graph"):
            self.arena.register(name)
        # cot: 3/3, graph: 1/3
        for i in range(3):
            self.arena.record("cot", ev(eid=f"c{i}"), success=True)
        self.arena.record("graph", ev(eid="g0"), success=True)
        self.arena.record("graph", ev(eid="g1"), success=False)
        self.arena.record("graph", ev(eid="g2"), success=False)
        self.assertEqual(self.arena.best().name, "cot")
        self.assertEqual(len(self.bus.log("representation.recorded")), 6)

    def test_below_min_trials_does_not_qualify(self):
        self.arena.register("untested")
        self.arena.record("untested", ev(), success=True)
        self.assertIsNone(self.arena.best())

    def test_only_evidence_survives_competition(self):
        # A representation that looks good but has too few trials loses to a
        # proven one — only evidence counts.
        self.arena.register("proven")
        self.arena.register("lucky")
        for i in range(4):
            self.arena.record("proven", ev(eid=f"p{i}"), success=(i < 3))  # 3/4
        self.arena.record("lucky", ev(eid="l0"), success=True)  # 1/1 but < min
        self.assertEqual(self.arena.best().name, "proven")


class TestOrganizationLibrary(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.lib = OrganizationLibrary(bus=self.bus, min_trials=2)

    def test_define_composition_not_agents(self):
        org = self.lib.define("research-then-build", ["research", "code", "verify"])
        self.assertEqual(org.capability_types, ["research", "code", "verify"])
        self.assertEqual(org.signature, "research→code→verify")
        self.assertEqual(len(self.bus.log("organization.defined")), 1)

    def test_best_for_signature_by_success(self):
        self.lib.define("careful", ["code", "verify"])
        self.lib.define("hasty", ["code", "verify"])
        for i in range(2):
            self.lib.record("careful", ev(eid=f"c{i}"), success=True)
        self.lib.record("hasty", ev(eid="h0"), success=True)
        self.lib.record("hasty", ev(eid="h1"), success=False)
        best = self.lib.best_for(["code", "verify"])
        self.assertEqual(best.name, "careful")

    def test_best_for_unknown_signature_is_none(self):
        self.lib.define("x", ["code"])
        self.assertIsNone(self.lib.best_for(["research"]))

    def test_unverified_rejected(self):
        self.lib.define("x", ["code"])
        with self.assertRaises(ScienceError):
            self.lib.record("x", ev(verified=False), success=True)


if __name__ == "__main__":
    unittest.main()
