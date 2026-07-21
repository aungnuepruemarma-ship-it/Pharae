import unittest

from nexus.kernel.events import EventBus


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_exact_topic_delivery(self):
        seen = []
        self.bus.subscribe("task.completed", lambda e: seen.append(e))
        self.bus.publish("task.completed", {"task_id": "t1"})
        self.bus.publish("task.failed", {"task_id": "t2"})
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].payload["task_id"], "t1")

    def test_prefix_wildcard(self):
        seen = []
        self.bus.subscribe("task.*", lambda e: seen.append(e.topic))
        self.bus.publish("task.started")
        self.bus.publish("task.completed")
        self.bus.publish("session.started")
        self.assertEqual(seen, ["task.started", "task.completed"])

    def test_global_wildcard(self):
        seen = []
        self.bus.subscribe("*", lambda e: seen.append(e.topic))
        self.bus.publish("a.b")
        self.bus.publish("c.d")
        self.assertEqual(seen, ["a.b", "c.d"])

    def test_wildcard_does_not_match_bare_prefix(self):
        seen = []
        self.bus.subscribe("task.*", lambda e: seen.append(e.topic))
        self.bus.publish("task")
        self.assertEqual(seen, [])

    def test_event_log_is_ordered_and_monotonic(self):
        self.bus.publish("a.one")
        self.bus.publish("a.two")
        self.bus.publish("b.one")
        log = self.bus.log()
        self.assertEqual([e.topic for e in log], ["a.one", "a.two", "b.one"])
        self.assertEqual([e.seq for e in log], [0, 1, 2])
        self.assertEqual([e.topic for e in self.bus.log("a.*")], ["a.one", "a.two"])

    def test_delivery_in_subscription_order(self):
        seen = []
        self.bus.subscribe("x.y", lambda e: seen.append("first"))
        self.bus.subscribe("x.*", lambda e: seen.append("second"))
        self.bus.publish("x.y")
        self.assertEqual(seen, ["first", "second"])

    def test_subscriber_error_is_isolated_and_reported(self):
        errors = []
        seen = []

        def bad(_event):
            raise ValueError("boom")

        self.bus.subscribe("bus.error", lambda e: errors.append(e.payload))
        self.bus.subscribe("t.go", bad)
        self.bus.subscribe("t.go", lambda e: seen.append(e.topic))
        self.bus.publish("t.go")  # must not raise
        self.assertEqual(seen, ["t.go"])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["topic"], "t.go")
        self.assertIn("boom", errors[0]["error"])

    def test_error_in_bus_error_handler_does_not_loop(self):
        def bad(_event):
            raise ValueError("boom")

        self.bus.subscribe("bus.error", bad)
        self.bus.subscribe("t.go", bad)
        self.bus.publish("t.go")  # must not raise or recurse
        self.assertEqual(len(self.bus.log("bus.error")), 1)

    def test_unsubscribe(self):
        seen = []
        unsub = self.bus.subscribe("t.go", lambda e: seen.append(1))
        self.bus.publish("t.go")
        unsub()
        self.bus.publish("t.go")
        self.assertEqual(seen, [1])

    def test_payload_is_copied(self):
        payload = {"k": "v"}
        event = self.bus.publish("t.go", payload)
        payload["k"] = "mutated"
        self.assertEqual(event.payload["k"], "v")


if __name__ == "__main__":
    unittest.main()
