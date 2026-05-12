"""Structured audit logger for product-key validation."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from ..security.data_masking import mask_ip, mask_product_key


class ProductKeyAuditLogger:
    def __init__(self, cache_backend: Any, *, archive_size: int = 5000) -> None:
        self._cache = cache_backend
        self._archive_size = max(100, int(archive_size))
        self._key = "audit:product_key_validation"
        self._key_status_key = "audit:key_status_change"

    def append(
        self,
        *,
        ip_address: str,
        user_agent: str | None,
        product_key: str,
        valid: bool,
        reason: str,
        key_type: str | None,
        processing_time_ms: int,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": int(time.time()),
            "event": "product_key_validation",
            "ip_address": mask_ip(ip_address),
            "user_agent": str(user_agent or "")[:512],
            "product_key": mask_product_key(product_key),
            "result": {
                "valid": bool(valid),
                "reason": str(reason),
                "key_type": key_type,
            },
            "processing_time_ms": max(0, int(processing_time_ms)),
        }
        rows = self._cache.get(self._key)
        logs: List[Dict[str, Any]] = list(rows) if isinstance(rows, list) else []
        logs.append(entry)
        if len(logs) > self._archive_size:
            logs = logs[-self._archive_size :]
        self._cache.set(self._key, logs, ttl=30 * 24 * 60 * 60)
        return entry

    def log_key_status_change(
        self,
        *,
        user_id: int,
        old_status: str,
        new_status: str,
        product_key: str | None = None,
        operator: str = "system",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": int(time.time()),
            "event": "key_status_change",
            "user_id": user_id,
            "old_status": old_status,
            "new_status": new_status,
            "product_key": mask_product_key(product_key) if product_key else None,
            "operator": operator,
            "ip_address": mask_ip(ip_address) if ip_address else None,
            "user_agent": str(user_agent or "")[:512],
        }
        rows = self._cache.get(self._key_status_key)
        logs: List[Dict[str, Any]] = list(rows) if isinstance(rows, list) else []
        logs.append(entry)
        if len(logs) > self._archive_size:
            logs = logs[-self._archive_size :]
        self._cache.set(self._key_status_key, logs, ttl=30 * 24 * 60 * 60)
        return entry

    def query_latest(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._cache.get(self._key)
        logs: List[Dict[str, Any]] = list(rows) if isinstance(rows, list) else []
        return logs[-max(1, int(limit)) :]

    def query_key_status_changes(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._cache.get(self._key_status_key)
        logs: List[Dict[str, Any]] = list(rows) if isinstance(rows, list) else []
        return logs[-max(1, int(limit)) :]

    def export_json(self, *, limit: int = 200) -> str:
        return json.dumps(self.query_latest(limit=limit), ensure_ascii=False)
