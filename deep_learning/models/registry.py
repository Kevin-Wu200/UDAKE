"""模型注册、版本与序列化管理。"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import asdict, dataclass
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


class ModelRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, builder: Callable[..., Any]) -> None:
        self._builders[name] = builder

    def create(self, name: str, **kwargs: Any) -> Any:
        if name not in self._builders:
            raise KeyError(f"模型未注册: {name}")
        return self._builders[name](**kwargs)

    def list_models(self) -> list[str]:
        return sorted(self._builders.keys())


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
