"""GPS 同步接口测试。"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 移动端GPS接口 as gps_api
from app.api.移动端GPS接口 import GPSSampleSyncRequest
from app.services.mobile_gps_service import MobileGPSService


@pytest.fixture(autouse=True)
def reset_service(monkeypatch: pytest.MonkeyPatch) -> MobileGPSService:
    service = MobileGPSService()
    monkeypatch.setattr(gps_api, "mobile_gps_service", service)
    return service


def _compress_payload(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(gzip.compress(raw)).decode("ascii")


def test_decode_compressed_payload_gzip() -> None:
    payload = {
        "client_id": "client-a",
        "project_id": "project-a",
        "strategy": "latest-wins",
        "samples": [{"id": "s1", "latitude": 39.9, "longitude": 116.4, "accuracy": 1}],
    }

    req = GPSSampleSyncRequest(
        compression="gzip",
        encoding="base64",
        compressed_payload=_compress_payload(payload),
    )

    parsed = gps_api._decode_compressed_payload(req)
    assert parsed["client_id"] == "client-a"
    assert parsed["project_id"] == "project-a"
    assert len(parsed["samples"]) == 1


def test_decode_compressed_payload_unsupported_algo() -> None:
    gps_api.brotli = None
    req = GPSSampleSyncRequest(
        compression="brotli",
        encoding="base64",
        compressed_payload=base64.b64encode(b"abc").decode("ascii"),
    )

    with pytest.raises(HTTPException):
        gps_api._decode_compressed_payload(req)


def test_sync_batch_accepts_compressed_payload() -> None:
    payload = {
        "client_id": "client-a",
        "project_id": "project-a",
        "strategy": "latest-wins",
        "message_id": "batch-msg-1",
        "samples": [
            {
                "id": "s1",
                "project_id": "project-a",
                "latitude": 39.9,
                "longitude": 116.4,
                "accuracy": 1,
                "collected_at": 1000,
                "updated_at": 1000,
                "version": 1,
            }
        ],
    }

    req = GPSSampleSyncRequest(
        compression="gzip",
        encoding="base64",
        compressed_payload=_compress_payload(payload),
    )

    result = asyncio.run(gps_api.sync_batch(req))

    assert result["success"] is True
    assert result["applied"] == 1
    assert result["duplicate_message"] is False
    assert result["batch_size"] >= 1
    assert "rate_limit" in result


def test_sync_sensitive_verification_and_backup_restore() -> None:
    first = GPSSampleSyncRequest(
        client_id="client-a",
        project_id="project-a",
        strategy="latest-wins",
        samples=[
            {
                "id": "s1",
                "project_id": "project-a",
                "latitude": 39.9,
                "longitude": 116.4,
                "accuracy": 1,
                "collected_at": 1000,
                "updated_at": 1000,
                "version": 1,
            }
        ],
    )
    second = GPSSampleSyncRequest(
        client_id="client-a",
        project_id="project-a",
        strategy="latest-wins",
        samples=[
            {
                "id": "s1",
                "project_id": "project-a",
                "latitude": 39.9,
                "longitude": 116.4,
                "accuracy": 1.5,
                "collected_at": 7000,
                "updated_at": 2000,
                "version": 2,
            }
        ],
    )
    assert asyncio.run(gps_api.sync_batch(first))["applied"] == 1
    assert asyncio.run(gps_api.sync_batch(second))["applied"] == 1

    with pytest.raises(HTTPException):
        asyncio.run(gps_api.rollback("s1", gps_api.RollbackRequest(user_id="alice", verification_token="")))

    rollback_token = asyncio.run(
        gps_api.issue_verification_token(
            gps_api.SensitiveOperationTokenRequest(user_id="alice", action="rollback", ttl_seconds=300)
        )
    )["token"]
    rollback_result = asyncio.run(
        gps_api.rollback("s1", gps_api.RollbackRequest(user_id="alice", verification_token=rollback_token))
    )
    assert rollback_result["success"] is True
    assert rollback_result["sample"]["version"] == 1

    backup = asyncio.run(gps_api.create_sync_backup(gps_api.BackupCreateRequest(mode="full", user_id="alice")))
    backup_id = backup["backup"]["backup_id"]

    # 先改写状态，再验证恢复
    third = GPSSampleSyncRequest(
        client_id="client-a",
        project_id="project-a",
        strategy="latest-wins",
        samples=[
            {
                "id": "s1",
                "project_id": "project-a",
                "latitude": 39.9,
                "longitude": 116.4,
                "accuracy": 1.8,
                "collected_at": 13000,
                "updated_at": 4000,
                "version": 2,
            }
        ],
    )
    assert asyncio.run(gps_api.sync_batch(third))["applied"] == 1

    with pytest.raises(HTTPException):
        asyncio.run(
            gps_api.restore_sync_backup(
                backup_id,
                gps_api.BackupRestoreRequest(user_id="alice", verification_token=""),
            )
        )

    restore_token = asyncio.run(
        gps_api.issue_verification_token(
            gps_api.SensitiveOperationTokenRequest(user_id="alice", action="restore_backup", ttl_seconds=300)
        )
    )["token"]
    restored = asyncio.run(
        gps_api.restore_sync_backup(
            backup_id,
            gps_api.BackupRestoreRequest(user_id="alice", verification_token=restore_token),
        )
    )
    assert restored["success"] is True
    assert restored["restored_samples"] >= 1

    audit_integrity = asyncio.run(gps_api.verify_audit_integrity())
    assert audit_integrity["success"] is True
    assert audit_integrity["valid"] is True
