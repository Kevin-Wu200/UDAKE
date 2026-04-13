from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from services.backend.app.dl_services.unified_framework import (
    FrameworkErrorCode,
    ModelMetadataStore,
    UnifiedAdapterBase,
    UnifiedAdapterError,
    UnifiedAdapterFactory,
    UnifiedLogger,
)


class _FactoryDemoAdapter(UnifiedAdapterBase):
    def __init__(self, *, feature_schema=None, scale: float = 1.0) -> None:
        super().__init__(feature_schema=feature_schema)
        self.scale = float(scale)
        self.started = False
        self.stopped = False

    @property
    def model_name(self) -> str:
        return "factory_demo"

    def on_create(self) -> None:
        self.started = True

    def on_destroy(self) -> None:
        self.stopped = True

    def _compute_contributions(self, *, model, matrix, processed, explanation_type, top_k):
        _ = model, processed, explanation_type, top_k
        rows: list[list[tuple[int, float]]] = []
        for row in matrix:
            arr = np.asarray(row, dtype=float)
            rows.append([(idx, float(val * self.scale)) for idx, val in enumerate(arr.tolist())])
        return rows


def test_unified_adapter_factory_create_cache_singleton_and_lifecycle() -> None:
    factory = UnifiedAdapterFactory(max_cache_size=2)
    factory.register(
        "demo",
        _FactoryDemoAdapter,
        singleton=True,
        validator=lambda payload: (float(payload.get("scale", 1.0)) > 0, "scale 必须大于 0"),
    )

    first = factory.create("demo", scale=2.0)
    second = factory.create("demo", scale=3.0)
    assert first is second
    assert first.started is True

    with pytest.raises(UnifiedAdapterError) as exc_info:
        factory.create("demo", scale=-1.0, singleton=False)
    assert exc_info.value.code == FrameworkErrorCode.ADAPTER_CREATE_FAILED

    released = factory.release("demo")
    assert released == 1
    assert first.stopped is True

    status = factory.status()
    assert "demo" in status["registered"]
    assert any(item["status"] in {"active", "destroyed"} for item in status["lifecycle"])


def test_model_metadata_store_upsert_query_versions_sync_and_export(tmp_path: Path) -> None:
    store = ModelMetadataStore(store_path=tmp_path / "metadata_store.json")

    first = store.upsert(
        {
            "model_name": "fusion_explainer",
            "model_type": "fusion",
            "framework": "pytorch",
            "version": "v1",
            "tags": ["prod", "explain"],
            "extra": {"owner": "team-a"},
        },
        note="initial",
    )
    assert first["record_id"] == "fusion_explainer:v1"

    second = store.upsert(
        {
            "record_id": "fusion_explainer:v1",
            "model_name": "fusion_explainer",
            "model_type": "fusion",
            "framework": "pytorch",
            "version": "v1",
            "status": "deprecated",
            "tags": ["prod"],
            "extra": {"owner": "team-b"},
        },
        note="deprecated",
    )
    assert second["status"] == "deprecated"

    queried = store.query(framework="pytorch", tags={"prod"})
    assert len(queried) == 1
    assert queried[0]["record_id"] == "fusion_explainer:v1"

    versions = store.versions("fusion_explainer:v1")
    assert len(versions) == 2

    mirror = ModelMetadataStore(store_path=tmp_path / "mirror_store.json")
    sync_stats = mirror.sync_from(store)
    assert sync_stats["inserted"] == 1
    assert sync_stats["updated"] == 0

    csv_path = store.export(tmp_path / "metadata_export.csv")
    json_path = store.export(tmp_path / "metadata_export.json")
    assert csv_path.exists()
    assert json_path.exists()

    spec = ModelMetadataStore.field_spec()
    assert "model_name" in spec and "version" in spec


def test_unified_logger_format_level_context_filter_and_aggregate() -> None:
    logger = UnifiedLogger("unified-stage3", level="INFO", json_format=False)

    logger.log("info", "boot", stage="init")
    with logger.bind_context(trace_id="trace-1", service="dl"):
        logger.log("warning", "latency high", ms=215)
        logger.log("error", "run failed", code="E001")

    warning_events = logger.query(level="WARNING")
    assert len(warning_events) == 1
    assert warning_events[0]["context"]["trace_id"] == "trace-1"

    matched = logger.query(contains="failed", context_filters={"service": "dl"})
    assert len(matched) == 1
    assert matched[0]["level"] == "ERROR"

    level_agg = logger.aggregate(by="level")
    assert level_agg["INFO"] == 1
    assert level_agg["WARNING"] == 1
    assert level_agg["ERROR"] == 1

    context_agg = logger.aggregate(by="context_key")
    assert context_agg["trace_id"] == 2

    guide = UnifiedLogger.generate_usage_guide()
    assert "# 统一日志使用指南" in guide
    assert "aggregate" in guide
