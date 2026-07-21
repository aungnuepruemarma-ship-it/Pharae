import io
import os
import tempfile
import unittest

from nexus.cli import run


def invoke(*argv, data_dir=None, research_root=None):
    out = io.StringIO()
    code = run(list(argv), out=out, data_dir=data_dir, research_root=research_root)
    return code, out.getvalue()


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def data(self, *a, **kw):
        kw.setdefault("data_dir", self.tmp)
        kw.setdefault("research_root", self.tmp)
        return invoke(*a, **kw)


class TestThink(CliTestCase):
    def test_think_reports_mode_and_goals(self):
        code, out = self.data("think", "Research solid-state batteries")
        self.assertEqual(code, 0)
        self.assertIn("research", out.lower())
        self.assertIn("Research solid-state batteries", out)

    def test_think_reflex_for_trivial(self):
        code, out = self.data("think", "Fix the typo")
        self.assertEqual(code, 0)
        self.assertIn("reflex", out.lower())


class TestPlan(CliTestCase):
    def test_plan_shows_dag_with_verify(self):
        code, out = self.data("plan", "Design the schema and then implement the API")
        self.assertEqual(code, 0)
        self.assertIn("goal-1", out)
        self.assertIn("goal-2", out)
        self.assertIn("verify", out)

    def test_plan_no_goals_reports_cleanly(self):
        code, out = self.data("plan", "What should we build?")
        self.assertNotEqual(code, 0)
        self.assertIn("no goals", out.lower())


class TestDo(CliTestCase):
    def test_do_runs_full_loop_and_learns(self):
        code, out = self.data("do", "Compute 6 * 7")
        self.assertEqual(code, 0)
        low = out.lower()
        # the six loop stages should all be visible
        for stage in ("intent", "plan", "rout", "execut", "verif", "learn"):
            self.assertIn(stage, low)
        self.assertIn("completed", low)

    def test_do_persists_learning_across_invocations(self):
        self.data("do", "Compute 6 * 7")
        # second run in same data dir: memory db carries prior episodes
        code, out = self.data("status")
        self.assertEqual(code, 0)
        self.assertIn("episodic", out.lower())

    def test_do_reports_unroutable_without_crashing(self):
        # A browser goal has no builtin capability → honest unroutable report.
        code, out = self.data("do", "Scrape the pricing page")
        low = out.lower()
        self.assertIn("unroutable", low)
        self.assertNotEqual(code, 0)

    def test_do_fails_honestly_on_non_computable_code(self):
        # The arithmetic builtin cannot implement prose code — the run does
        # not complete, and the CLI says so rather than faking success.
        code, out = self.data("do", "Implement a helper function")
        self.assertNotEqual(code, 0)
        self.assertNotIn("run run", out.lower().split("verify")[0])  # reached verify/failed


class TestMemory(CliTestCase):
    def test_memory_search_after_do(self):
        self.data("do", "Compute 6 * 7")
        code, out = self.data("memory", "search", "code")
        self.assertEqual(code, 0)

    def test_memory_list_layer(self):
        self.data("do", "Compute 6 * 7")
        code, out = self.data("memory", "list", "episodic")
        self.assertEqual(code, 0)
        self.assertIn("episodic", out.lower())


class TestStatusConfig(CliTestCase):
    def test_status_lists_capabilities(self):
        code, out = self.data("status")
        self.assertEqual(code, 0)
        self.assertIn("capabilit", out.lower())
        self.assertIn("code", out.lower())

    def test_config_shows_data_dir(self):
        code, out = self.data("config")
        self.assertEqual(code, 0)
        self.assertIn(self.tmp, out)

    def test_unknown_command_errors(self):
        code, out = self.data("frobnicate")
        self.assertNotEqual(code, 0)

    def test_no_command_prints_help(self):
        code, out = self.data()
        self.assertIn("usage", out.lower())


if __name__ == "__main__":
    unittest.main()
