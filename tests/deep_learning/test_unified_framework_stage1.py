from __future__ import annotations

import importlib
import time
from pathlib import Path

import numpy as np
import pytest

from deep_learning.models.registry import ModelRegistry
from services.backend.app.dl_services.unified_framework import (
    AdapterAutoLoader,
    ExplanationResult,
    ExplanationType,
    FeatureMetadata,
    FeatureSchema,
    FeatureType,
    UnifiedAdapterBase,
)


class _DemoAdapter(UnifiedAdapterBase):
    @property
    def model_name(self) -> str:
        return "demo"

    def _compute_contributions(self, *, model, matrix, processed, explanation_type, top_k):
        weight = np.asarray(getattr(model, "weights", np.ones(matrix.shape[1])), dtype=float)
        rows: list[list[tuple[int, float]]] = []
        for row in processed:
            values = row * weight
            rows.append([(i, float(v)) for i, v in enumerate(values.tolist())])
        return rows


class _DemoModel:
    def __init__(self, weights: list[float]) -> None:
        self.weights = weights


def test_unified_adapter_lime_shap_hybrid() -> None:
    schema = FeatureSchema(
        model_name="demo",
        features=[
            FeatureMetadata("f1", FeatureType.CONTINUOUS),
            FeatureMetadata("f2", FeatureType.CONTINUOUS),
        ],
    )
    adapter = _DemoAdapter(feature_schema=schema)
    model = _DemoModel(weights=[1.0, 2.0])

    data = [[1.0, 2.0], [3.0, 4.0]]

    lime = adapter.explain_lime(model, data, top_k=1)
    shap = adapter.explain_shap(model, data, top_k=2)
    hybrid = adapter.explain_hybrid(model, data, top_k=1)

    assert lime["explanation_type"] == "lime"
    assert shap["explanation_type"] == "shap"
    assert lime["validated"] is True
    assert shap["summary"]["feature_count"] == 2
    assert hybrid["explanation_type"] == "hybrid"
    assert "lime" in hybrid and "shap" in hybrid


def test_feature_schema_validate_transform_and_docs() -> None:
    schema = FeatureSchema(
        model_name="demo_feature",
        features=[
            FeatureMetadata("age", FeatureType.DISCRETE, min_value=0, max_value=120),
            FeatureMetadata("gender", FeatureType.CATEGORICAL, choices=("M", "F")),
            FeatureMetadata("income", FeatureType.CONTINUOUS, required=False, default=0.0),
        ],
    )

    transformed = schema.transform({"age": 20.2, "gender": "M"})
    assert transformed["age"] == 20
    assert transformed["income"] == 0.0

    with pytest.raises(ValueError):
        schema.validate({"age": -1, "gender": "X"})

    docs = schema.generate_docs()
    assert "# 特征文档 - demo_feature" in docs
    assert "age" in docs and "gender" in docs


def test_explanation_result_serialize_deserialize_and_validate() -> None:
    payload = {
        "model_name": "demo",
        "explanation_type": "lime",
        "records": [
            {
                "sample_index": 0,
                "score": 1.23,
                "contributions": [
                    {"feature": "f1", "value": 1.0, "contribution": 0.6},
                ],
            }
        ],
        "summary": {"top_k": 1},
    }

    result = ExplanationResult.from_dict(payload)
    assert result.explanation_type == ExplanationType.LIME

    raw = result.to_json()
    restored = ExplanationResult.from_json(raw)
    assert restored.model_name == "demo"
    assert restored.records[0].contributions[0].feature == "f1"

    with pytest.raises(ValueError):
        ExplanationResult(model_name="", explanation_type=ExplanationType.SHAP, records=[], summary={}).validate()


def test_model_registry_metadata_query_unregister_and_events() -> None:
    registry = ModelRegistry()
    events: list[dict[str, object]] = []
    registry.register_event_handler(lambda event: events.append(event))

    registry.register(
        "demo_a",
        lambda gain=1.0: {"gain": gain},
        metadata={"framework": "pytorch", "version": "v1"},
        tags={"anomaly", "prod"},
    )
    registry.register(
        "demo_b",
        lambda gain=1.0: {"gain": gain},
        metadata={"framework": "tensorflow", "version": "v2"},
        tags={"test"},
    )

    assert registry.query(framework="pytorch") == ["demo_a"]
    assert registry.query(tags={"anomaly"}) == ["demo_a"]
    assert registry.get_metadata("demo_a")["version"] == "v1"
    assert registry.create("demo_a", gain=2.0)["gain"] == 2.0

    registry.unregister("demo_b")
    status = registry.status()
    assert status["count"] == 1
    assert status["models"][0]["name"] == "demo_a"

    event_names = [str(item["event"]) for item in events]
    assert "model_registered" in event_names
    assert "model_unregistered" in event_names


def test_adapter_auto_loader_discover_load_and_hot_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_dir = tmp_path / "demo_adapters"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    module_path = package_dir / "sample_adapter.py"
    module_path.write_text(
        "from services.backend.app.dl_services.unified_framework import UnifiedAdapterBase\n"
        "class SampleAdapter(UnifiedAdapterBase):\n"
        "    @property\n"
        "    def model_name(self):\n"
        "        return 'sample_v1'\n"
        "    def _compute_contributions(self, *, model, matrix, processed, explanation_type, top_k):\n"
        "        return [[(0, 1.0)] for _ in range(len(matrix))]\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    loader = AdapterAutoLoader()
    modules = loader.discover("demo_adapters")
    assert "demo_adapters.sample_adapter" in modules

    loaded = loader.load_adapters(modules)
    key = "demo_adapters.sample_adapter:SampleAdapter"
    assert key in loaded

    cls_v1 = loader.get(key)
    assert cls_v1().model_name == "sample_v1"

    module_path.write_text(
        "from services.backend.app.dl_services.unified_framework import UnifiedAdapterBase\n"
        "class SampleAdapter(UnifiedAdapterBase):\n"
        "    @property\n"
        "    def model_name(self):\n"
        "        return 'sample_v2'\n"
        "    def _compute_contributions(self, *, model, matrix, processed, explanation_type, top_k):\n"
        "        return [[(0, 2.0)] for _ in range(len(matrix))]\n",
        encoding="utf-8",
    )
    time.sleep(1.1)
    importlib.invalidate_caches()

    reloaded = loader.hot_reload("demo_adapters.sample_adapter")
    assert key in reloaded
    cls_v2 = loader.get(key)
    assert cls_v2().model_name == "sample_v2"

    logs = loader.logs()
    assert any(item["module"] == "demo_adapters.sample_adapter" for item in logs)
