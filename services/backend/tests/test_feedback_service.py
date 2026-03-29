"""Unit tests for feedback collection service."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.feedback_service import FeedbackService


def _make_user(service: FeedbackService, username: str, role: str = "contributor") -> str:
    user = service.register_user(
        {
            "username": username,
            "password": "pass1234",
            "role": role,
            "display_name": username,
            "domain": "environment",
        }
    )
    return user["user_id"]


@pytest.fixture
def service() -> FeedbackService:
    return FeedbackService()


def test_user_register_auth_and_leaderboard(service: FeedbackService) -> None:
    uid = _make_user(service, "alice")

    login = service.authenticate_user("alice", "pass1234")
    assert login["token"].startswith("sess_")
    assert login["user"]["user_id"] == uid

    reliability = service.get_user_reliability(uid)
    assert 0 <= reliability["reliability_score"] <= 1

    leaderboard = service.get_leaderboard(metric="contribution", top_n=10)
    assert isinstance(leaderboard, list)
    assert len(leaderboard) >= 1


def test_feedback_flow_conflict_and_versioning(service: FeedbackService) -> None:
    user_a = _make_user(service, "bob")
    user_b = _make_user(service, "cathy")
    admin_id = service.resolve_user_id()

    input_record = service.submit_input(
        {
            "dataset_id": "dataset_alpha",
            "x": 120.1,
            "y": 30.2,
            "z": 0.0,
            "value": 18.5,
            "timestamp": "2026-03-20T10:00:00+00:00",
            "device": "sensor-A",
            "method": "manual",
            "source": "field",
            "quality_flag": "good",
            "metadata": {"scene": "test"},
        },
        user_a,
    )
    target_id = input_record["id"]

    mod_a = service.submit_modification(
        {
            "target_record_id": target_id,
            "new_value": 19.0,
            "reason": "update",
            "note": "first change",
        },
        user_a,
    )
    assert mod_a["type"] == "modification"

    mod_b = service.submit_modification(
        {
            "target_record_id": target_id,
            "new_value": 21.0,
            "reason": "correction",
            "note": "second change",
        },
        user_b,
    )
    assert mod_b["type"] == "modification"

    conflicts = service.get_conflicts(user_id=admin_id, unresolved_only=True)
    assert conflicts["count"] >= 1
    conflict_id = conflicts["items"][0]["conflict_id"]

    resolved = service.resolve_conflict(conflict_id, strategy="quality", user_id=admin_id)
    assert resolved["status"] == "resolved"

    validation = service.submit_validation(
        {
            "target_record_id": target_id,
            "predicted_value": 20.0,
            "result": "accept",
            "confidence": 0.88,
            "context": {"position": "A1", "scenario": "baseline"},
        },
        user_a,
    )
    assert validation["type"] == "validation"

    annotation = service.submit_annotation(
        {
            "target_record_id": target_id,
            "anomaly_type": "spatial_outlier",
            "severity": 4,
            "quality_grade": "B",
            "label": "outlier",
            "reason": "manual review",
        },
        user_b,
    )
    assert annotation["type"] == "annotation"

    history = service.get_history(target_id, user_id=admin_id)
    assert history["count"] >= 2

    compare = service.compare_versions(target_id, from_version=1, to_version=2, user_id=admin_id)
    assert compare["change_count"] >= 1

    rolled = service.rollback_version(target_id, version=1, user_id=admin_id)
    assert rolled["id"] == target_id


def test_batch_query_export_backup_archive(service: FeedbackService) -> None:
    user_id = _make_user(service, "derek", role="reviewer")
    admin_id = service.resolve_user_id()

    csv_content = "dataset_id,x,y,z,value,timestamp,source,device,method,quality_flag\n" \
        "dataset_beta,120.1,30.1,0,10.5,2026-03-01T00:00:00+00:00,csv,s1,batch,good\n" \
        "dataset_beta,120.2,30.2,0,11.0,2026-03-02T00:00:00+00:00,csv,s2,batch,good\n"

    result = service.import_batch(
        {
            "dataset_id": "dataset_beta",
            "format": "csv",
            "content": csv_content,
            "mapping": {},
        },
        user_id,
    )
    assert result["imported"] == 2

    queried = service.query_data(
        {
            "dataset_id": "dataset_beta",
            "record_type": "input",
            "limit": 20,
            "offset": 0,
        },
        user_id=admin_id,
    )
    assert queried["count"] >= 2

    export_csv = service.export_data(
        "csv",
        {"dataset_id": "dataset_beta", "record_type": "input", "limit": 50, "offset": 0},
        user_id=admin_id,
    )
    assert export_csv["format"] == "csv"
    assert "dataset_id" in export_csv["content"]

    backup = service.create_backup(mode="full", user_id=admin_id)
    assert backup["backup_id"].startswith("bak_")

    archive = service.archive_before(before="2027-01-01T00:00:00+00:00", user_id=admin_id)
    assert archive["moved"] >= 2

    restore = service.restore_backup(backup["backup_id"], user_id=admin_id)
    assert restore["backup_id"] == backup["backup_id"]


def test_integration_ingest(service: FeedbackService) -> None:
    user_id = _make_user(service, "eva")

    base = service.submit_input(
        {
            "dataset_id": "dataset_gamma",
            "x": 121.1,
            "y": 31.1,
            "z": 0,
            "value": 12.3,
            "timestamp": "2026-03-10T00:00:00+00:00",
            "source": "sensor",
            "device": "s1",
            "method": "manual",
            "quality_flag": "ok",
            "metadata": {},
        },
        user_id,
    )

    realtime = service.ingest_integration_feedback(
        "realtime_interpolation",
        {
            "dataset_id": "dataset_gamma",
            "x": 121.2,
            "y": 31.2,
            "observed_value": 13.2,
            "predicted_value": 13.0,
            "error": 0.2,
            "timestamp": "2026-03-10T01:00:00+00:00",
        },
        user_id,
    )
    assert "input" in realtime

    uncertainty = service.ingest_integration_feedback(
        "uncertainty_dashboard",
        {
            "target_record_id": base["id"],
            "predicted_value": 12.2,
            "result": "correct",
            "confidence": 0.75,
            "corrected_value": 12.25,
            "uncertainty": 0.12,
        },
        user_id,
    )
    assert "validation" in uncertainty


def test_invalid_import_format(service: FeedbackService) -> None:
    user_id = _make_user(service, "frank")
    with pytest.raises(ValueError):
        service.import_batch(
            {
                "dataset_id": "dataset_x",
                "format": "xml",
                "content": "<xml />",
            },
            user_id,
        )


def _legacy_xor_encrypt(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    key = b"udake-feedback-key-v1"
    encrypted = bytes(raw[idx] ^ key[idx % len(key)] for idx in range(len(raw)))
    return base64.b64encode(encrypted).decode("utf-8")


def test_encrypt_payload_supports_legacy_and_tamper_detection(service: FeedbackService) -> None:
    payload = {"dataset_id": "legacy", "value": 1.23}

    encrypted = service._encrypt_payload(payload)  # type: ignore[attr-defined]
    assert encrypted.startswith("fbenc:v1:")
    assert service._decrypt_payload(encrypted) == payload  # type: ignore[attr-defined]

    parts = encrypted.split(":")
    parts[-1] = f"{parts[-1][:-2]}AA"
    with pytest.raises(ValueError):
        service._decrypt_payload(":".join(parts))  # type: ignore[attr-defined]

    legacy = _legacy_xor_encrypt(payload)
    assert service._decrypt_payload(legacy) == payload  # type: ignore[attr-defined]


def test_encryption_key_rotation_masking_and_access_audit(service: FeedbackService) -> None:
    user_id = _make_user(service, "greg")
    admin_id = service.resolve_user_id()

    record = service.submit_input(
        {
            "dataset_id": "secure_dataset",
            "x": 120.1,
            "y": 30.1,
            "z": 0,
            "value": 19.2,
            "timestamp": "2026-03-10T00:00:00+00:00",
            "source": "sensor",
            "device": "d1",
            "method": "manual",
            "quality_flag": "good",
            "metadata": {"contact": "18888888888", "email": "test@example.com"},
        },
        user_id,
    )
    stored = service._records["input"][record["id"]]["encrypted_data"]  # type: ignore[attr-defined]
    assert "k1:" in stored

    rotate = service.rotate_encryption_key("k2", "new-feedback-key", user_id=admin_id)
    assert rotate["active_key_id"] == "k2"

    next_record = service.submit_input(
        {
            "dataset_id": "secure_dataset",
            "x": 120.2,
            "y": 30.2,
            "z": 0,
            "value": 18.5,
            "timestamp": "2026-03-11T00:00:00+00:00",
            "source": "sensor",
            "device": "d2",
            "method": "manual",
            "quality_flag": "good",
            "metadata": {"contact": "16666666666"},
        },
        user_id,
    )
    rotated_cipher = service._records["input"][next_record["id"]]["encrypted_data"]  # type: ignore[attr-defined]
    assert "k2:" in rotated_cipher
    assert service._decrypt_payload(stored)["dataset_id"] == "secure_dataset"  # type: ignore[attr-defined]

    query = service.query_data({"dataset_id": "secure_dataset", "limit": 10, "offset": 0}, user_id=admin_id, include_private=True)
    assert query["count"] >= 2
    masked_contact = query["items"][0]["data"]["metadata"]["contact"]
    assert masked_contact != "16666666666"
    assert "***" in masked_contact

    service.log_request({"api_key": "dev-feedback-key", "token": "abc123456", "path": "/api/feedback/data"})
    latest_request = service._request_logs[-1]  # type: ignore[attr-defined]
    assert latest_request["api_key"] != "dev-feedback-key"
    assert latest_request["token"] != "abc123456"

    actions = [item["action"] for item in service._audit_logs]  # type: ignore[attr-defined]
    assert "encryption_key_rotate" in actions
    assert any(action.startswith("data_access:query_data") for action in actions)
