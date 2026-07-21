"""SQLite-backed layered memory with a gated promotion path.

Gate rules implemented here (normative in Volume 3):

1. ``write_working`` is the only ungated write, session-scoped and cleared
   with the session.
2. ``promote`` demands verified Evidence and a policy id; anything else is
   rejected before touching storage. Promoted items carry full provenance
   (run, evidence, policy, time) and are reversible via ``deprecate``.
3. There is deliberately no generic ``write(layer, ...)`` API — the absence
   of that method is part of the contract, and a test asserts it.
4. Secret-like payloads are rejected at every write path: key names that
   look like credentials, and value patterns (cloud keys, tokens, PEM
   blocks).

Routing decisions are persisted here too, but as an *operational record*
distinct from the memory layers — they are the router's replay log
(Invariant I6), not knowledge, so they bypass no gate by existing.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from typing import Any

from nexus.kernel.events import EventBus
from nexus.schemas.core import Evidence
from nexus.schemas.memory import MemoryItem, MemoryLayer, PROMOTABLE_LAYERS
from nexus.schemas.routing import CandidateEvaluation, RoutingDecision


class MemoryError_(Exception):
    pass


_SECRET_KEY_NAMES = frozenset(
    {
        "password", "passwd", "secret", "api_key", "apikey", "token",
        "access_token", "refresh_token", "private_key", "credentials", "auth",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),  # GitHub token
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),  # generic api key shape
    re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]{20,}"),
)


def _scan_for_secrets(node: Any, path: str = "") -> str | None:
    """Return a description of the first secret-like finding, else None."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.lower() in _SECRET_KEY_NAMES and value:
                return f"key {key!r} looks like a credential"
            found = _scan_for_secrets(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, (list, tuple)):
        for value in node:
            found = _scan_for_secrets(value, path)
            if found:
                return found
    elif isinstance(node, str):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(node):
                return f"value at {path or '<root>'} matches a secret pattern"
    return None


def _reject_secrets(payload: Any) -> None:
    finding = _scan_for_secrets(payload)
    if finding:
        raise MemoryError_(f"secrets never enter memory: {finding}")


def _to_json(payload: Any, what: str) -> str:
    try:
        return json.dumps(payload)
    except TypeError as exc:
        raise MemoryError_(f"{what} must be JSON-serializable: {exc}") from None


def _layer(value: MemoryLayer | str) -> MemoryLayer:
    try:
        return MemoryLayer(value)
    except ValueError:
        raise MemoryError_(f"unknown memory layer {value!r}") from None


