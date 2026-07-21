# Module Spec — Browser Capability

**Status:** Implemented (Stage 9). Code: `nexus/browser/`. Tests:
`tests/test_browser.py` (deterministic FakeDriver suite + a live
Playwright/Chromium test against a local server that skips cleanly where the
optional dependency is absent).

## Purpose

Browser automation as another capability — sessions, scraping, interaction —
with **no browser-specific logic in the runtime** (Volume 1 §29, Invariant
I5). Ships as the standard capability pattern: manifest + handler + check on
existing seams, zero kernel changes.

## The Driver Seam

All backend-specific logic lives behind `BrowserDriver`: `name`, `goto`,
`click`, `fill`, `close` — navigation-ish calls return a uniform `PageState`
(url, title, text). Everything above the seam (session bookkeeping, action
scripts, the handler) is backend-agnostic; swapping backends touches only a
driver. **Playwright/Chromium is the one V1 backend** (adding more is ADR
territory), packaged as an *optional dependency*
(`pip install 'nexus-runtime[browser]'`) — importing the module is safe
without it; constructing the driver is not. Launch fallback chain absorbs
browser-build/version mismatches: explicit path → `NEXUS_BROWSER_EXECUTABLE`
→ Playwright default → known preinstalled path.

## Declarative Action Scripts

Browser work is data, not code:
`[{"action": "goto", "url": …}, {"action": "click", "selector": …},
{"action": "fill", "selector": …, "value": …}, {"action": "read"}]` — so
plans stay serializable, replayable, and auditable. A failed or unknown
action halts the script with the failure recorded; it does not raise.

## Failure Semantics (two deliberate modes)

- **Ref navigation failures propagate** — an unreachable ref is a retryable
  task failure; the executor's retry policy applies.
- **Scripted-action failures are recorded** in the output (`ok: false`) for
  verification to judge — a broken selector is a finding about the page, not
  a transient fault.

Either way the driver is always closed (fresh driver per task; isolation).

## Memory Discipline

The browser never stores memory: the handler writes its report to **working
memory only** (`browser:<task_id>`). Anything durable goes through the
verified-evidence promotion gate like every other result.

## Capability Packaging

- `browser_manifest(backend)` → `browser.<backend>`, type `browser`,
  permissions `net.fetch` + `proc.spawn`, honest routing signals.
- `make_browser_handler(driver_factory)` — visits the task's http(s)
  `context_refs` (planner now propagates refs to goal payloads), runs the
  payload's action script, returns `{backend, pages, actions, ok}`.
- `browser_activity_check` — a browser task must have done something, and
  every scripted action must have succeeded; idle output fails verification.

## Verification

12 tests: session visit/history, ordered action scripts, unknown-action and
driver-error halt semantics, driver close guarantees (success, recorded
failure, and propagated failure paths), manifest validity/registration,
handler ref filtering + working-memory write + serializability, activity
check (ok / failed action / idle), a two-capability full loop (research
gathers context, browser scrapes, verification judges both, confidence 1.0),
and the live Chromium round-trip: goto → click → fill → read against a local
HTTP server.
