import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest

from nexus.browser import (
    BrowserError,
    BrowserSession,
    PageState,
    browser_activity_check,
    browser_manifest,
    make_browser_handler,
)
from nexus.capabilities import CapabilityRegistry
from nexus.executor import Executor
from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Runtime, RunContext
from nexus.planner import Planner
from nexus.research import ResearchEngine, WebSource, make_research_handler, research_manifest
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import RunStatus, Task, TaskResult, TaskStatus
from nexus.verify import VerificationEngine


class FakeDriver:
    """Deterministic in-memory site for unit tests."""

    name = "fake"

    def __init__(self, site):
        self.site = site  # url -> {"title", "text", "links": {selector: url}}
        self.closed = False
        self.filled = []
        self._url = None

    def _state(self):
        page = self.site[self._url]
        return PageState(url=self._url, title=page["title"], text=page["text"])

    def goto(self, url):
        if url not in self.site:
            raise BrowserError(f"no such page {url!r}")
        self._url = url
        return self._state()

    def click(self, selector):
        links = self.site[self._url].get("links", {})
        if selector not in links:
            raise BrowserError(f"no element {selector!r}")
        self._url = links[selector]
        return self._state()

    def fill(self, selector, value):
        self.filled.append((self._url, selector, value))
        return self._state()

    def close(self):
        self.closed = True


SITE = {
    "https://shop.example/": {
        "title": "Shop",
        "text": "Welcome to the shop",
        "links": {"a#pricing": "https://shop.example/pricing"},
    },
    "https://shop.example/pricing": {
        "title": "Pricing",
        "text": "Pro plan pricing is $10 per month",
        "links": {},
    },
}


class TestBrowserSession(unittest.TestCase):
    def setUp(self):
        self.driver = FakeDriver(SITE)
        self.session = BrowserSession(self.driver)

    def test_visit_returns_state_and_records_history(self):
        state = self.session.visit("https://shop.example/")
        self.assertEqual(state.title, "Shop")
        self.assertEqual([p.url for p in self.session.history()], ["https://shop.example/"])

    def test_action_script_runs_in_order(self):
        results = self.session.run(
            [
                {"action": "goto", "url": "https://shop.example/"},
                {"action": "click", "selector": "a#pricing"},
                {"action": "read"},
            ]
        )
        self.assertTrue(all(r.ok for r in results))
        self.assertEqual(results[1].detail, "Pricing")
        self.assertIn("Pro plan pricing", results[2].detail)

    def test_unknown_action_fails_and_halts(self):
        results = self.session.run(
            [
                {"action": "teleport"},
                {"action": "goto", "url": "https://shop.example/"},
            ]
        )
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].ok)
        self.assertIn("unknown action", results[0].detail)

    def test_driver_error_fails_action_and_halts(self):
        results = self.session.run(
            [
                {"action": "goto", "url": "https://shop.example/"},
                {"action": "click", "selector": "a#missing"},
                {"action": "read"},
            ]
        )
        self.assertEqual(len(results), 2)
        self.assertFalse(results[1].ok)
        self.assertIn("no element", results[1].detail)

    def test_close_closes_driver(self):
        self.session.close()
        self.assertTrue(self.driver.closed)


class TestBrowserCapability(unittest.TestCase):
    def make_ctx(self):
        rt = Runtime()
        session = rt.sessions.create()
        return rt, RunContext(run_id="r", session=session, state=rt.state, bus=rt.bus)

    def test_manifest_is_valid_and_registrable(self):
        registry = CapabilityRegistry()
        manifest = browser_manifest(backend="fake")
        self.assertEqual(manifest.validate(), [])
        self.assertEqual(manifest.name, "browser.fake")
        registry.register(manifest)
        self.assertEqual(len(registry.find("browser")), 1)

    def test_handler_visits_refs_and_runs_actions(self):
        driver = FakeDriver(SITE)
        handler = make_browser_handler(lambda: driver)
        rt, ctx = self.make_ctx()
        task = Task(
            id="b1",
            capability_type="browser",
            payload={
                "description": "Scrape pricing",
                "context_refs": ["https://shop.example/pricing", "notes/local.md"],
                "actions": [{"action": "read"}],
            },
        )
        output = handler(task, ctx)
        json.dumps(output)  # serializable
        self.assertEqual(output["backend"], "fake")
        self.assertEqual(len(output["pages"]), 1)  # non-http ref ignored
        self.assertEqual(output["pages"][0]["title"], "Pricing")
        self.assertTrue(output["ok"])
        self.assertTrue(driver.closed)  # session closed after the task
        self.assertEqual(ctx.get("browser:b1"), output)  # working memory only

    def test_failed_action_reported_not_raised(self):
        driver = FakeDriver(SITE)
        handler = make_browser_handler(lambda: driver)
        _, ctx = self.make_ctx()
        task = Task(
            id="b1",
            capability_type="browser",
            payload={
                "context_refs": ["https://shop.example/"],
                "actions": [{"action": "click", "selector": "a#missing"}],
            },
        )
        output = handler(task, ctx)
        self.assertFalse(output["ok"])
        self.assertTrue(driver.closed)

    def test_unreachable_ref_raises_and_still_closes_driver(self):
        driver = FakeDriver(SITE)
        handler = make_browser_handler(lambda: driver)
        _, ctx = self.make_ctx()
        task = Task(
            id="b1",
            capability_type="browser",
            payload={"context_refs": ["https://nowhere.example/"]},
        )
        with self.assertRaises(BrowserError):
            handler(task, ctx)  # navigation failure is retryable: let it fail the task
        self.assertTrue(driver.closed)

    def test_activity_check(self):
        task = Task(id="b", capability_type="browser")
        ok = TaskResult(
            task_id="b", status=TaskStatus.COMPLETED,
            output={"pages": [{"url": "x"}], "actions": [], "ok": True},
        )
        bad_action = TaskResult(
            task_id="b", status=TaskStatus.COMPLETED,
            output={"pages": [{"url": "x"}], "actions": [{"ok": False}], "ok": False},
        )
        idle = TaskResult(
            task_id="b", status=TaskStatus.COMPLETED,
            output={"pages": [], "actions": [], "ok": True},
        )
        self.assertTrue(browser_activity_check(ok, task)[0])
        self.assertFalse(browser_activity_check(bad_action, task)[0])
        passed, detail = browser_activity_check(idle, task)
        self.assertFalse(passed)
        self.assertIn("no browser activity", detail)


