"""Runtime config manager with versioning, diff, rollback, and hot-reload support."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class ConfigVersion:
    version: int
    checksum: str
    created_at: int
    actor: str
    comment: str
    data: Dict[str, Any]


class RuntimeConfigManager:
    def __init__(
        self,
        *,
        config_path: str,
        max_history: int = 100,
    ) -> None:
        self._path = Path(config_path).expanduser().resolve()
        self._max_history = max(10, int(max_history))
        self._lock = threading.RLock()
        self._versions: List[ConfigVersion] = []
        self._callbacks: List[Callable[[ConfigVersion], None]] = []
        self._mtime = 0.0
        self._load_initial()

    def _checksum(self, payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _read_file(self) -> Dict[str, Any]:
        if not self._path.exists() or yaml is None:
            return {}
        with self._path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        return loaded if isinstance(loaded, dict) else {}

    def _write_file(self, payload: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if yaml is None:
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            self._path.write_text(text, encoding="utf-8")
            return
        with self._path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=True)

    def _append_version(self, payload: Dict[str, Any], *, actor: str, comment: str) -> ConfigVersion:
        version = int(self._versions[-1].version + 1) if self._versions else 1
        current = ConfigVersion(
            version=version,
            checksum=self._checksum(payload),
            created_at=int(time.time()),
            actor=str(actor or "system"),
            comment=str(comment or ""),
            data=dict(payload),
        )
        self._versions.append(current)
        if len(self._versions) > self._max_history:
            self._versions = self._versions[-self._max_history :]
        return current

    def _emit(self, config_version: ConfigVersion) -> None:
        for callback in list(self._callbacks):
            try:
                callback(config_version)
            except Exception:
                continue

    def _load_initial(self) -> None:
        with self._lock:
            payload = self._read_file()
            current = self._append_version(payload, actor="system", comment="initial_load")
            self._mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
        self._emit(current)

    def register_callback(self, callback: Callable[[ConfigVersion], None]) -> None:
        with self._lock:
            self._callbacks.append(callback)

    def current(self) -> Dict[str, Any]:
        with self._lock:
            current = self._versions[-1]
        return {
            "version": current.version,
            "checksum": current.checksum,
            "created_at": current.created_at,
            "actor": current.actor,
            "comment": current.comment,
            "data": dict(current.data),
        }

    def history(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self._versions)[-max(1, int(limit)) :]
        return [
            {
                "version": row.version,
                "checksum": row.checksum,
                "created_at": row.created_at,
                "actor": row.actor,
                "comment": row.comment,
            }
            for row in rows
        ]

    def update(self, payload: Dict[str, Any], *, actor: str = "system", comment: str = "") -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload 必须是对象")
        with self._lock:
            current = self._versions[-1].data if self._versions else {}
            merged = dict(current)
            merged.update(payload)
            self._write_file(merged)
            self._mtime = self._path.stat().st_mtime if self._path.exists() else self._mtime
            new_version = self._append_version(merged, actor=actor, comment=comment or "update")
        self._emit(new_version)
        return self.current()

    def rollback(self, version: int, *, actor: str = "system") -> Dict[str, Any]:
        with self._lock:
            target: Optional[ConfigVersion] = None
            for row in self._versions:
                if int(row.version) == int(version):
                    target = row
                    break
            if target is None:
                raise ValueError("目标版本不存在")
            self._write_file(target.data)
            self._mtime = self._path.stat().st_mtime if self._path.exists() else self._mtime
            new_version = self._append_version(dict(target.data), actor=actor, comment=f"rollback_to_{version}")
        self._emit(new_version)
        return self.current()

    def diff(self, from_version: int, to_version: int) -> Dict[str, Any]:
        with self._lock:
            left = next((item for item in self._versions if item.version == int(from_version)), None)
            right = next((item for item in self._versions if item.version == int(to_version)), None)
        if left is None or right is None:
            raise ValueError("对比版本不存在")

        left_data = left.data
        right_data = right.data
        keys = sorted(set(left_data.keys()) | set(right_data.keys()))
        changed: List[Dict[str, Any]] = []
        for key in keys:
            lv = left_data.get(key)
            rv = right_data.get(key)
            if lv != rv:
                changed.append({"key": key, "from": lv, "to": rv})
        return {
            "from_version": int(from_version),
            "to_version": int(to_version),
            "changed": changed,
            "changed_count": len(changed),
        }

    def check_reload(self, *, actor: str = "system") -> Dict[str, Any]:
        current_mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
        with self._lock:
            if current_mtime <= self._mtime:
                return {"reloaded": False, "version": self._versions[-1].version}
            payload = self._read_file()
            self._mtime = current_mtime
            new_version = self._append_version(payload, actor=actor, comment="hot_reload")
        self._emit(new_version)
        return {"reloaded": True, "version": new_version.version}


_runtime_manager: Optional[RuntimeConfigManager] = None


def get_runtime_config_manager(config_path: str) -> RuntimeConfigManager:
    global _runtime_manager
    if _runtime_manager is None:
        _runtime_manager = RuntimeConfigManager(config_path=config_path)
    return _runtime_manager


def reset_runtime_config_manager() -> None:
    global _runtime_manager
    _runtime_manager = None
