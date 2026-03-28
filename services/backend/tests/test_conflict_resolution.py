"""GPS 冲突解决与回滚测试。"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.mobile_gps_service import MobileGPSService


def _sample(sample_id: str, version: int, updated_at: int, value: int) -> dict:
    return {
        "id": sample_id,
        "project_id": "proj-conflict",
        "latitude": 39.9,
        "longitude": 116.4,
        "accuracy": 3,
        "attributes": {"v": value},
        "collected_at": updated_at * 10,
        "updated_at": updated_at,
        "version": version,
    }


def test_latest_wins_prefers_newer_timestamp() -> None:
    service = MobileGPSService()
    service.upsert_samples("client", [_sample("s1", 1, 1000, 1)], strategy="latest-wins")

    result = service.upsert_samples("client", [_sample("s1", 1, 900, 2)], strategy="latest-wins")

    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert service.samples["s1"]["attributes"]["v"] == 1


def test_client_wins_overrides_server_value() -> None:
    service = MobileGPSService()
    service.upsert_samples("client", [_sample("s1", 2, 1000, 1)], strategy="latest-wins")

    result = service.upsert_samples("client", [_sample("s1", 1, 900, 9)], strategy="client-wins")

    assert result["applied"] == 1
    assert service.samples["s1"]["attributes"]["v"] == 9


def test_manual_strategy_records_conflict_items() -> None:
    service = MobileGPSService()
    service.upsert_samples("client", [_sample("s1", 2, 1000, 1)], strategy="latest-wins")

    result = service.upsert_samples("client", [_sample("s1", 1, 900, 2)], strategy="manual")

    assert result["conflicts"] == 1
    assert len(result["conflict_items"]) == 1


def test_rollback_restores_previous_version() -> None:
    service = MobileGPSService()
    service.upsert_samples("client", [_sample("s1", 1, 1000, 1)], strategy="latest-wins")
    service.upsert_samples("client", [_sample("s1", 2, 2000, 2)], strategy="latest-wins")

    rolled = service.rollback("s1", to_version=1)

    assert rolled["version"] == 1
    assert rolled["attributes"]["v"] == 1
