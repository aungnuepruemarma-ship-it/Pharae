"""Stage 9 — Browser capability.

Spec: docs/volume-2-modules/browser.md. Browser automation as another
capability: manifest + handler + check on existing seams, zero kernel
changes (Invariant I5). All browser-specific logic lives behind the driver
seam; Playwright is the one V1 backend, an optional dependency. The browser
never stores memory — its handler writes working memory only.
"""

from nexus.browser.capability import (
    browser_activity_check,
    browser_manifest,
    make_browser_handler,
)
from nexus.browser.driver import ActionResult, BrowserError, BrowserSession, PageState
from nexus.browser.playwright_driver import PlaywrightDriver

__all__ = [
    "ActionResult",
    "BrowserError",
    "BrowserSession",
    "PageState",
    "PlaywrightDriver",
    "browser_activity_check",
    "browser_manifest",
    "make_browser_handler",
]
