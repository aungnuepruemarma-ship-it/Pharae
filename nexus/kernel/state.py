"""State manager: namespaced key-value state with snapshot/restore.

Snapshots are deep copies — the checkpointing primitive behind recovery and
resume (docs/volume-2-modules/kernel.md). Mutating live state never corrupts
a taken snapshot, and restoring never aliases the snapshot into live state.
"""

from __future__ import annotations

import copy
from typing import Any

_MISSING = object()


class StateManager:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def set(self, namespace: str, key: str, value: Any) -> None:
        self._data.setdefault(namespace, {})[key] = value

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        return self._data.get(namespace, {}).get(key, default)

    def delete(self, namespace: str, key: str) -> bool:
        ns = self._data.get(namespace)
        if ns is not None and ns.pop(key, _MISSING) is not _MISSING:
            return True
        return False

    def namespace(self, namespace: str) -> dict[str, Any]:
        """A shallow copy of one namespace's contents."""
        return dict(self._data.get(namespace, {}))

    def namespaces(self) -> list[str]:
        return sorted(self._data)

    def clear_namespace(self, namespace: str) -> None:
        self._data.pop(namespace, None)

    def snapshot(self, namespace: str | None = None) -> dict[str, Any]:
        """Deep-copied checkpoint of one namespace, or of everything."""
        if namespace is not None:
            return copy.deepcopy(self._data.get(namespace, {}))
        return copy.deepcopy(self._data)

    def restore(self, snapshot: dict[str, Any], namespace: str | None = None) -> None:
        """Replace one namespace (or the whole store) with a snapshot."""
        if namespace is not None:
            self._data[namespace] = copy.deepcopy(snapshot)
        else:
            self._data = copy.deepcopy(snapshot)
