import io
import tempfile
import unittest

from nexus.bench import default_suite, run_suite


class TestSuite(unittest.TestCase):
    def test_suite_spans_kinds_including_failures(self):
        suite = default_suite()
        kinds = {c.kind for c in suite}
        # deliberately includes an unroutable case — the gate is measured too
        self.assertIn("unroutable", kinds)
        self.assertIn("code", kinds)
        self.assertIn("research", kinds)
        self.assertGreaterEqual(len(suite), 8)


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_report_metrics_in_range(self):
        report = run_suite(self.tmp)
        s = report.summary()
        self.assertEqual(s["n"], len(default_suite()))
        for key in ("success_rate", "verified_rate", "unroutable_rate"):
            self.assertGreaterEqual(s[key], 0.0)
            self.assertLessEqual(s[key], 1.0)
        self.assertGreaterEqual(s["mean_tasks"], 1.0)

    def test_includes_failures(self):
        s = run_suite(self.tmp).summary()
        # at least one unroutable (browser case with no builtin)
        self.assertGreater(s["unroutable_rate"], 0.0)

    def test_learning_observed_across_suite(self):
        report = run_suite(self.tmp)
        # routable, verified runs promote episodic memory
        self.assertTrue(report.summary()["learning_observed"])

    def test_deterministic_summary(self):
        import shutil

        a = run_suite(self.tmp).deterministic_summary()
        second = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(second, ignore_errors=True))
        b = run_suite(second).deterministic_summary()
        self.assertEqual(a, b)

    def test_report_is_json_serializable(self):
        import json

        json.dumps(run_suite(self.tmp).as_dict())


class TestCliBench(unittest.TestCase):
    def test_nexus_bench_runs(self):
        from nexus.cli import run

        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        out = io.StringIO()
        code = run(["bench"], out=out, data_dir=tmp, research_root=tmp)
        self.assertEqual(code, 0)
        low = out.getvalue().lower()
        self.assertIn("success_rate", low)
        self.assertIn("verified_rate", low)


if __name__ == "__main__":
    unittest.main()
