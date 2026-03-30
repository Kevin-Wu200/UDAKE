"""GPS 功能/性能/稳定性验证清单（自动化基线）。"""

from __future__ import annotations

import time

from app.services.mobile_gps_service import MobileGPSService


def _sample(idx: int, *, project_id: str = "proj-check") -> dict:
    now = int(time.time() * 1000)
    return {
        "id": f"s_{idx}",
        "project_id": project_id,
        "latitude": 39.9 + idx * 0.00001,
        "longitude": 116.4 + idx * 0.00001,
        "accuracy": 4.0,
        "collected_at": now + idx * 10,
        "updated_at": now + idx * 10,
        "version": 1,
    }


def test_sync_latency_under_3_seconds() -> None:
    service = MobileGPSService()
    started = time.perf_counter()
    service.upsert_samples("client-latency", [_sample(1)], strategy="latest-wins")
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0


def test_offline_queue_equivalent_100_samples() -> None:
    service = MobileGPSService()
    samples = [_sample(i) for i in range(100)]
    result = service.upsert_samples("client-offline", samples, strategy="latest-wins")
    assert result["applied"] == 100
    assert result["conflicts"] == 0


def test_batch_sync_1000_under_10_seconds() -> None:
    service = MobileGPSService()
    samples = [_sample(i) for i in range(1000)]
    started = time.perf_counter()
    result = service.upsert_samples("client-batch", samples, strategy="latest-wins", batch_size=1000)
    elapsed = time.perf_counter() - started
    assert result["applied"] == 1000
    assert elapsed < 10.0


def test_conflict_detection_accuracy_above_95_percent() -> None:
    service = MobileGPSService()
    total_cases = 100
    expected_conflicts = 0
    detected_conflicts = 0

    for i in range(total_cases):
        base = _sample(i)
        service.upsert_samples("client-a", [base], strategy="latest-wins")
        incoming = dict(base)
        incoming["version"] = 1
        incoming["updated_at"] = base["updated_at"] - 1  # 触发同版本陈旧冲突
        incoming["collected_at"] = base["collected_at"] + 6000
        incoming["accuracy"] = base["accuracy"] + 1
        expected_conflicts += 1
        result = service.upsert_samples("client-b", [incoming], strategy="manual")
        detected_conflicts += result["conflicts"]

    accuracy = detected_conflicts / max(1, expected_conflicts)
    assert accuracy >= 0.95


def test_audit_integrity_and_backup_restore_stability() -> None:
    service = MobileGPSService()
    service.upsert_samples("client-sec", [_sample(1)], strategy="latest-wins")
    backup = service.create_backup(mode="full", user_id="qa-user")
    token = service.issue_sensitive_operation_token("qa-user", "restore_backup")["token"]
    assert service.verify_sensitive_operation_token(token, "qa-user", "restore_backup") is True
    restored = service.restore_backup(backup["backup_id"], user_id="qa-user")
    assert restored["restored_samples"] >= 1
    integrity = service.verify_audit_integrity()
    assert integrity["valid"] is True