class TestFullLoop(unittest.TestCase):
    """Two Phase 2 capabilities cooperating: research gathers context, the
    browser does the scraping, verification judges both. Kernel untouched."""

    def test_objective_to_verified_browser_run(self):
        bus = EventBus()
        registry = CapabilityRegistry(bus=bus)
        registry.register(research_manifest())
        registry.register(browser_manifest(backend="fake"))
        registry.register(
            CapabilityManifest(name="checks.local", capability_type="verify", version="1.0.0")
        )
        router = Router(registry, bus=bus)

        research = ResearchEngine()
        research.add_source(
            WebSource(fetcher=lambda url: "<p>pricing plans overview</p>", name="web.stub")
        )
        rt = Runtime(bus=bus)
        rt.register_handler("research", make_research_handler(research))
        rt.register_handler("browser", make_browser_handler(lambda: FakeDriver(SITE)))
        rt.register_handler("verify", lambda task, ctx: {"checked": True})
        rt.start()

        intent = IntentEngine(bus=bus).parse(
            make_objective("Scrape pricing details from https://shop.example/pricing")
        )
        plan = Planner(bus=bus).plan(intent)
        self.assertEqual(
            [(t.id, t.capability_type) for t in plan.tasks],
            [("gather-context", "research"), ("goal-1", "browser"), ("verify", "verify")],
        )
        self.assertEqual(
            plan.tasks[1].payload["context_refs"], ["https://shop.example/pricing"]
        )

        router.route_plan(plan)
        run = Executor(rt).execute(plan)
        self.assertIs(run.status, RunStatus.COMPLETED)
        browser_output = run.task_results["goal-1"].output
        self.assertIn("Pro plan pricing", browser_output["pages"][0]["excerpt"])

        verifier = VerificationEngine(bus=bus)
        verifier.register_check("browser", "activity", browser_activity_check)
        evidence = verifier.verify(run, plan=plan)
        self.assertTrue(evidence.verified)
        self.assertTrue(evidence.test_results["success"])
        self.assertEqual(evidence.confidence, 1.0)


def _serve(directory):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class TestPlaywrightLive(unittest.TestCase):
    """Real Chromium via Playwright against a local server. Skips cleanly
    where the optional dependency or a launchable browser is absent."""

    @classmethod
    def setUpClass(cls):
        try:
            from nexus.browser import PlaywrightDriver

            cls.driver = PlaywrightDriver()
        except Exception as exc:
            raise unittest.SkipTest(f"playwright unavailable: {exc}")
        cls.tmp = tempfile.mkdtemp()
        with open(os.path.join(cls.tmp, "index.html"), "w") as f:
            f.write(
                "<html><head><title>Index</title></head><body>"
                "<h1>Welcome home</h1>"
                '<a id="next" href="page2.html">Next</a></body></html>'
            )
        with open(os.path.join(cls.tmp, "page2.html"), "w") as f:
            f.write(
                "<html><head><title>Page Two</title></head><body>"
                '<input id="q"/><p>Second page content</p></body></html>'
            )
        cls.server, cls.base = _serve(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "driver"):
            cls.driver.close()
        if hasattr(cls, "server"):
            cls.server.shutdown()
            shutil.rmtree(cls.tmp)

    def test_goto_click_fill_roundtrip(self):
        session = BrowserSession(self.driver)
        results = session.run(
            [
                {"action": "goto", "url": f"{self.base}/index.html"},
                {"action": "click", "selector": "a#next"},
                {"action": "fill", "selector": "input#q", "value": "hello"},
                {"action": "read"},
            ]
        )
        self.assertTrue(all(r.ok for r in results), [r.detail for r in results])
        self.assertEqual(results[0].detail, "Index")
        self.assertEqual(results[1].detail, "Page Two")
        self.assertIn("Second page content", results[3].detail)
        self.assertEqual(session.history()[-1].title, "Page Two")


if __name__ == "__main__":
    unittest.main()
