# Module Spec — Research Capability

**Status:** Implemented (Stage 8). Code: `nexus/research/`. Tests:
`tests/test_research.py`. First Phase 2 capability — and the reference
pattern for every capability that follows.

## Purpose

A unified research interface that gathers information from different sources
**without changing the kernel** (Invariant I5). Finds, scores, and structures
external knowledge into a deterministic report.

## The Capability Pattern (normative for future capabilities)

Research ships as three attachments to existing seams, zero kernel changes:

1. **Manifest** — `research_manifest()` registers `research.local` (type
   `research`) in the registry: permissions `fs.read`/`net.fetch`, I/O
   schemas, routing signals.
2. **Handler** — `make_research_handler(engine)` attaches to the runtime's
   capability-type seam; reads the task's `description` as the query and its
   `context_refs` as source hints.
3. **Check** — `research_report_check` plugs into the verification engine:
   a report with zero findings is a failed research task, not a quietly
   empty success.

## Source-Adapter Model

`ResearchEngine` aggregates pluggable sources (`add_source`) — sources
register themselves, mirroring the capability philosophy one level down.
Each source filters the refs it understands; a broken source or dead ref
yields no findings, never an error.

| Source | Covers | Notes |
|--------|--------|-------|
| `DocumentationSource` | Doc trees (.md/.txt/.rst/.adoc) | Ignores refs; always covers its root |
| `RepositorySource` | Source+doc files, plus git commit history | History via `git log` subprocess; steps aside silently without git/.git |
| `WebSource` | The http(s) refs it is given | Deliberately no search-engine dependency in V1; injectable fetcher (stdlib urllib default, stubs in tests); HTML → text via stdlib parser, script/style stripped |

Guardrails: files over 512 KB and undecodable files skipped, hidden
directories pruned, 50 findings per source, 300-char excerpts.

## Determinism

Relevance is term-frequency scoring: query terms (lowercased, stopwords and
short tokens dropped) prefix-matched per word ("route" credits "routing"),
summed per paragraph. Ranking: score desc, then source/location/excerpt.
Same corpus + same query → identical report, tested.

## Findings and Memory

The handler returns the report and writes it to **working memory only**.
Storing summarized findings long-term goes through the verified-evidence
promotion gate (tested end to end: objective → research run → verified
evidence → semantic-memory promotion with full provenance) — never around it.

## V1 Limits (recorded)

No live web search (only given refs are fetched); scoring is lexical, not
semantic; sources are consulted serially. Each lifts independently — a
search-capable source, an embedding scorer, or parallel consultation plug in
behind the same `ResearchSource` interface without touching the engine's
contract.

## Verification

16 tests: source ranking/filtering/determinism, extension and binary
skipping, git-history search against a real temp repo (skipped without git),
web text extraction with script stripping, ref filtering, graceful fetch
failure, engine aggregation and top-k, JSON serializability, manifest
validity + registration, check pass/fail, and the full loop from objective
to gated promotion of findings.
