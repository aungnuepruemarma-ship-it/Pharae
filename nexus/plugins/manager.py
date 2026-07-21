"""Plugin lifecycle: install, disable/enable, update, remove.

Install is validate-everything-then-register: schema validation, permission
review against the manager's allowlist, cross-plugin capability-name
collision checks, and entrypoint loading all happen before the registry or
runtime is touched — a rejected plugin leaves no trace.

Entrypoint contract: ``"module.path:setup"`` where ``setup()`` returns
``{capability_name: handler}`` covering exactly the package's capabilities.
Handlers are registered under capability ids ("name@version"), so multiple
capabilities of one capability type coexist and the router's binding decides
which handler runs.

Permissions are fixed at install time — the manager grants what the package
requested and nothing more; there is no escalation API. In-process handlers
receiving only their RunContext is the structural expression of that; hard
enforcement arrives with the security layer.
"""

from __future__ import annotations

import copy
import importlib
import time
from dataclasses import dataclass, field
from enum import Enum

from nexus.capabilities.registry import CapabilityRegistry, RegistrationStatus
from nexus.kernel.events import EventBus
from nexus.kernel.runtime import Handler, Runtime
from nexus.schemas.plugin import PluginPackage


class PluginError(Exception):
    pass


class PluginStatus(str, Enum):
    INSTALLED = "installed"
    DISABLED = "disabled"
    REMOVED = "removed"


@dataclass
class PluginRecord:
    package: PluginPackage
    status: PluginStatus = PluginStatus.INSTALLED
    installed_at: float = field(default_factory=time.time)
    capability_ids: list[str] = field(default_factory=list)
    previous_versions: list[str] = field(default_factory=list)


