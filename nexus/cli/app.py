"""AppContext — wires the whole runtime for the CLI and registers built-in
reference capabilities.

Honesty about the built-ins: `research` is real (searches a document tree);
`code`, `verify`, and `note` are **reference handlers** — they record
structured work and complete the loop deterministically offline, but do not
perform external effects. Real code generation / browser / cloud arrive as
capabilities or plugins the user installs. `status` labels the built-ins so
this is never hidden.
"""

from __future__ import annotations

import os

from nexus.capabilities import CapabilityRegistry
from nexus.cog import Cog
from nexus.economics import Economist
from nexus.executor import Executor, RetryPolicy
from nexus.intent import IntentEngine, make_objective
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import RunContext, Runtime
from nexus.memory import MemorySystem
from nexus.planner import Planner
from nexus.pyexec import make_pyexec_handler, pyexec_check, pyexec_manifest
from nexus.research import DocumentationSource, ResearchEngine, make_research_handler, research_manifest, research_report_check
from nexus.router import Router
from nexus.schemas.capability import CapabilityManifest
from nexus.thinking import ThinkingBudgeter
from nexus.verify import VerificationEngine

_VERSION = "0.1.0"


def _builtin(name: str, ctype: str, reliability: float, desc: str) -> CapabilityManifest:
    return CapabilityManifest(
        name=name,
        capability_type=ctype,
        version=_VERSION,
        description=desc,
        permissions=["fs.read"],
        cost=0.1,
        latency_ms=10.0,
        reliability=reliability,
        trust_score=0.3,
    )


class AppContext:
    def __init__(self, data_dir: str, research_root: str | None = None) -> None:
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)
        self.research_root = research_root or os.getcwd()

        self.bus = EventBus()
        self.memory = MemorySystem(
            path=os.path.join(self.data_dir, "memory.sqlite"), bus=self.bus
        )
        self.registry = CapabilityRegistry(bus=self.bus)
        self.runtime = Runtime(bus=self.bus)
        self.router = Router(
            self.registry, bus=self.bus, decision_sink=self.memory.record_routing_decision
        )
        self.intent = IntentEngine(bus=self.bus)
        self.thinking = ThinkingBudgeter(bus=self.bus)
        self.planner = Planner(bus=self.bus)
        self.executor = Executor(self.runtime, retry=RetryPolicy(max_attempts=1))
        self.verifier = VerificationEngine(bus=self.bus)
        self.economist = Economist(bus=self.bus)
        self.cog = Cog(self.memory, registry=self.registry, bus=self.bus)

        self.builtin_names: set[str] = set()
        self._register_builtins()
        self.runtime.start()

    # -- builtin capabilities ------------------------------------------------

    def _register_builtins(self) -> None:
        engine = ResearchEngine()
        engine.add_source(DocumentationSource(self.research_root, name="docs.cwd"))
        research_handler = make_research_handler(engine)
        self.verifier.register_check("research", "has-findings", research_report_check)
        self.verifier.register_check("code", "computed-result", pyexec_check)

        specs = [
            (research_manifest(), research_handler),
            # A real, failable code capability (arithmetic). Prose-code goals it
            # cannot compute fail honestly — the builtin does not fake coding.
            (pyexec_manifest(), make_pyexec_handler()),
            (_builtin("builtin.verify", "verify", 0.9,
                      "reference verifier: marks the run checked"),
             self._verify_handler),
        ]
        for manifest, handler in specs:
            self.registry.register(manifest)
            self.runtime.register_handler(f"{manifest.name}@{manifest.version}", handler)
            self.builtin_names.add(manifest.name)

    @staticmethod
    def _verify_handler(task, ctx: RunContext):
        return {"checked": True, "builtin": True}

    # -- the loop ------------------------------------------------------------

    def parse(self, text: str):
        return self.intent.parse(make_objective(text))

    def close(self) -> None:
        self.runtime.stop()
        self.memory.close()
