"""统一解释适配框架：基类、特征接口、解释结果格式与自动加载。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import importlib
import json
import logging
from pathlib import Path
import pkgutil
from types import ModuleType
from typing import Any, Iterable

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
