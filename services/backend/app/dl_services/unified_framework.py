"""统一解释适配框架：基类、特征接口、解释结果格式与自动加载。"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections import Counter, OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return str.__str__(self)
import hashlib
import importlib
import inspect
import json
import logging
import pkgutil
import shutil
import traceback
from pathlib import Path
from threading import RLock
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
    METADATA_VALIDATE_FAILED = "FWK_4001"
    METADATA_SYNC_FAILED = "FWK_4002"
    LOG_CONFIG_FAILED = "FWK_5001"
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
            ("FWK_4001", "元数据校验失败", "检查必填字段和字段类型"),
            ("FWK_4002", "元数据同步失败", "检查同步源和冲突策略"),
            ("FWK_5001", "日志配置失败", "检查日志级别和格式化配置"),
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


@dataclass(frozen=True)
class AdapterFactoryRegistration:
    key: str
    adapter_cls: type[UnifiedAdapterBase]
    singleton: bool = False
    cacheable: bool = True
    default_kwargs: dict[str, Any] = field(default_factory=dict)
    validator: Callable[[dict[str, Any]], tuple[bool, str]] | None = None


@dataclass
class AdapterFactoryLifecycle:
    instance_id: str
    key: str
    created_at: str
    updated_at: str
    status: str
    source: str
    hit_count: int = 0


class UnifiedAdapterFactory:
    """适配器工厂：注册、创建、缓存、单例与生命周期管理。"""

    def __init__(self, *, max_cache_size: int = 64) -> None:
        self.max_cache_size = max(1, int(max_cache_size))
        self._registry: dict[str, AdapterFactoryRegistration] = {}
        self._instance_cache: "OrderedDict[str, UnifiedAdapterBase]" = OrderedDict()
        self._singletons: dict[str, UnifiedAdapterBase] = {}
        self._lifecycle: dict[str, AdapterFactoryLifecycle] = {}
        self._lock = RLock()

    def register(
        self,
        key: str,
        adapter_cls: type[UnifiedAdapterBase],
        *,
        singleton: bool = False,
        cacheable: bool = True,
        default_kwargs: dict[str, Any] | None = None,
        validator: Callable[[dict[str, Any]], tuple[bool, str]] | None = None,
    ) -> None:
        normalized_key = self._normalize_key(key)
        if not inspect.isclass(adapter_cls) or not issubclass(adapter_cls, UnifiedAdapterBase):
            raise UnifiedAdapterError(
                f"适配器类型非法: {adapter_cls}",
                code=FrameworkErrorCode.ADAPTER_LOAD_FAILED,
                context={"key": normalized_key},
            )
        with self._lock:
            self._registry[normalized_key] = AdapterFactoryRegistration(
                key=normalized_key,
                adapter_cls=adapter_cls,
                singleton=bool(singleton),
                cacheable=bool(cacheable),
                default_kwargs=dict(default_kwargs or {}),
                validator=validator,
            )

    def unregister(self, key: str) -> None:
        normalized_key = self._normalize_key(key)
        with self._lock:
            self.release(normalized_key)
            self._registry.pop(normalized_key, None)

    def create(
        self,
        key: str,
        *,
        singleton: bool | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> UnifiedAdapterBase:
        normalized_key = self._normalize_key(key)
        with self._lock:
            registration = self._registry.get(normalized_key)
            if registration is None:
                raise UnifiedAdapterError(
                    f"适配器未注册: {normalized_key}",
                    code=FrameworkErrorCode.ADAPTER_LOAD_FAILED,
                    context={"key": normalized_key},
                )

            params = dict(registration.default_kwargs)
            params.update(kwargs)
            self._validate_create_params(registration, params)

            use_singleton = registration.singleton if singleton is None else bool(singleton)
            if use_singleton and normalized_key in self._singletons:
                instance = self._singletons[normalized_key]
                self._touch_lifecycle(instance, source="singleton")
                return instance

            cache_key = self._build_cache_key(normalized_key, params)
            if use_cache and registration.cacheable and cache_key in self._instance_cache:
                instance = self._instance_cache[cache_key]
                self._instance_cache.move_to_end(cache_key)
                self._touch_lifecycle(instance, source="cache")
                return instance

            try:
                instance = registration.adapter_cls(**params)
                self._invoke_on_create(instance)
            except Exception as exc:
                raise UnifiedAdapterError(
                    "适配器创建失败",
                    code=FrameworkErrorCode.ADAPTER_CREATE_FAILED,
                    context={"key": normalized_key, "params": params},
                    recoverable=True,
                ) from exc

            self._record_lifecycle(instance, key=normalized_key, source="create")
            if use_singleton:
                self._singletons[normalized_key] = instance
            elif use_cache and registration.cacheable:
                self._cache_instance(cache_key, instance)
            return instance

    def release(self, key: str, *, instance: UnifiedAdapterBase | None = None) -> int:
        """释放单个适配器键关联实例，或释放给定实例。"""
        normalized_key = self._normalize_key(key)
        released: list[UnifiedAdapterBase] = []
        with self._lock:
            if instance is not None:
                released.append(instance)
            else:
                if normalized_key in self._singletons:
                    released.append(self._singletons.pop(normalized_key))
                for cache_key in [k for k in self._instance_cache if k.startswith(f"{normalized_key}::")]:
                    released.append(self._instance_cache.pop(cache_key))
            for obj in released:
                self._invoke_on_destroy(obj)
                self._mark_lifecycle_destroyed(obj)
        return len(released)

    def shutdown(self) -> int:
        """释放所有实例。"""
        released = 0
        with self._lock:
            for instance in list(self._singletons.values()):
                self._invoke_on_destroy(instance)
                self._mark_lifecycle_destroyed(instance)
                released += 1
            self._singletons.clear()
            for instance in list(self._instance_cache.values()):
                self._invoke_on_destroy(instance)
                self._mark_lifecycle_destroyed(instance)
                released += 1
            self._instance_cache.clear()
        return released

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "registered": sorted(self._registry.keys()),
                "singletons": sorted(self._singletons.keys()),
                "cache_size": len(self._instance_cache),
                "lifecycle": [asdict(item) for item in self._lifecycle.values()],
            }

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = str(key).strip()
        if not normalized:
            raise UnifiedAdapterError(
                "适配器 key 不能为空",
                code=FrameworkErrorCode.ADAPTER_CREATE_FAILED,
                recoverable=True,
            )
        return normalized

    def _validate_create_params(self, registration: AdapterFactoryRegistration, params: dict[str, Any]) -> None:
        cls = registration.adapter_cls
        signature = inspect.signature(cls.__init__)
        parameters = [item for name, item in signature.parameters.items() if name != "self"]
        accepts_kwargs = any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters)
        accepted_names = {item.name for item in parameters}
        required = {
            item.name
            for item in parameters
            if item.default is inspect._empty
            and item.kind
            in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        }
        missing = sorted(name for name in required if name not in params)
        unknown = sorted(name for name in params if name not in accepted_names) if not accepts_kwargs else []
        if missing or unknown:
            raise UnifiedAdapterError(
                "创建参数校验失败",
                code=FrameworkErrorCode.ADAPTER_CREATE_FAILED,
                context={"missing": missing, "unknown": unknown, "key": registration.key},
                recoverable=True,
            )
        if registration.validator is not None:
            ok, reason = registration.validator(dict(params))
            if not ok:
                raise UnifiedAdapterError(
                    f"创建参数校验失败: {reason}",
                    code=FrameworkErrorCode.ADAPTER_CREATE_FAILED,
                    context={"key": registration.key, "params": params},
                    recoverable=True,
                )

    @staticmethod
    def _build_cache_key(key: str, params: dict[str, Any]) -> str:
        payload = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{key}::{digest}"

    def _cache_instance(self, cache_key: str, instance: UnifiedAdapterBase) -> None:
        self._instance_cache[cache_key] = instance
        self._instance_cache.move_to_end(cache_key)
        while len(self._instance_cache) > self.max_cache_size:
            _, evicted = self._instance_cache.popitem(last=False)
            self._invoke_on_destroy(evicted)
            self._mark_lifecycle_destroyed(evicted)

    def _record_lifecycle(self, instance: UnifiedAdapterBase, *, key: str, source: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        item = AdapterFactoryLifecycle(
            instance_id=self._instance_id(instance),
            key=key,
            created_at=now,
            updated_at=now,
            status="active",
            source=source,
            hit_count=0,
        )
        self._lifecycle[item.instance_id] = item

    def _touch_lifecycle(self, instance: UnifiedAdapterBase, *, source: str) -> None:
        ident = self._instance_id(instance)
        item = self._lifecycle.get(ident)
        if item is None:
            self._record_lifecycle(instance, key="unknown", source=source)
            return
        item.updated_at = datetime.now(timezone.utc).isoformat()
        item.hit_count += 1
        item.source = source

    def _mark_lifecycle_destroyed(self, instance: UnifiedAdapterBase) -> None:
        ident = self._instance_id(instance)
        item = self._lifecycle.get(ident)
        if item is None:
            return
        item.status = "destroyed"
        item.updated_at = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _instance_id(instance: UnifiedAdapterBase) -> str:
        return hex(id(instance))

    @staticmethod
    def _invoke_on_create(instance: UnifiedAdapterBase) -> None:
        callback = getattr(instance, "on_create", None)
        if callable(callback):
            callback()

    @staticmethod
    def _invoke_on_destroy(instance: UnifiedAdapterBase) -> None:
        for name in ("on_destroy", "close", "stop"):
            callback = getattr(instance, name, None)
            if callable(callback):
                callback()
                return


@dataclass
class ModelMetadataRecord:
    record_id: str
    model_name: str
    model_type: str
    framework: str
    version: str
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    checksum: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelMetadataVersion:
    record_id: str
    revision: int
    checksum: str
    created_at: str
    note: str
    snapshot: dict[str, Any]


class ModelMetadataStore:
    """模型元数据管理：字段规范、持久化、查询、版本、同步与导出。"""

    def __init__(self, *, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        self._lock = RLock()
        self._records: dict[str, ModelMetadataRecord] = {}
        self._history: dict[str, list[ModelMetadataVersion]] = {}
        self._load()

    @staticmethod
    def field_spec() -> dict[str, str]:
        return {
            "record_id": "唯一标识，默认 model_name:version",
            "model_name": "模型名称，必填",
            "model_type": "模型类型，必填",
            "framework": "训练框架，必填",
            "version": "版本号，必填",
            "tags": "标签列表，可选",
            "status": "状态，如 active/deprecated",
            "checksum": "元数据快照校验和",
            "created_at": "首次创建时间(UTC ISO8601)",
            "updated_at": "最近更新时间(UTC ISO8601)",
            "extra": "扩展字段对象",
        }

    def upsert(self, payload: dict[str, Any], *, note: str = "upsert", persist: bool = True) -> dict[str, Any]:
        with self._lock:
            record = self._normalize_record(payload)
            previous = self._records.get(record.record_id)
            if previous is not None:
                record.created_at = previous.created_at
            self._records[record.record_id] = record
            self._record_version(record, note=note)
            if persist:
                self._persist()
            return asdict(record)

    def get(self, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._records.get(str(record_id))
            return asdict(item) if item is not None else None

    def query(
        self,
        *,
        model_name: str | None = None,
        model_type: str | None = None,
        framework: str | None = None,
        tags: set[str] | list[str] | tuple[str, ...] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            name_kw = str(model_name or "").strip().lower()
            type_kw = str(model_type or "").strip().lower()
            framework_kw = str(framework or "").strip().lower()
            status_kw = str(status or "").strip().lower()
            tag_filter = {str(tag).strip().lower() for tag in (tags or set()) if str(tag).strip()}
            result: list[dict[str, Any]] = []
            for item in self._records.values():
                if name_kw and name_kw not in item.model_name.lower():
                    continue
                if type_kw and type_kw != item.model_type.lower():
                    continue
                if framework_kw and framework_kw != item.framework.lower():
                    continue
                if status_kw and status_kw != item.status.lower():
                    continue
                item_tags = {str(tag).lower() for tag in item.tags}
                if tag_filter and not tag_filter.issubset(item_tags):
                    continue
                result.append(asdict(item))
            result.sort(key=lambda x: (x["model_name"], x["version"], x["record_id"]))
            return result

    def versions(self, record_id: str) -> list[dict[str, Any]]:
        with self._lock:
            history = self._history.get(str(record_id), [])
            return [asdict(item) for item in history]

    def sync_from(self, source: ModelMetadataStore | Iterable[dict[str, Any]], *, note: str = "sync") -> dict[str, int]:
        with self._lock:
            if isinstance(source, ModelMetadataStore):
                source_items = source.query()
            else:
                source_items = [dict(item) for item in source]
            inserted = 0
            updated = 0
            for item in source_items:
                normalized = self._normalize_record(item)
                existed = normalized.record_id in self._records
                self._records[normalized.record_id] = normalized
                self._record_version(normalized, note=note)
                if existed:
                    updated += 1
                else:
                    inserted += 1
            self._persist()
            return {"inserted": inserted, "updated": updated}

    def export(self, target_path: str | Path) -> Path:
        with self._lock:
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = [asdict(item) for item in self._records.values()]
            suffix = path.suffix.lower()
            if suffix == ".csv":
                keys = [
                    "record_id",
                    "model_name",
                    "model_type",
                    "framework",
                    "version",
                    "status",
                    "checksum",
                    "created_at",
                    "updated_at",
                    "tags",
                    "extra",
                ]
                with path.open("w", encoding="utf-8", newline="") as fp:
                    writer = csv.DictWriter(fp, fieldnames=keys)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(
                            {
                                **row,
                                "tags": ",".join(row.get("tags", [])),
                                "extra": json.dumps(row.get("extra", {}), ensure_ascii=False, sort_keys=True),
                            }
                        )
            else:
                path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return path

    def _normalize_record(self, payload: dict[str, Any]) -> ModelMetadataRecord:
        model_name = str(payload.get("model_name", "")).strip()
        model_type = str(payload.get("model_type", "")).strip()
        framework_name = str(payload.get("framework", "")).strip()
        version = str(payload.get("version", "")).strip()
        if not all([model_name, model_type, framework_name, version]):
            raise UnifiedFrameworkError(
                "元数据缺少必填字段",
                code=FrameworkErrorCode.METADATA_VALIDATE_FAILED,
                context={"payload_keys": sorted(payload.keys())},
                recoverable=True,
            )
        record_id = str(payload.get("record_id") or f"{model_name}:{version}")
        status = str(payload.get("status") or "active").strip() or "active"
        tags = [str(item).strip() for item in payload.get("tags", []) if str(item).strip()]
        extra = payload.get("extra", {})
        if not isinstance(extra, dict):
            raise UnifiedFrameworkError(
                "元数据 extra 字段必须为对象",
                code=FrameworkErrorCode.METADATA_VALIDATE_FAILED,
                context={"record_id": record_id},
                recoverable=True,
            )
        created_at = str(payload.get("created_at") or datetime.now(timezone.utc).isoformat())
        updated_at = datetime.now(timezone.utc).isoformat()
        checksum = str(payload.get("checksum") or self._checksum(payload))
        return ModelMetadataRecord(
            record_id=record_id,
            model_name=model_name,
            model_type=model_type,
            framework=framework_name,
            version=version,
            tags=tags,
            status=status,
            checksum=checksum,
            created_at=created_at,
            updated_at=updated_at,
            extra=dict(extra),
        )

    def _record_version(self, record: ModelMetadataRecord, *, note: str) -> None:
        history = self._history.setdefault(record.record_id, [])
        snapshot = asdict(record)
        revision = len(history) + 1
        history.append(
            ModelMetadataVersion(
                record_id=record.record_id,
                revision=revision,
                checksum=record.checksum,
                created_at=datetime.now(timezone.utc).isoformat(),
                note=note,
                snapshot=snapshot,
            )
        )

    @staticmethod
    def _checksum(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _persist(self) -> None:
        payload = {
            "records": [asdict(item) for item in self._records.values()],
            "history": {key: [asdict(version) for version in versions] for key, versions in self._history.items()},
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        raw = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        records = raw.get("records", [])
        history = raw.get("history", {})
        for item in records:
            record = ModelMetadataRecord(**item)
            self._records[record.record_id] = record
        for record_id, versions in history.items():
            self._history[record_id] = [ModelMetadataVersion(**version) for version in versions]


class UnifiedLogFormatter(logging.Formatter):
    """统一日志格式化器，支持文本与 JSON 两种输出。"""

    def __init__(self, *, json_format: bool = False, timefmt: str | None = None) -> None:
        super().__init__(datefmt=timefmt)
        self.json_format = bool(json_format)

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        context = getattr(record, "context", {})
        if not isinstance(context, dict):
            context = {"raw_context": str(context)}
        payload = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": context,
        }
        if self.json_format:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        context_text = ", ".join(f"{k}={v}" for k, v in sorted(context.items())) if context else "-"
        return (
            f"{payload['timestamp']} | {payload['level']} | {payload['logger']} | "
            f"{payload['message']} | context: {context_text}"
        )


class UnifiedLogger:
    """统一日志：规范格式、级别、上下文、过滤与聚合。"""

    def __init__(
        self,
        name: str = "unified_framework",
        *,
        level: str = "INFO",
        json_format: bool = False,
    ) -> None:
        self.logger = logging.getLogger(name)
        self.logger.propagate = False
        self._events: list[dict[str, Any]] = []
        self._context_stack: list[dict[str, Any]] = []
        self._lock = RLock()
        formatter = UnifiedLogFormatter(json_format=json_format)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        else:
            for handler in self.logger.handlers:
                handler.setFormatter(formatter)
        self.set_level(level)

    def set_level(self, level: str) -> None:
        normalized = str(level or "").strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise UnifiedFrameworkError(
                f"非法日志级别: {level}",
                code=FrameworkErrorCode.LOG_CONFIG_FAILED,
                recoverable=True,
            )
        self.logger.setLevel(getattr(logging, normalized))

    @contextmanager
    def bind_context(self, **context: Any):
        with self._lock:
            self._context_stack.append({k: v for k, v in context.items()})
        try:
            yield
        finally:
            with self._lock:
                if self._context_stack:
                    self._context_stack.pop()

    def log(self, level: str, message: str, **context: Any) -> dict[str, Any]:
        normalized = str(level).strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            normalized = "INFO"
        merged_context = self._merged_context(extra=context)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": normalized,
            "logger": self.logger.name,
            "message": str(message),
            "context": merged_context,
        }
        with self._lock:
            self._events.append(event)
        self.logger.log(getattr(logging, normalized), str(message), extra={"context": merged_context})
        return dict(event)

    def query(
        self,
        *,
        level: str | None = None,
        contains: str | None = None,
        context_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        level_kw = str(level or "").strip().upper()
        message_kw = str(contains or "").strip().lower()
        filters = dict(context_filters or {})
        with self._lock:
            result: list[dict[str, Any]] = []
            for event in self._events:
                if level_kw and event["level"] != level_kw:
                    continue
                if message_kw and message_kw not in str(event["message"]).lower():
                    continue
                context = dict(event.get("context", {}))
                if any(context.get(k) != v for k, v in filters.items()):
                    continue
                result.append(dict(event))
            return result

    def aggregate(self, *, by: str = "level") -> dict[str, int]:
        with self._lock:
            if by == "context_key":
                counter: Counter[str] = Counter()
                for event in self._events:
                    for key in dict(event.get("context", {})).keys():
                        counter[str(key)] += 1
                return dict(counter)
            counter = Counter(str(event.get(by, "unknown")) for event in self._events)
            return dict(counter)

    @staticmethod
    def generate_usage_guide() -> str:
        return "\n".join(
            [
                "# 统一日志使用指南",
                "",
                "## 日志格式规范",
                "- 标准字段: `timestamp`, `level`, `logger`, `message`, `context`。",
                "- 支持文本与 JSON 输出，JSON 适合日志采集系统。",
                "",
                "## 日志级别管理",
                "- 使用 `set_level` 在运行时动态切换级别。",
                "",
                "## 上下文与过滤",
                "- 使用 `bind_context` 绑定请求级上下文。",
                "- 使用 `query` 按级别、关键字、上下文字段过滤。",
                "",
                "## 聚合分析",
                "- 使用 `aggregate(by='level')` 统计级别分布。",
                "- 使用 `aggregate(by='context_key')` 统计上下文字段覆盖率。",
            ]
        )

    def _merged_context(self, *, extra: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            merged: dict[str, Any] = {}
            for item in self._context_stack:
                merged.update(item)
            merged.update(extra)
            return merged
