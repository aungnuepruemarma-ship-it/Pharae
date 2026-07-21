import unittest

from nexus.kernel.events import EventBus
from nexus.kernel.sessions import SessionManager, SessionStatus
from nexus.kernel.state import StateManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.state = StateManager()
        self.sessions = SessionManager(self.bus, self.state)

    def test_create_emits_event_and_is_active(self):
        session = self.sessions.create({"user": "u1"})
        self.assertIs(session.status, SessionStatus.ACTIVE)
        self.assertEqual(session.metadata, {"user": "u1"})
        self.assertEqual(self.sessions.get(session.id), session)
        self.assertIn(session, self.sessions.active())
        events = self.bus.log("session.started")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["session_id"], session.id)

    def test_ids_are_unique(self):
        ids = {self.sessions.create().id for _ in range(5)}
        self.assertEqual(len(ids), 5)

    def test_end_clears_namespace_and_emits(self):
        session = self.sessions.create()
        self.state.set(session.namespace, "scratch", "data")
        self.sessions.end(session.id)
        self.assertIs(session.status, SessionStatus.ENDED)
        self.assertIsNotNone(session.ended_at)
        self.assertIsNone(self.state.get(session.namespace, "scratch"))
        self.assertNotIn(session, self.sessions.active())
        self.assertEqual(len(self.bus.log("session.ended")), 1)

    def test_end_is_idempotent(self):
        session = self.sessions.create()
        self.sessions.end(session.id)
        self.sessions.end(session.id)
        self.sessions.end("ses-does-not-exist")  # no error
        self.assertEqual(len(self.bus.log("session.ended")), 1)

    def test_sessions_do_not_share_state(self):
        s1 = self.sessions.create()
        s2 = self.sessions.create()
        self.state.set(s1.namespace, "k", "one")
        self.assertIsNone(self.state.get(s2.namespace, "k"))


if __name__ == "__main__":
    unittest.main()
