"""Unit tests for key validation security/support modules."""

from __future__ import annotations

from app.audit.audit_logger import ProductKeyAuditLogger
from app.cache.validation_cache import ValidationCacheManager
from app.monitoring.alerting import ValidationAlerting
from app.monitoring.metrics import ValidationMetrics
from app.security.data_masking import mask_ip, mask_product_key
from app.security.ip_reputation import IPReputationService


class InMemoryCache:
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ttl=None):
        self._store[key] = value
        return True

    def delete(self, key):
        self._store.pop(key, None)
        return True


def test_validation_cache_metrics_and_invalidate():
    cache = InMemoryCache()
    manager = ValidationCacheManager(cache, ttl_seconds=60)

    assert manager.get("A") is None
    manager.set("A", {"valid": True, "key_type": "personal_standard", "message": "ok"})
    assert manager.get("A") is not None
    manager.invalidate("A")
    assert manager.get("A") is None

    metrics = manager.metrics()
    assert metrics["hits"] >= 1
    assert metrics["misses"] >= 1


def test_ip_reputation_blacklist_and_whitelist_flow():
    cache = InMemoryCache()
    svc = IPReputationService(cache, default_score=50, blacklist_threshold=20, whitelist_threshold=60)

    assert svc.check("1.1.1.1").allowed is True
    svc.record_success("1.1.1.1")
    svc.record_success("1.1.1.1")
    svc.record_success("1.1.1.1")
    svc.record_success("1.1.1.1")
    svc.record_success("1.1.1.1")
    assert svc.check("1.1.1.1").reason == "whitelisted"

    for _ in range(20):
        svc.record_rate_limited("2.2.2.2")
    decision = svc.check("2.2.2.2")
    assert decision.allowed is False
    assert decision.reason == "blacklisted"


def test_audit_logger_masks_sensitive_fields():
    cache = InMemoryCache()
    logger = ProductKeyAuditLogger(cache)
    row = logger.append(
        ip_address="10.10.10.10",
        user_agent="pytest",
        product_key="abc-1234-5678-9xyz",
        valid=False,
        reason="invalid",
        key_type=None,
        processing_time_ms=12,
    )
    assert row["ip_address"].endswith("***.***")
    assert "*" in row["product_key"]


def test_data_masking_helpers():
    assert mask_product_key("uda-1234-5678-9xyz").startswith("UDA")
    assert mask_ip("192.168.1.20").startswith("192.168")


def test_metrics_and_alerting_workflow():
    cache = InMemoryCache()
    metrics = ValidationMetrics()
    for _ in range(40):
        metrics.record(valid=False, processing_time_ms=800, is_error=True)

    snapshot = metrics.snapshot()
    alerting = ValidationAlerting(cache)
    alerts = alerting.evaluate(snapshot, cache_hit_rate=0.1)
    assert len(alerts) >= 1
    latest = alerting.latest(limit=10)
    assert latest
