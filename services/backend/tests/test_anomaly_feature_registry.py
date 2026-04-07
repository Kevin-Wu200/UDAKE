"""异常检测特征注册测试。"""

from __future__ import annotations

from app.dl_services.anomaly_features import AnomalyFeatureRegistry


def test_anomaly_feature_registry_supports_all_models() -> None:
    registry = AnomalyFeatureRegistry()
    assert registry.supported_models() == ["contrastive", "gan", "gcae", "vae"]


def test_anomaly_feature_registry_vae_mapping_and_standardization() -> None:
    registry = AnomalyFeatureRegistry()
    analysis = registry.analyze("vae")
    mapping = analysis["feature_name_mapping"]
    plan = analysis["standardization_plan"]

    assert analysis["feature_count"] >= 12
    assert mapping["value"] == "观测值"
    assert mapping["raw_value"] == "残差连接值"
    assert plan["coord_x"] == "zscore"
    assert plan["value"] == "robust_zscore"
