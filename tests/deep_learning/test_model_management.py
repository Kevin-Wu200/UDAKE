from __future__ import annotations

from pathlib import Path

from deep_learning.models.registry import (
    ModelExporter,
    ModelQuantizer,
    ModelRegistry,
    ModelSerializer,
    ModelVersioning,
    build_metadata,
)


def test_registry_and_versioning(tmp_path: Path) -> None:
    registry = ModelRegistry()
    registry.register("demo", lambda gain=1.0: {"gain": gain})

    model = registry.create("demo", gain=2.0)
    assert model["gain"] == 2.0
    assert registry.list_models() == ["demo"]

    versioning = ModelVersioning(repo_dir=str(tmp_path / "repo"))
    version = versioning.allocate_version("demo")
    assert version == "v1"

    metadata = build_metadata("demo", version, {"rmse": 0.12})
    meta_path = versioning.save_metadata(metadata)
    assert Path(meta_path).exists()
    assert versioning.latest_version("demo") == "v1"


def test_serializer_exporter_quantizer(tmp_path: Path) -> None:
    serializer = ModelSerializer()
    exporter = ModelExporter()
    quantizer = ModelQuantizer()

    model_obj = {"weights": [1.0, 2.0, 3.0]}
    model_path = tmp_path / "model" / "model.pkl"
    serializer.save(model_obj, str(model_path))
    loaded = serializer.load(str(model_path))
    assert loaded["weights"] == [1.0, 2.0, 3.0]

    ts_path = exporter.export_torchscript(model_obj, str(tmp_path / "model" / "model.ts"))
    onnx_path = exporter.export_onnx(model_obj, str(tmp_path / "model" / "model.onnx"))
    assert Path(ts_path).exists()
    assert Path(onnx_path).exists()

    assert quantizer.quantize([1.23456, -2.34567], dtype="float16") == [1.2346, -2.3457]
    assert quantizer.quantize([1.2, -200.0, 300.0], dtype="int8") == [1, -128, 127]
