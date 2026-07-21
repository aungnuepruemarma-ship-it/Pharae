import unittest

from nexus.capabilities import (
    CapabilityRegistry,
    HealthStatus,
    RegistrationStatus,
    RegistryError,
)
from nexus.kernel.events import EventBus
from nexus.schemas.capability import CapabilityManifest
from nexus.schemas.core import Evidence


def manifest(name="browser.playwright", ctype="browser", version="1.0.0", **overrides):
    base = dict(
        name=name,
        capability_type=ctype,
        version=version,
        permissions=["net.fetch"],
        cost=1.0,
        latency_ms=100.0,
        reliability=0.5,
        trust_score=0.2,
    )
    base.update(overrides)
    return CapabilityManifest(**base)


def evidence(verified=True, confidence=0.9):
    return Evidence(id="ev-1", run_id="run-1", verified=verified, confidence=confidence)


class TestRegistration(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry(bus=self.bus)

    def test_register_returns_id_and_emits_event(self):
        cap_id = self.registry.register(manifest())
        self.assertEqual(cap_id, "browser.playwright@1.0.0")
        events = self.bus.log("capability.registered")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["capability"], cap_id)
        self.assertEqual(events[0].payload["capability_type"], "browser")

    def test_rejects_invalid_manifest_with_reasons(self):
        with self.assertRaises(RegistryError) as ctx:
            self.registry.register(manifest(version="not-semver"))
        self.assertIn("semver", str(ctx.exception))

    def test_rejects_duplicate_name_version(self):
        self.registry.register(manifest())
        with self.assertRaises(RegistryError):
            self.registry.register(manifest())

    def test_versions_coexist(self):
        self.registry.register(manifest(version="1.0.0"))
        self.registry.register(manifest(version="1.1.0"))
        self.assertIsNotNone(self.registry.get("browser.playwright", "1.0.0"))
        self.assertIsNotNone(self.registry.get("browser.playwright", "1.1.0"))

    def test_get_without_version_returns_latest_active(self):
        self.registry.register(manifest(version="1.2.0"))
        self.registry.register(manifest(version="1.10.0"))  # numeric, not lexical
        record = self.registry.get("browser.playwright")
        self.assertEqual(record.manifest.version, "1.10.0")

    def test_rejects_permissions_outside_allowlist(self):
        registry = CapabilityRegistry(allowed_permissions={"net.fetch"})
        with self.assertRaises(RegistryError) as ctx:
            registry.register(manifest(permissions=["net.fetch", "fs.write"]))
        self.assertIn("fs.write", str(ctx.exception))

    def test_rejects_unknown_capability_type_when_vocabulary_fixed(self):
        registry = CapabilityRegistry(known_types={"browser", "code"})
        registry.register(manifest())  # browser: allowed
        with self.assertRaises(RegistryError):
            registry.register(manifest(name="x.y", ctype="teleportation"))

    def test_registry_stores_a_copy(self):
        m = manifest()
        self.registry.register(m)
        m.trust_score = 0.99  # caller mutates their object after registration
        self.assertEqual(self.registry.get("browser.playwright").manifest.trust_score, 0.2)

    def test_returned_records_are_copies(self):
        self.registry.register(manifest())
        self.registry.get("browser.playwright").manifest.trust_score = 0.99
        self.assertEqual(self.registry.get("browser.playwright").manifest.trust_score, 0.2)


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.registry.register(manifest(name="browser.playwright", ctype="browser"))
        self.registry.register(manifest(name="browser.selenium", ctype="browser"))
        self.registry.register(manifest(name="python.local", ctype="code"))

    def test_find_by_type(self):
        found = self.registry.find("browser")
        self.assertEqual(
            [r.manifest.name for r in found],
            ["browser.playwright", "browser.selenium"],  # deterministic name order
        )

    def test_find_unknown_type_is_empty(self):
        self.assertEqual(self.registry.find("teleportation"), [])

    def test_types_lists_active_vocabulary(self):
        self.assertEqual(self.registry.types(), ["browser", "code"])


