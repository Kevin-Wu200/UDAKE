"""异常检测模型特征定义与标准化方案。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureDefinition:
    feature_name: str
    display_name: str
    category: str
    standardization: str


class AnomalyFeatureRegistry:
    """集中管理异常检测模型的特征列表、名称映射与标准化策略。"""

    _COMMON_DEFINITIONS: dict[str, FeatureDefinition] = {
        "coord_x": FeatureDefinition("coord_x", "坐标X", "spatial", "zscore"),
        "coord_y": FeatureDefinition("coord_y", "坐标Y", "spatial", "zscore"),
        "radius": FeatureDefinition("radius", "到中心半径", "spatial", "zscore"),
        "angle": FeatureDefinition("angle", "方位角", "spatial", "zscore"),
        "value": FeatureDefinition("value", "观测值", "value", "robust_zscore"),
        "value_centered": FeatureDefinition("value_centered", "中心化观测值", "value", "robust_zscore"),
        "value_squared": FeatureDefinition("value_squared", "观测值平方", "value", "robust_zscore"),
        "local_mean_k3": FeatureDefinition("local_mean_k3", "3邻域均值", "context", "robust_zscore"),
        "local_std_k3": FeatureDefinition("local_std_k3", "3邻域标准差", "context", "robust_zscore"),
        "local_mean_k5": FeatureDefinition("local_mean_k5", "5邻域均值", "context", "robust_zscore"),
        "local_std_k5": FeatureDefinition("local_std_k5", "5邻域标准差", "context", "robust_zscore"),
        "local_mean_k9": FeatureDefinition("local_mean_k9", "9邻域均值", "context", "robust_zscore"),
        "local_std_k9": FeatureDefinition("local_std_k9", "9邻域标准差", "context", "robust_zscore"),
        "raw_coord_x": FeatureDefinition("raw_coord_x", "残差连接X", "residual", "zscore"),
        "raw_coord_y": FeatureDefinition("raw_coord_y", "残差连接Y", "residual", "zscore"),
        "raw_value": FeatureDefinition("raw_value", "残差连接值", "residual", "robust_zscore"),
        "gcn_response": FeatureDefinition("gcn_response", "GCN响应", "graph", "zscore"),
        "gat_response": FeatureDefinition("gat_response", "GAT响应", "graph", "zscore"),
        "edgeconv_response": FeatureDefinition("edgeconv_response", "EdgeConv响应", "graph", "zscore"),
        "node_degree": FeatureDefinition("node_degree", "节点度", "graph", "minmax"),
        "adj_density": FeatureDefinition("adj_density", "图密度", "graph", "minmax"),
        "disc_score": FeatureDefinition("disc_score", "判别器分数", "gan", "minmax"),
        "recon_score": FeatureDefinition("recon_score", "重建分数", "gan", "minmax"),
        "grad_score": FeatureDefinition("grad_score", "梯度分数", "gan", "minmax"),
        "noise_level": FeatureDefinition("noise_level", "噪声强度", "gan", "zscore"),
        "feature_distance": FeatureDefinition("feature_distance", "特征空间距离", "embedding", "minmax"),
        "density_score": FeatureDefinition("density_score", "密度分数", "embedding", "minmax"),
        "nearest_score": FeatureDefinition("nearest_score", "最近邻分数", "embedding", "minmax"),
        "bank_similarity": FeatureDefinition("bank_similarity", "特征库相似度", "embedding", "minmax"),
    }

    _MODEL_FEATURES: dict[str, list[str]] = {
        "vae": [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "value",
            "value_centered",
            "value_squared",
            "local_mean_k3",
            "local_std_k3",
            "local_mean_k5",
            "local_std_k5",
            "local_mean_k9",
            "local_std_k9",
            "raw_coord_x",
            "raw_coord_y",
            "raw_value",
        ],
        "gcae": [
            "coord_x",
            "coord_y",
            "radius",
            "value",
            "gcn_response",
            "gat_response",
            "edgeconv_response",
            "node_degree",
            "adj_density",
            "local_mean_k5",
            "local_std_k5",
        ],
        "gan": [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "value",
            "disc_score",
            "recon_score",
            "grad_score",
            "noise_level",
        ],
        "contrastive": [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "value",
            "value_centered",
            "feature_distance",
            "density_score",
            "nearest_score",
            "bank_similarity",
        ],
    }

    def supported_models(self) -> list[str]:
        return sorted(self._MODEL_FEATURES.keys())

    def model_features(self, model_name: str) -> list[FeatureDefinition]:
        key = (model_name or "").strip().lower()
        if key not in self._MODEL_FEATURES:
            raise ValueError(f"不支持的异常检测模型: {model_name}")
        return [self._COMMON_DEFINITIONS[name] for name in self._MODEL_FEATURES[key]]

    def feature_name_mapping(self, model_name: str) -> dict[str, str]:
        return {item.feature_name: item.display_name for item in self.model_features(model_name)}

    def standardization_plan(self, model_name: str) -> dict[str, str]:
        return {item.feature_name: item.standardization for item in self.model_features(model_name)}

    def analyze(self, model_name: str) -> dict[str, Any]:
        features = self.model_features(model_name)
        category_count: dict[str, int] = {}
        for item in features:
            category_count[item.category] = category_count.get(item.category, 0) + 1
        return {
            "model_name": (model_name or "").strip().lower(),
            "feature_count": len(features),
            "feature_list": [
                {
                    "feature_name": item.feature_name,
                    "display_name": item.display_name,
                    "category": item.category,
                    "standardization": item.standardization,
                }
                for item in features
            ],
            "feature_name_mapping": self.feature_name_mapping(model_name),
            "standardization_plan": self.standardization_plan(model_name),
            "category_distribution": category_count,
        }

