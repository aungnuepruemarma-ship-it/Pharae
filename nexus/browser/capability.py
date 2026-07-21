"""Browser packaged as a capability: manifest, handler, verification check.

Same pattern as research (the normative capability pattern): three
attachments to existing seams, zero kernel changes. The handler creates a
fresh driver per task (isolation), always closes it, and writes only working
memory — the browser never stores memory (Volume 1 §29).
"""

from __future__ import annotations

from typing import Any, Callable

from nexus.browser.driver import BrowserDriver, BrowserSession
from nexus.kernel.runtime import RunContext
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Task, TaskResult

_EXCERPT_CHARS = 300


def browser_manifest(backend: str = "playwright", version: str = "0.1.0") -> CapabilityManifest:
    return CapabilityManifest(
        name=f"browser.{backend}",
        capability_type="browser",
        version=version,
        description=(
            "Browser automation: visit refs, run declarative action scripts "
            f"(goto/click/fill/read) via the {backend} backend"
        ),
        input_schema={
            "description": "str",
            "context_refs": "list[str] — http(s) refs are visited",
            "actions": "list[{action, ...}] — optional script",
        },
        output_schema={
            "backend": "str",
            "pages": "list[{url, title, excerpt, text_chars}]",
            "actions": "list[{action, ok, detail}]",
            "ok": "bool",
        },
        permissions=["net.fetch", "proc.spawn"],
        cost=0.0,
        latency_ms=1500.0,
        reliability=0.6,
        trust_score=0.2,
        evidence_score=0.5,
        confidence=0.2,
        strengths=["automation", "scraping", "interaction"],
    )


def make_browser_handler(
    driver_factory: Callable[[], BrowserDriver],
) -> Callable[[Task, RunContext], dict[str, Any]]:
    """A fresh driver per task, always closed afterward. Ref navigation
    failures propagate (retryable task failure); scripted-action failures are
    recorded in the output for verification to judge."""

    def handler(task: Task, ctx: RunContext) -> dict[str, Any]:
        driver = driver_factory()
        session = BrowserSession(driver)
        try:
            pages = []
            for ref in task.payload.get("context_refs", []):
                if not ref.startswith(("http://", "https://")):
                    continue
                state = session.visit(ref)
                pages.append(
                    {
                        "url": state.url,
                        "title": state.title,
                        "excerpt": state.text[:_EXCERPT_CHARS],
                        "text_chars": len(state.text),
                    }
                )
            results = session.run(task.payload.get("actions", []))
            output = {
                "backend": driver.name,
                "pages": pages,
                "actions": [
                    {"action": r.action, "ok": r.ok, "detail": r.detail} for r in results
                ],
                "ok": all(r.ok for r in results),
            }
        finally:
            session.close()
        ctx.set(f"browser:{task.id}", output)
        return output

    return handler


def browser_activity_check(result: TaskResult, task: Task) -> tuple[bool, str]:
    """Verification check: a browser task must have done something, and every
    scripted action must have succeeded."""
    output = result.output
    if not isinstance(output, dict) or "pages" not in output:
        return False, "output is not a browser report"
    pages = output.get("pages") or []
    actions = output.get("actions") or []
    if not pages and not actions:
        return False, "no browser activity: no pages visited, no actions run"
    failed = [a for a in actions if not a.get("ok")]
    if failed:
        return False, f"{len(failed)} failed action(s): {failed[0].get('detail', '')}"
    return True, f"{len(pages)} page(s) visited, {len(actions)} action(s) ok"
