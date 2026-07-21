"""The model-adapter seam. A model is anything with a name and
``complete(prompt) -> str``. Everything above the seam is model-independent."""

from __future__ import annotations

from typing import Callable, Protocol


class ModelAdapter(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class CallableAdapter:
    """Wrap any ``str -> str`` function as a model — the offline/local floor."""

    def __init__(self, fn: Callable[[str], str], name: str = "callable") -> None:
        self._fn = fn
        self.name = name

    def complete(self, prompt: str) -> str:
        return self._fn(prompt)


class ScriptedAdapter:
    """Deterministic canned responses — the test/replay floor."""

    def __init__(
        self, responses: dict[str, str], default: str = "", name: str = "scripted"
    ) -> None:
        self._responses = dict(responses)
        self._default = default
        self.name = name

    def complete(self, prompt: str) -> str:
        return self._responses.get(prompt, self._default)
