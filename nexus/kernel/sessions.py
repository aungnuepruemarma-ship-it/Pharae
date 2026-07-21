"""Session manager: live execution contexts.

Spec: docs/volume-3-protocols/session-api.md. Each session owns the isolated
state namespace ``session:<id>``; its id is the correlation id stamped on
session-scoped events. Ending a session releases only ephemeral working state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus.kernel.events import EventBus
from nexus.kernel.state import StateManager


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


@dataclass
class Session:
    id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def namespace(self) -> str:
        return f"session:{self.id}"


class SessionManager:
    def __init__(self, bus: EventBus, state: StateManager) -> None:
        self._bus = bus
        self._state = state
        self._sessions: dict[str, Session] = {}
        self._counter = 0

    def create(self, metadata: dict[str, Any] | None = None) -> Session:
        self._counter += 1
        session = Session(id=f"ses-{self._counter:06x}", metadata=dict(metadata or {}))
        self._sessions[session.id] = session
        self._bus.publish("session.started", {"session_id": session.id})
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def active(self) -> list[Session]:
        return [s for s in self._sessions.values() if s.status is SessionStatus.ACTIVE]

    def end(self, session_id: str) -> None:
        """Idempotent. Clears the session's state namespace; durable outputs
        (runs, evidence, artifacts) are never touched here."""
        session = self._sessions.get(session_id)
        if session is None or session.status is SessionStatus.ENDED:
            return
        session.status = SessionStatus.ENDED
        session.ended_at = time.time()
        self._state.clear_namespace(session.namespace)
        self._bus.publish("session.ended", {"session_id": session.id})
