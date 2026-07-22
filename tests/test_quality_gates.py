"""Architectural Quality Gates (AQ1–AQ7).

A second category, distinct from the Kernel Invariants: these are engineering
quality guarantees that keep the *implementation* healthy as it grows, not
identity-level rules. A failure here is a quality regression to fix (add the
spec, break the cycle, add coverage), not a constitutional breach.

Honest status: AQ1/AQ2/AQ3/AQ6/AQ7 are enforced in full. AQ4 (deterministic
migrations) and AQ5 (per-capability benchmark coverage) are enforced in their
current honest form with the remaining gap recorded — see the handbook.
"""

import ast
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(__file__))
_NEXUS = os.path.join(_ROOT, "nexus")
_SPECS = os.path.join(_ROOT, "docs", "volume-2-modules")

# AQ1: every runtime subpackage declares ownership/interfaces/invariants via a
# module spec. schemas is data (Volume 3 protocol specs), exempt here.
MODULE_SPECS = {
    "kernel": "kernel.md",
    "intent": "intent.md",
    "thinking": "thinking.md",
    "planner": "planner.md",
    "capabilities": "capability-registry.md",
    "router": "router.md",
    "executor": "executor.md",
    "memory": "memory.md",
    "verify": "verification.md",
    "research": "research.md",
    "browser": "browser.md",
    "plugins": "plugins.md",
    "cog": "cog.md",
    "economics": "economics.md",
    "models": "economics.md",  # model capability documented in the economics spec
    "experiments": "experiments.md",
    "science": "science.md",
    "bench": "bench.md",
    "cli": "cli.md",
    "pyexec": "pyexec.md",
    "security": "security.md",
    "sandbox": "sandbox.md",
}
_EXEMPT = {"schemas"}


def _subpackages() -> set[str]:
    return {
        name
        for name in os.listdir(_NEXUS)
        if os.path.isfile(os.path.join(_NEXUS, name, "__init__.py"))
    }


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _load_time_nexus_deps(path: str) -> set[str]:
    """nexus subpackages imported at *module load time* — excluding imports
    inside functions (lazy) and under `if TYPE_CHECKING` (never executed).
    These are the edges that can form real import cycles."""
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    deps: set[str] = set()

    def visit(node: ast.AST, in_func: bool, in_typing: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, True, in_typing)
            elif isinstance(child, ast.If) and _is_type_checking(child.test):
                visit(child, in_func, True)
            elif isinstance(child, ast.ImportFrom):
                if not in_func and not in_typing and child.level == 0 and child.module:
                    if child.module.startswith("nexus."):
                        deps.add(child.module.split(".")[1])
            elif isinstance(child, ast.Import):
                if not in_func and not in_typing:
                    for alias in child.names:
                        if alias.name.startswith("nexus."):
                            deps.add(alias.name.split(".")[1])
            else:
                visit(child, in_func, in_typing)

    visit(tree, False, False)
    return deps


def _py_files(subdir: str) -> list[str]:
    out = []
    for dirpath, _dirs, files in os.walk(os.path.join(_NEXUS, subdir)):
        out.extend(os.path.join(dirpath, f) for f in files if f.endswith(".py"))
    return out


class TestAQ1_ModuleDeclarations(unittest.TestCase):
    def test_every_subpackage_has_a_spec(self):
        for pkg in _subpackages() - _EXEMPT:
            self.assertIn(pkg, MODULE_SPECS, f"nexus/{pkg} has no module spec mapping (AQ1)")

    def test_specs_exist_and_declare_boundary_and_verification(self):
        for pkg, doc in MODULE_SPECS.items():
            path = os.path.join(_SPECS, doc)
            self.assertTrue(os.path.exists(path), f"missing spec {doc} for {pkg}")
            text = open(path).read().lower()
            self.assertIn("boundary", text, f"{doc} lacks a Boundary section (AQ1)")
            self.assertIn("verification", text, f"{doc} lacks a Verification section (AQ1)")


class TestAQ2_NoCyclicDependencies(unittest.TestCase):
    def _graph(self) -> dict[str, set[str]]:
        pkgs = _subpackages()
        graph: dict[str, set[str]] = {p: set() for p in pkgs}
        for pkg in pkgs:
            for path in _py_files(pkg):
                for dep in _load_time_nexus_deps(path):
                    if dep in pkgs and dep != pkg:
                        graph[pkg].add(dep)
        return graph

    def test_import_graph_is_acyclic(self):
        graph = self._graph()
        state: dict[str, int] = {}  # 0=visiting, 1=done

        def dfs(node: str, stack: list[str]) -> None:
            state[node] = 0
            for nxt in sorted(graph[node]):
                if state.get(nxt) == 0:
                    cycle = stack[stack.index(nxt):] + [nxt] if nxt in stack else [nxt]
                    self.fail(f"import cycle (AQ2): {' → '.join(stack + [nxt])} (loop {cycle})")
                if nxt not in state:
                    dfs(nxt, stack + [nxt])
            state[node] = 1

        for pkg in sorted(graph):
            if pkg not in state:
                dfs(pkg, [pkg])


