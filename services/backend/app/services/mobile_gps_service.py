"""
移动端 GPS 采样同步服务
提供样点 upsert、冲突检测、版本回滚、批量压缩与审计能力
"""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import hmac
import json
import os
import time
from copy import deepcopy
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _now_ms() -> int:
    return int(time.time() * 1000)


class MobileGPSService:
    def __init__(self) -> None:
        self.samples: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[Dict[str, Any]] = []
        self.sample_history: Dict[str, List[Dict[str, Any]]] = {}
        self.processed_messages: Dict[str, float] = {}
        self.processed_sample_fingerprints: Dict[str, float] = {}
        self.dedup_ttl_seconds = 15 * 60

        self._audit_logs: List[Dict[str, Any]] = []
        seed = os.getenv("GPS_AUDIT_HMAC_KEY", "udake-gps-audit-default-key")
        self._audit_hmac_key = hashlib.sha256(seed.encode("utf-8")).digest()
        self._last_audit_hash = "gps_audit_genesis"

        self._backups: Dict[str, Dict[str, Any]] = {}
        self._last_full_snapshot: Dict[str, Any] = {}

        self._sensitive_tokens: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_state: Dict[str, List[float]] = {}

    def check_request_rate_limit(
        self,
        identity: str,
        *,
        action: str = "sync_batch",
        limit: int = 180,
        window_seconds: int = 60,
    ) -> Dict[str, Any]:
        now = time.time()
        key = f"{str(identity or 'anonymous').strip().lower()}:{action}"
        bucket = [ts for ts in self._rate_limit_state.get(key, []) if now - ts <= max(1, int(window_seconds))]
        if len(bucket) >= max(1, int(limit)):
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            return {"allowed": False, "remaining": 0, "retry_after_seconds": retry_after}
        bucket.append(now)
        self._rate_limit_state[key] = bucket
        return {"allowed": True, "remaining": max(0, int(limit) - len(bucket)), "retry_after_seconds": 0}

    def issue_sensitive_operation_token(self, user_id: str, action: str, ttl_seconds: int = 300) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        act = str(action or "").strip()
        if not uid or not act:
            raise ValueError("user_id 和 action 不能为空")
        token = f"vt_{uuid4().hex}"
        expires_at = time.time() + max(60, int(ttl_seconds))
        self._sensitive_tokens[token] = {"user_id": uid, "action": act, "expires_at": expires_at}
        self._append_audit_event(
            action="issue_sensitive_token",
            details={"user_id": uid, "target_action": act, "expires_at": int(expires_at)},
            success=True,
        )
        return {"token": token, "expires_at": int(expires_at)}

    def verify_sensitive_operation_token(self, token: str, user_id: str, action: str) -> bool:
        info = self._sensitive_tokens.get(str(token or ""))
        if not info:
            return False
        now = time.time()
        if now > float(info.get("expires_at", 0)):
            self._sensitive_tokens.pop(str(token), None)
            return False
        if str(info.get("user_id")) != str(user_id) or str(info.get("action")) != str(action):
            return False
        self._sensitive_tokens.pop(str(token), None)
        return True

    def recommend_batch_size(
        self,
        *,
        network_rtt_ms: Optional[int] = None,
        network_bandwidth_kbps: Optional[int] = None,
        default_batch_size: int = 1000,
    ) -> int:
        batch_size = max(100, min(2000, int(default_batch_size)))
        if network_rtt_ms is not None:
            rtt = max(0, int(network_rtt_ms))
            if rtt > 1800:
                batch_size = min(batch_size, 200)
            elif rtt > 1000:
                batch_size = min(batch_size, 350)
            elif rtt > 600:
                batch_size = min(batch_size, 500)
            elif rtt < 200:
                batch_size = min(2000, batch_size + 300)
        if network_bandwidth_kbps is not None:
            bw = max(1, int(network_bandwidth_kbps))
            if bw < 512:
                batch_size = min(batch_size, 180)
            elif bw < 1024:
                batch_size = min(batch_size, 350)
            elif bw < 4096:
                batch_size = min(batch_size, 700)
            else:
                batch_size = min(2000, batch_size + 400)
        return max(100, min(2000, batch_size))

    def upsert_samples(
        self,
        client_id: str,
        samples: List[Dict[str, Any]],
        strategy: str = "latest-wins",
        message_id: Optional[str] = None,
        batch_size: int = 1000,
        adaptive_batch: bool = False,
        network_rtt_ms: Optional[int] = None,
        network_bandwidth_kbps: Optional[int] = None,
        enable_diff_sync: bool = False,
        diff_base_fingerprint: Optional[str] = None,
        rate_limit_kbps: Optional[int] = None,
    ) -> Dict[str, Any]:
        started_at = time.time()
        self._cleanup_dedup_state()
        if message_id and self._is_duplicate_message(message_id):
            return {
                "applied": 0,
                "skipped": 0,
                "conflicts": 0,
                "duplicate_samples": 0,
                "deleted": 0,
                "applied_samples": [],
                "conflict_items": [],
                "duplicate_message": True,
                "batch_size": int(batch_size),
                "pipeline_batches": 0,
                "effective_kbps": 0.0,
            }

        applied: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        duplicate_samples: List[Dict[str, Any]] = []
        deleted = 0
        processed_bytes = 0
        pipeline_batches = 0

        safe_batch_size = self.recommend_batch_size(
            network_rtt_ms=network_rtt_ms,
            network_bandwidth_kbps=network_bandwidth_kbps,
            default_batch_size=batch_size,
        ) if adaptive_batch else max(1, int(batch_size))

        for offset in range(0, len(samples), safe_batch_size):
            batch = samples[offset:offset + safe_batch_size]
            pipeline_batches += 1
            batch_started_at = time.time()
            batch_bytes = 0
            for raw_sample in batch:
                batch_bytes += len(json.dumps(raw_sample, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                op = str(raw_sample.get("_op") or raw_sample.get("op") or "upsert").strip().lower()
                if op == "delete":
                    sample_id = str(raw_sample.get("id") or "")
                    existing = self.samples.get(sample_id)
                    if existing:
                        self._archive_sample(existing)
                        self.samples.pop(sample_id, None)
                        deleted += 1
                    else:
                        skipped.append({"id": sample_id, "reason": "delete_target_missing"})
                    continue

                incoming = self._normalize_or_patch_sample(raw_sample)
                fingerprint = self._build_sample_fingerprint(incoming)
                if self._is_duplicate_sample_fingerprint(fingerprint):
                    skipped.append(incoming)
                    duplicate_samples.append(incoming)
                    continue

                sample_id = incoming["id"]
                existing = self.samples.get(sample_id)
                if enable_diff_sync and existing and diff_base_fingerprint:
                    server_fp = self._build_rabin_fingerprint(existing)
                    if str(server_fp) != str(diff_base_fingerprint):
                        conflict_item = {
                            "conflict_id": f"gps_conflict_{datetime.now().timestamp()}_{sample_id}",
                            "sample_id": sample_id,
                            "project_id": incoming["project_id"],
                            "client_id": client_id,
                            "server_sample": existing,
                            "client_sample": incoming,
                            "reason": "diff_base_fingerprint_mismatch",
                            "created_at": datetime.now().isoformat(),
                            "resolution": "manual-required",
                        }
                        conflicts.append(conflict_item)
                        self.conflicts.append(conflict_item)
                        continue

                if not existing:
                    self.samples[sample_id] = incoming
                    applied.append(incoming)
                    self.processed_sample_fingerprints[fingerprint] = time.time()
                    continue

                conflict = self._detect_conflict(existing, incoming)
                if not conflict:
                    self._archive_sample(existing)
                    self.samples[sample_id] = incoming
                    applied.append(incoming)
                    self.processed_sample_fingerprints[fingerprint] = time.time()
                    continue

                conflict_item = {
                    "conflict_id": f"gps_conflict_{datetime.now().timestamp()}_{sample_id}",
                    "sample_id": sample_id,
                    "project_id": incoming["project_id"],
                    "client_id": client_id,
                    "server_sample": existing,
                    "client_sample": incoming,
                    "reason": conflict,
                    "created_at": datetime.now().isoformat()
                }

                if strategy == "client-wins":
                    self._archive_sample(existing)
                    self.samples[sample_id] = incoming
                    applied.append(incoming)
                    self.processed_sample_fingerprints[fingerprint] = time.time()
                    conflict_item["resolution"] = "client-wins"
                elif strategy == "server-wins":
                    skipped.append(incoming)
                    conflict_item["resolution"] = "server-wins"
                else:
                    server_ts = int(existing.get("updated_at", 0))
                    client_ts = int(incoming.get("updated_at", 0))
                    if strategy == "latest-wins" and client_ts >= server_ts:
                        self._archive_sample(existing)
                        self.samples[sample_id] = incoming
                        applied.append(incoming)
                        self.processed_sample_fingerprints[fingerprint] = time.time()
                        conflict_item["resolution"] = "client-latest"
                    elif strategy == "latest-wins":
                        skipped.append(incoming)
                        conflict_item["resolution"] = "server-latest"
                    else:
                        conflicts.append(conflict_item)
                        conflict_item["resolution"] = "manual-required"

                self.conflicts.append(conflict_item)

            processed_bytes += batch_bytes
            if rate_limit_kbps and rate_limit_kbps > 0:
                expected_seconds = (batch_bytes * 8) / (int(rate_limit_kbps) * 1000)
                elapsed = time.time() - batch_started_at
                if expected_seconds > elapsed:
                    # 控制单批休眠时长，避免极端场景阻塞太久
                    time.sleep(min(expected_seconds - elapsed, 0.2))

        if message_id:
            self.processed_messages[message_id] = time.time()

        elapsed_seconds = max(time.time() - started_at, 1e-6)
        effective_kbps = round((processed_bytes * 8 / 1000) / elapsed_seconds, 2)
        project_scope = [item for item in applied if item.get("project_id")]
        dataset_fp = self._build_rabin_fingerprint(project_scope)

        self._append_audit_event(
            action="sync_batch",
            details={
                "client_id": client_id,
                "message_id": message_id,
                "applied": len(applied),
                "conflicts": len(conflicts),
                "deleted": deleted,
                "batch_size": safe_batch_size,
                "pipeline_batches": pipeline_batches,
                "effective_kbps": effective_kbps,
                "dataset_fingerprint": dataset_fp,
            },
            success=True,
        )

        return {
            "applied": len(applied),
            "skipped": len(skipped),
            "conflicts": len(conflicts),
            "duplicate_samples": len(duplicate_samples),
            "deleted": deleted,
            "applied_samples": applied,
            "conflict_items": conflicts,
            "duplicate_message": False,
            "batch_size": safe_batch_size,
            "pipeline_batches": pipeline_batches,
            "effective_kbps": effective_kbps,
            "dataset_fingerprint": dataset_fp,
        }

    def get_samples(
        self,
        project_id: Optional[str] = None,
        since: Optional[int] = None,
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        rows = list(self.samples.values())
        if project_id:
            rows = [row for row in rows if row.get("project_id") == project_id]
        if since is not None:
            rows = [row for row in rows if int(row.get("updated_at", 0)) >= int(since)]
        rows.sort(key=lambda item: int(item.get("updated_at", 0)), reverse=True)
        return rows[:limit]

    def list_conflicts(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not project_id:
            return self.conflicts[-200:]
        return [item for item in self.conflicts if item.get("project_id") == project_id][-200:]

    def rollback(self, sample_id: str, to_version: Optional[int] = None) -> Dict[str, Any]:
        history = self.sample_history.get(sample_id, [])
        if not history:
            raise KeyError(f"样点 {sample_id} 没有可回滚历史")

        if to_version is None:
            target = history[-1]
            history.pop()
        else:
            matched = [item for item in history if int(item.get("version", 0)) == int(to_version)]
            if not matched:
                raise KeyError(f"样点 {sample_id} 不存在版本 {to_version}")
            target = matched[-1]
            history[:] = [item for item in history if int(item.get("version", 0)) < int(to_version)]

        current = self.samples.get(sample_id)
        if current:
            self._archive_sample(current)
        self.samples[sample_id] = deepcopy(target)
        self._append_audit_event(
            action="rollback",
            details={"sample_id": sample_id, "to_version": to_version, "result_version": target.get("version")},
            success=True,
        )
        return self.samples[sample_id]

    def export_geojson(self, project_id: str) -> Dict[str, Any]:
        samples = self.get_samples(project_id=project_id, limit=100000)
        features = []
        for sample in samples:
            properties = {
                "id": sample["id"],
                "project_id": sample["project_id"],
                "accuracy": sample.get("accuracy"),
                "altitude": sample.get("altitude"),
                "speed": sample.get("speed"),
                "heading": sample.get("heading"),
                "collected_at": sample.get("collected_at"),
                "updated_at": sample.get("updated_at"),
                "version": sample.get("version"),
                "source": sample.get("source"),
            }
            attributes = sample.get("attributes") or {}
            if isinstance(attributes, dict):
                properties.update(attributes)
            features.append({
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        sample.get("longitude"),
                        sample.get("latitude"),
                        sample.get("altitude") or 0
                    ]
                }
            })
        return {
            "type": "FeatureCollection",
            "features": features
        }

    def export_csv(self, project_id: str) -> str:
        samples = self.get_samples(project_id=project_id, limit=100000)
        attribute_keys = set()
        for sample in samples:
            attributes = sample.get("attributes") or {}
            if isinstance(attributes, dict):
                attribute_keys.update(attributes.keys())

        base_columns = [
            "id",
            "project_id",
            "latitude",
            "longitude",
            "accuracy",
            "altitude",
            "speed",
            "heading",
            "collected_at",
            "updated_at",
            "version",
            "source"
        ]
        columns = base_columns + sorted(attribute_keys)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for sample in samples:
            row = {column: sample.get(column, "") for column in base_columns}
            attributes = sample.get("attributes") or {}
            if isinstance(attributes, dict):
                for key in attribute_keys:
                    row[key] = attributes.get(key, "")
            writer.writerow(row)
        return output.getvalue()

    def get_summary(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        rows = self.get_samples(project_id=project_id, limit=100000)
        return {
            "total_samples": len(rows),
            "total_conflicts": len(self.list_conflicts(project_id=project_id)),
            "latest_updated_at": rows[0].get("updated_at") if rows else None,
            "audit_events": len(self._audit_logs),
            "backup_count": len(self._backups),
        }

    def create_backup(self, mode: str = "full", user_id: Optional[str] = None) -> Dict[str, Any]:
        normalized_mode = str(mode or "full").strip().lower()
        if normalized_mode not in {"full", "incremental"}:
            raise ValueError("mode 仅支持 full 或 incremental")

        snapshot = {
            "samples": deepcopy(self.samples),
            "conflicts": deepcopy(self.conflicts[-500:]),
            "sample_history": deepcopy(self.sample_history),
            "created_at": _now_ms(),
        }
        if normalized_mode == "incremental":
            delta_samples = {}
            for key, value in snapshot["samples"].items():
                if self._last_full_snapshot.get("samples", {}).get(key) != value:
                    delta_samples[key] = value
            payload = {
                "base_snapshot": deepcopy(self._last_full_snapshot.get("samples", {})),
                "delta_samples": delta_samples,
                "conflicts": snapshot["conflicts"],
                "sample_history": snapshot["sample_history"],
            }
        else:
            payload = snapshot
            self._last_full_snapshot = deepcopy(snapshot)

        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        compressed = gzip.compress(raw)
        backup_id = f"gpsbak_{uuid4().hex[:12]}"
        item = {
            "backup_id": backup_id,
            "mode": normalized_mode,
            "created_at": _now_ms(),
            "digest": hashlib.sha256(raw).hexdigest(),
            "payload": base64.b64encode(compressed).decode("ascii"),
            "created_by": str(user_id or "system"),
        }
        self._backups[backup_id] = item
        self._append_audit_event(
            action="create_backup",
            details={"backup_id": backup_id, "mode": normalized_mode, "user_id": user_id},
            success=True,
        )
        return {k: v for k, v in item.items() if k != "payload"}

    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        item = self._backups.get(str(backup_id or ""))
        if not item:
            raise KeyError("backup 不存在")
        raw = gzip.decompress(base64.b64decode(item["payload"].encode("ascii")))
        verified = hmac.compare_digest(hashlib.sha256(raw).hexdigest(), str(item["digest"]))
        return {
            "backup_id": item["backup_id"],
            "mode": item["mode"],
            "verified": verified,
            "created_at": item["created_at"],
        }

    def restore_backup(self, backup_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        item = self._backups.get(str(backup_id or ""))
        if not item:
            raise KeyError("backup 不存在")
        raw = gzip.decompress(base64.b64decode(item["payload"].encode("ascii")))
        digest = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(digest, str(item["digest"])):
            raise ValueError("backup 完整性校验失败")
        payload = json.loads(raw.decode("utf-8"))
        if item["mode"] == "incremental":
            merged_samples = {**(payload.get("base_snapshot") or {}), **(payload.get("delta_samples") or {})}
            self.samples = merged_samples
            self.conflicts = list(payload.get("conflicts") or [])
            self.sample_history = dict(payload.get("sample_history") or {})
        else:
            self.samples = dict(payload.get("samples") or {})
            self.conflicts = list(payload.get("conflicts") or [])
            self.sample_history = dict(payload.get("sample_history") or {})
        self._append_audit_event(
            action="restore_backup",
            details={"backup_id": backup_id, "mode": item["mode"], "user_id": user_id},
            success=True,
        )
        return {
            "backup_id": item["backup_id"],
            "mode": item["mode"],
            "restored_samples": len(self.samples),
            "restored_conflicts": len(self.conflicts),
        }

    def list_audit_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 2000))
        return deepcopy(self._audit_logs[-safe_limit:])

    def verify_audit_integrity(self) -> Dict[str, Any]:
        previous = "gps_audit_genesis"
        checked = 0
        for idx, item in enumerate(self._audit_logs):
            payload = json.dumps(
                {
                    "event_id": item.get("event_id"),
                    "action": item.get("action"),
                    "timestamp": item.get("timestamp"),
                    "success": item.get("success"),
                    "details": item.get("details"),
                    "previous_hash": item.get("previous_hash"),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            expected = hmac.new(self._audit_hmac_key, previous.encode("utf-8") + payload, hashlib.sha256).hexdigest()
            if str(item.get("previous_hash")) != previous or str(item.get("hash")) != expected:
                return {"valid": False, "checked": checked, "failed_index": idx}
            previous = expected
            checked += 1
        return {"valid": True, "checked": checked, "failed_index": None}

    def _append_audit_event(self, action: str, details: Dict[str, Any], success: bool) -> None:
        event = {
            "event_id": f"gps_audit_{uuid4().hex[:12]}",
            "action": str(action or "unknown"),
            "timestamp": _now_ms(),
            "success": bool(success),
            "details": deepcopy(details),
            "previous_hash": self._last_audit_hash,
        }
        payload = json.dumps(
            {
                "event_id": event["event_id"],
                "action": event["action"],
                "timestamp": event["timestamp"],
                "success": event["success"],
                "details": event["details"],
                "previous_hash": event["previous_hash"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        event_hash = hmac.new(
            self._audit_hmac_key,
            self._last_audit_hash.encode("utf-8") + payload,
            hashlib.sha256,
        ).hexdigest()
        event["hash"] = event_hash
        self._last_audit_hash = event_hash
        self._audit_logs.append(event)

    def _normalize_or_patch_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        op = str(sample.get("_op") or sample.get("op") or "upsert").strip().lower()
        if op != "patch":
            return self._normalize_sample(sample)
        sample_id = str(sample.get("id") or "")
        if not sample_id:
            raise ValueError("patch 操作必须包含 id")
        existing = self.samples.get(sample_id)
        if not existing:
            raise KeyError(f"patch 目标样点不存在: {sample_id}")
        merged = deepcopy(existing)
        patch_fields = sample.get("changed_fields") or sample.get("patch") or {}
        if isinstance(patch_fields, list):
            for field_name in patch_fields:
                key = str(field_name)
                if key in sample:
                    merged[key] = sample.get(key)
        elif isinstance(patch_fields, dict):
            for key, value in patch_fields.items():
                merged[str(key)] = value
        else:
            for key, value in sample.items():
                if key in {"_op", "op"}:
                    continue
                merged[str(key)] = value
        merged["updated_at"] = int(sample.get("updated_at") or sample.get("updatedAt") or _now_ms())
        requested_version = int(sample.get("version") or merged.get("version") or existing.get("version", 1))
        merged["version"] = int(max(int(existing.get("version", 1)), requested_version))
        return self._normalize_sample(merged)

    def _normalize_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        now = _now_ms()
        sample_id = sample.get("id") or f"gps_{now}"
        project_id = sample.get("project_id") or sample.get("projectId") or "default_mobile_project"
        normalized = {
            "id": str(sample_id),
            "project_id": str(project_id),
            "latitude": float(sample.get("latitude")),
            "longitude": float(sample.get("longitude")),
            "accuracy": float(sample.get("accuracy", 0)),
            "altitude": sample.get("altitude"),
            "speed": sample.get("speed"),
            "heading": sample.get("heading"),
            "attributes": sample.get("attributes") or {},
            "collected_at": int(sample.get("collected_at") or sample.get("collectedAt") or now),
            "updated_at": int(sample.get("updated_at") or sample.get("updatedAt") or now),
            "version": int(sample.get("version", 1)),
            "source": sample.get("source", "mobile"),
            "fingerprint_rabin": sample.get("fingerprint_rabin") or self._build_rabin_fingerprint(sample),
        }
        return normalized

    def _detect_conflict(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> Optional[str]:
        existing_version = int(existing.get("version", 1))
        incoming_version = int(incoming.get("version", 1))
        if incoming_version < existing_version:
            return "incoming_version_older"

        if incoming_version == existing_version:
            existing_updated = int(existing.get("updated_at", 0))
            incoming_updated = int(incoming.get("updated_at", 0))
            changed = self._strip_meta(existing) != self._strip_meta(incoming)
            if changed and incoming_updated <= existing_updated:
                return "same_version_but_stale_timestamp"

        return None

    def _strip_meta(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        data = deepcopy(sample)
        data.pop("updated_at", None)
        data.pop("collected_at", None)
        data.pop("fingerprint_rabin", None)
        return data

    def _archive_sample(self, sample: Dict[str, Any]) -> None:
        sample_id = sample["id"]
        self.sample_history.setdefault(sample_id, []).append(deepcopy(sample))

    def _build_sample_fingerprint(self, sample: Dict[str, Any]) -> str:
        lat = round(float(sample.get("latitude", 0.0)), 6)
        lng = round(float(sample.get("longitude", 0.0)), 6)
        time_bucket = int(sample.get("collected_at", 0)) // 5000
        project_id = sample.get("project_id", "")
        return f"{project_id}:{lat}:{lng}:{time_bucket}"

    def _build_rabin_fingerprint(self, payload: Any) -> str:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        mod = (1 << 61) - 1
        base = 257
        value = 0
        for byte in data:
            value = (value * base + byte + 1) % mod
        return f"rb_{value:016x}"

    def _is_duplicate_sample_fingerprint(self, fingerprint: str) -> bool:
        if fingerprint in self.processed_sample_fingerprints:
            return True
        self.processed_sample_fingerprints[fingerprint] = time.time()
        return False

    def _is_duplicate_message(self, message_id: str) -> bool:
        if message_id in self.processed_messages:
            return True
        self.processed_messages[message_id] = time.time()
        return False

    def _cleanup_dedup_state(self) -> None:
        now = time.time()
        expire_before = now - self.dedup_ttl_seconds
        self.processed_messages = {
            key: ts for key, ts in self.processed_messages.items() if ts >= expire_before
        }
        self.processed_sample_fingerprints = {
            key: ts for key, ts in self.processed_sample_fingerprints.items() if ts >= expire_before
        }
        self._sensitive_tokens = {
            key: value for key, value in self._sensitive_tokens.items() if float(value.get("expires_at", 0)) >= now
        }
        self._rate_limit_state = {
            key: [ts for ts in values if now - ts <= 60]
            for key, values in self._rate_limit_state.items()
            if values
        }


mobile_gps_service = MobileGPSService()
