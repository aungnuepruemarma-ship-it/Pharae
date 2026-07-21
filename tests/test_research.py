import json
import os
import shutil
import subprocess
import tempfile
import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.executor import Executor
from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime
from nexus.memory import MemoryLayer, MemorySystem
from nexus.planner import Planner
from nexus.research import (
    DocumentationSource,
    RepositorySource,
    ResearchEngine,
    WebSource,
    make_research_handler,
    research_manifest,
    research_report_check,
)
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import RunStatus
from nexus.verify import VerificationEngine


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class TestDocumentationSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        write(
            self.tmp,
            "docs/routing.md",
            "# Routing\n\nThe router scores capability manifests.\n\n"
            "Cost and latency are normalized within the eligible set.",
        )
        write(self.tmp, "docs/memory.md", "# Memory\n\nSix layered stores on SQLite.")
        write(self.tmp, "image.png", "binary-ish routing routing routing")

    def test_finds_and_ranks_matching_paragraphs(self):
        source = DocumentationSource(self.tmp)
        findings = source.search("routing capability manifests", [])
        self.assertGreater(len(findings), 0)
        top = findings[0]
        self.assertIn("routing.md", top.location)
        self.assertIn("router scores capability manifests", top.excerpt)
        self.assertGreater(top.score, 0)

    def test_non_matching_content_excluded(self):
        source = DocumentationSource(self.tmp)
        findings = source.search("kubernetes federation", [])
        self.assertEqual(findings, [])

    def test_extension_filter_skips_binaries(self):
        source = DocumentationSource(self.tmp)
        findings = source.search("routing", [])
        self.assertTrue(all(not f.location.endswith(".png") for f in findings))

    def test_deterministic(self):
        source = DocumentationSource(self.tmp)
        first = source.search("routing", [])
        second = source.search("routing", [])
        self.assertEqual(first, second)


class TestRepositorySource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        write(self.tmp, "src/router.py", "# The router chooses capabilities by score\n")

    def test_scans_code_files(self):
        source = RepositorySource(self.tmp)
        findings = source.search("router capabilities", [])
        self.assertTrue(any("router.py" in f.location for f in findings))

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_searches_git_history(self):
        def git(*args):
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=T", *args],
                cwd=self.tmp, check=True, capture_output=True,
            )

        git("init", "-q")
        git("add", ".")
        git("commit", "-q", "-m", "Add routing table for capability selection")
        findings = RepositorySource(self.tmp).search("routing capability", [])
        history = [f for f in findings if f.location.startswith("git:")]
        self.assertEqual(len(history), 1)
        self.assertIn("routing table", history[0].excerpt)


class TestWebSource(unittest.TestCase):
    def test_fetches_only_http_refs_and_extracts_text(self):
        pages = {
            "https://example.com/spec": (
                "<html><head><script>var x=1;</script></head>"
                "<body><h1>Spec</h1><p>Routing uses capability manifests.</p>"
                "<p>Nothing relevant here.</p></body></html>"
            )
        }
        fetched = []

        def fetcher(url):
            fetched.append(url)
            return pages[url]

        source = WebSource(fetcher=fetcher)
        findings = source.search(
            "routing manifests", ["https://example.com/spec", "docs/local.md"]
        )
        self.assertEqual(fetched, ["https://example.com/spec"])  # non-http ref ignored
        self.assertEqual(len(findings), 1)
        self.assertIn("Routing uses capability manifests", findings[0].excerpt)
        self.assertNotIn("var x=1", " ".join(f.excerpt for f in findings))

    def test_fetch_error_degrades_gracefully(self):
        def failing(url):
            raise ConnectionError("offline")

        source = WebSource(fetcher=failing)
        self.assertEqual(source.search("anything", ["https://example.com/x"]), [])

    def test_no_refs_no_fetches(self):
        source = WebSource(fetcher=lambda url: self.fail("must not fetch"))
        self.assertEqual(source.search("query", []), [])


class TestResearchEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        write(self.tmp, "a.md", "Routing scores manifests.\n\nrouting routing routing everywhere.")
        self.engine = ResearchEngine()
        self.engine.add_source(DocumentationSource(self.tmp, name="docs.a"))
        self.engine.add_source(
            WebSource(fetcher=lambda url: "<p>routing on the web</p>", name="web.stub")
        )

    def test_aggregates_and_ranks_across_sources(self):
        report = self.engine.research("routing", refs=["https://example.com/page"])
        self.assertEqual(report.query, "routing")
        self.assertEqual(sorted(report.sources_consulted), ["docs.a", "web.stub"])
        sources_seen = {f.source for f in report.findings}
        self.assertEqual(sources_seen, {"docs.a", "web.stub"})
        scores = [f.score for f in report.findings]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_limit(self):
        report = self.engine.research("routing", top_k=1)
        self.assertEqual(len(report.findings), 1)
        self.assertGreaterEqual(report.stats["findings_total"], 2)

    def test_report_is_json_serializable(self):
        report = self.engine.research("routing")
        json.dumps(report.as_dict())  # raises on failure

    def test_deterministic(self):
        r1 = self.engine.research("routing", refs=["https://example.com/page"])
        r2 = self.engine.research("routing", refs=["https://example.com/page"])
        self.assertEqual(r1.as_dict(), r2.as_dict())


class TestCapabilityIntegration(unittest.TestCase):
    """Research arrives as a capability: manifest + handler + check.
    The kernel is untouched."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        write(
            self.tmp,
            "notes/decisions.md",
            "Routing decisions are recorded with candidates and scores.\n\n"
            "Unroutable tasks fail explicitly.",
        )
        self.engine = ResearchEngine()
        self.engine.add_source(DocumentationSource(self.tmp))

    def test_manifest_is_valid_and_registrable(self):
        registry = CapabilityRegistry()
        manifest = research_manifest()
        self.assertEqual(manifest.validate(), [])
        cap_id = registry.register(manifest)
        self.assertEqual(registry.find("research")[0].capability_id, cap_id)

    def test_check_passes_with_findings_fails_without(self):
        from nexus.schemas.core import Task, TaskResult, TaskStatus

        task = Task(id="t", capability_type="research")
        good = TaskResult(
            task_id="t", status=TaskStatus.COMPLETED,
            output={"findings": [{"excerpt": "x"}], "sources_consulted": ["docs"]},
        )
        empty = TaskResult(
            task_id="t", status=TaskStatus.COMPLETED,
            output={"findings": [], "sources_consulted": ["docs"]},
        )
        passed, _ = research_report_check(good, task)
        failed, detail = research_report_check(empty, task)
        self.assertTrue(passed)
        self.assertFalse(failed)
        self.assertIn("no findings", detail)

    def test_full_loop_objective_to_promoted_findings(self):
        bus = EventBus()
        registry = CapabilityRegistry(bus=bus)
        registry.register(research_manifest())
        registry.register(
            CapabilityManifest(name="checks.local", capability_type="verify", version="1.0.0")
        )
        memory = MemorySystem(bus=bus)
        router = Router(registry, bus=bus, decision_sink=memory.record_routing_decision)

        rt = Runtime(bus=bus)
        rt.register_handler("research", make_research_handler(self.engine))
        rt.register_handler("verify", lambda task, ctx: {"checked": True})
        rt.start()

        intent = IntentEngine(bus=bus).parse(
            make_objective("Research how routing decisions are recorded")
        )
        plan = Planner(bus=bus).plan(intent)
        self.assertEqual(plan.tasks[0].capability_type, "research")
        router.route_plan(plan)
        self.assertEqual(plan.tasks[0].capability_binding, "research.local@0.1.0")

        run = Executor(rt).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        report = run.task_results["goal-1"].output
        self.assertGreater(len(report["findings"]), 0)
        self.assertIn("recorded with candidates", report["findings"][0]["excerpt"])

        verifier = VerificationEngine(bus=bus)
        verifier.register_check("research", "has-findings", research_report_check)
        evidence = verifier.verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertTrue(evidence.test_results["success"])

        # Store summarized findings — through the gate, never around it.
        item = memory.promote(
            evidence,
            MemoryLayer.SEMANTIC,
            {"query": report["query"], "top_findings": report["findings"][:3]},
            policy_id="promo@1.0.0",
        )
        self.assertEqual(len(memory.search("candidates")), 1)
        self.assertEqual(memory.provenance(item.id)["evidence_id"], evidence.id)
        memory.close()


if __name__ == "__main__":
    unittest.main()
