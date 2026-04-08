"""异常检测解释服务测试。"""

from __future__ import annotations

from app.dl_services.service import DeepLearningService


def _build_payload() -> tuple[list[list[float]], list[float]]:
    coords = [
        [120.10, 30.20],
        [120.20, 30.25],
        [120.18, 30.30],
        [120.24, 30.28],
        [120.15, 30.35],
        [120.28, 30.22],
        [120.30, 30.26],
        [120.12, 30.18],
    ]
    values = [1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98]
    return coords, values


def test_explain_anomaly_vae_hybrid() -> None:
    service = DeepLearningService()
    coords, values = _build_payload()

    result = service.explain_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        method="hybrid",
        top_k=3,
        max_explain_nodes=3,
    )

    assert result["model_name"] == "vae"
    assert result["summary"]["method"] == "hybrid"
    assert "feature_analysis" in result
    assert "lime" in result
    assert "shap" in result
    assert result["feature_analysis"]["feature_count"] >= 12


def test_explain_anomaly_gan_hybrid() -> None:
    service = DeepLearningService()
    coords, values = _build_payload()

    result = service.explain_anomaly(
        model_name="gan",
        coords=coords,
        values=values,
        method="hybrid",
    )

    assert result["model_name"] == "gan"
    assert result["summary"]["method"] == "hybrid"
    assert "lime" in result
    assert "shap" in result
    assert result["feature_analysis"]["model_name"] == "gan"


def test_explain_anomaly_contrastive_returns_pending_adapter() -> None:
    service = DeepLearningService()
    coords, values = _build_payload()

    result = service.explain_anomaly(
        model_name="contrastive",
        coords=coords,
        values=values,
        method="hybrid",
    )

    assert result["summary"]["adapter_status"] == "pending"
    assert result["feature_analysis"]["model_name"] == "contrastive"
