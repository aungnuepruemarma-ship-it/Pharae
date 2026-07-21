# Module Spec — Pyexec (real code capability)

**Status:** Implemented. Code: `nexus/pyexec/`. Tests: `tests/test_pyexec.py`.
The first *failable* built-in capability; wired as the CLI/bench `code`
handler, replacing the reference no-op.

## Purpose

Do genuine, verifiable work offline — and **fail honestly** on anything it
cannot do. That failure is the feature: it lets verification grade real
outcomes, which is what turned the benchmark's confidence metric from harness
determinism (flat 1.0) into a real quality signal (spread [0.20, 1.00],
baseline v0.1.1).

## Behavior

- `safe_eval(expr)` — evaluates an arithmetic expression by walking a parsed
  AST and permitting **only** numeric constants and whitelisted operators
  (`+ - * / // % **`, unary ±). No `Name`, `Call`, `Attribute`, subscript, or
  comprehension can survive the walk, so there is no path to attributes or
  imports. `**` exponent is bounded. Deterministic, side-effect-free.
- Handler: reads `payload.expression`, else extracts the first parseable
  arithmetic substring from the goal description. No computable expression →
  `PyexecError` → the task fails (honest; the builtin does not fake coding).
- `pyexec_check` — verification check: output carries a numeric `result`.
- Manifest: type `code`, name `pyexec.local`, permission `proc.compute`.

## Boundary

**Owns:** safe arithmetic evaluation and its capability packaging. **Must
never:** use `eval`/`exec`, admit names/calls/attributes, or perform I/O.

## Recorded limits

Arithmetic only — it is *a* real code capability, not a general coder. Prose
coding, file edits, and language execution need a model-backed or sandboxed
capability (future work / installable plugin). Its value here is being the
first capability that can genuinely succeed *and* fail, making downstream
metrics honest.

## Verification

9 tests: arithmetic correctness across operators, safety (names, calls,
attributes, subscripts, huge exponents, non-expressions all rejected),
manifest validity/type, handler extraction + explicit-expression preference +
honest failure on non-computable goals, and the verification check.
