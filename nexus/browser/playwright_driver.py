"""Playwright/Chromium backend — the one V1 browser backend (ADR territory
to add more). Optional dependency: importing this module is safe without
playwright installed; constructing the driver is not.

Launch strategy: explicit path → NEXUS_BROWSER_EXECUTABLE → Playwright's
default browser → the well-known preinstalled path. Environments often ship
a Chromium build that mismatches the installed Playwright version's
expectations; the fallback chain absorbs that instead of failing.
"""

from __future__ import annotations

import os

from nexus.browser.driver import BrowserError, PageState

_KNOWN_EXECUTABLES = ("/opt/pw-browsers/chromium",)
_DEFAULT = object()  # sentinel: launch with Playwright's own browser


class PlaywrightDriver:
    name = "playwright"

    def __init__(
        self,
        headless: bool = True,
        executable_path: str | None = None,
        timeout_ms: float = 15000,
    ) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserError(
                "the browser capability needs its optional dependency: "
                "pip install 'nexus-runtime[browser]'"
            ) from exc
        self._pw = sync_playwright().start()
        self._closed = False
        try:
            self._browser = self._launch(headless, executable_path)
            self._page = self._browser.new_page()
            self._page.set_default_timeout(timeout_ms)
        except Exception:
            self._pw.stop()
            raise

    def _launch(self, headless: bool, explicit: str | None):
        candidates: list[object] = []
        if explicit:
            candidates.append(explicit)
        env_path = os.environ.get("NEXUS_BROWSER_EXECUTABLE")
        if env_path:
            candidates.append(env_path)
        candidates.append(_DEFAULT)
        candidates.extend(p for p in _KNOWN_EXECUTABLES if os.path.exists(p))

        attempts = []
        for candidate in candidates:
            kwargs = {} if candidate is _DEFAULT else {"executable_path": candidate}
            try:
                return self._pw.chromium.launch(headless=headless, **kwargs)
            except Exception as exc:
                label = "default" if candidate is _DEFAULT else str(candidate)
                attempts.append(f"{label}: {str(exc).splitlines()[0][:120]}")
        raise BrowserError("could not launch chromium — " + " | ".join(attempts))

    # -- driver seam ---------------------------------------------------------

    def goto(self, url: str) -> PageState:
        self._page.goto(url)
        return self._state()

    def click(self, selector: str) -> PageState:
        self._page.click(selector)
        return self._state()

    def fill(self, selector: str, value: str) -> PageState:
        self._page.fill(selector, value)
        return self._state()

    def _state(self) -> PageState:
        try:
            text = self._page.inner_text("body")
        except Exception:
            text = ""
        return PageState(url=self._page.url, title=self._page.title(), text=text)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._browser.close()
        finally:
            self._pw.stop()
