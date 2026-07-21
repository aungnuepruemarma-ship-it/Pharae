import unittest

from nexus.capabilities import CapabilityRegistry
from nexus.kernel.runtime import RunContext, Runtime
from nexus.models import (
    CallableAdapter,
    ScriptedAdapter,
    make_model_handler,
    model_manifest,
    model_output_check,
)
from nexus.schemas.core import Task, TaskResult, TaskStatus


def ctx_for(rt):
    session = rt.sessions.create()
    return RunContext(run_id="r", session=session, state=rt.state, bus=rt.bus)


class TestAdapters(unittest.TestCase):
    def test_scripted_adapter_is_deterministic(self):
        a = ScriptedAdapter({"hello": "world"}, default="idk", name="scripted")
        self.assertEqual(a.complete("hello"), "world")
        self.assertEqual(a.complete("hello"), "world")
        self.assertEqual(a.complete("unknown"), "idk")
        self.assertEqual(a.name, "scripted")

    def test_callable_adapter(self):
        a = CallableAdapter(lambda p: p.upper(), name="upper")
        self.assertEqual(a.complete("hi"), "HI")


class TestModelCapability(unittest.TestCase):
    def test_manifest_valid_and_registrable(self):
        registry = CapabilityRegistry()
        m = model_manifest("model.local", tier="small", cost=0.1, latency_ms=50)
        self.assertEqual(m.validate(), [])
        self.assertEqual(m.capability_type, "model")
        self.assertEqual(m.constraints["tier"], "small")
        registry.register(m)
        self.assertEqual(len(registry.find("model")), 1)

    def test_handler_runs_adapter_and_writes_working_memory(self):
        rt = Runtime()
        handler = make_model_handler(ScriptedAdapter({}, default="answer"))
        ctx = ctx_for(rt)
        task = Task(id="m1", capability_type="model", payload={"prompt": "question?"})
        out = handler(task, ctx)
        self.assertEqual(out["output"], "answer")
        self.assertEqual(out["model"], "scripted")
        self.assertEqual(ctx.get("model:m1"), out)

    def test_handler_uses_description_when_no_prompt(self):
        rt = Runtime()
        handler = make_model_handler(CallableAdapter(lambda p: f"echo:{p}"))
        out = handler(Task(id="m", capability_type="model", payload={"description": "hi"}), ctx_for(rt))
        self.assertEqual(out["output"], "echo:hi")

    def test_output_check(self):
        task = Task(id="m", capability_type="model")
        good = TaskResult(task_id="m", status=TaskStatus.COMPLETED, output={"output": "text"})
        empty = TaskResult(task_id="m", status=TaskStatus.COMPLETED, output={"output": ""})
        self.assertTrue(model_output_check(good, task)[0])
        self.assertFalse(model_output_check(empty, task)[0])


class TestRealAdaptersOptional(unittest.TestCase):
    def test_anthropic_adapter_importable_and_needs_key(self):
        from nexus.models import AnthropicAdapter

        # Construction without a key/SDK must fail clearly, never at import.
        with self.assertRaises(Exception):
            AnthropicAdapter(api_key=None).complete("hi")


if __name__ == "__main__":
    unittest.main()