class TestRetirement(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry(bus=self.bus)
        self.registry.register(manifest(version="1.0.0"))
        self.registry.register(manifest(version="2.0.0"))

    def test_retire_excludes_from_find_but_keeps_record(self):
        self.registry.retire("browser.playwright", "2.0.0")
        found = self.registry.find("browser")
        self.assertEqual([r.manifest.version for r in found], ["1.0.0"])
        record = self.registry.get("browser.playwright", "2.0.0")
        self.assertIs(record.status, RegistrationStatus.RETIRED)
        self.assertEqual(len(self.bus.log("capability.retired")), 1)

    def test_get_latest_skips_retired(self):
        self.registry.retire("browser.playwright", "2.0.0")
        self.assertEqual(self.registry.get("browser.playwright").manifest.version, "1.0.0")

    def test_retire_is_idempotent_but_unknown_errors(self):
        self.registry.retire("browser.playwright", "2.0.0")
        self.registry.retire("browser.playwright", "2.0.0")  # no-op
        self.assertEqual(len(self.bus.log("capability.retired")), 1)
        with self.assertRaises(RegistryError):
            self.registry.retire("ghost", "1.0.0")


class TestHealth(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.registry = CapabilityRegistry(bus=self.bus)

    def test_health_starts_unknown(self):
        self.registry.register(manifest())
        self.assertIs(self.registry.get("browser.playwright").health, HealthStatus.UNKNOWN)

    def test_probe_success_and_failure(self):
        healthy = {"value": True}
        self.registry.register(manifest(), health_probe=lambda: healthy["value"])
        self.assertIs(
            self.registry.check_health("browser.playwright", "1.0.0"), HealthStatus.HEALTHY
        )
        healthy["value"] = False
        self.assertIs(
            self.registry.check_health("browser.playwright", "1.0.0"), HealthStatus.UNHEALTHY
        )

    def test_probe_exception_means_unhealthy_not_crash(self):
        def probe():
            raise ConnectionError("down")

        self.registry.register(manifest(), health_probe=probe)
        self.assertIs(
            self.registry.check_health("browser.playwright", "1.0.0"), HealthStatus.UNHEALTHY
        )

    def test_unhealthy_remains_registered_and_findable_but_flagged(self):
        self.registry.register(manifest(), health_probe=lambda: False)
        self.registry.check_health("browser.playwright", "1.0.0")
        found = self.registry.find("browser")
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].health, HealthStatus.UNHEALTHY)
        self.assertEqual(self.registry.find("browser", healthy_only=True), [])

    def test_health_change_emits_event_once_per_transition(self):
        self.registry.register(manifest(), health_probe=lambda: True)
        self.registry.check_health("browser.playwright", "1.0.0")
        self.registry.check_health("browser.playwright", "1.0.0")  # no change
        events = self.bus.log("capability.health")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["health"], "healthy")

    def test_check_all_health(self):
        self.registry.register(manifest(name="a.b", ctype="code"), health_probe=lambda: True)
        self.registry.register(manifest(name="c.d", ctype="code"))  # no probe
        results = self.registry.check_all_health()
        self.assertIs(results["a.b@1.0.0"], HealthStatus.HEALTHY)
        self.assertIs(results["c.d@1.0.0"], HealthStatus.UNKNOWN)


class TestScoreGating(unittest.TestCase):
    """Invariant I2: only verified evidence moves reliability/trust."""

    def setUp(self):
        self.registry = CapabilityRegistry()
        self.registry.register(manifest())

    def test_verified_success_raises_scores(self):
        before = self.registry.get("browser.playwright").manifest
        self.registry.record_outcome(
            "browser.playwright", "1.0.0", evidence=evidence(), success=True
        )
        after = self.registry.get("browser.playwright").manifest
        self.assertGreater(after.reliability, before.reliability)
        self.assertGreater(after.trust_score, before.trust_score)

    def test_verified_failure_lowers_scores(self):
        before = self.registry.get("browser.playwright").manifest
        self.registry.record_outcome(
            "browser.playwright", "1.0.0", evidence=evidence(), success=False
        )
        after = self.registry.get("browser.playwright").manifest
        self.assertLess(after.reliability, before.reliability)
        self.assertLess(after.trust_score, before.trust_score)

    def test_unverified_evidence_is_rejected_and_scores_unchanged(self):
        before = self.registry.get("browser.playwright").manifest
        with self.assertRaises(RegistryError):
            self.registry.record_outcome(
                "browser.playwright", "1.0.0", evidence=evidence(verified=False), success=True
            )
        after = self.registry.get("browser.playwright").manifest
        self.assertEqual(after.reliability, before.reliability)
        self.assertEqual(after.trust_score, before.trust_score)

    def test_scores_stay_in_unit_interval(self):
        for _ in range(50):
            self.registry.record_outcome(
                "browser.playwright", "1.0.0", evidence=evidence(), success=True
            )
        m = self.registry.get("browser.playwright").manifest
        self.assertLessEqual(m.reliability, 1.0)
        self.assertLessEqual(m.trust_score, 1.0)

    def test_updates_are_deterministic(self):
        r2 = CapabilityRegistry()
        r2.register(manifest())
        self.registry.record_outcome("browser.playwright", "1.0.0", evidence=evidence(), success=True)
        r2.record_outcome("browser.playwright", "1.0.0", evidence=evidence(), success=True)
        self.assertEqual(
            self.registry.get("browser.playwright").manifest.reliability,
            r2.get("browser.playwright").manifest.reliability,
        )


if __name__ == "__main__":
    unittest.main()
