"""阶段7：模型管理系统（注册、存储、加载、验证、部署）。"""

from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class RegisteredModel:
    model_id: str
    version: str
    model_type: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


class FusionModelManager:
    """面向融合策略与元学习器的模型管理。"""

    def __init__(self, root_dir: str = "deep_learning/fusion/repository") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._builders: dict[str, Callable[..., Any]] = {}
        self._cache: dict[str, Any] = {}

    def register_builder(self, model_id: str, builder: Callable[..., Any]) -> None:
        self._builders[model_id] = builder

    def list_models(self) -> list[str]:
        return sorted(self._builders.keys())

    def create_model(self, model_id: str, **kwargs: Any) -> Any:
        if model_id not in self._builders:
            raise KeyError(f"模型未注册: {model_id}")
        return self._builders[model_id](**kwargs)

    def allocate_version(self, model_id: str) -> str:
        model_dir = self.root_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        versions = [d.name for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
        nums = [int(v[1:]) for v in versions if v[1:].isdigit()]
        next_ver = f"v{(max(nums) + 1) if nums else 1}"
        (model_dir / next_ver).mkdir(parents=True, exist_ok=False)
        return next_ver

    def store_model(
        self,
        model_id: str,
        model_obj: Any,
        model_type: str,
        config: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
        version: str | None = None,
    ) -> RegisteredModel:
        ver = version or self.allocate_version(model_id)
        target = self.root_dir / model_id / ver
        target.mkdir(parents=True, exist_ok=True)

        model_file = target / "model.pkl"
        with open(model_file, "wb") as fp:
            pickle.dump(model_obj, fp)

        cfg = config or {}
        (target / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

        reg = RegisteredModel(
            model_id=model_id,
            version=ver,
            model_type=model_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
            metrics=metrics or {},
        )
        (target / "metadata.json").write_text(json.dumps(asdict(reg), ensure_ascii=False, indent=2), encoding="utf-8")

        self._cache[self._cache_key(model_id, ver)] = model_obj
        return reg

    def load_model(
        self,
        model_id: str,
        version: str | None = None,
        lazy: bool = True,
        use_cache: bool = True,
    ) -> Any:
        ver = version or self.latest_version(model_id)
        if ver is None:
            raise FileNotFoundError(f"模型不存在: {model_id}")

        key = self._cache_key(model_id, ver)
        model_file = self.root_dir / model_id / ver / "model.pkl"
        if lazy:
            # 懒加载场景仅返回路径描述，减少内存占用。
            return {"model_id": model_id, "version": ver, "path": str(model_file)}

        if use_cache and key in self._cache:
            return self._cache[key]

        with open(model_file, "rb") as fp:
            obj = pickle.load(fp)
        if use_cache:
            self._cache[key] = obj
        return obj

    def batch_load(self, items: list[tuple[str, str | None]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for model_id, version in items:
            try:
                out[model_id] = self.load_model(model_id=model_id, version=version, lazy=False, use_cache=True)
            except Exception as exc:
                out[model_id] = {"error": str(exc)}
        return out

    def latest_version(self, model_id: str) -> str | None:
        model_dir = self.root_dir / model_id
        if not model_dir.exists():
            return None
        versions = [d.name for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
        nums = sorted((int(v[1:]) for v in versions if v[1:].isdigit()), reverse=True)
        return f"v{nums[0]}" if nums else None

    def list_versions(self, model_id: str) -> list[str]:
        model_dir = self.root_dir / model_id
        if not model_dir.exists():
            return []
        versions = [d.name for d in model_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
        versions.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else -1)
        return versions

    def validate_model(
        self,
        model_id: str,
        version: str | None = None,
        performance_validator: Callable[[Any], dict[str, float]] | None = None,
    ) -> dict[str, Any]:
        ver = version or self.latest_version(model_id)
        if ver is None:
            return {"ok": False, "reason": "model_not_found"}

        target = self.root_dir / model_id / ver
        required = [target / "model.pkl", target / "config.json", target / "metadata.json"]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            return {"ok": False, "reason": "missing_files", "missing": missing}

        md5 = self._file_md5(target / "model.pkl")
        payload: dict[str, Any] = {
            "ok": True,
            "model_id": model_id,
            "version": ver,
            "integrity": {"md5": md5},
        }

        if performance_validator is not None:
            model = self.load_model(model_id=model_id, version=ver, lazy=False, use_cache=True)
            payload["performance"] = performance_validator(model)

        return payload

    def export_model(self, model_id: str, version: str | None = None, export_format: str = "onnx") -> str:
        ver = version or self.latest_version(model_id)
        if ver is None:
            raise FileNotFoundError(f"模型不存在: {model_id}")

        if export_format not in {"onnx", "torchscript", "pickle"}:
            raise ValueError("仅支持 onnx/torchscript/pickle")

        target = self.root_dir / model_id / ver
        ext = {"onnx": "onnx", "torchscript": "ts", "pickle": "pkl"}[export_format]
        out = target / f"export.{ext}"

        if export_format == "pickle":
            model_path = target / "model.pkl"
            out.write_bytes(model_path.read_bytes())
        else:
            out.write_text(
                f"# export placeholder\nmodel_id={model_id}\nversion={ver}\nformat={export_format}\n",
                encoding="utf-8",
            )

        return str(out)

    def deploy_ab_test(
        self,
        model_a: tuple[str, str | None],
        model_b: tuple[str, str | None],
        traffic_split: float = 0.5,
    ) -> dict[str, Any]:
        ratio = float(min(0.95, max(0.05, traffic_split)))
        a_id, a_ver = model_a
        b_id, b_ver = model_b

        resolved_a = a_ver or self.latest_version(a_id)
        resolved_b = b_ver or self.latest_version(b_id)
        if resolved_a is None or resolved_b is None:
            raise FileNotFoundError("A/B 模型版本不存在")

        deployment = {
            "model_a": {"id": a_id, "version": resolved_a, "ratio": ratio},
            "model_b": {"id": b_id, "version": resolved_b, "ratio": 1.0 - ratio},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        dep_dir = self.root_dir / "deployments"
        dep_dir.mkdir(parents=True, exist_ok=True)
        dep_file = dep_dir / f"ab_{a_id}_{resolved_a}__{b_id}_{resolved_b}.json"
        dep_file.write_text(json.dumps(deployment, ensure_ascii=False, indent=2), encoding="utf-8")
        return deployment

    def _cache_key(self, model_id: str, version: str) -> str:
        return f"{model_id}:{version}"

    def _file_md5(self, path: Path) -> str:
        h = hashlib.md5()  # noqa: S324 - 仅用于完整性指纹
        with open(path, "rb") as fp:
            for chunk in iter(lambda: fp.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


def load_model_metadata(model_dir: str) -> dict[str, Any]:
    meta_file = Path(model_dir) / "metadata.json"
    if not meta_file.exists():
        return {}
    return json.loads(meta_file.read_text(encoding="utf-8"))


def build_model_signature(model_id: str, version: str, payload: dict[str, Any] | None = None) -> str:
    seed = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    raw = f"{model_id}:{version}:{seed}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()  # noqa: S324 - 仅用于签名标识
