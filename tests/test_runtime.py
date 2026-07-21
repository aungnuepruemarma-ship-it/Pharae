import unittest

from nexus.kernel.runtime import Runtime, RuntimeError_
from nexus.schemas.core import Plan, RunStatus, Task, TaskStatus


def make_plan(tasks):
    return Plan(id="plan-1", tasks=tasks)


class TestRuntimeLifecycle(unittest.TestCase):
    def test_start_stop_events_and_idempotence(self):
        rt = Runtime()
        rt.start()
        rt.start()
        rt.stop()
        rt.stop()
        self.assertEqual(len(rt.bus.log("runtime.started")), 1)
        self.assertEqual(len(rt.bus.log("runtime.stopped")), 1)

    def test_stop_ends_active_sessions(self):
        rt = Runtime()
        rt.start()
        session = rt.sessions.create()
        rt.stop()
        self.assertEqual(rt.sessions.active(), [])
        self.assertEqual(
            rt.bus.log("session.ended")[0].payload["session_id"], session.id
        )

    def test_execute_requires_started_runtime(self):
        rt = Runtime()
        with self.assertRaises(RuntimeError_):
            rt.execute(make_plan([Task(id="a", capability_type="echo")]))


class TestRuntimeExecution(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()
        self.rt.start()
        self.calls = []
        self.rt.register_handler("echo", self._echo)

    def _echo(self, task, ctx):
        self.calls.append(task.id)
        return {"echo": task.payload.get("msg")}

    def test_successful_run(self):
        plan = make_plan(
            [
                Task(id="a", capability_type="echo", payload={"msg": "one"}),
                Task(id="b", capability_type="echo", payload={"msg": "two"}, depends_on=["a"]),
            ]
        )
        run = self.rt.execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(self.calls, ["a", "b"])  # dependency order
        self.assertEqual(run.task_results["b"].output, {"echo": "two"})
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(len(self.rt.bus.log("run.completed")), 1)
        self.assertEqual(len(self.rt.bus.log("task.completed")), 2)

    def test_handler_exception_fails_task_and_blocks_dependents(self):
        def boom(task, ctx):
            raise ValueError("kaput")

        self.rt.register_handler("boom", boom)
        plan = make_plan(
            [
                Task(id="a", capability_type="boom"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
                Task(id="c", capability_type="echo"),
            ]
        )
        run = self.rt.execute(plan)
        self.assertIs(run.status, RunStatus.PARTIAL)  # c completed, a failed, b blocked
        self.assertIs(run.task_results["a"].status, TaskStatus.FAILED)
        self.assertIn("kaput", run.task_results["a"].error)
        self.assertIs(run.task_results["b"].status, TaskStatus.BLOCKED)
        self.assertIs(run.task_results["c"].status, TaskStatus.COMPLETED)
        self.assertEqual(len(self.rt.bus.log("run.failed")), 1)

    def test_missing_handler_fails_task(self):
        plan = make_plan([Task(id="a", capability_type="unregistered")])
        run = self.rt.execute(plan)
        self.assertIs(run.status, RunStatus.FAILED)
        self.assertIn("no handler", run.task_results["a"].error)

    def test_handlers_share_session_working_memory(self):
        def writer(task, ctx):
            ctx.set("shared", "from-writer")

        def reader(task, ctx):
            return ctx.get("shared")

        self.rt.register_handler("writer", writer)
        self.rt.register_handler("reader", reader)
        plan = make_plan(
            [
                Task(id="w", capability_type="writer"),
                Task(id="r", capability_type="reader", depends_on=["w"]),
            ]
        )
        run = self.rt.execute(plan)
        self.assertEqual(run.task_results["r"].output, "from-writer")

    def test_runs_in_distinct_sessions_are_isolated(self):
        def reader(task, ctx):
            return ctx.get("shared", "empty")

        def writer(task, ctx):
            ctx.set("shared", "polluted")

        self.rt.register_handler("writer", writer)
        self.rt.register_handler("reader", reader)
        self.rt.execute(make_plan([Task(id="w", capability_type="writer")]))
        run2 = self.rt.execute(make_plan([Task(id="r", capability_type="reader")]))
        self.assertEqual(run2.task_results["r"].output, "empty")

    def test_run_ids_are_unique_and_sessions_created_on_demand(self):
        r1 = self.rt.execute(make_plan([Task(id="a", capability_type="echo")]))
        r2 = self.rt.execute(make_plan([Task(id="a", capability_type="echo")]))
        self.assertNotEqual(r1.id, r2.id)
        self.assertNotEqual(r1.session_id, r2.session_id)

    def test_event_trace_covers_every_transition(self):
        plan = make_plan(
            [
                Task(id="a", capability_type="echo"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
            ]
        )
        self.rt.execute(plan)
        topics = [e.topic for e in self.rt.bus.log()]
        for expected in ("run.started", "task.started", "task.completed", "run.completed"):
            self.assertIn(expected, topics)
        # started before completed, per task
        self.assertLess(topics.index("task.started"), topics.index("task.completed"))


if __name__ == "__main__":
    unittest.main()
