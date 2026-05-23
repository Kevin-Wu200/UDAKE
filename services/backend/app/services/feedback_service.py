"""Feedback collection service for data, users, quality and conflict workflows."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import math
import os
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev, quantiles
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from ..auth.security import _decrypt_aes_gcm, _encrypt_aes_gcm
from ..config import settings

ROLE_PERMISSIONS: Dict[str, set[str]] = {
    "admin": {
        "read_feedback",
        "write_feedback",
        "manage_users",
        "resolve_conflicts",
        "manage_api_keys",
        "export_feedback",
        "backup_feedback",
    },
    "reviewer": {
        "read_feedback",
        "write_feedback",
        "resolve_conflicts",
        "export_feedback",
    },
    "contributor": {
        "read_feedback",
        "write_feedback",
    },
    "viewer": {
        "read_feedback",
    },
}

FEEDBACK_ENCRYPTION_PREFIX = "fbenc:v1:"
LEGACY_XOR_KEY = b"udake-feedback-key-v1"
DEFAULT_MASK_FIELDS = {
    "password",
    "token",
    "api_key",
    "authorization",
    "contact",
    "phone",
    "email",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _month_partition(ts: datetime) -> str:
    return ts.strftime("%Y-%m")


def _region_partition(x: float, y: float, precision: int = 1) -> str:
    fx = round(x, precision)
    fy = round(y, precision)
    return f"{fx:.{precision}f},{fy:.{precision}f}"


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


class FeedbackService:
    """Application-level feedback aggregation and governance service."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._legacy_xor_key = LEGACY_XOR_KEY
        self._active_key_id = str(settings.FEEDBACK_ACTIVE_KEY_ID or "k1").strip() or "k1"
        self._encryption_keys: Dict[str, Dict[str, bytes]] = {}
        key_material = str(settings.FEEDBACK_ENCRYPTION_KEY or settings.AUTH_ENCRYPTION_KEY or "udake-feedback-key-v2")
        hmac_material = str(settings.FEEDBACK_HMAC_KEY or f"{key_material}:hmac")
        self._register_encryption_key(self._active_key_id, key_material, hmac_material)

        for idx, item in enumerate(settings.FEEDBACK_FALLBACK_KEYS or [], start=1):
            text = str(item).strip()
            if not text:
                continue
            if ":" in text:
                fallback_id, fallback_material = text.split(":", 1)
                key_id = fallback_id.strip() or f"legacy_{idx}"
                material = fallback_material.strip()
            else:
                key_id = f"legacy_{idx}"
                material = text
            if not material:
                continue
            self._register_encryption_key(key_id, material, f"{material}:hmac")

        masked_fields = set(DEFAULT_MASK_FIELDS)
        masked_fields.update(str(item).strip().lower() for item in (settings.FEEDBACK_MASK_FIELDS or []) if str(item).strip())
        self._masked_fields = masked_fields

        # core storage tables
        self._records: Dict[str, Dict[str, Dict[str, Any]]] = {
            "input": {},
            "modification": {},
            "validation": {},
            "annotation": {},
        }
        self._versions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._audit_logs: List[Dict[str, Any]] = []
        self._request_logs: List[Dict[str, Any]] = []
        self._conflicts: Dict[str, Dict[str, Any]] = {}

        # index and partition structures
        self._time_index: List[Tuple[str, str, str]] = []
        self._user_index: Dict[str, set[str]] = defaultdict(set)
        self._geo_index: Dict[str, set[str]] = defaultdict(set)
        self._time_partitions: Dict[str, set[str]] = defaultdict(set)
        self._region_partitions: Dict[str, set[str]] = defaultdict(set)

        # users / auth
        self._users: Dict[str, Dict[str, Any]] = {}
        self._users_by_name: Dict[str, str] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._api_keys: Dict[str, Dict[str, Any]] = {
            "dev-feedback-key": {
                "key": "dev-feedback-key",
                "owner": "system",
                "scopes": ["read", "write", "admin"],
                "created_at": _iso(_utcnow()),
                "enabled": True,
            }
        }

        # backup / archive
        self._backups: Dict[str, Dict[str, Any]] = {}
        self._archives: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # simple cache for query optimization
        self._query_cache: Dict[str, Dict[str, Any]] = {}

        self._bootstrap_users()

    # --------------------------
    # auth and user management
    # --------------------------
    def _bootstrap_users(self) -> None:
        self.register_user(
            {
                "username": "admin",
                "password": "admin123",
                "role": "admin",
                "display_name": "System Admin",
                "domain": "global",
            }
        )

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

    def _hash_user(self, user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]

    def _derive_key(self, material: str, purpose: str) -> bytes:
        return hashlib.sha256(f"{purpose}:{material}".encode("utf-8")).digest()

    def _register_encryption_key(self, key_id: str, key_material: str, hmac_material: str) -> None:
        kid = key_id.strip()
        if not kid:
            raise ValueError("key_id cannot be empty")
        self._encryption_keys[kid] = {
            "enc": self._derive_key(key_material, "feedback-aes-gcm"),
            "hmac": self._derive_key(hmac_material, "feedback-hmac"),
        }

    def rotate_encryption_key(
        self,
        key_id: str,
        key_material: str,
        user_id: str = "system",
        hmac_material: Optional[str] = None,
    ) -> Dict[str, Any]:
        material = str(key_material or "").strip()
        if not material:
            raise ValueError("key_material cannot be empty")
        kid = str(key_id or "").strip()
        if not kid:
            raise ValueError("key_id cannot be empty")
        self._register_encryption_key(kid, material, str(hmac_material or f"{material}:hmac"))
        previous = self._active_key_id
        self._active_key_id = kid
        self._append_audit(
            "encryption_key_rotate",
            user_id,
            {"from_key_id": previous, "to_key_id": kid},
        )
        return {"active_key_id": self._active_key_id, "key_count": len(self._encryption_keys)}

    @staticmethod
    def _b64encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def _b64decode(raw: str) -> bytes:
        return base64.urlsafe_b64decode(raw.encode("ascii"))

    def register_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        role = str(payload.get("role") or "contributor")

        if not username:
            raise ValueError("username is required")
        if len(password) < 6:
            raise ValueError("password must be at least 6 characters")
        if role not in ROLE_PERMISSIONS:
            raise ValueError("invalid role")
        if username in self._users_by_name:
            raise ValueError("username already exists")

        user_id = f"usr_{uuid4().hex[:12]}"
        salt = uuid4().hex
        now = _utcnow()
        user = {
            "user_id": user_id,
            "username": username,
            "password_hash": self._hash_password(password, salt),
            "password_salt": salt,
            "role": role,
            "display_name": str(payload.get("display_name") or username),
            "domain": str(payload.get("domain") or "general"),
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "preferences": payload.get("preferences") or {},
            "stats": {
                "input_count": 0,
                "modification_count": 0,
                "validation_count": 0,
                "annotation_count": 0,
                "accepted_validation_count": 0,
                "quality_contribution": 0.0,
                "activity_score": 0.0,
                "contribution_score": 0.0,
                "reliability_score": 0.5,
                "points": 0,
                "badges": [],
            },
            "active": True,
        }

        self._users[user_id] = user
        self._users_by_name[username] = user_id
        self._append_audit("user_register", user_id, {"username": username, "role": role})
        return self._public_user(user)

    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        user_id = self._users_by_name.get(username)
        if not user_id:
            raise ValueError("invalid username or password")

        user = self._users[user_id]
        expected = self._hash_password(password, user["password_salt"])
        if expected != user["password_hash"]:
            raise ValueError("invalid username or password")
        if not user.get("active", True):
            raise ValueError("user disabled")

        token = f"sess_{secrets.token_hex(16)}"
        expires_at = _utcnow() + timedelta(hours=24)
        self._sessions[token] = {
            "token": token,
            "user_id": user_id,
            "expires_at": _iso(expires_at),
        }

        self._append_audit("user_auth", user_id, {"username": username})
        return {
            "token": token,
            "user": self._public_user(user),
            "expires_at": _iso(expires_at),
        }

    def resolve_user_id(self, user_id: Optional[str] = None, session_token: Optional[str] = None) -> str:
        if user_id and user_id in self._users:
            return user_id

        if session_token:
            session = self._sessions.get(session_token)
            if session:
                exp = _parse_ts(session["expires_at"])
                if exp > _utcnow():
                    return str(session["user_id"])

        # fallback user
        admin = self._users_by_name.get("admin")
        if not admin:
            raise ValueError("no default user available")
        return admin

    def get_user(self, user_id: str) -> Dict[str, Any]:
        user = self._users.get(user_id)
        if not user:
            raise KeyError("user not found")
        return self._public_user(user)

    def get_user_reliability(self, user_id: str) -> Dict[str, Any]:
        user = self._users.get(user_id)
        if not user:
            raise KeyError("user not found")

        stats = user["stats"]
        accuracy = 0.0
        if stats["validation_count"] > 0:
            accuracy = stats["accepted_validation_count"] / stats["validation_count"]

        activity = min(stats["activity_score"], 1.0)
        quality = min(max(stats["quality_contribution"], 0.0), 1.0)
        reliability = round(0.45 * accuracy + 0.25 * quality + 0.2 * activity + 0.1 * self._domain_weight(user), 4)

        stats["reliability_score"] = reliability
        return {
            "user_id": user_id,
            "accuracy": round(accuracy, 4),
            "quality_contribution": round(quality, 4),
            "activity_score": round(activity, 4),
            "domain_weight": round(self._domain_weight(user), 4),
            "reliability_score": reliability,
        }

    def get_user_contributions(self, user_id: str) -> Dict[str, Any]:
        user = self._users.get(user_id)
        if not user:
            raise KeyError("user not found")

        stats = user["stats"]
        return {
            "user_id": user_id,
            "input_count": stats["input_count"],
            "modification_count": stats["modification_count"],
            "validation_count": stats["validation_count"],
            "annotation_count": stats["annotation_count"],
            "points": stats["points"],
            "badges": list(stats["badges"]),
            "contribution_score": round(stats["contribution_score"], 4),
        }

    def get_leaderboard(self, metric: str = "contribution", top_n: int = 20) -> List[Dict[str, Any]]:
        metric = metric.lower().strip()
        if metric not in {"contribution", "reliability", "points", "quality"}:
            raise ValueError("unsupported leaderboard metric")

        rows: List[Dict[str, Any]] = []
        for user in self._users.values():
            stats = user["stats"]
            if metric == "contribution":
                score = stats["contribution_score"]
            elif metric == "reliability":
                score = self.get_user_reliability(user["user_id"])["reliability_score"]
            elif metric == "quality":
                score = stats["quality_contribution"]
            else:
                score = float(stats["points"])

            rows.append(
                {
                    "user_id": user["user_id"],
                    "display_name": user["display_name"],
                    "role": user["role"],
                    "score": round(float(score), 4),
                }
            )

        rows.sort(key=lambda item: item["score"], reverse=True)
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx
        return rows[:top_n]

    def _domain_weight(self, user: Dict[str, Any]) -> float:
        mapping = {
            "global": 1.0,
            "geology": 0.9,
            "hydrology": 0.88,
            "environment": 0.86,
            "general": 0.82,
        }
        return float(mapping.get(str(user.get("domain") or "general"), 0.8))

    def _require_permission(self, user_id: str, perm: str) -> None:
        user = self._users.get(user_id)
        if not user:
            raise ValueError("user not found")

        role = str(user.get("role") or "viewer")
        perms = ROLE_PERMISSIONS.get(role, set())
        if perm not in perms:
            raise PermissionError(f"permission denied: {perm}")

    def _update_user_activity(
        self,
        user_id: str,
        event_type: str,
        quality: Optional[float] = None,
        accepted: Optional[bool] = None,
    ) -> None:
        user = self._users.get(user_id)
        if not user:
            return

        stats = user["stats"]
        if event_type == "input":
            stats["input_count"] += 1
            stats["points"] += 5
        elif event_type == "modification":
            stats["modification_count"] += 1
            stats["points"] += 4
        elif event_type == "validation":
            stats["validation_count"] += 1
            stats["points"] += 3
            if accepted:
                stats["accepted_validation_count"] += 1
                stats["points"] += 1
        elif event_type == "annotation":
            stats["annotation_count"] += 1
            stats["points"] += 2

        if quality is not None:
            prev = stats["quality_contribution"]
            stats["quality_contribution"] = min(1.0, (prev * 0.7 + float(quality) * 0.3))

        total_actions = (
            stats["input_count"]
            + stats["modification_count"]
            + stats["validation_count"]
            + stats["annotation_count"]
        )
        stats["activity_score"] = min(1.0, total_actions / 100.0)
        stats["contribution_score"] = (
            stats["input_count"] * 1.0
            + stats["modification_count"] * 1.2
            + stats["validation_count"] * 0.8
            + stats["annotation_count"] * 0.6
            + stats["quality_contribution"] * 10
        )

        badges: List[str] = list(stats["badges"])
        if stats["points"] >= 100 and "贡献达人" not in badges:
            badges.append("贡献达人")
        if stats["accepted_validation_count"] >= 20 and "验证专家" not in badges:
            badges.append("验证专家")
        if stats["quality_contribution"] >= 0.85 and "质量卫士" not in badges:
            badges.append("质量卫士")
        stats["badges"] = badges

    # --------------------------
    # api key / request logs
    # --------------------------
    def verify_api_key(self, api_key: str, required_scope: str = "read") -> Dict[str, Any]:
        key_info = self._api_keys.get(api_key)
        if not key_info or not key_info.get("enabled", False):
            raise PermissionError("invalid api key")

        scopes = set(key_info.get("scopes") or [])
        if required_scope not in scopes and "admin" not in scopes:
            raise PermissionError("api key scope denied")
        return key_info

    def create_api_key(self, owner: str, scopes: Iterable[str], created_by: str) -> Dict[str, Any]:
        self._require_permission(created_by, "manage_api_keys")
        scope_set = {str(item).strip() for item in scopes if str(item).strip()}
        if not scope_set:
            raise ValueError("scopes cannot be empty")

        key = f"fbk_{secrets.token_urlsafe(18)}"
        item = {
            "key": key,
            "owner": owner,
            "scopes": sorted(scope_set),
            "created_at": _iso(_utcnow()),
            "enabled": True,
        }
        self._api_keys[key] = item
        self._append_audit("api_key_create", created_by, {"owner": owner, "scopes": item["scopes"]})
        return item

    def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        self._require_permission(user_id, "manage_api_keys")
        return [
            {
                "key": self._mask_api_key(str(item["key"])),
                "owner": item["owner"],
                "scopes": list(item["scopes"]),
                "created_at": item["created_at"],
                "enabled": bool(item["enabled"]),
            }
            for item in self._api_keys.values()
        ]

    def log_request(self, payload: Dict[str, Any]) -> None:
        sanitized = self._sanitize_payload(payload, flatten_for_log=False)
        item = {
            "id": f"req_{uuid4().hex[:12]}",
            "timestamp": _iso(_utcnow()),
            **sanitized,
        }
        self._request_logs.append(item)
        if len(self._request_logs) > 5000:
            self._request_logs = self._request_logs[-5000:]

    @staticmethod
    def _mask_api_key(raw: str) -> str:
        text = str(raw or "")
        if len(text) <= 8:
            return "***"
        return f"{text[:4]}***{text[-4:]}"

    def _mask_value(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return "***"
        if len(text) <= 6:
            return "***"
        return f"{text[:2]}***{text[-2:]}"

    def _sanitize_payload(self, payload: Any, flatten_for_log: bool = False) -> Any:
        if isinstance(payload, dict):
            masked: Dict[str, Any] = {}
            for key, value in payload.items():
                key_text = str(key).strip().lower()
                if key_text in self._masked_fields:
                    masked[key] = self._mask_value(value)
                elif flatten_for_log and key_text in {"x", "y", "z", "value"}:
                    masked[key] = "***"
                else:
                    masked[key] = self._sanitize_payload(value, flatten_for_log=flatten_for_log)
            return masked
        if isinstance(payload, list):
            return [self._sanitize_payload(item, flatten_for_log=flatten_for_log) for item in payload]
        return payload

    # --------------------------
    # data collection interfaces
    # --------------------------
    def submit_input(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "write_feedback")

        validation = self._validate_input_payload(payload)
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))

        now = _utcnow()
        timestamp = _parse_ts(payload.get("timestamp"))
        x = _safe_float(payload.get("x"))
        y = _safe_float(payload.get("y"))
        z = _safe_float(payload.get("z"), 0.0)

        data = {
            "dataset_id": str(payload.get("dataset_id")),
            "x": x,
            "y": y,
            "z": z,
            "value": _safe_float(payload.get("value")),
            "observed_value": _safe_float(payload.get("observed_value", payload.get("value"))),
            "measured_value": _safe_float(payload.get("measured_value", payload.get("value"))),
            "timestamp": _iso(timestamp),
            "device": str(payload.get("device") or "unknown"),
            "method": str(payload.get("method") or "manual"),
            "source": str(payload.get("source") or "manual"),
            "quality_flag": str(payload.get("quality_flag") or "unknown"),
            "metadata": payload.get("metadata") or {},
        }

        consistency = self._check_consistency(data)
        privacy = self._check_privacy(data)
        anomalies = self._detect_anomalies(data["dataset_id"], data)
        quality = self._score_quality(data, user_id, consistency)

        record_id = f"in_{uuid4().hex[:12]}"
        record = {
            "id": record_id,
            "type": "input",
            "dataset_id": data["dataset_id"],
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "user_id": user_id,
            "encrypted_data": self._encrypt_payload(data),
            "quality": quality,
            "validation": validation,
            "consistency": consistency,
            "privacy": privacy,
            "anomalies": anomalies,
            "version": 1,
            "partition_month": _month_partition(timestamp),
            "partition_region": _region_partition(x, y),
            "status": "active",
        }

        with self._lock:
            self._records["input"][record_id] = record
            self._add_version(record_id, "input_create", user_id, data)
            self._index_record(record)
            self._append_audit("input_create", user_id, {"record_id": record_id, "dataset_id": data["dataset_id"]})
            self._update_user_activity(user_id, "input", quality=quality["overall"])
            self._query_cache.clear()

        return self._materialize_record(record)

    def submit_modification(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "write_feedback")

        target_id = str(payload.get("target_record_id") or "").strip()
        if not target_id:
            raise ValueError("target_record_id is required")

        target = self._records["input"].get(target_id)
        if not target:
            raise KeyError("target record not found")

        reason = str(payload.get("reason") or "update").strip().lower()
        if reason not in {"correction", "update", "delete"}:
            raise ValueError("reason must be one of correction, update, delete")

        now = _utcnow()
        target_data = self._decrypt_payload(target["encrypted_data"])
        old_value = target_data.get("value")
        new_value = None if reason == "delete" else _safe_float(payload.get("new_value", old_value))

        item_id = f"mod_{uuid4().hex[:12]}"
        mod_data = {
            "target_record_id": target_id,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "timestamp": _iso(now),
            "operator_id": user_id,
            "note": str(payload.get("note") or ""),
        }

        quality = self._score_modification(mod_data, user_id)
        record = {
            "id": item_id,
            "type": "modification",
            "dataset_id": target["dataset_id"],
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "user_id": user_id,
            "encrypted_data": self._encrypt_payload(mod_data),
            "quality": quality,
            "version": 1,
            "status": "active",
            "partition_month": _month_partition(now),
            "partition_region": target["partition_region"],
        }

        with self._lock:
            self._records["modification"][item_id] = record
            self._index_record(record)
            self._add_version(item_id, "modification_create", user_id, mod_data)

            # apply to target record
            target_data["value"] = new_value
            target["encrypted_data"] = self._encrypt_payload(target_data)
            target["updated_at"] = _iso(now)
            target["version"] = int(target["version"]) + 1
            if reason == "delete":
                target["status"] = "deleted"

            self._add_version(target_id, "input_update", user_id, target_data)
            conflict = self._check_conflict_for_target(target_id)
            self._append_audit("modification_create", user_id, {"modification_id": item_id, "target_record_id": target_id})
            self._update_user_activity(user_id, "modification", quality=quality["overall"])
            self._query_cache.clear()

        result = self._materialize_record(record)
        if conflict:
            result["conflict"] = conflict
        return result

    def submit_validation(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "write_feedback")

        target_id = str(payload.get("target_record_id") or "").strip()
        if not target_id:
            raise ValueError("target_record_id is required")

        target = self._records["input"].get(target_id)
        if not target:
            raise KeyError("target record not found")

        result = str(payload.get("result") or "").lower().strip()
        if result not in {"accept", "reject", "correct"}:
            raise ValueError("result must be one of accept, reject, correct")

        confidence = _safe_float(payload.get("confidence", 0.5))
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1")

        now = _utcnow()
        data = {
            "target_record_id": target_id,
            "predicted_value": _safe_float(payload.get("predicted_value")),
            "result": result,
            "confidence": confidence,
            "timestamp": _iso(now),
            "context": payload.get("context") or {},
            "corrected_value": payload.get("corrected_value"),
        }

        item_id = f"val_{uuid4().hex[:12]}"
        quality = self._score_validation(data, user_id)
        record = {
            "id": item_id,
            "type": "validation",
            "dataset_id": target["dataset_id"],
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "user_id": user_id,
            "encrypted_data": self._encrypt_payload(data),
            "quality": quality,
            "version": 1,
            "status": "active",
            "partition_month": _month_partition(now),
            "partition_region": target["partition_region"],
        }

        with self._lock:
            self._records["validation"][item_id] = record
            self._index_record(record)
            self._add_version(item_id, "validation_create", user_id, data)
            self._append_audit("validation_create", user_id, {"validation_id": item_id, "target_record_id": target_id})
            self._update_user_activity(user_id, "validation", quality=quality["overall"], accepted=result in {"accept", "correct"})

            if result == "correct" and data["corrected_value"] is not None:
                target_data = self._decrypt_payload(target["encrypted_data"])
                target_data["value"] = _safe_float(data["corrected_value"])
                target["encrypted_data"] = self._encrypt_payload(target_data)
                target["version"] = int(target["version"]) + 1
                target["updated_at"] = _iso(now)
                self._add_version(target_id, "input_corrected", user_id, target_data)

            self._query_cache.clear()

        return self._materialize_record(record)

    def submit_annotation(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "write_feedback")

        now = _utcnow()
        target_id = str(payload.get("target_record_id") or "").strip()
        if target_id and target_id not in self._records["input"]:
            raise KeyError("target record not found")

        severity = _safe_int(payload.get("severity", 3), 3)
        severity = max(1, min(5, severity))

        data = {
            "target_record_id": target_id or None,
            "anomaly_type": str(payload.get("anomaly_type") or "unknown"),
            "severity": severity,
            "quality_grade": str(payload.get("quality_grade") or "C").upper(),
            "label": str(payload.get("label") or "general"),
            "reason": str(payload.get("reason") or ""),
            "annotator_id": user_id,
            "timestamp": _iso(now),
        }

        item_id = f"ann_{uuid4().hex[:12]}"
        quality = self._score_annotation(data, user_id)
        record = {
            "id": item_id,
            "type": "annotation",
            "dataset_id": payload.get("dataset_id") or (self._records["input"].get(target_id, {}).get("dataset_id") if target_id else "global"),
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "user_id": user_id,
            "encrypted_data": self._encrypt_payload(data),
            "quality": quality,
            "version": 1,
            "status": "active",
            "partition_month": _month_partition(now),
            "partition_region": self._records["input"].get(target_id, {}).get("partition_region", "0.0,0.0"),
        }

        with self._lock:
            self._records["annotation"][item_id] = record
            self._index_record(record)
            self._add_version(item_id, "annotation_create", user_id, data)
            self._append_audit("annotation_create", user_id, {"annotation_id": item_id, "target_record_id": target_id})
            self._update_user_activity(user_id, "annotation", quality=quality["overall"])
            self._query_cache.clear()

        return self._materialize_record(record)

    def import_batch(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "write_feedback")

        dataset_id = str(payload.get("dataset_id") or "default_dataset")
        import_format = str(payload.get("format") or "csv").lower()
        mapping = payload.get("mapping") or {}
        if import_format not in {"csv", "geojson", "excel"}:
            raise ValueError("format must be csv, geojson or excel")

        rows = self._parse_batch_rows(import_format, payload)
        imported = 0
        errors: List[Dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            try:
                normalized = {
                    "dataset_id": row.get(mapping.get("dataset_id", "dataset_id"), dataset_id),
                    "x": row.get(mapping.get("x", "x")),
                    "y": row.get(mapping.get("y", "y")),
                    "z": row.get(mapping.get("z", "z"), 0),
                    "value": row.get(mapping.get("value", "value")),
                    "observed_value": row.get(mapping.get("observed_value", "observed_value"), row.get("value")),
                    "measured_value": row.get(mapping.get("measured_value", "measured_value"), row.get("value")),
                    "timestamp": row.get(mapping.get("timestamp", "timestamp")),
                    "device": row.get(mapping.get("device", "device"), "import"),
                    "method": row.get(mapping.get("method", "method"), "batch"),
                    "source": row.get(mapping.get("source", "source"), import_format),
                    "quality_flag": row.get(mapping.get("quality_flag", "quality_flag"), "unknown"),
                    "metadata": {"batch_index": idx, "import_format": import_format},
                }
                self.submit_input(normalized, user_id)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"row": idx, "error": str(exc)})

        job_id = f"imp_{uuid4().hex[:12]}"
        self._append_audit(
            "batch_import",
            user_id,
            {
                "job_id": job_id,
                "format": import_format,
                "dataset_id": dataset_id,
                "imported": imported,
                "errors": len(errors),
            },
        )

        return {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "format": import_format,
            "total": len(rows),
            "imported": imported,
            "failed": len(errors),
            "errors": errors,
        }

    def _parse_batch_rows(self, import_format: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if import_format == "csv":
            content = str(payload.get("content") or "")
            if not content.strip():
                raise ValueError("csv content is required")
            reader = csv.DictReader(io.StringIO(content))
            return [dict(row) for row in reader]

        if import_format == "geojson":
            content = payload.get("content")
            if isinstance(content, str):
                obj = json.loads(content)
            elif isinstance(content, dict):
                obj = content
            else:
                raise ValueError("geojson content must be object or json string")

            features = obj.get("features") or []
            rows: List[Dict[str, Any]] = []
            for item in features:
                props = item.get("properties") or {}
                coords = ((item.get("geometry") or {}).get("coordinates") or [0, 0, 0])
                rows.append(
                    {
                        "x": coords[0] if len(coords) > 0 else 0,
                        "y": coords[1] if len(coords) > 1 else 0,
                        "z": coords[2] if len(coords) > 2 else 0,
                        "value": props.get("value"),
                        "timestamp": props.get("timestamp"),
                        "source": props.get("source", "geojson"),
                        "device": props.get("device", "geojson"),
                        "method": props.get("method", "batch"),
                        "quality_flag": props.get("quality_flag", "unknown"),
                    }
                )
            return rows

        # excel support: accept rows list or tab/csv text fallback
        rows_payload = payload.get("rows")
        if isinstance(rows_payload, list):
            return [dict(item) for item in rows_payload if isinstance(item, dict)]

        content = str(payload.get("content") or "")
        if not content.strip():
            raise ValueError("excel rows/content is required")

        delimiter = "\t" if "\t" in content else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        return [dict(row) for row in reader]

    # --------------------------
    # storage/query
    # --------------------------
    def query_data(self, filters: Dict[str, Any], user_id: str, include_private: bool = False) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")

        normalized_filters = {
            "dataset_id": filters.get("dataset_id"),
            "record_type": filters.get("record_type"),
            "user_id": filters.get("user_id"),
            "start": filters.get("start"),
            "end": filters.get("end"),
            "region": filters.get("region"),
            "limit": int(filters.get("limit", 50)),
            "offset": int(filters.get("offset", 0)),
            "status": filters.get("status"),
        }
        cache_key = json.dumps(normalized_filters, sort_keys=True, ensure_ascii=False)
        cached = self._query_cache.get(cache_key)
        if cached:
            # return deep copy-ish via dumps to prevent mutation outside.
            cached_result = json.loads(json.dumps(cached))
            self._append_access_audit(
                "query_data",
                user_id,
                {
                    "filters": self._sanitize_payload(normalized_filters, flatten_for_log=True),
                    "count": cached_result.get("count", 0),
                    "include_private": bool(include_private),
                    "cache_hit": True,
                },
            )
            return cached_result

        record_types: List[str]
        req_type = str(normalized_filters.get("record_type") or "").strip().lower()
        if req_type and req_type in self._records:
            record_types = [req_type]
        else:
            record_types = list(self._records.keys())

        start_ts = _parse_ts(normalized_filters["start"]) if normalized_filters.get("start") else None
        end_ts = _parse_ts(normalized_filters["end"]) if normalized_filters.get("end") else None
        region_filter = str(normalized_filters.get("region") or "").strip()

        matched: List[Dict[str, Any]] = []
        for table_name in record_types:
            for record in self._records[table_name].values():
                if normalized_filters["dataset_id"] and record["dataset_id"] != normalized_filters["dataset_id"]:
                    continue
                if normalized_filters["user_id"] and record["user_id"] != normalized_filters["user_id"]:
                    continue
                if normalized_filters["status"] and record.get("status") != normalized_filters["status"]:
                    continue
                if region_filter and record.get("partition_region") != region_filter:
                    continue

                created_at = _parse_ts(record["created_at"])
                if start_ts and created_at < start_ts:
                    continue
                if end_ts and created_at > end_ts:
                    continue

                matched.append(self._materialize_record(record, anonymize=(not include_private)))

        matched.sort(key=lambda item: item["created_at"], reverse=True)

        offset = max(0, int(normalized_filters["offset"]))
        limit = min(500, max(1, int(normalized_filters["limit"])))
        page = matched[offset : offset + limit]

        result = {
            "filters": normalized_filters,
            "count": len(matched),
            "offset": offset,
            "limit": limit,
            "items": page,
        }
        self._query_cache[cache_key] = result
        payload = json.loads(json.dumps(result))
        self._append_access_audit(
            "query_data",
            user_id,
            {
                "filters": self._sanitize_payload(normalized_filters, flatten_for_log=True),
                "count": payload.get("count", 0),
                "include_private": bool(include_private),
                "cache_hit": False,
            },
        )
        return payload

    def get_history(self, entity_id: str, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")
        versions = list(self._versions.get(entity_id, []))
        self._append_access_audit("get_history", user_id, {"entity_id": entity_id, "count": len(versions)})
        return {"entity_id": entity_id, "count": len(versions), "versions": versions}

    def compare_versions(self, entity_id: str, from_version: int, to_version: int, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")
        history = self._versions.get(entity_id, [])
        if not history:
            raise KeyError("entity version history not found")

        old = next((v for v in history if int(v["version"]) == from_version), None)
        new = next((v for v in history if int(v["version"]) == to_version), None)
        if old is None or new is None:
            raise ValueError("version not found")

        old_data = old["data"]
        new_data = new["data"]
        changed = []
        all_keys = sorted(set(old_data.keys()) | set(new_data.keys()))
        for key in all_keys:
            if old_data.get(key) != new_data.get(key):
                changed.append({"field": key, "from": old_data.get(key), "to": new_data.get(key)})

        return {
            "entity_id": entity_id,
            "from_version": from_version,
            "to_version": to_version,
            "changes": changed,
            "change_count": len(changed),
        }

    def rollback_version(self, entity_id: str, version: int, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "resolve_conflicts")

        history = self._versions.get(entity_id, [])
        selected = next((v for v in history if int(v["version"]) == version), None)
        if not selected:
            raise ValueError("version not found")

        record = self._records["input"].get(entity_id)
        if not record:
            raise KeyError("target record not found")

        now = _utcnow()
        data = dict(selected["data"])
        record["encrypted_data"] = self._encrypt_payload(data)
        record["updated_at"] = _iso(now)
        record["version"] = int(record["version"]) + 1

        self._add_version(entity_id, "rollback", user_id, data)
        self._append_audit("version_rollback", user_id, {"entity_id": entity_id, "version": version})
        self._query_cache.clear()
        return self._materialize_record(record)

    def get_statistics(self, dataset_id: Optional[str], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")

        table_counts: Dict[str, int] = {}
        by_user: Counter[str] = Counter()
        by_day: Counter[str] = Counter()
        quality_values: List[float] = []

        for table_name, table in self._records.items():
            rows = list(table.values())
            if dataset_id:
                rows = [row for row in rows if row["dataset_id"] == dataset_id]
            table_counts[table_name] = len(rows)

            for row in rows:
                by_user[row["user_id"]] += 1
                day = row["created_at"][:10]
                by_day[day] += 1
                quality_values.append(_safe_float((row.get("quality") or {}).get("overall"), 0.0))

        return {
            "dataset_id": dataset_id,
            "table_counts": table_counts,
            "total": sum(table_counts.values()),
            "daily_trend": [{"day": k, "count": by_day[k]} for k in sorted(by_day.keys())],
            "top_contributors": [
                {"user_id": uid, "count": cnt}
                for uid, cnt in by_user.most_common(10)
            ],
            "avg_quality": round(mean(quality_values), 4) if quality_values else 0.0,
            "updated_at": _iso(_utcnow()),
        }

    def get_quality_report(
        self,
        user_id: str,
        dataset_id: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")

        if record_id:
            for table_name, table in self._records.items():
                row = table.get(record_id)
                if row:
                    self._append_access_audit(
                        "get_quality_report",
                        user_id,
                        {"record_id": record_id, "dataset_id": row["dataset_id"], "record_type": table_name},
                    )
                    return {
                        "record_id": record_id,
                        "record_type": table_name,
                        "dataset_id": row["dataset_id"],
                        "quality": row.get("quality") or {},
                        "consistency": row.get("consistency"),
                        "validation": row.get("validation"),
                        "privacy": row.get("privacy"),
                    }
            raise KeyError("record not found")

        metrics = {
            "completeness": [],
            "accuracy": [],
            "consistency": [],
            "timeliness": [],
            "overall": [],
        }

        for table in self._records.values():
            for row in table.values():
                if dataset_id and row["dataset_id"] != dataset_id:
                    continue
                quality = row.get("quality") or {}
                for key in metrics:
                    metrics[key].append(_safe_float(quality.get(key), 0.0))

        summary = {
            key: round(mean(values), 4) if values else 0.0
            for key, values in metrics.items()
        }
        self._append_access_audit(
            "get_quality_report",
            user_id,
            {"dataset_id": dataset_id, "record_count": len(metrics["overall"])},
        )
        return {
            "dataset_id": dataset_id,
            "summary": summary,
            "record_count": len(metrics["overall"]),
            "generated_at": _iso(_utcnow()),
        }

    def get_conflicts(self, user_id: str, unresolved_only: bool = False) -> Dict[str, Any]:
        self._require_permission(user_id, "read_feedback")
        items = list(self._conflicts.values())
        if unresolved_only:
            items = [item for item in items if item["status"] == "open"]
        return {"count": len(items), "items": items}

    def resolve_conflict(
        self,
        conflict_id: str,
        strategy: str,
        user_id: str,
        manual_modification_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_permission(user_id, "resolve_conflicts")

        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            raise KeyError("conflict not found")
        if conflict["status"] != "open":
            return conflict

        options = conflict["candidates"]
        selected = None

        strategy = strategy.lower().strip()
        if strategy == "latest":
            selected = max(options, key=lambda x: x["timestamp"])
        elif strategy == "quality":
            selected = max(options, key=lambda x: x.get("quality", 0.0))
        elif strategy == "manual":
            if not manual_modification_id:
                raise ValueError("manual_modification_id is required for manual strategy")
            selected = next((item for item in options if item["modification_id"] == manual_modification_id), None)
            if not selected:
                raise ValueError("manual_modification_id not found in candidates")
        else:
            raise ValueError("strategy must be latest, quality or manual")

        target_id = conflict["target_record_id"]
        target = self._records["input"].get(target_id)
        if not target:
            raise KeyError("target record not found")

        target_data = self._decrypt_payload(target["encrypted_data"])
        target_data["value"] = selected["new_value"]
        target["encrypted_data"] = self._encrypt_payload(target_data)
        target["updated_at"] = _iso(_utcnow())
        target["version"] = int(target["version"]) + 1

        self._add_version(target_id, "conflict_resolve", user_id, target_data)

        conflict["status"] = "resolved"
        conflict["resolved_by"] = user_id
        conflict["resolved_at"] = _iso(_utcnow())
        conflict["resolution_strategy"] = strategy
        conflict["selected"] = selected

        self._append_audit("conflict_resolve", user_id, {"conflict_id": conflict_id, "strategy": strategy})
        self._query_cache.clear()
        return conflict

    def export_data(self, fmt: str, filters: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "export_feedback")
        data = self.query_data(filters, user_id=user_id, include_private=True)["items"]
        fmt = fmt.lower().strip()
        self._append_access_audit(
            "export_data",
            user_id,
            {
                "format": fmt,
                "filters": self._sanitize_payload(filters, flatten_for_log=True),
                "count": len(data),
            },
        )

        if fmt == "json":
            return {"format": "json", "content": data}

        if fmt in {"csv", "excel"}:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id",
                "type",
                "dataset_id",
                "user_id",
                "created_at",
                "x",
                "y",
                "z",
                "value",
                "status",
                "quality_overall",
            ])
            for row in data:
                payload = row.get("data") or {}
                writer.writerow(
                    [
                        row.get("id"),
                        row.get("type"),
                        row.get("dataset_id"),
                        row.get("user_id"),
                        row.get("created_at"),
                        payload.get("x"),
                        payload.get("y"),
                        payload.get("z"),
                        payload.get("value"),
                        row.get("status"),
                        (row.get("quality") or {}).get("overall"),
                    ]
                )
            return {"format": fmt, "content": output.getvalue()}

        if fmt == "geojson":
            features = []
            for row in data:
                if row.get("type") != "input":
                    continue
                payload = row.get("data") or {}
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [
                                _safe_float(payload.get("x"), 0.0),
                                _safe_float(payload.get("y"), 0.0),
                                _safe_float(payload.get("z"), 0.0),
                            ],
                        },
                        "properties": {
                            "id": row.get("id"),
                            "dataset_id": row.get("dataset_id"),
                            "value": payload.get("value"),
                            "timestamp": payload.get("timestamp"),
                            "quality": (row.get("quality") or {}).get("overall"),
                        },
                    }
                )
            return {"format": "geojson", "content": {"type": "FeatureCollection", "features": features}}

        raise ValueError("unsupported export format")

    def create_backup(self, mode: str, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "backup_feedback")
        mode = mode.lower().strip()
        if mode not in {"full", "incremental"}:
            raise ValueError("mode must be full or incremental")

        snapshot = {
            "records": self._records,
            "versions": self._versions,
            "conflicts": self._conflicts,
            "users": self._users,
            "audit_logs": self._audit_logs,
        }

        backup_id = f"bak_{uuid4().hex[:12]}"
        item = {
            "backup_id": backup_id,
            "mode": mode,
            "created_at": _iso(_utcnow()),
            "size": len(json.dumps(snapshot, ensure_ascii=False)),
            "snapshot": json.loads(json.dumps(snapshot, ensure_ascii=False)),
        }
        self._backups[backup_id] = item
        self._append_audit("backup_create", user_id, {"backup_id": backup_id, "mode": mode})
        return {k: v for k, v in item.items() if k != "snapshot"}

    def restore_backup(self, backup_id: str, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "backup_feedback")
        item = self._backups.get(backup_id)
        if not item:
            raise KeyError("backup not found")

        snapshot = item["snapshot"]
        self._records = snapshot["records"]
        self._versions = defaultdict(list, snapshot["versions"])
        self._conflicts = snapshot["conflicts"]
        self._users = snapshot["users"]
        self._audit_logs = snapshot["audit_logs"]
        self._query_cache.clear()

        self._append_audit("backup_restore", user_id, {"backup_id": backup_id})
        return {"backup_id": backup_id, "restored_at": _iso(_utcnow())}

    def archive_before(self, before: str, user_id: str) -> Dict[str, Any]:
        self._require_permission(user_id, "backup_feedback")
        cutoff = _parse_ts(before)
        moved = 0

        for table_name, table in self._records.items():
            to_remove = []
            for rid, row in table.items():
                created = _parse_ts(row["created_at"])
                if created < cutoff:
                    self._archives[table_name].append(row)
                    to_remove.append(rid)
            for rid in to_remove:
                del table[rid]
                moved += 1

        self._query_cache.clear()
        self._append_audit("archive_before", user_id, {"before": before, "moved": moved})
        return {"before": before, "moved": moved}

    # --------------------------
    # integration
    # --------------------------
    def ingest_integration_feedback(self, module: str, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        module_name = module.strip().lower()
        if module_name not in {
            "realtime_interpolation",
            "adaptive_sampling",
            "ai_extension",
            "uncertainty_dashboard",
        }:
            raise ValueError("unsupported integration module")

        outputs: Dict[str, Any] = {"module": module_name}

        if module_name == "realtime_interpolation":
            outputs["input"] = self.submit_input(
                {
                    "dataset_id": payload.get("dataset_id", "realtime"),
                    "x": payload.get("x"),
                    "y": payload.get("y"),
                    "z": payload.get("z", 0),
                    "value": payload.get("observed_value"),
                    "observed_value": payload.get("observed_value"),
                    "measured_value": payload.get("observed_value"),
                    "timestamp": payload.get("timestamp", _iso(_utcnow())),
                    "source": "realtime_interpolation",
                    "device": payload.get("device", "realtime-sensor"),
                    "method": "integration",
                    "quality_flag": payload.get("quality_flag", "auto"),
                    "metadata": {
                        "predicted_value": payload.get("predicted_value"),
                        "interpolation_error": payload.get("error"),
                    },
                },
                user_id,
            )

        elif module_name == "adaptive_sampling":
            outputs["annotation"] = self.submit_annotation(
                {
                    "dataset_id": payload.get("dataset_id", "adaptive_sampling"),
                    "anomaly_type": "sampling_feedback",
                    "severity": payload.get("severity", 3),
                    "quality_grade": payload.get("quality_grade", "B"),
                    "label": payload.get("label", "sampling_advice"),
                    "reason": payload.get("feedback", ""),
                },
                user_id,
            )

        elif module_name == "ai_extension":
            outputs["annotation"] = self.submit_annotation(
                {
                    "dataset_id": payload.get("dataset_id", "ai_extension"),
                    "anomaly_type": payload.get("anomaly_type", "ai_anomaly"),
                    "severity": payload.get("severity", 3),
                    "quality_grade": payload.get("quality_grade", "C"),
                    "label": payload.get("label", "ai_detection"),
                    "reason": payload.get("note", ""),
                },
                user_id,
            )

        else:  # uncertainty_dashboard
            outputs["validation"] = self.submit_validation(
                {
                    "target_record_id": payload.get("target_record_id"),
                    "predicted_value": payload.get("predicted_value", 0),
                    "result": payload.get("result", "accept"),
                    "confidence": payload.get("confidence", 0.5),
                    "context": {
                        "source": "uncertainty_dashboard",
                        "uncertainty": payload.get("uncertainty"),
                    },
                    "corrected_value": payload.get("corrected_value"),
                },
                user_id,
            )

        return outputs

    # --------------------------
    # scoring and validation
    # --------------------------
    def _validate_input_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        required_fields = ["dataset_id", "x", "y", "value", "timestamp", "source"]
        for key in required_fields:
            if payload.get(key) in {None, ""}:
                errors.append(f"{key} is required")

        x = _safe_float(payload.get("x"), math.nan)
        y = _safe_float(payload.get("y"), math.nan)
        if math.isnan(x) or x < -180 or x > 180:
            errors.append("x out of range [-180, 180]")
        if math.isnan(y) or y < -90 or y > 90:
            errors.append("y out of range [-90, 90]")

        value = _safe_float(payload.get("value"), math.nan)
        if math.isnan(value):
            errors.append("value must be numeric")
        elif abs(value) > 1e9:
            warnings.append("value is unusually large")

        try:
            ts = _parse_ts(payload.get("timestamp"))
            if ts > _utcnow() + timedelta(minutes=5):
                errors.append("timestamp cannot be in the future")
        except Exception:  # noqa: BLE001
            errors.append("invalid timestamp format")

        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            errors.append("metadata must be object")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "required_checked": required_fields,
        }

    def _check_consistency(self, data: Dict[str, Any]) -> Dict[str, Any]:
        checks = {
            "spatial": {"ok": True, "issues": []},
            "temporal": {"ok": True, "issues": []},
            "logical": {"ok": True, "issues": []},
            "cross_table": {"ok": True, "issues": []},
            "statistical": {"ok": True, "issues": []},
        }

        # logical rules
        if data.get("observed_value") is None and data.get("measured_value") is None:
            checks["logical"]["ok"] = False
            checks["logical"]["issues"].append("observed_value and measured_value cannot both be empty")

        # compare with nearby records in same dataset
        dataset_id = str(data.get("dataset_id"))
        x = _safe_float(data.get("x"))
        y = _safe_float(data.get("y"))
        value = _safe_float(data.get("value"))

        nearby_values: List[float] = []
        for record in self._records["input"].values():
            if record["dataset_id"] != dataset_id:
                continue
            existing = self._decrypt_payload(record["encrypted_data"])
            d = _distance((x, y), (_safe_float(existing.get("x")), _safe_float(existing.get("y"))))
            if d <= 0.5:
                nearby_values.append(_safe_float(existing.get("value"), value))

        if nearby_values:
            avg_near = mean(nearby_values)
            if abs(value - avg_near) > max(10.0, abs(avg_near) * 0.6):
                checks["spatial"]["ok"] = False
                checks["spatial"]["issues"].append("value differs significantly from nearby points")

        # temporal continuity check for same rounded location
        key = _region_partition(x, y, precision=2)
        recent_values: List[Tuple[datetime, float]] = []
        for record in self._records["input"].values():
            if record["dataset_id"] != dataset_id:
                continue
            if _region_partition(_safe_float(self._decrypt_payload(record["encrypted_data"]).get("x")), _safe_float(self._decrypt_payload(record["encrypted_data"]).get("y")), precision=2) != key:
                continue
            payload = self._decrypt_payload(record["encrypted_data"])
            try:
                recent_values.append((_parse_ts(payload.get("timestamp")), _safe_float(payload.get("value"), value)))
            except Exception:  # noqa: BLE001
                continue

        if recent_values:
            recent_values.sort(key=lambda item: item[0], reverse=True)
            latest_ts, latest_value = recent_values[0]
            current_ts = _parse_ts(data.get("timestamp"))
            if abs((current_ts - latest_ts).total_seconds()) <= 24 * 3600:
                if abs(value - latest_value) > max(15.0, abs(latest_value) * 0.8):
                    checks["temporal"]["ok"] = False
                    checks["temporal"]["issues"].append("temporal jump exceeds threshold")

        values = [
            _safe_float(self._decrypt_payload(record["encrypted_data"]).get("value"), 0.0)
            for record in self._records["input"].values()
            if record["dataset_id"] == dataset_id
        ]
        if len(values) >= 5:
            avg = mean(values)
            sd = pstdev(values) or 1.0
            z = abs((value - avg) / sd)
            if z > 3.0:
                checks["statistical"]["ok"] = False
                checks["statistical"]["issues"].append("z-score exceeds 3")

        flags = [1.0 if item["ok"] else 0.0 for item in checks.values()]
        checks["score"] = round(sum(flags) / len(flags), 4)
        return checks

    def _detect_anomalies(self, dataset_id: str, current: Dict[str, Any]) -> List[Dict[str, Any]]:
        values = [
            _safe_float(self._decrypt_payload(item["encrypted_data"]).get("value"), 0.0)
            for item in self._records["input"].values()
            if item["dataset_id"] == dataset_id
        ]
        values.append(_safe_float(current.get("value"), 0.0))

        anomalies: List[Dict[str, Any]] = []
        current_value = _safe_float(current.get("value"), 0.0)

        if len(values) >= 3:
            avg = mean(values)
            sd = pstdev(values) or 1.0
            z = abs((current_value - avg) / sd)
            if z > 3.0:
                anomalies.append({"type": "statistical_3sigma", "score": round(z, 4), "value": current_value})

        if len(values) >= 4:
            q1, _, q3 = quantiles(values, n=4, method="inclusive")
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            if current_value < lower or current_value > upper:
                anomalies.append(
                    {
                        "type": "statistical_iqr",
                        "bounds": [round(lower, 4), round(upper, 4)],
                        "value": current_value,
                    }
                )

        ts = _parse_ts(current.get("timestamp"))
        now = _utcnow()
        if ts < now - timedelta(days=3650):
            anomalies.append({"type": "temporal_stale", "timestamp": _iso(ts)})

        if ts > now + timedelta(minutes=5):
            anomalies.append({"type": "temporal_future", "timestamp": _iso(ts)})

        return anomalies

    def _score_quality(self, data: Dict[str, Any], user_id: str, consistency: Dict[str, Any]) -> Dict[str, float]:
        required = ["dataset_id", "x", "y", "value", "timestamp", "source", "device", "method"]
        complete = sum(1 for key in required if data.get(key) not in {None, ""})
        completeness = complete / len(required)

        reliability = self.get_user_reliability(user_id)["reliability_score"]
        accuracy = min(1.0, 0.5 + reliability * 0.5)

        consistency_score = _safe_float(consistency.get("score"), 0.0)

        age_days = abs((_utcnow() - _parse_ts(data.get("timestamp"))).total_seconds()) / 86400.0
        timeliness = max(0.0, min(1.0, 1.0 - age_days / 365.0))

        overall = 0.3 * completeness + 0.25 * accuracy + 0.25 * consistency_score + 0.2 * timeliness
        return {
            "completeness": round(completeness, 4),
            "accuracy": round(accuracy, 4),
            "consistency": round(consistency_score, 4),
            "timeliness": round(timeliness, 4),
            "overall": round(overall, 4),
        }

    def _score_modification(self, data: Dict[str, Any], user_id: str) -> Dict[str, float]:
        base = 0.7 if data.get("reason") == "correction" else 0.6
        rel = self.get_user_reliability(user_id)["reliability_score"]
        overall = min(1.0, base * 0.6 + rel * 0.4)
        return {
            "completeness": 1.0,
            "accuracy": round(rel, 4),
            "consistency": 0.8,
            "timeliness": 1.0,
            "overall": round(overall, 4),
        }

    def _score_validation(self, data: Dict[str, Any], user_id: str) -> Dict[str, float]:
        rel = self.get_user_reliability(user_id)["reliability_score"]
        confidence = _safe_float(data.get("confidence"), 0.5)
        result_factor = 1.0 if data.get("result") in {"accept", "correct"} else 0.6
        overall = 0.35 * rel + 0.35 * confidence + 0.3 * result_factor
        return {
            "completeness": 1.0,
            "accuracy": round(rel, 4),
            "consistency": round(result_factor, 4),
            "timeliness": 1.0,
            "overall": round(overall, 4),
        }

    def _score_annotation(self, data: Dict[str, Any], user_id: str) -> Dict[str, float]:
        rel = self.get_user_reliability(user_id)["reliability_score"]
        severity = _safe_float(data.get("severity"), 3.0) / 5.0
        overall = 0.5 * rel + 0.5 * severity
        return {
            "completeness": 1.0,
            "accuracy": round(rel, 4),
            "consistency": 0.75,
            "timeliness": 1.0,
            "overall": round(overall, 4),
        }

    def _check_privacy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        issues = []
        if "contact" in (data.get("metadata") or {}):
            issues.append("metadata.contact is sensitive")
        compliant = len(issues) == 0
        return {
            "compliant": compliant,
            "issues": issues,
            "anonymized_user": True,
            "masked_coordinates": True,
            "masked_value_range": True,
            "encrypted_storage": True,
        }

    # --------------------------
    # internals
    # --------------------------
    def _encrypt_payload(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        key_entry = self._encryption_keys.get(self._active_key_id)
        if not key_entry:
            raise ValueError("active encryption key is unavailable")
        nonce = os.urandom(12)
        ciphertext, tag = _encrypt_aes_gcm(key_entry["enc"], nonce, raw)
        body = nonce + ciphertext + tag
        signature = hmac.new(
            key_entry["hmac"],
            self._active_key_id.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).digest()
        return (
            f"{FEEDBACK_ENCRYPTION_PREFIX}{self._active_key_id}:"
            f"{self._b64encode(body)}:{self._b64encode(signature)}"
        )

    def _decrypt_payload(self, encrypted: str) -> Dict[str, Any]:
        text = str(encrypted or "")
        if text.startswith(FEEDBACK_ENCRYPTION_PREFIX):
            _, _, body = text.partition(FEEDBACK_ENCRYPTION_PREFIX)
            try:
                key_id, body_b64, signature_b64 = body.split(":", 2)
            except ValueError as exc:
                raise ValueError("invalid encrypted payload format") from exc
            key_entry = self._encryption_keys.get(key_id)
            if not key_entry:
                raise ValueError(f"encryption key id not found: {key_id}")
            packed = self._b64decode(body_b64)
            signature = self._b64decode(signature_b64)
            expected = hmac.new(
                key_entry["hmac"],
                key_id.encode("utf-8") + b"." + packed,
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("encrypted payload signature mismatch")
            if len(packed) < 28:
                raise ValueError("encrypted payload is too short")
            nonce = packed[:12]
            ciphertext = packed[12:-16]
            tag = packed[-16:]
            raw = _decrypt_aes_gcm(key_entry["enc"], nonce, ciphertext, tag)
            return json.loads(raw.decode("utf-8"))

        # 兼容历史数据：旧版本采用 XOR + Base64。
        blob = base64.b64decode(text.encode("utf-8"))
        raw = bytes(blob[idx] ^ self._legacy_xor_key[idx % len(self._legacy_xor_key)] for idx in range(len(blob)))
        return json.loads(raw.decode("utf-8"))

    def _index_record(self, record: Dict[str, Any]) -> None:
        rec_id = record["id"]
        rec_type = record["type"]
        created = record["created_at"]
        user_id = record["user_id"]
        region = record.get("partition_region") or "0.0,0.0"
        month = record.get("partition_month") or created[:7]

        self._time_index.append((created, rec_type, rec_id))
        self._user_index[user_id].add(rec_id)
        self._geo_index[region].add(rec_id)
        self._time_partitions[month].add(rec_id)
        self._region_partitions[region].add(rec_id)

    def _add_version(self, entity_id: str, action: str, user_id: str, data: Dict[str, Any]) -> None:
        history = self._versions[entity_id]
        version_no = len(history) + 1
        history.append(
            {
                "version": version_no,
                "action": action,
                "operator": user_id,
                "timestamp": _iso(_utcnow()),
                "data": json.loads(json.dumps(data, ensure_ascii=False)),
            }
        )

    def _check_conflict_for_target(self, target_record_id: str) -> Optional[Dict[str, Any]]:
        candidates = []
        for row in self._records["modification"].values():
            payload = self._decrypt_payload(row["encrypted_data"])
            if payload.get("target_record_id") != target_record_id:
                continue
            if row.get("status") != "active":
                continue
            candidates.append(
                {
                    "modification_id": row["id"],
                    "user_id": row["user_id"],
                    "new_value": payload.get("new_value"),
                    "timestamp": row["created_at"],
                    "quality": _safe_float((row.get("quality") or {}).get("overall"), 0.0),
                }
            )

        if len(candidates) < 2:
            return None

        unique_values = {item["new_value"] for item in candidates}
        if len(unique_values) <= 1:
            return None

        conflict_id = f"cfl_{uuid4().hex[:12]}"
        conflict = {
            "conflict_id": conflict_id,
            "target_record_id": target_record_id,
            "status": "open",
            "created_at": _iso(_utcnow()),
            "candidates": sorted(candidates, key=lambda item: item["timestamp"], reverse=True),
        }
        self._conflicts[conflict_id] = conflict
        return conflict

    def _append_audit(self, action: str, actor: str, detail: Dict[str, Any]) -> None:
        self._audit_logs.append(
            {
                "audit_id": f"aud_{uuid4().hex[:12]}",
                "action": action,
                "actor": actor,
                "detail": self._sanitize_payload(detail, flatten_for_log=True),
                "timestamp": _iso(_utcnow()),
            }
        )
        if len(self._audit_logs) > 20000:
            self._audit_logs = self._audit_logs[-20000:]

    def _append_access_audit(self, action: str, actor: str, detail: Dict[str, Any]) -> None:
        self._append_audit(f"data_access:{action}", actor, detail)

    def _materialize_record(self, record: Dict[str, Any], anonymize: bool = False) -> Dict[str, Any]:
        payload = self._decrypt_payload(record["encrypted_data"])
        if anonymize:
            payload = self._anonymize_payload(payload)
            user_id = self._hash_user(record["user_id"])
        else:
            user_id = record["user_id"]
        payload = self._sanitize_payload(payload, flatten_for_log=False)

        return {
            "id": record["id"],
            "type": record["type"],
            "dataset_id": record["dataset_id"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "user_id": user_id,
            "status": record.get("status", "active"),
            "version": record.get("version", 1),
            "quality": record.get("quality") or {},
            "validation": record.get("validation"),
            "consistency": record.get("consistency"),
            "privacy": record.get("privacy"),
            "anomalies": record.get("anomalies") or [],
            "partition_month": record.get("partition_month"),
            "partition_region": record.get("partition_region"),
            "data": payload,
        }

    def _anonymize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        masked = dict(payload)
        if "x" in masked:
            masked["x"] = round(_safe_float(masked.get("x")), 2)
        if "y" in masked:
            masked["y"] = round(_safe_float(masked.get("y")), 2)
        if "z" in masked:
            masked["z"] = round(_safe_float(masked.get("z")), 1)
        if "value" in masked:
            value = _safe_float(masked.get("value"))
            bucket = math.floor(value / 10.0) * 10.0
            masked["value"] = f"[{bucket:.1f}, {bucket + 10.0:.1f})"
        if "operator_id" in masked:
            masked["operator_id"] = "anon_operator"
        if "annotator_id" in masked:
            masked["annotator_id"] = "anon_annotator"
        return masked

    def _public_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "domain": user["domain"],
            "created_at": user["created_at"],
            "preferences": user.get("preferences") or {},
            "stats": user.get("stats") or {},
            "active": bool(user.get("active", True)),
        }


_feedback_service: Optional[FeedbackService] = None


def get_feedback_service() -> FeedbackService:
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service


feedback_service = get_feedback_service()
