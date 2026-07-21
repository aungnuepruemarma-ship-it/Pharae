# Module Spec — Intent Engine

**Status:** Spec (Stage 1). Not yet implemented.

## Purpose

Convert user language into a structured objective the planner can act on.
No execution, no tool calls, no side effects.

```
Objective (text, files, repos, questions)
   ↓
Intent { goals[], constraints[], desired_outcomes[], context_refs[] }
```

## Boundary

**Owns:** objective parsing, constraint extraction, goal decomposition, intent
representation.

**Must never:** execute anything, call capabilities, write memory (beyond
working memory of the current session).

## Behavior

- **Deterministic where possible:** identical objective text + context should
  produce a structurally identical intent. Where a model assists parsing, the
  parse result is normalized into the stable `Intent` schema so downstream
  behavior does not depend on the parser implementation.
- Ambiguity is represented explicitly (open questions on the intent), not
  silently resolved.
- Emits `intent.parsed` on the event bus with the intent id.

## Interfaces

- Input: `Objective` (Volume 3 / `nexus/schemas`).
- Output: `Intent` (Volume 3 / `nexus/schemas`).
- The parsing implementation is swappable; only the schema is stable.

## Verification

Golden tests: corpus of objectives → expected intent structures. Determinism
test: repeated parses of the same input are structurally equal.