class MemorySystem:
    def __init__(self, path: str = ":memory:", bus: EventBus | None = None) -> None:
        self._bus = bus
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS memory_items (
                 seq INTEGER PRIMARY KEY AUTOINCREMENT,
                 id TEXT UNIQUE NOT NULL,
                 layer TEXT NOT NULL,
                 content TEXT NOT NULL,
                 run_id TEXT NOT NULL,
                 evidence_id TEXT NOT NULL,
                 policy_id TEXT NOT NULL,
                 promoted_at REAL NOT NULL,
                 confidence REAL NOT NULL,
                 deprecated INTEGER NOT NULL DEFAULT 0,
                 deprecated_reason TEXT,
                 deprecated_at REAL
               )"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS working_memory (
                 session_id TEXT NOT NULL,
                 key TEXT NOT NULL,
                 value TEXT NOT NULL,
                 updated_at REAL NOT NULL,
                 PRIMARY KEY (session_id, key)
               )"""
        )
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS routing_decisions (
                 seq INTEGER PRIMARY KEY AUTOINCREMENT,
                 id TEXT NOT NULL,
                 task_id TEXT NOT NULL,
                 capability_type TEXT NOT NULL,
                 policy_id TEXT NOT NULL,
                 chosen TEXT,
                 reason TEXT NOT NULL,
                 candidates TEXT NOT NULL,
                 created_at REAL NOT NULL
               )"""
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # -- working memory (the only ungated write path) ------------------------

    def write_working(self, session_id: str, key: str, value: Any) -> None:
        _reject_secrets({key: value})
        serialized = _to_json(value, "working-memory value")
        with self._lock:
            self._db.execute(
                """INSERT INTO working_memory (session_id, key, value, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT (session_id, key) DO UPDATE
                   SET value = excluded.value, updated_at = excluded.updated_at""",
                (session_id, key, serialized, time.time()),
            )
            self._db.commit()

    def read_working(self, session_id: str, key: str | None = None) -> Any:
        with self._lock:
            if key is not None:
                row = self._db.execute(
                    "SELECT value FROM working_memory WHERE session_id = ? AND key = ?",
                    (session_id, key),
                ).fetchone()
                return json.loads(row[0]) if row else None
            rows = self._db.execute(
                "SELECT key, value FROM working_memory WHERE session_id = ? ORDER BY key",
                (session_id,),
            ).fetchall()
            return {k: json.loads(v) for k, v in rows}

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM working_memory WHERE session_id = ?", (session_id,)
            )
            self._db.commit()

    # -- gated promotion (Invariants I2/I3) ----------------------------------

    def promote(
        self,
        evidence: Evidence,
        layer: MemoryLayer | str,
        content: dict[str, Any],
        *,
        policy_id: str,
    ) -> MemoryItem:
        """The only write path above working memory. Caller restriction (Cog
        only) is organizational until the security layer lands; the evidence
        and policy gates are enforced here."""
        if not isinstance(evidence, Evidence) or not evidence.verified:
            raise MemoryError_(
                "promotion requires verified Evidence (Kernel Invariant I2)"
            )
        if not policy_id or not policy_id.strip():
            raise MemoryError_("promotion requires the approving policy_id")
        resolved = _layer(layer)
        if resolved not in PROMOTABLE_LAYERS:
            raise MemoryError_(f"cannot promote into layer {resolved.value!r}")
        _reject_secrets(content)
        serialized = _to_json(content, "memory content")
        now = time.time()
        with self._lock:
            cursor = self._db.execute(
                """INSERT INTO memory_items
                   (id, layer, content, run_id, evidence_id, policy_id,
                    promoted_at, confidence)
                   VALUES ('', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolved.value, serialized, evidence.run_id, evidence.id,
                    policy_id, now, evidence.confidence,
                ),
            )
            item_id = f"mem-{cursor.lastrowid:08x}"
            self._db.execute(
                "UPDATE memory_items SET id = ? WHERE seq = ?",
                (item_id, cursor.lastrowid),
            )
            self._db.commit()
        item = MemoryItem(
            id=item_id,
            layer=resolved,
            content=json.loads(serialized),
            provenance={
                "run_id": evidence.run_id,
                "evidence_id": evidence.id,
                "policy_id": policy_id,
                "promoted_at": now,
            },
            confidence=evidence.confidence,
            created_at=now,
        )
        if self._bus is not None:
            self._bus.publish(
                "memory.promoted",
                {"item_id": item.id, "layer": resolved.value, "policy_id": policy_id},
            )
        return item

    def deprecate(self, item_id: str, *, reason: str) -> None:
        """Reversible removal: the item stays queryable with
        ``include_deprecated=True``. Idempotent; unknown ids are an error."""
        with self._lock:
            row = self._db.execute(
                "SELECT deprecated FROM memory_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                raise MemoryError_(f"unknown memory item {item_id!r}")
            if row[0]:
                return
            self._db.execute(
                """UPDATE memory_items
                   SET deprecated = 1, deprecated_reason = ?, deprecated_at = ?
                   WHERE id = ?""",
                (reason, time.time(), item_id),
            )
            self._db.commit()
        if self._bus is not None:
            self._bus.publish(
                "memory.deprecated", {"item_id": item_id, "reason": reason}
            )

    # -- reads ---------------------------------------------------------------

    def read(
        self, layer: MemoryLayer | str, include_deprecated: bool = False
    ) -> list[MemoryItem]:
        resolved = _layer(layer)
        query = "SELECT * FROM memory_items WHERE layer = ?"
        if not include_deprecated:
            query += " AND deprecated = 0"
        with self._lock:
            rows = self._db.execute(query + " ORDER BY seq", (resolved.value,)).fetchall()
        return [self._row_to_item(row) for row in rows]

    def search(
        self,
        text: str,
        layer: MemoryLayer | str | None = None,
        include_deprecated: bool = False,
    ) -> list[MemoryItem]:
        query = "SELECT * FROM memory_items WHERE content LIKE ?"
        params: list[Any] = [f"%{text}%"]
        if layer is not None:
            query += " AND layer = ?"
            params.append(_layer(layer).value)
        if not include_deprecated:
            query += " AND deprecated = 0"
        with self._lock:
            rows = self._db.execute(query + " ORDER BY seq", params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def provenance(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                """SELECT run_id, evidence_id, policy_id, promoted_at
                   FROM memory_items WHERE id = ?""",
                (item_id,),
            ).fetchone()
        if row is None:
            raise MemoryError_(f"unknown memory item {item_id!r}")
        return {
            "run_id": row[0],
            "evidence_id": row[1],
            "policy_id": row[2],
            "promoted_at": row[3],
        }

    @staticmethod
    def _row_to_item(row: tuple) -> MemoryItem:
        (_seq, item_id, layer, content, run_id, evidence_id, policy_id,
         promoted_at, confidence, deprecated, _reason, _dep_at) = row
        return MemoryItem(
            id=item_id,
            layer=MemoryLayer(layer),
            content=json.loads(content),
            provenance={
                "run_id": run_id,
                "evidence_id": evidence_id,
                "policy_id": policy_id,
                "promoted_at": promoted_at,
            },
            confidence=confidence,
            created_at=promoted_at,
            deprecated=bool(deprecated),
        )

    # -- routing-decision record (operational log, not a memory layer) -------

    def record_routing_decision(self, decision: RoutingDecision) -> None:
        candidates = json.dumps(
            [
                {"capability_id": c.capability_id, "score": c.score, "excluded": c.excluded}
                for c in decision.candidates
            ]
        )
        with self._lock:
            self._db.execute(
                """INSERT INTO routing_decisions
                   (id, task_id, capability_type, policy_id, chosen, reason,
                    candidates, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.id, decision.task_id, decision.capability_type,
                    decision.policy_id, decision.chosen, decision.reason,
                    candidates, decision.created_at,
                ),
            )
            self._db.commit()

    def routing_decisions(self) -> list[RoutingDecision]:
        with self._lock:
            rows = self._db.execute(
                """SELECT id, task_id, capability_type, policy_id, chosen,
                          reason, candidates, created_at
                   FROM routing_decisions ORDER BY seq"""
            ).fetchall()
        return [
            RoutingDecision(
                id=row[0],
                task_id=row[1],
                capability_type=row[2],
                policy_id=row[3],
                chosen=row[4],
                reason=row[5],
                candidates=[CandidateEvaluation(**c) for c in json.loads(row[6])],
                created_at=row[7],
            )
            for row in rows
        ]
