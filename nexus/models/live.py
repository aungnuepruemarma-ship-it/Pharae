"""Live model adapters — optional, network-touching. Import-safe: these
classes always import; only ``complete`` reaches out. Kept dependency-light
(stdlib HTTP), so the browser-style optional-extra rule applies without a
hard SDK requirement.

Inspired by the sibling `cog` repo's adapters (Volume 4 comparison). The
runtime treats these exactly like the scripted floor — same seam, no core
change (Invariant I1).
"""

from __future__ import annotations

import json
import os
import urllib.request


class AnthropicAdapter:
    """Drive reasoning with a live Claude model via the Messages API.

    No third-party SDK required — uses the stdlib transport. Set
    ``ANTHROPIC_API_KEY`` or pass ``api_key``."""

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        api_key: str | None = None,
        max_tokens: int = 1024,
        base_url: str = "https://api.anthropic.com/v1/messages",
    ) -> None:
        self.model = model
        self.name = f"anthropic:{model}"
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._max_tokens = max_tokens
        self._base_url = base_url

    def complete(self, prompt: str) -> str:
        if not self._api_key:
            raise RuntimeError(
                "AnthropicAdapter needs an API key (ANTHROPIC_API_KEY or api_key=)"
            )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": self._max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()
        req = urllib.request.Request(
            self._base_url,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return "".join(
            block.get("text", "") for block in data.get("content", []) if isinstance(block, dict)
        )


class OpenAIAdapter:
    """Drive reasoning with an OpenAI-compatible chat endpoint (also serves
    local/OSS models behind an OpenAI-shaped server). ``temperature`` defaults
    to 0 for determinism."""

    def __init__(
        self,
        model: str = "local",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1/chat/completions",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.name = f"openai:{model}"
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(self._base_url, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]
