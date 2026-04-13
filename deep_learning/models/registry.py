"""模型注册、版本与序列化管理。"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class ModelMetadata:
    name: str
    version: str
    framework: str
    created_at: str
    metrics: dict[str, float]


@dataclass
class ModelRegistration:
    """注册表条目。"""

    name: str
    builder: Callable[..., Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ModelRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, Callable[..., Any]] = {}
        self._entries: dict[str, ModelRegistration] = {}
        self._events: list[Callable[[dict[str, Any]], None]] = []

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = (name or "").strip()
        if not normalized:
            raise ValueError("模型名称不能为空")
        return normalized

    @staticmethod
    def _validate_builder(builder: Callable[..., Any]) -> None:
        if not callable(builder):
            raise TypeError("builder 必须是可调用对象")

    def register(
        self,
        name: str,
        builder: Callable[..., Any],
        *,
        metadata: dict[str, Any] | None = None,
        tags: set[str] | list[str] | tuple[str, ...] | None = None,
        overwrite: bool = True,
    ) -> None:
        normalized_name = self._normalize_name(name)
        self._validate_builder(builder)

        if not overwrite and normalized_name in self._entries:
            raise ValueError(f"模型已存在且禁止覆盖: {normalized_name}")

        now = datetime.now(timezone.utc).isoformat()
        previous = self._entries.get(normalized_name)
        registered_at = previous.registered_at if previous is not None else now

        entry = ModelRegistration(
            name=normalized_name,
            builder=builder,
            metadata=dict(metadata or {}),
            tags={str(tag) for tag in (tags or set()) if str(tag).strip()},
            registered_at=registered_at,
            updated_at=now,
        )
        self._builders[normalized_name] = builder
        self._entries[normalized_name] = entry

        self._emit(
            "model_updated" if previous is not None else "model_registered",
            {
                "name": normalized_name,
                "metadata": dict(entry.metadata),
                "tags": sorted(entry.tags),
                "registered_at": entry.registered_at,
                "updated_at": entry.updated_at,
            },
        )

    def unregister(self, name: str) -> None:
        normalized_name = self._normalize_name(name)
        if normalized_name not in self._entries:
            raise KeyError(f"模型未注册: {normalized_name}")
        del self._entries[normalized_name]
        if normalized_name in self._builders:
            del self._builders[normalized_name]

        self._emit(
            "model_unregistered",
            {
                "name": normalized_name,
                "unregistered_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def create(self, name: str, **kwargs: Any) -> Any:
        normalized_name = self._normalize_name(name)
        if normalized_name not in self._builders:
            raise KeyError(f"模型未注册: {normalized_name}")
        return self._builders[normalized_name](**kwargs)

    def get_metadata(self, name: str) -> dict[str, Any]:
        normalized_name = self._normalize_name(name)
        if normalized_name not in self._entries:
            raise KeyError(f"模型未注册: {normalized_name}")
        return dict(self._entries[normalized_name].metadata)

    def list_models(self) -> list[str]:
        return sorted(self._builders.keys())

    def query(
        self,
        *,
        framework: str | None = None,
        tags: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> list[str]:
        framework_filter = (framework or "").strip().lower()
        tag_filter = {str(t).strip() for t in (tags or set()) if str(t).strip()}

        names: list[str] = []
        for name, entry in self._entries.items():
            item_framework = str(entry.metadata.get("framework", "")).strip().lower()
            if framework_filter and item_framework != framework_filter:
                continue
            if tag_filter and not tag_filter.issubset(entry.tags):
                continue
            names.append(name)
        return sorted(names)

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self._entries),
            "models": [
                {
                    "name": entry.name,
                    "metadata": dict(entry.metadata),
                    "tags": sorted(entry.tags),
                    "registered_at": entry.registered_at,
                    "updated_at": entry.updated_at,
                }
                for entry in sorted(self._entries.values(), key=lambda x: x.name)
            ],
        }

    def register_event_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        if not callable(handler):
            raise TypeError("handler 必须是可调用对象")
        self._events.append(handler)

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        item = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        for handler in list(self._events):
            try:
                handler(item)
            except Exception:
                # 事件回调不应阻断主流程。
                continue


class ModelVersioning:
    def __init__(self, repo_dir: str = "deep_learning/models/repository") -> None:
        self.repo_dir = Path(repo_dir)
        self.repo_dir.mkdir(parents=True, exist_ok=True)

    def allocate_version(self, model_name: str) -> str:
        model_dir = self.repo_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        versions = [d.name for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
        nums = [int(v[1:]) for v in versions if v[1:].isdigit()]
        next_version = f"v{(max(nums) + 1) if nums else 1}"
        (model_dir / next_version).mkdir(parents=True, exist_ok=False)
        return next_version

    def save_metadata(self, metadata: ModelMetadata) -> str:
        model_dir = self.repo_dir / metadata.name / metadata.version
        model_dir.mkdir(parents=True, exist_ok=True)
        file_path = model_dir / "metadata.json"
        file_path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(file_path)

    def latest_version(self, model_name: str) -> str | None:
        model_dir = self.repo_dir / model_name
        if not model_dir.exists():
            return None
        versions = [d.name for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
        nums = sorted((int(v[1:]) for v in versions if v[1:].isdigit()), reverse=True)
        return f"v{nums[0]}" if nums else None


class ModelSerializer:
    def save(self, model: Any, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fp:
            pickle.dump(model, fp)

    def load(self, path: str) -> Any:
        with open(path, "rb") as fp:
            return pickle.load(fp)


class ModelExporter:
    def export_torchscript(self, model: Any, path: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("# TorchScript export placeholder\n")
            fp.write(f"model={type(model).__name__}\n")
        return path

    def export_onnx(self, model: Any, path: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("# ONNX export placeholder\n")
            fp.write(f"model={type(model).__name__}\n")
        return path


class ModelQuantizer:
    def quantize(self, weights: list[float], dtype: str = "float16") -> list[float]:
        if dtype not in {"float16", "int8"}:
            raise ValueError("仅支持 float16/int8")
        if dtype == "float16":
            return [round(float(w), 4) for w in weights]
        return [max(-128, min(127, int(round(w)))) for w in weights]


def build_metadata(name: str, version: str, metrics: dict[str, float], framework: str = "pytorch") -> ModelMetadata:
    return ModelMetadata(
        name=name,
        version=version,
        framework=framework,
        created_at=datetime.now(timezone.utc).isoformat(),
        metrics=metrics,
    )
