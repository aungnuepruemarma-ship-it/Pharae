"""The driver seam and the declarative action session.

A driver exposes exactly: ``name``, ``goto``, ``click``, ``fill``, ``close``,
each navigation-ish call returning a ``PageState``. Everything above the seam
(session bookkeeping, action scripts, the capability handler) is
backend-agnostic; everything below it is one backend's concern. Swapping
Playwright for anything else touches only the driver.

Action scripts are data, not code — tasks describe browser work as
``[{"action": "goto", "url": …}, {"action": "click", "selector": …}, …]`` so
plans stay serializable, replayable, and auditable. A failed action halts the
script and is recorded; it does not raise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

_READ_CHARS = 200


class BrowserError(Exception):
    pass


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    text: str


@dataclass(frozen=True)
class ActionResult:
    action: str
    ok: bool
    detail: str


class BrowserDriver(Protocol):
    name: str

    def goto(self, url: str) -> PageState: ...
    def click(self, selector: str) -> PageState: ...
    def fill(self, selector: str, value: str) -> PageState: ...
    def close(self) -> None: ...


class BrowserSession:
    def __init__(self, driver: BrowserDriver) -> None:
        self._driver = driver
        self._history: list[PageState] = []
        self._last: PageState | None = None

    def visit(self, url: str) -> PageState:
        """Direct navigation. Unlike scripted actions, failures propagate —
        an unreachable ref is a retryable task failure."""
        state = self._driver.goto(url)
        self._record(state)
        return state

    def run(self, actions: list[dict[str, Any]]) -> list[ActionResult]:
        """Run a declarative action script. Stops at the first failure with
        the failure recorded; remaining actions are not attempted."""
        results: list[ActionResult] = []
        for spec in actions:
            name = str(spec.get("action", ""))
            try:
                detail = self._apply(name, spec)
            except Exception as exc:
                results.append(ActionResult(action=name or "?", ok=False, detail=str(exc)))
                break
            results.append(ActionResult(action=name, ok=True, detail=detail))
        return results

    def _apply(self, name: str, spec: dict[str, Any]) -> str:
        if name == "goto":
            state = self._driver.goto(spec["url"])
            self._record(state)
            return state.title
        if name == "click":
            state = self._driver.click(spec["selector"])
            self._record(state)
            return state.title
        if name == "fill":
            state = self._driver.fill(spec["selector"], spec["value"])
            self._record(state)
            return f"filled {spec['selector']}"
        if name == "read":
            if self._last is None:
                raise BrowserError("nothing to read: no page loaded")
            return self._last.text[:_READ_CHARS]
        raise BrowserError(f"unknown action {name!r}")

    def _record(self, state: PageState) -> None:
        self._last = state
        if not self._history or self._history[-1].url != state.url:
            self._history.append(state)

    def history(self) -> list[PageState]:
        return list(self._history)

    def close(self) -> None:
        self._driver.close()
