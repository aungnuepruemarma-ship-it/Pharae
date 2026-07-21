# Module Spec — CLI (the front door)

**Status:** Implemented. Code: `nexus/cli/`. Tests: `tests/test_cli.py`.
The first interface surface (Volume 1 §16); makes the Volume 0 §9 success
criterion a runnable command.

## Purpose

Let a human drive the runtime with cognition verbs, not tool names. Turns 300+
tests of internal machinery into something a person can invoke.

```
nexus do "Build a REST API from spec.md"     # the whole loop
nexus think "should we use SQLite or Postgres?"
nexus plan "design the schema and then implement"
nexus memory search "routing"
nexus status
nexus config
```

## Verbs (V1 subset of the 12)

| Verb | Does |
|------|------|
| `do` | intent → thinking → plan → route → execute → verify → learn, printed stage by stage |
| `think` | intent + reasoning budget; no execution |
| `plan` | intent → plan; prints the task DAG |
| `memory search/list` | query the memory layers |
| `status` | runtime state, registered capabilities (built-ins labeled), memory counts, active routing policy |
| `config` | effective configuration (data dir, memory db, research root) |

`browse`, `research`, `verify <run>`, `learn`, `plugin`, `route` are the
remaining blueprint verbs — added as their backing surfaces mature.

## Architecture

`run(argv, out, data_dir, research_root) → exit code` is the testable entry
point: writes to a stream, returns a code, never touches `sys` directly.
`AppContext` wires every subsystem (registry, runtime, router with a memory
decision-sink, intent, thinking, planner, executor, verifier, economist, cog)
and opens a SQLite memory at `<data_dir>/memory.sqlite`, so learning
**persists across invocations** — successive `do` runs accumulate episodes,
scores, and skills.

## Built-in reference capabilities (honest labeling)

The CLI registers built-ins so `do` runs offline out of the box: `research`
is **real** (searches a document tree); `code` and `verify` are **reference
handlers** that record structured work and complete the loop deterministically
but perform no external effects. `status` labels built-ins as such. Real code
generation, browser, and cloud arrive as capabilities/plugins the user
installs — the CLI never pretends a reference handler wrote real code.

## Boundary

**Owns:** argument parsing, subsystem wiring, human-readable output.

**Must never:** contain runtime logic (it orchestrates existing subsystems),
weaken a gate, or fabricate results — an unroutable objective is reported
honestly with a non-zero exit, not papered over.

## Verification

13 tests over a temp data dir: think (mode/goals, reflex vs research), plan
(DAG with verify, no-goals error), do (all six stages visible, completes,
learns; persistence across invocations; unroutable reported without crashing),
memory search/list, status (labels capabilities), config, and help/unknown-
command handling.
