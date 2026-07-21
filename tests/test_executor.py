import threading
import time
import unittest

from nexus.executor import Executor, ExecutorError, RetryPolicy
from nexus.kernel.runtime import Runtime
from nexus.schemas.core import Plan, RunStatus, Task, TaskStatus


def make_plan(tasks, pid="plan-x"):
    return Plan(id=pid, tasks=tasks)


def wait_until(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


class ExecutorTestCase(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime()
        self.rt.start()
        self.rt.register_handler("echo", lambda task, ctx: {"echo": task.id})


class TestSyncExecution(ExecutorTestCase):
    def test_dag_completes_in_dependency_order(self):
        order = []
        self.rt.register_handler("track", lambda task, ctx: order.append(task.id))
        executor = Executor(self.rt)
        plan = make_plan(
            [
                Task(id="a", capability_type="track"),
                Task(id="b", capability_type="track", depends_on=["a"]),
                Task(id="c", capability_type="track", depends_on=["b"]),
            ]
        )
        run = executor.execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(order, ["a", "b", "c"])

    def test_independent_tasks_run_in_parallel(self):
        barrier = threading.Barrier(2, timeout=5)
        self.rt.register_handler("meet", lambda task, ctx: barrier.wait())
        executor = Executor(self.rt, max_workers=2)
        plan = make_plan(
            [Task(id="a", capability_type="meet"), Task(id="b", capability_type="meet")]
        )
        run = executor.execute(plan)  # deadlocks into failure unless truly parallel
        self.assertIs(run.status, RunStatus.COMPLETED)

    def test_failure_blocks_dependents(self):
        def boom(task, ctx):
            raise ValueError("kaput")

        self.rt.register_handler("boom", boom)
        executor = Executor(self.rt)
        plan = make_plan(
            [
                Task(id="a", capability_type="boom"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
            ]
        )
        run = executor.execute(plan)
        self.assertIs(run.status, RunStatus.FAILED)
        self.assertIs(run.task_results["a"].status, TaskStatus.FAILED)
        self.assertIn("kaput", run.task_results["a"].error)
        self.assertIs(run.task_results["b"].status, TaskStatus.BLOCKED)

    def test_missing_handler_fails_without_retry(self):
        executor = Executor(self.rt, retry=RetryPolicy(max_attempts=3))
        plan = make_plan([Task(id="a", capability_type="unregistered")])
        run = executor.execute(plan)
        self.assertIs(run.status, RunStatus.FAILED)
        self.assertEqual(run.task_results["a"].attempts, 1)
        self.assertEqual(self.rt.bus.log("task.retried"), [])

    def test_plan_object_is_not_mutated(self):
        executor = Executor(self.rt)
        plan = make_plan([Task(id="a", capability_type="echo")])
        executor.execute(plan)
        self.assertIs(plan.tasks[0].status, TaskStatus.PENDING)

    def test_requires_started_runtime(self):
        self.rt.stop()
        with self.assertRaises(ExecutorError):
            Executor(self.rt).execute(make_plan([Task(id="a", capability_type="echo")]))


class TestRetries(ExecutorTestCase):
    def test_flaky_task_retries_to_success(self):
        calls = {"n": 0}

        def flaky(task, ctx):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("transient")
            return "ok"

        self.rt.register_handler("flaky", flaky)
        executor = Executor(self.rt, retry=RetryPolicy(max_attempts=3))
        run = executor.execute(make_plan([Task(id="a", capability_type="flaky")]))
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(run.task_results["a"].attempts, 3)
        self.assertEqual(run.task_results["a"].output, "ok")
        retried = self.rt.bus.log("task.retried")
        self.assertEqual([e.payload["attempt"] for e in retried], [2, 3])

    def test_retry_exhaustion_fails_and_blocks(self):
        def always(task, ctx):
            raise ValueError("permanent")

        self.rt.register_handler("always", always)
        executor = Executor(self.rt, retry=RetryPolicy(max_attempts=2))
        plan = make_plan(
            [
                Task(id="a", capability_type="always"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
            ]
        )
        run = executor.execute(plan)
        self.assertIs(run.status, RunStatus.FAILED)
        self.assertEqual(run.task_results["a"].attempts, 2)
        self.assertIs(run.task_results["b"].status, TaskStatus.BLOCKED)
        self.assertEqual(len(self.rt.bus.log("task.retried")), 1)

    def test_default_policy_is_single_attempt(self):
        def boom(task, ctx):
            raise ValueError("no")

        self.rt.register_handler("boom", boom)
        run = Executor(self.rt).execute(make_plan([Task(id="a", capability_type="boom")]))
        self.assertEqual(run.task_results["a"].attempts, 1)
        self.assertEqual(self.rt.bus.log("task.retried"), [])


class TestCheckpointResume(ExecutorTestCase):
    def setUp(self):
        super().setUp()
        self.counts = {"first": 0}
        self.broken = {"value": True}

        def first(task, ctx):
            self.counts["first"] += 1
            ctx.set("carried", "from-first-run")
            return "first-output"

        def second(task, ctx):
            if self.broken["value"]:
                raise ValueError("still broken")
            return {"carried": ctx.get("carried")}

        self.rt.register_handler("first", first)
        self.rt.register_handler("second", second)
        self.executor = Executor(self.rt)
        self.plan = make_plan(
            [
                Task(id="t1", capability_type="first"),
                Task(id="t2", capability_type="second", depends_on=["t1"]),
            ],
            pid="plan-ckpt",
        )

    def test_resume_skips_completed_and_restores_state(self):
        run1 = self.executor.execute(self.plan)
        self.assertIs(run1.status, RunStatus.PARTIAL)  # t1 completed, t2 failed
        self.assertEqual(self.counts["first"], 1)

        self.broken["value"] = False
        run2 = self.executor.resume(self.plan)
        self.assertIs(run2.status, RunStatus.COMPLETED)
        self.assertEqual(self.counts["first"], 1)  # not re-executed
        self.assertEqual(run2.task_results["t1"].output, "first-output")  # from checkpoint
        self.assertEqual(
            run2.task_results["t2"].output, {"carried": "from-first-run"}
        )  # session state survived via snapshot
        resumed = self.rt.bus.log("run.resumed")
        self.assertEqual(len(resumed), 1)
        self.assertEqual(resumed[0].payload["restored"], ["t1"])

    def test_checkpoint_events_emitted(self):
        self.executor.execute(self.plan)
        self.assertGreaterEqual(len(self.rt.bus.log("run.checkpointed")), 1)

    def test_resume_without_checkpoint_raises(self):
        with self.assertRaises(ExecutorError):
            self.executor.resume(make_plan([Task(id="x", capability_type="echo")], pid="fresh"))

    def test_checkpointing_can_be_disabled(self):
        executor = Executor(self.rt, checkpoints=False)
        executor.execute(self.plan)
        self.assertEqual(self.rt.bus.log("run.checkpointed"), [])
        with self.assertRaises(ExecutorError):
            executor.resume(self.plan)


class TestBackgroundJobs(ExecutorTestCase):
    def test_submit_and_wait(self):
        executor = Executor(self.rt)
        job = executor.submit(make_plan([Task(id="a", capability_type="echo")]))
        run = job.wait(timeout=5)
        self.assertIsNotNone(run)
        self.assertIs(run.status, RunStatus.COMPLETED)

    def test_cancel_mid_run_finishes_inflight_and_cancels_rest(self):
        gate = threading.Event()

        def slow(task, ctx):
            gate.wait(timeout=5)
            return "slow-done"

        self.rt.register_handler("slow", slow)
        executor = Executor(self.rt)
        plan = make_plan(
            [
                Task(id="a", capability_type="slow"),
                Task(id="b", capability_type="echo", depends_on=["a"]),
            ]
        )
        job = executor.submit(plan)
        self.assertTrue(wait_until(lambda: len(self.rt.bus.log("task.started")) == 1))
        job.cancel()
        gate.set()
        run = job.wait(timeout=5)
        self.assertIs(run.status, RunStatus.CANCELLED)
        self.assertIs(run.task_results["a"].status, TaskStatus.COMPLETED)  # cooperative
        self.assertIs(run.task_results["b"].status, TaskStatus.CANCELLED)  # boundary
        self.assertEqual(len(self.rt.bus.log("run.cancelled")), 1)

    def test_start_paused_then_unpause(self):
        executor = Executor(self.rt)
        job = executor.submit(make_plan([Task(id="a", capability_type="echo")]), paused=True)
        time.sleep(0.15)  # dispatcher is alive but must not have started anything
        self.assertEqual(self.rt.bus.log("task.started"), [])
        self.assertTrue(job.paused)
        job.unpause()
        run = job.wait(timeout=5)
        self.assertIs(run.status, RunStatus.COMPLETED)

    def test_cancel_while_paused(self):
        executor = Executor(self.rt)
        job = executor.submit(make_plan([Task(id="a", capability_type="echo")]), paused=True)
        job.cancel()
        run = job.wait(timeout=5)
        self.assertIs(run.status, RunStatus.CANCELLED)
        self.assertIs(run.task_results["a"].status, TaskStatus.CANCELLED)
        self.assertEqual(self.rt.bus.log("task.started"), [])


class TestThreadSafety(ExecutorTestCase):
    def test_parallel_events_have_unique_ordered_seq(self):
        executor = Executor(self.rt, max_workers=8)
        plan = make_plan([Task(id=f"t{i}", capability_type="echo") for i in range(8)])
        run = executor.execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        self.assertEqual(len(self.rt.bus.log("task.completed")), 8)
        seqs = [e.seq for e in self.rt.bus.log()]
        self.assertEqual(len(seqs), len(set(seqs)))


if __name__ == "__main__":
    unittest.main()
