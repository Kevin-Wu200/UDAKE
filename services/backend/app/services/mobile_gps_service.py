"""
移动端 GPS 采样同步服务
提供样点 upsert、冲突检测、版本回滚与导出能力
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional
import csv
import time


class MobileGPSService:
    def __init__(self) -> None:
        self.samples: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[Dict[str, Any]] = []
        self.sample_history: Dict[str, List[Dict[str, Any]]] = {}
        self.processed_messages: Dict[str, float] = {}
        self.processed_sample_fingerprints: Dict[str, float] = {}
        self.dedup_ttl_seconds = 15 * 60

    def upsert_samples(
        self,
        client_id: str,
        samples: List[Dict[str, Any]],
        strategy: str = "latest-wins",
        message_id: Optional[str] = None,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        self._cleanup_dedup_state()
        if message_id and self._is_duplicate_message(message_id):
            return {
                "applied": 0,
                "skipped": 0,
                "conflicts": 0,
                "duplicate_samples": 0,
                "applied_samples": [],
                "conflict_items": [],
                "duplicate_message": True
            }

        applied: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        duplicate_samples: List[Dict[str, Any]] = []

        safe_batch_size = max(1, int(batch_size))
        for offset in range(0, len(samples), safe_batch_size):
            batch = samples[offset:offset + safe_batch_size]
            for raw_sample in batch:
                incoming = self._normalize_sample(raw_sample)
                fingerprint = self._build_sample_fingerprint(incoming)
                if self._is_duplicate_sample_fingerprint(fingerprint):
                    skipped.append(incoming)
                    duplicate_samples.append(incoming)
                    continue

                sample_id = incoming["id"]
                existing = self.samples.get(sample_id)
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

        if message_id:
            self.processed_messages[message_id] = time.time()

        return {
            "applied": len(applied),
            "skipped": len(skipped),
            "conflicts": len(conflicts),
            "duplicate_samples": len(duplicate_samples),
            "applied_samples": applied,
            "conflict_items": conflicts,
            "duplicate_message": False
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
            "latest_updated_at": rows[0].get("updated_at") if rows else None
        }

    def _normalize_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        now = int(datetime.now().timestamp() * 1000)
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
            "source": sample.get("source", "mobile")
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


mobile_gps_service = MobileGPSService()