class TestAQ3_ManifestsValidate(unittest.TestCase):
    def test_all_capability_manifests_are_schema_valid(self):
        from nexus.browser import browser_manifest
        from nexus.models import model_manifest
        from nexus.pyexec import pyexec_manifest
        from nexus.research import research_manifest

        manifests = [
            research_manifest(),
            browser_manifest(backend="playwright"),
            model_manifest("model.x", tier="mid"),
            pyexec_manifest(),
        ]
        for m in manifests:
            self.assertEqual(m.validate(), [], f"{m.name} manifest invalid (AQ3)")


class TestAQ4_DeterministicMemorySchema(unittest.TestCase):
    """Honest current form: no migration system yet, so the gate is that
    schema init is idempotent and reopening preserves data deterministically.
    Full migration-determinism lands with a migration system (recorded)."""

    def test_reopen_is_idempotent_and_preserves_data(self):
        import tempfile

        from nexus.memory import MemoryLayer, MemorySystem
        from nexus.schemas.core import Evidence

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.sqlite")
            m1 = MemorySystem(path=path)
            item = m1.promote(
                Evidence(id="e", run_id="r", verified=True, confidence=0.9),
                MemoryLayer.SEMANTIC, {"fact": "x"}, policy_id="p@1",
            )
            m1.close()
            m2 = MemorySystem(path=path)  # re-init must not error or wipe
            got = m2.read(MemoryLayer.SEMANTIC)
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0].id, item.id)
            m2.close()


class TestAQ5_BenchmarkCoverage(unittest.TestCase):
    """Honest current form: the core capability types the planner emits have
    benchmark coverage. Dedicated model/verify coverage is recorded as a gap."""

    def test_core_capability_types_are_covered(self):
        from nexus.bench import default_suite

        kinds = {c.kind for c in default_suite()}
        for required in ("code", "research", "unroutable"):
            self.assertIn(required, kinds, f"benchmark lacks {required} coverage (AQ5)")


class TestAQ6_Replayable(unittest.TestCase):
    def test_run_emits_a_complete_ordered_trace(self):
        from nexus.executor import Executor
        from nexus.kernel.runtime import Runtime
        from nexus.schemas.core import Plan, Task

        rt = Runtime()
        rt.start()
        rt.register_handler("code", lambda t, c: {"ok": t.id})
        plan = Plan(id="p", tasks=[
            Task(id="a", capability_type="code"),
            Task(id="b", capability_type="code", depends_on=["a"]),
        ])
        run = Executor(rt).execute(plan)
        events = [e for e in rt.bus.log() if e.payload.get("run_id") == run.id]
        topics = [e.topic for e in events]
        self.assertIn("run.started", topics)
        self.assertIn("run.completed", topics)
        for tid in ("a", "b"):
            started = [e for e in events if e.topic == "task.started" and e.payload["task_id"] == tid]
            done = [e for e in events if e.topic == "task.completed" and e.payload["task_id"] == tid]
            self.assertTrue(started and done, f"task {tid} not fully traced (AQ6)")
            self.assertLess(started[0].seq, done[0].seq)


class TestAQ7_TraceablePersistentWrites(unittest.TestCase):
    def test_every_promoted_item_has_full_provenance(self):
        from nexus.memory import MemoryLayer, MemorySystem
        from nexus.schemas.core import Evidence

        m = MemorySystem()
        self.addCleanup(m.close)
        for layer in (MemoryLayer.EPISODIC, MemoryLayer.SEMANTIC, MemoryLayer.PROCEDURAL):
            item = m.promote(
                Evidence(id=f"e-{layer.value}", run_id="r", verified=True, confidence=0.8),
                layer, {"k": layer.value}, policy_id="p@1",
            )
            prov = m.provenance(item.id)
            for field in ("run_id", "evidence_id", "policy_id", "promoted_at"):
                self.assertIn(field, prov, f"{layer.value} write missing {field} (AQ7)")
                self.assertIsNotNone(prov[field])


if __name__ == "__main__":
    unittest.main()
