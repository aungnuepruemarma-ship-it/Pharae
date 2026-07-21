# Module Spec — Intent Engine

**Status:** Implemented (Stage 1). Code: `nexus/intent/`. Tests: `tests/test_intent.py`.

## Purpose

Convert user language into a structured objective the planner can act on.
No execution, no tool calls, no side effects.

```
Objective (text + context refs)
   ↓
Intent { goals[], constraints[], desired_outcomes[], open_questions[], context_refs[] }
```

## Boundary

**Owns:** objective parsing, constraint extraction, goal decomposition, intent
representation.

**Must never:** execute anything, call capabilities, write memory (beyond
working memory of the current session).

## Behavior (V1: rule-based, model-free)

V1 parsing is a transparent ordered rule set — deterministic by construction
and vendor-free (Invariant I1). A model-assisted parser may arrive later as a
*capability* whose output is normalized into the same `Intent` schema; the
schema, not the parser, is the stable surface.

Clause pipeline: text → lines (bullet/number prefixes stripped) → sentence
split (period/semicolon/bang followed by whitespace, so versions like `3.11`
and filenames survive) → per-clause classification, in order:

| # | Rule | Bucket |
|---|------|--------|
| 1 | ends with `?` | open question |
| 2 | contains `so that` | right side → outcome; left side re-enters classification |
| 3 | starts with a constraint marker (`must`, `should (not)`, `don't`, `never`, `avoid`, `only`, `without`, `use/using`, `keep`, `ensure`, `stay`, `limit`, `no more than`, `at most/least`, `within`, `under`, `budget`, `deadline`, `no …`) | constraint |
| 4 | starts with an outcome marker (`deliver`, `the result`, `end result`, `end up with`, `the final`, `output/result should`) | desired outcome |
| 5 | otherwise | goal; `and then` / `, then` splits compound goals; embedded phrases (`using …`, `without …`, `no more than …`, `at most/least …`, `within …`) are additionally extracted as constraints |

Further behavior:

- **Determinism:** identical objective text + refs produce a structurally
  identical Intent *including its id* — ids are content-derived
  (`obj-<sha256[:12]>`, `int-<sha256[:12]>`), never random.
- **Ambiguity is explicit:** questions are captured, never answered; an
  objective with no recognizable goal yields an open question rather than a
  guessed goal. Parsing is total — no input raises.
- **Context refs:** URLs, paths with a directory component, and bare filenames
  with documentation/data extensions are detected in the text and merged after
  the objective's explicit refs, deduplicated in first-occurrence order.
  Dotted product names ("Node.js") are deliberately not treated as files.
- All output lists are deduplicated preserving first occurrence.
- Emits `intent.parsed` (`{intent_id, objective_id}`) when a bus is attached;
  works without one.

## Interfaces

- Input: `Objective` (`make_objective(text, context_refs)` builds one with a
  content-derived id).
- Output: `Intent` (Volume 3 / `nexus/schemas`).
- The parsing implementation is swappable; only the schema is stable.

## Known V1 Limits (accepted, recorded)

Marker lists are English-only and heuristic; a goal phrased as a bare noun
("battery research pipeline") classifies as a goal only because nothing else
claims it. Improving classification quality is routine rule-tuning against the
golden tests — not an architecture change.

## Verification

Golden tests: corpus of objectives → expected buckets (27 cases), including
the V1 success-criteria objective end to end. Determinism test: repeated
parses are equal. Event-emission and no-bus operation tests.
