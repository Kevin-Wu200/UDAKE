"""GPS 同步接口测试。"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import sys
from pathlib import Path

import pytest

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
    req = GPSSampleSyncRequest(
        compression="brotli",
        encoding="base64",
        compressed_payload=base64.b64encode(b"abc").decode("ascii"),
    )

    with pytest.raises(Exception):
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
