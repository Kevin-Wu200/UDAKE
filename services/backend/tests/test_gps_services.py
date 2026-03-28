"""GPS 服务层测试。"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.mobile_gps_service import MobileGPSService


def _sample(sample_id: str, updated_at: int = 1000, collected_at: int = 1000) -> dict:
    return {
        "id": sample_id,
        "project_id": "proj-a",
        "latitude": 39.9042,
        "longitude": 116.4074,
        "accuracy": 4.2,
        "collected_at": collected_at,
        "updated_at": updated_at,
        "version": 1,
        "source": "mobile",
    }


def test_upsert_and_summary() -> None:
    service = MobileGPSService()

    result = service.upsert_samples("client-1", [_sample("s1")], strategy="latest-wins")

    assert result["applied"] == 1
    assert result["skipped"] == 0
    summary = service.get_summary(project_id="proj-a")
    assert summary["total_samples"] == 1


def test_message_id_idempotent() -> None:
    service = MobileGPSService()
    payload = [_sample("s1")]

    first = service.upsert_samples("client-1", payload, strategy="latest-wins", message_id="msg-1")
    second = service.upsert_samples("client-1", payload, strategy="latest-wins", message_id="msg-1")

    assert first["duplicate_message"] is False
    assert second["duplicate_message"] is True
    assert second["applied"] == 0


def test_duplicate_samples_are_filtered_by_fingerprint() -> None:
    service = MobileGPSService()

    s1 = _sample("s1", updated_at=1000, collected_at=15000)
    s2 = _sample("s2", updated_at=1001, collected_at=15001)

    result = service.upsert_samples("client-1", [s1, s2], strategy="latest-wins")

    assert result["applied"] == 1
    assert result["duplicate_samples"] == 1


def test_batch_upsert_supports_large_payload() -> None:
    service = MobileGPSService()
    samples = [_sample(f"s{i}", updated_at=1000 + i, collected_at=20000 + i * 10000) for i in range(1205)]

    result = service.upsert_samples("client-1", samples, strategy="latest-wins", batch_size=1000)

    assert result["applied"] == 1205
    assert result["conflicts"] == 0
