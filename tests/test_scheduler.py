import unittest

from nexus.kernel.scheduler import Scheduler, SchedulerError
from nexus.schemas.core import Task, TaskStatus


def t(tid, deps=(), priority=0):
    return Task(id=tid, capability_type="test", depends_on=list(deps), priority=priority)


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.sched = Scheduler()

    def test_ready_respects_dependencies(self):
        self.sched.submit([t("a"), t("b", deps=["a"]), t("c", deps=["a", "b"])])
        self.assertEqual([x.id for x in self.sched.ready()], ["a"])
        self.sched.start("a")
        self.sched.complete("a")
        self.assertEqual([x.id for x in self.sched.ready()], ["b"])
        self.sched.start("b")
        self.sched.complete("b")
        self.assertEqual([x.id for x in self.sched.ready()], ["c"])
        self.sched.start("c")
        self.sched.complete("c")
        self.assertTrue(self.sched.done())

    def test_deterministic_ordering_priority_then_submission(self):
        self.sched.submit([t("low"), t("high", priority=5), t("mid", priority=1), t("low2")])
        self.assertEqual([x.id for x in self.sched.ready()], ["high", "mid", "low", "low2"])

    def test_rejects_cycle(self):
        with self.assertRaises(SchedulerError):
            self.sched.submit([t("a", deps=["b"]), t("b", deps=["a"])])

    def test_rejects_self_dependency(self):
        with self.assertRaises(SchedulerError):
            self.sched.submit([t("a", deps=["a"])])

    def test_rejects_unknown_dependency(self):
        with self.assertRaises(SchedulerError):
            self.sched.submit([t("a", deps=["ghost"])])

    def test_rejects_duplicate_ids(self):
        with self.assertRaises(SchedulerError):
            self.sched.submit([t("a"), t("a")])
        self.sched.submit([t("b")])
        with self.assertRaises(SchedulerError):
            self.sched.submit([t("b")])

    def test_incremental_submission_may_depend_on_existing(self):
        self.sched.submit([t("a")])
        self.sched.submit([t("b", deps=["a"])])
        self.assertEqual([x.id for x in self.sched.ready()], ["a"])

    def test_failure_blocks_transitive_dependents(self):
        self.sched.submit([t("a"), t("b", deps=["a"]), t("c", deps=["b"]), t("d")])
        self.sched.start("a")
        self.sched.fail("a")
        statuses = self.sched.statuses()
        self.assertIs(statuses["a"], TaskStatus.FAILED)
        self.assertIs(statuses["b"], TaskStatus.BLOCKED)
        self.assertIs(statuses["c"], TaskStatus.BLOCKED)
        self.assertIs(statuses["d"], TaskStatus.PENDING)
        self.assertEqual([x.id for x in self.sched.ready()], ["d"])

    def test_cannot_complete_task_that_is_not_running(self):
        self.sched.submit([t("a")])
        with self.assertRaises(SchedulerError):
            self.sched.complete("a")

    def test_cancel_non_terminal_task(self):
        self.sched.submit([t("a")])
        self.sched.cancel("a")
        self.assertIs(self.sched.get("a").status, TaskStatus.CANCELLED)
        self.assertTrue(self.sched.done())

    def test_done_false_while_work_remains(self):
        self.sched.submit([t("a")])
        self.assertFalse(self.sched.done())


if __name__ == "__main__":
    unittest.main()
