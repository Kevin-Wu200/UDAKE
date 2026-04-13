"""统一解释适配框架：基类、特征接口、解释结果格式与自动加载。"""

from __future__ import annotations

from abc import ABC, abstractmethod
import csv
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import importlib
import inspect
import json
import logging
from pathlib import Path
import pkgutil
import shutil
from threading import RLock
import traceback
from types import ModuleType
from typing import Any, Callable, Iterable
from uuid import uuid4

import numpy as np

logger = logging.getLogger(__name__)


class FeatureType(StrEnum):
    """特征类型定义。"""

    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"
    BINARY = "binary"
    ORDINAL = "ordinal"


@dataclass(frozen=True)
class FeatureMetadata:
    """单个特征元数据与约束。"""

    name: str
    feature_type: FeatureType
    description: str = ""
    required: bool = True
    default: Any | None = None
    min_value: float | None = None
    max_value: float | None = None
    choices: tuple[Any, ...] = ()

    def validate(self, value: Any) -> tuple[bool, str]:
        if value is None:
            if self.required and self.default is None:
                return False, f"特征 `{self.name}` 必填"
            return True, ""

        if self.feature_type in {FeatureType.CONTINUOUS, FeatureType.DISCRETE, FeatureType.ORDINAL}:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return False, f"特征 `{self.name}` 需要数值类型"
            if self.feature_type in {FeatureType.DISCRETE, FeatureType.ORDINAL} and abs(numeric - round(numeric)) > 1e-9:
                return False, f"特征 `{self.name}` 需要整数值"
            if self.min_value is not None and numeric < self.min_value:
                return False, f"特征 `{self.name}` 小于最小值 {self.min_value}"
            if self.max_value is not None and numeric > self.max_value:
                return False, f"特征 `{self.name}` 大于最大值 {self.max_value}"

        if self.feature_type == FeatureType.BINARY and value not in {0, 1, False, True}:
            return False, f"特征 `{self.name}` 需要二值(0/1)"

        if self.choices and value not in self.choices:
            return False, f"特征 `{self.name}` 不在允许集合 {list(self.choices)}"

        return True, ""

    def transform(self, value: Any) -> Any:
        """将输入转换为统一类型。"""

        if value is None:
            return self.default

        if self.feature_type == FeatureType.CONTINUOUS:
            return float(value)
        if self.feature_type in {FeatureType.DISCRETE, FeatureType.ORDINAL}:
            return int(round(float(value)))
        if self.feature_type == FeatureType.BINARY:
            return int(bool(value))
        return value


@dataclass
class FeatureSchema:
    """特征集合接口。"""

    model_name: str
    features: list[FeatureMetadata]

    def feature_names(self) -> list[str]:
        return [item.name for item in self.features]

    def validate(self, values: dict[str, Any]) -> None:
        errors: list[str] = []
        for item in self.features:
            ok, reason = item.validate(values.get(item.name))
            if not ok:
                errors.append(reason)
        if errors:
            raise ValueError("; ".join(errors))

    def transform(self, values: dict[str, Any]) -> dict[str, Any]:
        transformed: dict[str, Any] = {}
        errors: list[str] = []
        for item in self.features:
            transformed[item.name] = item.transform(values.get(item.name))
            ok, reason = item.validate(transformed[item.name])
            if not ok:
                errors.append(reason)
        if errors:
            raise ValueError("; ".join(errors))
        return transformed

    def generate_docs(self) -> str:
        lines = [f"# 特征文档 - {self.model_name}", "", "| 特征 | 类型 | 必填 | 约束 | 描述 |", "|---|---|---|---|---|"]
        for item in self.features:
            constraints: list[str] = []
            if item.min_value is not None:
                constraints.append(f"min={item.min_value}")
            if item.max_value is not None:
                constraints.append(f"max={item.max_value}")
            if item.choices:
                constraints.append(f"choices={list(item.choices)}")
            lines.append(
                f"| {item.name} | {item.feature_type.value} | {'是' if item.required else '否'} | "
                f"{', '.join(constraints) or '-'} | {item.description or '-'} |"
            )
        return "\n".join(lines)


