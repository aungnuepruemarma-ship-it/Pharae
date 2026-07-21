"""Event bus: topic-based pub/sub with a replayable event log.

Spec: docs/volume-3-protocols/event-bus.md. Delivery is synchronous and
deterministic (subscription order); every event is appended to the log with a
monotonic sequence number (Kernel Invariant I6). A subscriber exception is
republished on ``bus.error`` and never propagates to the publisher.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

Handler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    topic: str
    payload: dict[str, Any]
    seq: int
    timestamp: float


@dataclass
class _Subscription:
    pattern: str
    handler: Handler
    order: int


def _matches(pattern: str, topic: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return topic.startswith(pattern[:-1]) and len(topic) > len(pattern) - 1
    return pattern == topic


class EventBus:
    def __init__(self) -> None:
        self._subscriptions: list[_Subscription] = []
        self._log: list[Event] = []
        self._seq = 0
        self._sub_order = 0
        # Reentrant: publishing from a subscriber (bus.error) must not deadlock.
        # The lock keeps seq/log/delivery consistent under the executor's
        # worker threads (Stage 5); delivery order stays deterministic per
        # publish because the whole publish is one critical section.
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        """Subscribe ``handler`` to topics matching ``pattern``.

        Patterns: exact topic, prefix wildcard (``task.*``), or ``*``.
        Returns an unsubscribe function."""
        sub = _Subscription(pattern, handler, self._sub_order)
        with self._lock:
            self._sub_order += 1
            self._subscriptions.append(sub)

        def unsubscribe() -> None:
            with self._lock:
                if sub in self._subscriptions:
                    self._subscriptions.remove(sub)

        return unsubscribe

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> Event:
        with self._lock:
            event = Event(
                topic=topic,
                payload=dict(payload or {}),
                seq=self._seq,
                timestamp=time.time(),
            )
            self._seq += 1
            self._log.append(event)
            for sub in sorted(self._matching(topic), key=lambda s: s.order):
                try:
                    sub.handler(event)
                except Exception as exc:  # one bad subscriber must not break the loop
                    if topic != "bus.error":
                        self.publish(
                            "bus.error",
                            {
                                "topic": topic,
                                "error": repr(exc),
                                "subscriber": getattr(
                                    sub.handler, "__qualname__", repr(sub.handler)
                                ),
                            },
                        )
            return event

    def _matching(self, topic: str) -> list[_Subscription]:
        return [s for s in self._subscriptions if _matches(s.pattern, topic)]

    def log(self, pattern: str | None = None) -> list[Event]:
        """The replayable event log, optionally filtered by topic pattern."""
        with self._lock:
            if pattern is None:
                return list(self._log)
            return [e for e in self._log if _matches(pattern, e.topic)]
