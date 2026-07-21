# Module Spec — Economics (L5) + Model Capability

**Status:** Implemented. Code: `nexus/economics/`, `nexus/models/`. Tests:
`tests/test_economics.py`, `tests/test_models.py`. Layer L5 of the CogOS v2.0
map; consumes the L4 Thinking budget.

## Model capability (`nexus/models/`)

Reasoning-via-a-model as an ordinary capability, following the research/browser
pattern (manifest + handler + check), so the runtime stays model-agnostic
(Invariant I1):

- **Adapters** behind `ModelAdapter` (`name`, `complete(prompt) → str`):
  `ScriptedAdapter` (deterministic test/replay floor), `CallableAdapter`
  (any `str→str`), and optional live `AnthropicAdapter` / `OpenAIAdapter`
  (import-safe; stdlib HTTP; only `complete` touches the network; key via env
  or arg). Adapted in spirit from the sibling `cog` repo (Volume 4).
- `model_manifest(name, tier, …)` → type `model`, carrying a **tier**
  (small/mid/frontier/local) in constraints — the Economist's signal.
- `make_model_handler(adapter)` reads `payload.prompt` (or description), calls
  the adapter, writes working memory only.
- `model_output_check` — empty output fails verification.

## Economist (`nexus/economics/`)

`Economist.choose(budget, candidates) → manifest`: given the L4 Thinking
budget and candidate model capabilities, selects the compute tier. Distinct
from the router — the router binds a task to a capability of a type; the
Economist decides *which model tier to reason with*.

Policy (deterministic, manifest fields only):

| Mode | Objective |
|------|-----------|
| REFLEX | minimize cost (cheapest) |
| RESEARCH | maximize capability (trust·reliability), cost secondary |
| DELIBERATIVE | balance capability vs normalized cost + latency |

Ties break by name. Empty candidates raise; a single candidate is always
chosen. Emits `economics.chosen` (`{capability, mode, tier}`).

## Boundary

**Owns:** compute-tier selection. **Must never:** execute, or open any gate —
it selects among already-registered capabilities on manifest fields only.

## Recorded limits

Reasoning-economics here is tier selection, not the full cost/quality
optimization the blueprint envisions (replay vs. small vs. frontier with
learned cost models) — that arrives once the benchmark harness (L8) supplies
real cost/quality data. Live adapters are untested against the network in CI
by design (offline suite).

## Verification

14 tests: adapter determinism, manifest validity/registration, handler
behavior + working-memory write, output check, and Economist tier selection
per mode (reflex→cheapest, research→most capable, deliberative→balanced),
determinism, empty/single-candidate handling, and event emission.