class PluginManager:
    def __init__(
        self,
        registry: CapabilityRegistry,
        runtime: Runtime,
        bus: EventBus | None = None,
        allowed_permissions: set[str] | None = None,
    ) -> None:
        self._registry = registry
        self._runtime = runtime
        self._bus = bus
        self._allowed = allowed_permissions
        self._plugins: dict[str, PluginRecord] = {}

    # -- install -------------------------------------------------------------

    def install(self, package: PluginPackage) -> PluginRecord:
        existing = self._plugins.get(package.name)
        if existing is not None and existing.status is not PluginStatus.REMOVED:
            raise PluginError(
                f"plugin {package.name!r} is already installed (use update)"
            )
        handlers = self._validate_and_load(package)
        record = self._wire(package, handlers)
        if existing is not None:  # reinstall after removal keeps history
            record.previous_versions = existing.previous_versions + [
                existing.package.version
            ]
        self._plugins[package.name] = record
        self._publish("plugin.installed", record)
        return record

    def update(self, package: PluginPackage) -> PluginRecord:
        """Side-by-side swap: validate and load the new version fully, then
        retire the old capabilities and wire the new ones."""
        current = self._plugins.get(package.name)
        if current is None or current.status is PluginStatus.REMOVED:
            raise PluginError(f"plugin {package.name!r} is not installed")
        if package.version == current.package.version:
            raise PluginError(
                f"plugin {package.name!r} is already at version {package.version}"
            )
        handlers = self._validate_and_load(package, ignore_owner=package.name)
        self._unwire(current)
        record = self._wire(package, handlers)
        record.previous_versions = current.previous_versions + [current.package.version]
        self._plugins[package.name] = record
        self._publish("plugin.updated", record)
        return record

    # -- lifecycle -----------------------------------------------------------

    def disable(self, name: str) -> None:
        record = self._require(name, PluginStatus.INSTALLED)
        self._unwire(record)
        record.status = PluginStatus.DISABLED
        self._publish("plugin.disabled", record)

    def enable(self, name: str) -> None:
        record = self._require(name, PluginStatus.DISABLED)
        handlers = self._load_handlers(record.package)
        self._wire(record.package, handlers, record=record)
        record.status = PluginStatus.INSTALLED
        self._publish("plugin.enabled", record)

    def remove(self, name: str) -> None:
        """Deregisters capabilities and handlers. Registry records stay,
        retired — durable history is never deleted."""
        record = self._plugins.get(name)
        if record is None or record.status is PluginStatus.REMOVED:
            raise PluginError(f"plugin {name!r} is not installed")
        if record.status is PluginStatus.INSTALLED:
            self._unwire(record)
        record.status = PluginStatus.REMOVED
        self._publish("plugin.removed", record)

    # -- queries -------------------------------------------------------------

    def get(self, name: str) -> PluginRecord | None:
        record = self._plugins.get(name)
        return copy.deepcopy(record) if record else None

    def list(self, include_removed: bool = False) -> list[PluginRecord]:
        return copy.deepcopy(
            [
                r
                for r in self._plugins.values()
                if include_removed or r.status is not PluginStatus.REMOVED
            ]
        )

    # -- internals -----------------------------------------------------------

    def _validate_and_load(
        self, package: PluginPackage, ignore_owner: str | None = None
    ) -> dict[str, Handler]:
        errors = package.validate()
        if self._allowed is not None:
            excess = set(package.requested_permissions) - self._allowed
            if excess:
                errors.append(
                    f"permissions not allowed by policy: {sorted(excess)}"
                )
        for manifest in package.capabilities:
            owner = self._capability_owner(manifest.name)
            if owner is not None and owner != ignore_owner:
                errors.append(
                    f"capability {manifest.name!r} is already provided by "
                    f"plugin {owner!r}"
                )
        if errors:
            raise PluginError(f"plugin rejected: {'; '.join(errors)}")
        return self._load_handlers(package)

    def _capability_owner(self, capability_name: str) -> str | None:
        for record in self._plugins.values():
            if record.status is PluginStatus.REMOVED:
                continue
            if any(m.name == capability_name for m in record.package.capabilities):
                return record.package.name
        return None

    @staticmethod
    def _load_handlers(package: PluginPackage) -> dict[str, Handler]:
        module_path, _, attr = package.entrypoint.partition(":")
        try:
            module = importlib.import_module(module_path)
            setup = getattr(module, attr)
            handlers = setup()
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                f"entrypoint {package.entrypoint!r} failed: {exc!r}"
            ) from exc
        expected = {m.name for m in package.capabilities}
        if not isinstance(handlers, dict) or not all(
            callable(h) for h in handlers.values()
        ):
            raise PluginError(
                f"entrypoint {package.entrypoint!r} must return "
                "{capability_name: handler}"
            )
        if set(handlers) != expected:
            raise PluginError(
                f"entrypoint handlers {sorted(handlers)} do not match the "
                f"package's capabilities {sorted(expected)}"
            )
        return handlers

    def _wire(
        self,
        package: PluginPackage,
        handlers: dict[str, Handler],
        record: PluginRecord | None = None,
    ) -> PluginRecord:
        capability_ids = []
        for manifest in package.capabilities:
            capability_ids.append(self._registry.register(manifest))
        for manifest in package.capabilities:
            self._runtime.register_handler(
                f"{manifest.name}@{manifest.version}", handlers[manifest.name]
            )
        if record is None:
            record = PluginRecord(package=package, capability_ids=capability_ids)
        else:
            record.capability_ids = capability_ids
        return record

    def _unwire(self, record: PluginRecord) -> None:
        for manifest in record.package.capabilities:
            registered = self._registry.get(manifest.name, manifest.version)
            if registered is not None and registered.status is RegistrationStatus.ACTIVE:
                self._registry.retire(manifest.name, manifest.version)
            self._runtime.unregister_handler(f"{manifest.name}@{manifest.version}")

    def _require(self, name: str, status: PluginStatus) -> PluginRecord:
        record = self._plugins.get(name)
        if record is None or record.status is not status:
            current = record.status.value if record else "not installed"
            raise PluginError(f"plugin {name!r} is {current}, expected {status.value}")
        return record

    def _publish(self, topic: str, record: PluginRecord) -> None:
        if self._bus is not None:
            self._bus.publish(
                topic,
                {
                    "plugin": record.package.name,
                    "version": record.package.version,
                    "capabilities": list(record.capability_ids),
                },
            )
