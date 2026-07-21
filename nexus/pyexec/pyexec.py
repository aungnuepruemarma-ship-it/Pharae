"""Safe arithmetic evaluation + its capability packaging.

``safe_eval`` walks a parsed AST and permits *only* numeric constants and a
whitelist of arithmetic operators — no `Name`, `Call`, `Attribute`,
subscript, or comprehension can survive, so there is no path to attribute
traversal or imports. Deterministic and side-effect-free.
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any, Callable

from nexus.kernel.runtime import RunContext
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Task, TaskResult

_VERSION = "0.1.0"
_MAX_EXPONENT = 1000

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

# Candidate arithmetic substrings: digits and operators only.
_EXPR = re.compile(r"[-+*/%().\d\s]+")


class PyexecError(Exception):
    pass


def safe_eval(expression: str) -> float | int:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise PyexecError(f"not a valid expression: {exc}") from None
    return _eval(tree.body)


def _eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise PyexecError("only numeric constants are allowed")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        if isinstance(node.op, ast.Pow):
            right = _eval(node.right)
            if abs(right) > _MAX_EXPONENT:
                raise PyexecError("exponent too large")
            return operator.pow(_eval(node.left), right)
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval(node.operand))
    raise PyexecError(f"unsupported expression element: {type(node).__name__}")


def _extract(text: str) -> str | None:
    """The first substring that looks arithmetic (has a digit and an operator)
    and actually parses. Deterministic (first match)."""
    for candidate in _EXPR.findall(text):
        candidate = candidate.strip()
        if not candidate or not any(c.isdigit() for c in candidate):
            continue
        if not any(op in candidate for op in "+-*/%"):
            continue
        try:
            safe_eval(candidate)
        except PyexecError:
            continue
        return candidate
    return None


def pyexec_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        name="pyexec.local",
        capability_type="code",
        version=_VERSION,
        description="Safe arithmetic evaluation (no eval/names/calls) — a real, failable code capability",
        input_schema={"expression": "str", "description": "str"},
        output_schema={"result": "number", "expression": "str"},
        permissions=["proc.compute"],
        cost=0.05,
        latency_ms=5.0,
        reliability=0.7,
        trust_score=0.3,
        evidence_score=0.9,
        confidence=0.3,
        strengths=["arithmetic", "deterministic"],
    )


def make_pyexec_handler(
    sandbox: bool = False,
) -> Callable[[Task, RunContext], dict[str, Any]]:
    """When ``sandbox=True``, the evaluation runs in a resource-limited child
    process (defense in depth; `safe_eval` is already safe, but the sandbox
    also caps CPU/memory/time). Falls back to in-process where fork is
    unavailable."""

    def handler(task: Task, ctx: RunContext) -> dict[str, Any]:
        expression = task.payload.get("expression") or _extract(
            task.payload.get("description", "")
        )
        if not expression:
            raise PyexecError(
                f"no computable expression in {task.payload.get('description', '')!r}"
            )
        value = _evaluate_sandboxed(expression) if sandbox else safe_eval(expression)
        result = {"result": value, "expression": expression}
        ctx.set(f"pyexec:{task.id}", result)
        return result

    return handler


def _evaluate_sandboxed(expression: str) -> float | int:
    from nexus.sandbox import SandboxLimits, run_sandboxed

    r = run_sandboxed(
        safe_eval, (expression,), limits=SandboxLimits(cpu_seconds=2, memory_mb=256, wall_seconds=3)
    )
    if r.reason == "unsupported":
        return safe_eval(expression)  # no fork here; the AST whitelist still applies
    if not r.ok:
        raise PyexecError(f"sandboxed evaluation failed ({r.reason}): {r.error}")
    return r.value


def pyexec_check(result: TaskResult, task: Task) -> tuple[bool, str]:
    output = result.output
    if not isinstance(output, dict) or "result" not in output:
        return False, "no computed result"
    if not isinstance(output["result"], (int, float)):
        return False, "result is not numeric"
    return True, f"{output.get('expression', '?')} = {output['result']}"
