"""CLI dispatch. Cognition verbs over the runtime; stdlib argparse, no deps.

`run(argv, out, data_dir, research_root)` is the testable entry point — it
writes to a stream and returns an exit code, never touches sys directly.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TextIO

from nexus.cli.app import AppContext
from nexus.memory import MemoryLayer
from nexus.planner import PlannerError
from nexus.router import UnroutableError
from nexus.schemas.core import RunStatus, TaskStatus

_VERBS = ("do", "think", "plan", "memory", "status", "config")


def run(
    argv: list[str],
    out: TextIO | None = None,
    data_dir: str | None = None,
    research_root: str | None = None,
) -> int:
    out = out or sys.stdout
    parser = _build_parser()
    if not argv:
        parser.print_help(out)
        return 2
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse error already printed to stderr
        return int(exc.code or 2)

    data_dir = data_dir or os.environ.get("NEXUS_DATA_DIR", ".nexus")
    ctx = AppContext(data_dir=data_dir, research_root=research_root)
    try:
        handler = _HANDLERS[args.command]
        return handler(ctx, args, out)
    finally:
        ctx.close()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nexus", description="Intelligence runtime CLI")
    sub = p.add_subparsers(dest="command")

    for verb, help_text in (
        ("do", "execute an objective end to end"),
        ("think", "reason about an objective without executing"),
        ("plan", "build and print an execution plan"),
    ):
        sp = sub.add_parser(verb, help=help_text)
        sp.add_argument("objective", help="the objective text")

    mem = sub.add_parser("memory", help="search and inspect memory")
    mem.add_argument("action", choices=("search", "list"))
    mem.add_argument("query", help="search text, or a layer name for 'list'")

    sub.add_parser("status", help="show live runtime state")
    sub.add_parser("config", help="show effective configuration")
    sub.add_parser("bench", help="run the benchmark suite and report metrics")
    return p


# -- verb handlers -----------------------------------------------------------


def _cmd_think(ctx: AppContext, args, out: TextIO) -> int:
    intent = ctx.parse(args.objective)
    budget = ctx.thinking.assess(intent)
    _section(out, "THINK")
    out.write(f"  mode        : {budget.mode.value}\n")
    out.write(f"  rationale   : {budget.rationale}\n")
    out.write(f"  goals       : {intent.goals or '—'}\n")
    out.write(f"  constraints : {intent.constraints or '—'}\n")
    out.write(f"  outcomes    : {intent.desired_outcomes or '—'}\n")
    if intent.open_questions:
        out.write(f"  questions   : {intent.open_questions}\n")
    out.write(
        f"  budget      : depth={budget.max_plan_depth} gather={budget.gather_context} "
        f"parallel={budget.max_parallelism} retries={budget.max_retries} "
        f"stop@{budget.stopping_confidence}\n"
    )
    return 0


def _cmd_plan(ctx: AppContext, args, out: TextIO) -> int:
    intent = ctx.parse(args.objective)
    budget = ctx.thinking.assess(intent)
    try:
        plan = ctx.planner.plan(intent, budget=budget)
    except PlannerError as exc:
        out.write(f"cannot plan: {exc}\n")
        return 1
    _section(out, f"PLAN  ({budget.mode.value})")
    for task in plan.tasks:
        deps = f"  ← {', '.join(task.depends_on)}" if task.depends_on else ""
        out.write(f"  {task.id:<16} [{task.capability_type}]{deps}\n")
    return 0


def _cmd_do(ctx: AppContext, args, out: TextIO) -> int:
    intent = ctx.parse(args.objective)
    budget = ctx.thinking.assess(intent)
    _section(out, "INTENT")
    out.write(f"  goals: {intent.goals or '—'}  mode: {budget.mode.value}\n")

    try:
        plan = ctx.planner.plan(intent, budget=budget)
    except PlannerError as exc:
        out.write(f"cannot plan: {exc}\n")
        return 1
    _section(out, "PLAN")
    out.write(f"  {len(plan.tasks)} task(s): {', '.join(t.id for t in plan.tasks)}\n")

    _section(out, "ROUTE")
    try:
        decisions = ctx.router.route_plan(plan)
    except UnroutableError as exc:
        out.write(f"  unroutable: {exc}\n")
        out.write("  (install capabilities/plugins for the missing types, then retry)\n")
        return 1
    for tid, d in decisions.items():
        out.write(f"  {tid:<16} → {d.chosen}\n")

    _section(out, "EXECUTE")
    run_ = ctx.executor.execute(plan)
    for tid, res in sorted(run_.task_results.items()):
        out.write(f"  {tid:<16} {res.status.value}\n")

    _section(out, "VERIFY")
    evidence = ctx.verifier.verify(run_, plan=plan)
    out.write(
        f"  verified={evidence.verified}  confidence={evidence.confidence:.2f}  "
        f"success={evidence.test_results.get('success')}\n"
    )

    _section(out, "LEARN")
    if evidence.verified:
        result = ctx.cog.learn(run_, evidence, plan=plan)
        out.write(f"  episodic memory: {result.episodic_id}\n")
        if result.skill_id:
            out.write(f"  skill promoted : {result.skill_id}\n")
        if result.score_updates:
            out.write(f"  scores updated : {len(result.score_updates)} capability outcome(s)\n")
        if result.failure_ids:
            out.write(f"  failures noted : {len(result.failure_ids)}\n")
    else:
        out.write("  (unverified run — nothing learned)\n")

    out.write(f"\nrun {run_.id}: {run_.status.value}\n")
    return 0 if run_.status is RunStatus.COMPLETED else 1


def _cmd_memory(ctx: AppContext, args, out: TextIO) -> int:
    if args.action == "search":
        hits = ctx.memory.search(args.query)
        _section(out, f"MEMORY search {args.query!r}")
        if not hits:
            out.write("  (no matches)\n")
        for item in hits:
            out.write(f"  [{item.layer.value}] {item.id}: {item.content}\n")
        return 0
    # list
    try:
        layer = MemoryLayer(args.query)
    except ValueError:
        out.write(f"unknown layer {args.query!r}; choose from "
                  f"{', '.join(l.value for l in MemoryLayer)}\n")
        return 1
    items = ctx.memory.read(layer)
    _section(out, f"MEMORY {layer.value} ({len(items)})")
    for item in items:
        out.write(f"  {item.id}: {item.content}\n")
    return 0


def _cmd_status(ctx: AppContext, args, out: TextIO) -> int:
    _section(out, "STATUS")
    out.write(f"  runtime      : {'running' if ctx.runtime.running else 'stopped'}\n")
    out.write("  capabilities :\n")
    for ctype in ctx.registry.types():
        names = [r.manifest.name for r in ctx.registry.find(ctype)]
        labeled = [n + (" (builtin)" if n in ctx.builtin_names else "") for n in names]
        out.write(f"      {ctype:<10} {', '.join(labeled)}\n")
    out.write("  memory       :\n")
    for layer in MemoryLayer:
        if layer is MemoryLayer.WORKING:
            continue
        out.write(f"      {layer.value:<11} {len(ctx.memory.read(layer))}\n")
    active = ctx.cog.policies.active("routing")
    out.write(f"  routing policy: {active.id if active else '— (default rules)'}\n")
    pol = ctx.security._policy  # display-only
    rules = len(pol.denied_permissions) + len(pol.approval_permissions) + len(pol.approval_types)
    out.write(f"  security      : {'permissive' if rules == 0 else f'{rules} rule(s)'}\n")
    return 0


def _cmd_bench(ctx: AppContext, args, out: TextIO) -> int:
    from nexus.bench import run_suite

    report = run_suite(os.path.join(ctx.data_dir, "bench"))
    _section(out, "BENCH")
    for key, value in report.deterministic_summary().items():
        out.write(f"  {key:<16}: {value}\n")
    return 0


def _cmd_config(ctx: AppContext, args, out: TextIO) -> int:
    _section(out, "CONFIG")
    out.write(f"  data dir      : {ctx.data_dir}\n")
    out.write(f"  memory db     : {os.path.join(ctx.data_dir, 'memory.sqlite')}\n")
    out.write(f"  research root : {ctx.research_root}\n")
    out.write(f"  capability types: {', '.join(ctx.registry.types())}\n")
    return 0


_HANDLERS = {
    "do": _cmd_do,
    "think": _cmd_think,
    "plan": _cmd_plan,
    "memory": _cmd_memory,
    "status": _cmd_status,
    "config": _cmd_config,
    "bench": _cmd_bench,
}


def _section(out: TextIO, title: str) -> None:
    out.write(f"\n{title}\n")


def _main() -> int:  # pragma: no cover - real entry point
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
