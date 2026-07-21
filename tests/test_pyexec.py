import unittest

from nexus.kernel.runtime import RunContext, Runtime
from nexus.pyexec import (
    PyexecError,
    make_pyexec_handler,
    pyexec_check,
    pyexec_manifest,
    safe_eval,
)
from nexus.schemas.core import Task, TaskResult, TaskStatus


class TestSafeEval(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(safe_eval("6 * 7"), 42)
        self.assertEqual(safe_eval("(12 + 8) / 4"), 5)
        self.assertEqual(safe_eval("2 ** 10"), 1024)
        self.assertEqual(safe_eval("100 - 37"), 63)
        self.assertEqual(safe_eval("15 % 4"), 3)
        self.assertEqual(safe_eval("-3 + 5"), 2)

    def test_rejects_names_calls_attributes(self):
        for danger in ("x + 1", "__import__('os')", "abs(-1)", "(1).__class__", "[1,2]"):
            with self.assertRaises(PyexecError):
                safe_eval(danger)

    def test_rejects_huge_exponent(self):
        with self.assertRaises(PyexecError):
            safe_eval("2 ** 100000")

    def test_rejects_non_expression(self):
        with self.assertRaises(PyexecError):
            safe_eval("not an expression at all")


class TestCapability(unittest.TestCase):
    def ctx(self):
        rt = Runtime()
        return RunContext(run_id="r", session=rt.sessions.create(), state=rt.state, bus=rt.bus)

    def test_manifest_valid_type_code(self):
        m = pyexec_manifest()
        self.assertEqual(m.validate(), [])
        self.assertEqual(m.capability_type, "code")

    def test_handler_evaluates_expression_from_description(self):
        handler = make_pyexec_handler()
        out = handler(Task(id="t", capability_type="code", payload={"description": "Compute 6 * 7"}), self.ctx())
        self.assertEqual(out["result"], 42)
        self.assertEqual(out["expression"], "6 * 7")

    def test_handler_prefers_explicit_expression(self):
        handler = make_pyexec_handler()
        out = handler(Task(id="t", capability_type="code", payload={"expression": "3+4"}), self.ctx())
        self.assertEqual(out["result"], 7)

    def test_handler_fails_on_non_computable_goal(self):
        handler = make_pyexec_handler()
        with self.assertRaises(PyexecError):
            handler(Task(id="t", capability_type="code", payload={"description": "Implement a helper function"}), self.ctx())

    def test_check_grades_result(self):
        task = Task(id="t", capability_type="code")
        good = TaskResult(task_id="t", status=TaskStatus.COMPLETED, output={"result": 42})
        bad = TaskResult(task_id="t", status=TaskStatus.COMPLETED, output={"note": "x"})
        self.assertTrue(pyexec_check(good, task)[0])
        self.assertFalse(pyexec_check(bad, task)[0])


if __name__ == "__main__":
    unittest.main()