class ExplanationType(StrEnum):
    LIME = "lime"
    SHAP = "shap"
    HYBRID = "hybrid"


@dataclass
class ExplanationContribution:
    feature: str
    value: float
    contribution: float


@dataclass
class ExplanationRecord:
    sample_index: int
    score: float
    contributions: list[ExplanationContribution]


@dataclass
class ExplanationResult:
    model_name: str
    explanation_type: ExplanationType
    records: list[ExplanationRecord]
    summary: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name 不能为空")
        if not isinstance(self.explanation_type, ExplanationType):
            raise ValueError("explanation_type 非法")
        if not isinstance(self.records, list):
            raise ValueError("records 必须为列表")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["explanation_type"] = self.explanation_type.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExplanationResult:
        records = [
            ExplanationRecord(
                sample_index=int(item["sample_index"]),
                score=float(item["score"]),
                contributions=[
                    ExplanationContribution(
                        feature=str(c["feature"]),
                        value=float(c["value"]),
                        contribution=float(c["contribution"]),
                    )
                    for c in item.get("contributions", [])
                ],
            )
            for item in payload.get("records", [])
        ]
        result = cls(
            model_name=str(payload.get("model_name", "")),
            explanation_type=ExplanationType(str(payload.get("explanation_type", "lime"))),
            records=records,
            summary=dict(payload.get("summary", {})),
            created_at=str(payload.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
        result.validate()
        return result

    @classmethod
    def from_json(cls, raw: str) -> ExplanationResult:
        return cls.from_dict(json.loads(raw))


class UnifiedAdapterBase(ABC):
    """统一适配器基类，封装 LIME/SHAP 公共流程。"""

    def __init__(self, feature_schema: FeatureSchema | None = None) -> None:
        self.feature_schema = feature_schema

    def extract_features(self, data: Any) -> np.ndarray:
        matrix = np.asarray(data, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return matrix

    def preprocess_features(self, matrix: np.ndarray) -> np.ndarray:
        x = np.asarray(matrix, dtype=float)
        mean = np.mean(x, axis=0, keepdims=True)
        std = np.std(x, axis=0, keepdims=True)
        std = np.where(std < 1e-9, 1.0, std)
        return (x - mean) / std

    def postprocess_result(self, result: ExplanationResult) -> dict[str, Any]:
        payload = result.to_dict()
        payload["validated"] = True
        return payload

    def explain_lime(
        self,
        model: Any,
        data: Any,
        *,
        top_k: int = 5,
    ) -> dict[str, Any]:
        matrix = self.extract_features(data)
        processed = self.preprocess_features(matrix)
        result = self._run_common_explanation(
            model=model,
            matrix=matrix,
            processed=processed,
            explanation_type=ExplanationType.LIME,
            top_k=top_k,
        )
        return self.postprocess_result(result)

    def explain_shap(
        self,
        model: Any,
        data: Any,
        *,
        top_k: int = 5,
    ) -> dict[str, Any]:
        matrix = self.extract_features(data)
        processed = self.preprocess_features(matrix)
        result = self._run_common_explanation(
            model=model,
            matrix=matrix,
            processed=processed,
            explanation_type=ExplanationType.SHAP,
            top_k=top_k,
        )
        return self.postprocess_result(result)

    def explain_hybrid(self, model: Any, data: Any, *, top_k: int = 5) -> dict[str, Any]:
        lime_result = self.explain_lime(model, data, top_k=top_k)
        shap_result = self.explain_shap(model, data, top_k=top_k)
        return {
            "model_name": lime_result["model_name"],
            "explanation_type": ExplanationType.HYBRID.value,
            "lime": lime_result,
            "shap": shap_result,
            "summary": {
                "top_k": int(top_k),
                "record_count": max(len(lime_result.get("records", [])), len(shap_result.get("records", []))),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _run_common_explanation(
        self,
        *,
        model: Any,
        matrix: np.ndarray,
        processed: np.ndarray,
        explanation_type: ExplanationType,
        top_k: int,
    ) -> ExplanationResult:
        contributions = self._compute_contributions(
            model=model,
            matrix=matrix,
            processed=processed,
            explanation_type=explanation_type,
            top_k=top_k,
        )

        feature_names = self._resolve_feature_names(matrix.shape[1])
        records: list[ExplanationRecord] = []
        for idx, row in enumerate(matrix):
            score = float(np.sum(np.asarray(row, dtype=float)))
            row_contrib = contributions[idx] if idx < len(contributions) else []
            ranked = sorted(row_contrib, key=lambda x: abs(float(x[1])), reverse=True)[: max(1, int(top_k))]
            items = [
                ExplanationContribution(
                    feature=str(feature_names[int(i)] if int(i) < len(feature_names) else f"feature_{int(i)}"),
                    value=float(row[int(i)]),
                    contribution=float(v),
                )
                for i, v in ranked
            ]
            records.append(ExplanationRecord(sample_index=int(idx), score=score, contributions=items))

        return ExplanationResult(
            model_name=self.model_name,
            explanation_type=explanation_type,
            records=records,
            summary={
                "top_k": int(top_k),
                "sample_count": int(matrix.shape[0]),
                "feature_count": int(matrix.shape[1]),
            },
        )

    def _resolve_feature_names(self, width: int) -> list[str]:
        if self.feature_schema is None:
            return [f"feature_{i}" for i in range(width)]
        names = self.feature_schema.feature_names()
        if len(names) >= width:
            return names[:width]
        return names + [f"feature_{i}" for i in range(len(names), width)]

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _compute_contributions(
        self,
        *,
        model: Any,
        matrix: np.ndarray,
        processed: np.ndarray,
        explanation_type: ExplanationType,
        top_k: int,
    ) -> list[list[tuple[int, float]]]:
        """返回每个样本的贡献列表: [[(feature_idx, contribution), ...], ...]。"""
        raise NotImplementedError


@dataclass
class AdapterLoadLog:
    module: str
    adapter_names: list[str]
    success: bool
    error: str = ""


class AdapterAutoLoader:
    """自动发现/加载/缓存适配器，并支持热重载。"""

    def __init__(self) -> None:
        self._cache: dict[str, type[UnifiedAdapterBase]] = {}
        self._module_cache: dict[str, ModuleType] = {}
        self._logs: list[AdapterLoadLog] = []

    def discover(self, package: str) -> list[str]:
        module = importlib.import_module(package)
        if not hasattr(module, "__path__"):
            return []
        modules = [name for _, name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + ".")]
        return sorted(modules)

    def load_adapters(self, modules: Iterable[str]) -> dict[str, type[UnifiedAdapterBase]]:
        for mod in modules:
            self._load_one(mod)
        return dict(self._cache)

    def _load_one(self, module_name: str) -> None:
        try:
            module = importlib.import_module(module_name)
            self._module_cache[module_name] = module
            found: list[str] = []
            for name, value in vars(module).items():
                if not isinstance(value, type):
                    continue
                if not issubclass(value, UnifiedAdapterBase) or value is UnifiedAdapterBase:
                    continue
                key = f"{module_name}:{name}"
                self._cache[key] = value
                found.append(name)
            self._logs.append(AdapterLoadLog(module=module_name, adapter_names=found, success=True))
        except Exception as exc:  # pragma: no cover - 防御分支
            logger.exception("加载适配器失败: %s", module_name)
            self._logs.append(AdapterLoadLog(module=module_name, adapter_names=[], success=False, error=str(exc)))

    def get(self, key: str) -> type[UnifiedAdapterBase]:
        if key not in self._cache:
            raise KeyError(f"适配器未加载: {key}")
        return self._cache[key]

    def unload(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]

    def hot_reload(self, module_name: str) -> dict[str, type[UnifiedAdapterBase]]:
        importlib.invalidate_caches()
        previous_keys = [k for k in self._cache if k.startswith(f"{module_name}:")]
        for key in previous_keys:
            del self._cache[key]

        module = self._module_cache.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
        if getattr(module, "__file__", None):
            Path(str(module.__file__)).touch()
        reloaded = importlib.reload(module)
        self._module_cache[module_name] = reloaded
        self._load_one(module_name)
        return {k: v for k, v in self._cache.items() if k.startswith(f"{module_name}:")}

    def logs(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self._logs]


class FrameworkErrorCode(StrEnum):
    """统一错误码。"""

    UNKNOWN = "FWK_0000"
    CONFIG_LOAD_FAILED = "FWK_1001"
    CONFIG_VALIDATE_FAILED = "FWK_1002"
    CONFIG_HOT_RELOAD_FAILED = "FWK_1003"
    CONFIG_BACKUP_FAILED = "FWK_1004"
    CONFIG_RESTORE_FAILED = "FWK_1005"
    ADAPTER_LOAD_FAILED = "FWK_2001"
    ADAPTER_CREATE_FAILED = "FWK_2002"
    DATA_VALIDATE_FAILED = "FWK_3001"
    EXECUTION_FAILED = "FWK_9001"


class UnifiedFrameworkError(RuntimeError):
    """统一框架基础异常。"""

    def __init__(
        self,
        message: str,
        *,
        code: FrameworkErrorCode = FrameworkErrorCode.UNKNOWN,
        context: dict[str, Any] | None = None,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}
        self.recoverable = bool(recoverable)


class UnifiedConfigError(UnifiedFrameworkError):
    pass


class UnifiedAdapterError(UnifiedFrameworkError):
    pass


class UnifiedValidationError(UnifiedFrameworkError):
    pass


class UnifiedExecutionError(UnifiedFrameworkError):
    pass


@dataclass(frozen=True)
class ConfigVersion:
    version_id: str
    checksum: str
    created_at: str
    source: str
    note: str = ""


class UnifiedConfigValidator:
    """统一配置验证器。"""

    def __init__(self) -> None:
        self._rules: dict[str, Callable[[Any], tuple[bool, str]]] = {}
        self._required_paths: list[str] = []

    def add_required(self, dotted_path: str) -> None:
        if dotted_path not in self._required_paths:
            self._required_paths.append(dotted_path)

    def add_rule(self, dotted_path: str, rule: Callable[[Any], tuple[bool, str]]) -> None:
        self._rules[dotted_path] = rule

    def validate(self, config: dict[str, Any]) -> None:
        errors: list[str] = []
        for path in self._required_paths:
            exists, value = self._try_get(config, path)
            if not exists or value is None:
                errors.append(f"缺少必填配置: {path}")
        for path, rule in self._rules.items():
            exists, value = self._try_get(config, path)
            if not exists:
                continue
            ok, reason = rule(value)
            if not ok:
                errors.append(f"{path}: {reason}")
        if errors:
            raise UnifiedConfigError(
                "; ".join(errors),
                code=FrameworkErrorCode.CONFIG_VALIDATE_FAILED,
                context={"errors": errors},
            )

    @staticmethod
    def _try_get(payload: dict[str, Any], dotted_path: str) -> tuple[bool, Any]:
        current: Any = payload
        for item in dotted_path.split("."):
            if not isinstance(current, dict) or item not in current:
                return False, None
            current = current[item]
        return True, current


class UnifiedConfigManager:
    """统一配置管理：加载、验证、热更新、版本、备份与文档。"""

    def __init__(
        self,
        *,
        config_path: str | Path,
        validator: UnifiedConfigValidator | None = None,
        backup_dir: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.config_path.parent / ".config_backups"
        self.validator = validator or self._default_validator()
        self._lock = RLock()
        self._config: dict[str, Any] = {}
        self._versions: list[ConfigVersion] = []
        self._version_counter = 0

    @staticmethod
    def default_config_template() -> dict[str, Any]:
        return {
            "meta": {"name": "unified_framework", "version": "1.0.0"},
            "runtime": {"max_workers": 4, "cache_size": 64, "strict_mode": True},
            "adapters": {"auto_discover": True, "packages": ["services.backend.app.dl_services"]},
            "logging": {"level": "INFO", "json_format": False},
            "features": {"enable_hot_reload": True, "enable_metrics": True},
        }

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.config_path.exists():
                template = self.default_config_template()
                self._persist(template)
                self._config = deepcopy(template)
                self._record_version(source="bootstrap", note="create default config")
                return deepcopy(self._config)

            try:
                raw = self._read_file(self.config_path)
            except Exception as exc:
                raise UnifiedConfigError(
                    f"加载配置失败: {self.config_path}",
                    code=FrameworkErrorCode.CONFIG_LOAD_FAILED,
                    context={"path": str(self.config_path)},
                ) from exc
            self.validator.validate(raw)
            self._config = deepcopy(raw)
            self._record_version(source="load", note="load from file")
            return deepcopy(self._config)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._config)

    def hot_update(self, patch: dict[str, Any], *, note: str = "hot_update", persist: bool = True) -> dict[str, Any]:
        with self._lock:
            try:
                base = deepcopy(self._config) if self._config else self.load()
                merged = self._deep_merge(base, patch)
                self.validator.validate(merged)
                self._config = merged
                if persist:
                    self._persist(self._config)
                self._record_version(source="hot_update", note=note)
                return deepcopy(self._config)
            except UnifiedFrameworkError:
                raise
            except Exception as exc:
                raise UnifiedConfigError(
                    "配置热更新失败",
                    code=FrameworkErrorCode.CONFIG_HOT_RELOAD_FAILED,
                    context={"note": note},
                    recoverable=True,
                ) from exc

    def backup(self, *, note: str = "manual_backup") -> Path:
        with self._lock:
            try:
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                target = self.backup_dir / f"{self.config_path.stem}.{stamp}.bak{self.config_path.suffix or '.json'}"
                if self.config_path.exists():
                    shutil.copy2(self.config_path, target)
                else:
                    self._persist(self.default_config_template(), target_path=target)
                self._record_version(source="backup", note=note)
                return target
            except Exception as exc:
                raise UnifiedConfigError(
                    "配置备份失败",
                    code=FrameworkErrorCode.CONFIG_BACKUP_FAILED,
                    context={"backup_dir": str(self.backup_dir)},
                ) from exc

    def restore(self, backup_path: str | Path) -> dict[str, Any]:
        with self._lock:
            source = Path(backup_path)
            if not source.exists():
                raise UnifiedConfigError(
                    f"备份文件不存在: {source}",
                    code=FrameworkErrorCode.CONFIG_RESTORE_FAILED,
                    context={"backup_path": str(source)},
                )
            try:
                restored = self._read_file(source)
                self.validator.validate(restored)
                self._config = deepcopy(restored)
                self._persist(self._config)
                self._record_version(source="restore", note=f"from:{source.name}")
                return deepcopy(self._config)
            except UnifiedFrameworkError:
                raise
            except Exception as exc:
                raise UnifiedConfigError(
                    "配置恢复失败",
                    code=FrameworkErrorCode.CONFIG_RESTORE_FAILED,
                    context={"backup_path": str(source)},
                ) from exc

    def versions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(item) for item in self._versions]

    def generate_docs(self) -> str:
        with self._lock:
            cfg = deepcopy(self._config) if self._config else self.default_config_template()
        lines = [
            "# 统一配置文档",
            "",
            "## 配置结构",
            "| 路径 | 类型 | 示例值 |",
            "|---|---|---|",
        ]
        for dotted, value in self._flatten_dict(cfg).items():
            value_repr = json.dumps(value, ensure_ascii=False)
            lines.append(f"| {dotted} | {type(value).__name__} | `{value_repr}` |")
        lines.extend(
            [
                "",
                "## 版本记录",
                "| version_id | checksum | source | created_at | note |",
                "|---|---|---|---|---|",
            ]
        )
        for item in self._versions:
            lines.append(
                f"| {item.version_id} | {item.checksum[:12]} | {item.source} | {item.created_at} | {item.note or '-'} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _flatten_dict(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        flat: dict[str, Any] = {}
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                flat.update(UnifiedConfigManager._flatten_dict(value, prefix=path))
            else:
                flat[path] = value
        return flat

    @staticmethod
    def _default_validator() -> UnifiedConfigValidator:
        validator = UnifiedConfigValidator()
        validator.add_required("meta.name")
        validator.add_required("meta.version")
        validator.add_required("runtime.max_workers")
        validator.add_required("runtime.cache_size")
        validator.add_rule("runtime.max_workers", lambda v: (isinstance(v, int) and v > 0, "必须为正整数"))
        validator.add_rule("runtime.cache_size", lambda v: (isinstance(v, int) and v > 0, "必须为正整数"))
        validator.add_rule("logging.level", lambda v: (str(v).upper() in {"DEBUG", "INFO", "WARNING", "ERROR"}, "日志级别非法"))
        return validator

    def _record_version(self, *, source: str, note: str) -> None:
        self._version_counter += 1
        payload = json.dumps(self._config, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        version = ConfigVersion(
            version_id=f"v{self._version_counter:04d}",
            checksum=checksum,
            created_at=datetime.now(timezone.utc).isoformat(),
            source=source,
            note=note,
        )
        self._versions.append(version)

    def _persist(self, config: dict[str, Any], target_path: Path | None = None) -> None:
        path = target_path or self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:
                raise UnifiedConfigError(
                    "写入 YAML 失败，缺少 PyYAML",
                    code=FrameworkErrorCode.CONFIG_LOAD_FAILED,
                    context={"path": str(path)},
                ) from exc
            path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
            return
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _read_file(self, path: Path) -> dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:
                raise UnifiedConfigError(
                    "读取 YAML 失败，缺少 PyYAML",
                    code=FrameworkErrorCode.CONFIG_LOAD_FAILED,
                    context={"path": str(path)},
                ) from exc
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            payload = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            raise UnifiedConfigError(
                "配置根节点必须为对象",
                code=FrameworkErrorCode.CONFIG_VALIDATE_FAILED,
                context={"path": str(path)},
            )
        return dict(payload)

    @staticmethod
    def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = UnifiedConfigManager._deep_merge(dict(merged[key]), value)
            else:
                merged[key] = value
        return merged


@dataclass
class FrameworkErrorEvent:
    event_id: str
    code: str
    message: str
    error_type: str
    created_at: str
    recoverable: bool
    recovered: bool
    context: dict[str, Any] = field(default_factory=dict)
    traceback: str = ""


class UnifiedErrorHandler:
    """统一错误处理：捕获、日志、恢复、通知与文档。"""

    def __init__(self) -> None:
        self._events: list[FrameworkErrorEvent] = []
        self._recoveries: dict[str, Callable[[FrameworkErrorEvent], bool]] = {}
        self._notifiers: list[Callable[[FrameworkErrorEvent], None]] = []
        self._lock = RLock()

    def register_recovery(self, code: FrameworkErrorCode | str, fn: Callable[[FrameworkErrorEvent], bool]) -> None:
        with self._lock:
            self._recoveries[str(code)] = fn

    def register_notifier(self, fn: Callable[[FrameworkErrorEvent], None]) -> None:
        with self._lock:
            self._notifiers.append(fn)

    def capture(
        self,
        exc: Exception,
        *,
        context: dict[str, Any] | None = None,
        attempt_recovery: bool = True,
    ) -> FrameworkErrorEvent:
        event = self._to_event(exc, context=context)
        self._log_event(event)
        if attempt_recovery and event.recoverable:
            recovery = self._recoveries.get(event.code)
            if recovery is not None:
                try:
                    event.recovered = bool(recovery(event))
                except Exception:
                    logger.exception("错误恢复策略执行失败: %s", event.code)
        self._notify(event)
        with self._lock:
            self._events.append(event)
        return event

    @contextmanager
    def capture_context(
        self,
        *,
        context: dict[str, Any] | None = None,
        default: Any = None,
        reraise: bool = False,
        recoverable: bool = False,
    ):
        try:
            yield
        except Exception as exc:
            wrapped = self._normalize_exception(exc, context=context, recoverable=recoverable)
            self.capture(wrapped, context=context, attempt_recovery=True)
            if reraise:
                raise wrapped from exc
            return default

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(item) for item in self._events]

    def generate_docs(self) -> str:
        rows = [
            ("FWK_0000", "未知异常", "兜底异常"),
            ("FWK_1001", "配置加载失败", "检查配置路径和格式"),
            ("FWK_1002", "配置校验失败", "检查必填字段和类型"),
            ("FWK_1003", "配置热更新失败", "回滚到上一版本"),
            ("FWK_1004", "配置备份失败", "检查备份目录权限"),
            ("FWK_1005", "配置恢复失败", "确认备份可读且合法"),
            ("FWK_2001", "适配器加载失败", "检查模块路径和导入依赖"),
            ("FWK_2002", "适配器创建失败", "检查构造参数"),
            ("FWK_3001", "数据校验失败", "检查输入数据范围"),
            ("FWK_9001", "执行失败", "检查运行时依赖和状态"),
        ]
        lines = [
            "# 统一错误处理文档",
            "",
            "## 错误码规范",
            "| 错误码 | 含义 | 建议处理 |",
            "|---|---|---|",
        ]
        lines.extend([f"| {code} | {desc} | {action} |" for code, desc, action in rows])
        lines.extend(
            [
                "",
                "## 捕获机制",
                "- 使用 `capture` 上报异常并生成标准事件。",
                "- 使用 `capture_context` 包裹业务代码实现自动捕获。",
                "",
                "## 恢复与通知",
                "- `register_recovery` 注册按错误码生效的恢复函数。",
                "- `register_notifier` 注册告警通知函数。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _normalize_exception(
        exc: Exception,
        *,
        context: dict[str, Any] | None = None,
        recoverable: bool = False,
    ) -> UnifiedFrameworkError:
        if isinstance(exc, UnifiedFrameworkError):
            return exc
        return UnifiedExecutionError(
            str(exc) or exc.__class__.__name__,
            code=FrameworkErrorCode.EXECUTION_FAILED,
            context=context,
            recoverable=recoverable,
        )

    def _to_event(self, exc: Exception, *, context: dict[str, Any] | None = None) -> FrameworkErrorEvent:
        normalized = self._normalize_exception(exc, context=context)
        merged_context = dict(normalized.context)
        if context:
            merged_context.update(context)
        return FrameworkErrorEvent(
            event_id=uuid4().hex,
            code=str(normalized.code),
            message=str(normalized),
            error_type=normalized.__class__.__name__,
            created_at=datetime.now(timezone.utc).isoformat(),
            recoverable=bool(normalized.recoverable),
            recovered=False,
            context=merged_context,
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )

    @staticmethod
    def _log_event(event: FrameworkErrorEvent) -> None:
        logger.error(
            "框架错误[%s] %s | type=%s | recoverable=%s | context=%s",
            event.code,
            event.message,
            event.error_type,
            event.recoverable,
            event.context,
        )

    def _notify(self, event: FrameworkErrorEvent) -> None:
        for callback in list(self._notifiers):
            try:
                callback(event)
            except Exception:
                logger.exception("错误通知回调执行失败: %s", event.event_id)
