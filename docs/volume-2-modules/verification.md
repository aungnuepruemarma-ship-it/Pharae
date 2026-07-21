# Module Spec — Verification Engine

**Status:** Spec (Stage 6). Not yet implemented. The `Evidence` schema is
canonical in `nexus/schemas/core.py`.

## Purpose

First-class subsystem that decides whether results are true, reproducible,
safe, and consistent. Nothing is trusted by default; verification output is the
*only* input to learning and long-term memory (Invariant I2).

## Boundary

**Owns:** evidence collection, test execution, replay/validation, confidence
scoring, reproducibility assessment.

**Must never:** repair results (that is re-planning), or be skippable for runs
that feed learning or memory promotion.

## Behavior

Every serious run ends with:

- **Output** and **evidence**: logs, artifacts, traces, screenshots, datasets.
- **Tests** where applicable (generated or provided), with results attached.
- **Confidence score** in [0, 1] with the scoring inputs recorded.
- **Reproducibility status**: replayable / partially / not, and why.
- **Cost report**: tokens, time, money per capability.

Verification strategies are pluggable per capability type (code → run tests;
research → source cross-checks; browser → assertion on page state), but the
`Evidence` envelope is uniform.

Emits `run.verified` with the evidence id; `run.unverified` when verification
cannot be performed — unverified runs cannot promote memory or update policy.

## Interfaces

- Input: `Run` + artifacts + logs.
- Output: `Evidence` (Volume 3 / `nexus/schemas`), linked to the run.

## Verification (of the verifier)

Known-good and known-bad fixture runs must score high/low respectively;
evidence envelopes are schema-validated; unverified runs are provably unable to
reach the memory promotion path.
