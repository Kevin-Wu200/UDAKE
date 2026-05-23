"""图卷积自编码异常检测（轻量 numpy 实现）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import (
    ThresholdMethod,
    compute_threshold,
    knn_graph,
    multiscale_value_features,
    normalize_adjacency,
    safe_minmax,
    standardize,
)


@dataclass
class GCAEConfig:
    latent_dim: int = 4
    knn_k: int = 8
    structure_weight: float = 0.4
    feature_weight: float = 0.6
    random_state: int = 42


class GCAEAnomalyDetector:
    """模拟 GCN+GAT+EdgeConv+Pooling 的图异常检测器。"""

    def __init__(self, config: GCAEConfig | None = None) -> None:
        self.config = config or GCAEConfig()
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None
        self.proj: np.ndarray | None = None
        self.embed_center: np.ndarray | None = None
        self.adj_template: np.ndarray | None = None
        self.rng = np.random.default_rng(self.config.random_state)

    def is_trained(self) -> bool:
        return self.proj is not None and self.feature_mean is not None and self.feature_std is not None

    def _validate_inputs(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if c.shape[0] != v.shape[0]:
            raise ValueError("coords and values length mismatch")
        if c.shape[0] < 2:
            raise ValueError("at least 2 points are required")
        if not np.isfinite(c).all() or not np.isfinite(v).all():
            raise ValueError("coords and values must be finite")
        return c, v

    def preprocess_graph_data(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        *,
        batch_size: int | None = None,
        use_training_stats: bool = True,
    ) -> dict[str, object]:
        c, v = self._validate_inputs(coords, values)
        node_features = self._build_node_features(c, v)
        if use_training_stats and self.feature_mean is not None and self.feature_std is not None:
            feat_norm = (node_features - self.feature_mean) / self.feature_std
            scaler = {
                "mean": np.asarray(self.feature_mean, dtype=float).reshape(-1).tolist(),
                "std": np.asarray(self.feature_std, dtype=float).reshape(-1).tolist(),
                "source": "trained",
            }
        else:
            feat_norm, mean, std = standardize(node_features)
            scaler = {
                "mean": mean.reshape(-1).tolist(),
                "std": std.reshape(-1).tolist(),
                "source": "runtime",
            }

        adj = knn_graph(c, k=self.config.knn_k)
        adj_norm = normalize_adjacency(adj)
        gcn = self._gcn_layer(feat_norm, adj_norm)
        gat = self._gat_layer(gcn, adj)
        edge = self._edgeconv_layer(gat, adj)

        graph_signals = np.column_stack(
            [
                np.mean(gcn, axis=1),
                np.mean(gat, axis=1),
                np.mean(edge, axis=1),
            ]
        )
        node_degree = adj.sum(axis=1, keepdims=True)
        density = float(adj.sum() / max(1, adj.size))
        adj_density = np.full((len(c), 1), density, dtype=float)
        local = multiscale_value_features(c, v, scales=(5,))
        processed = np.column_stack(
            [
                c[:, 0],
                c[:, 1],
                np.linalg.norm(c, axis=1),
                v,
                graph_signals[:, 0],
                graph_signals[:, 1],
                graph_signals[:, 2],
                node_degree.reshape(-1),
                adj_density.reshape(-1),
                local[:, 0],
                local[:, 1],
            ]
        )
        names = [
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
        ]
        size = int(max(1, batch_size or len(c)))
        slices = [[int(i), int(min(i + size, len(c)))] for i in range(0, len(c), size)]
        return {
            "coords": c,
            "values": v,
            "node_features": node_features,
            "normalized_node_features": feat_norm,
            "adjacency_matrix": adj,
            "processed_features": processed,
            "feature_names": names,
            "batch_slices": slices,
            "scaler": scaler,
            "validation": {"is_valid": True, "n_nodes": int(len(c)), "batch_size": size},
        }

    def _build_node_features(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        return np.concatenate([c, radius, v], axis=1)

    def _gcn_layer(self, features: np.ndarray, adj_norm: np.ndarray) -> np.ndarray:
        return adj_norm @ features

    def _gat_layer(self, features: np.ndarray, adj: np.ndarray) -> np.ndarray:
        # 简化版注意力：按节点特征相似度分配邻居权重。
        logits = features @ features.T
        mask = np.where(adj > 0, 0.0, -1e9)
        logits = logits + mask
        logits = logits - logits.max(axis=1, keepdims=True)
        weights = np.exp(logits)
        weights = weights / (weights.sum(axis=1, keepdims=True) + 1e-12)
        return weights @ features

    def _edgeconv_layer(self, features: np.ndarray, adj: np.ndarray) -> np.ndarray:
        n = len(features)
        out = np.zeros_like(features)
        for i in range(n):
            idx = np.where(adj[i] > 0)[0]
            if len(idx) == 0:
                out[i] = features[i]
                continue
            edge_feat = features[idx] - features[i]
            out[i] = features[i] + edge_feat.mean(axis=0)
        return out

    def _graph_pooling(self, node_embedding: np.ndarray) -> np.ndarray:
        return np.concatenate([node_embedding.mean(axis=0), node_embedding.max(axis=0)], axis=0)

    def _encode(self, features: np.ndarray, adj: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        adj_norm = normalize_adjacency(adj)
        gcn = self._gcn_layer(features, adj_norm)
        gat = self._gat_layer(gcn, adj)
        edge = self._edgeconv_layer(gat, adj)
        merged = np.concatenate([features, gcn, gat, edge], axis=1)

        centered = merged - merged.mean(axis=0, keepdims=True)
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        latent_dim = int(max(1, min(self.config.latent_dim, vt.shape[0])))
        proj = vt[:latent_dim].T
        z = centered @ proj
        return z, proj

    def _decode(self, latent: np.ndarray, proj: np.ndarray, merged_mean: np.ndarray) -> np.ndarray:
        return latent @ proj.T + merged_mean

    def fit(self, coords: np.ndarray, values: np.ndarray) -> dict[str, float]:
        coords, values = self._validate_inputs(coords, values)
        node_features = self._build_node_features(coords, values)
        feat_norm, mean, std = standardize(node_features)
        adj = knn_graph(coords, k=self.config.knn_k)

        z, proj = self._encode(feat_norm, adj)

        self.feature_mean = mean
        self.feature_std = std
        self.proj = proj
        self.embed_center = z.mean(axis=0, keepdims=True)
        self.adj_template = adj

        merged, merged_mean = self._build_context_features(feat_norm, adj)
        recon = self._decode(z, proj, merged_mean)

        feature_recon_loss = float(np.mean((merged - recon) ** 2))
        adj_recon = safe_minmax(z @ z.T)
        structure_loss = float(np.mean((adj - adj_recon) ** 2))
        total = self.config.feature_weight * feature_recon_loss + self.config.structure_weight * structure_loss

        return {
            "feature_recon_loss": feature_recon_loss,
            "structure_loss": structure_loss,
            "total_loss": float(total),
            "graph_nodes": float(len(node_features)),
            "graph_density": float(adj.sum() / max(1, adj.size)),
        }

    def _build_context_features(self, feat_norm: np.ndarray, adj: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        adj_norm = normalize_adjacency(adj)
        gcn = self._gcn_layer(feat_norm, adj_norm)
        gat = self._gat_layer(gcn, adj)
        edge = self._edgeconv_layer(gat, adj)
        merged = np.concatenate([feat_norm, gcn, gat, edge], axis=1)
        return merged, merged.mean(axis=0, keepdims=True)

    def _infer_latent(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if not self.is_trained():
            raise ValueError("模型尚未训练")
        coords, values = self._validate_inputs(coords, values)
        node_features = self._build_node_features(coords, values)
        feat_norm = (node_features - self.feature_mean) / self.feature_std
        adj = knn_graph(coords, k=self.config.knn_k)
        merged, merged_mean = self._build_context_features(feat_norm, adj)
        centered = merged - merged.mean(axis=0, keepdims=True)
        latent = centered @ self.proj
        recon = self._decode(latent, self.proj, merged_mean)
        return latent, merged, recon, adj

    def anomaly_scores(self, coords: np.ndarray, values: np.ndarray) -> dict[str, object]:
        latent, merged, recon, adj = self._infer_latent(coords, values)

        node_recon = np.mean((merged - recon) ** 2, axis=1)
        node_dist = np.linalg.norm(latent - latent.mean(axis=0, keepdims=True), axis=1)
        node_scores = 0.7 * safe_minmax(node_recon) + 0.3 * safe_minmax(node_dist)

        adj_recon = safe_minmax(latent @ latent.T)
        edge_scores = np.abs(adj - adj_recon)

        subgraph_scores = np.zeros(len(node_scores), dtype=float)
        for i in range(len(node_scores)):
            nbr = np.where(adj[i] > 0)[0]
            if len(nbr) == 0:
                subgraph_scores[i] = node_scores[i]
            else:
                subgraph_scores[i] = float((node_scores[i] + node_scores[nbr].mean()) / 2.0)

        return {
            "node": node_scores,
            "edge": edge_scores,
            "subgraph": subgraph_scores,
            "labels": (node_scores >= compute_threshold(node_scores, method="percentile", percentile=95.0).value).astype(int).tolist(),
            "pooling": self._graph_pooling(latent).tolist(),
        }

    def predict(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        threshold_method: ThresholdMethod = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, object]:
        coords, values = self._validate_inputs(coords, values)
        score_bundle = self.anomaly_scores(coords, values)
        node_scores = np.asarray(score_bundle["node"], dtype=float)
        edge_scores = np.asarray(score_bundle["edge"], dtype=float)
        subgraph_scores = np.asarray(score_bundle["subgraph"], dtype=float)

        node_thr = compute_threshold(node_scores, method=threshold_method, percentile=percentile, k=k)
        sub_thr = compute_threshold(subgraph_scores, method=threshold_method, percentile=percentile, k=k)
        edge_thr = compute_threshold(edge_scores.reshape(-1), method=threshold_method, percentile=percentile, k=k)

        node_idx = np.where(node_scores >= node_thr.value)[0]
        sub_idx = np.where(subgraph_scores >= sub_thr.value)[0]
        edge_idx = np.argwhere(edge_scores >= edge_thr.value)

        return {
            "node_anomalies": node_idx.tolist(),
            "edge_anomalies": edge_idx.tolist(),
            "subgraph_anomalies": sub_idx.tolist(),
            "node_scores": node_scores.tolist(),
            "subgraph_scores": subgraph_scores.tolist(),
            "anomaly_scores": node_scores.tolist(),
            "anomaly_labels": (node_scores >= node_thr.value).astype(int).tolist(),
            "anomaly_count": int(len(node_idx)),
            "anomaly_indices": node_idx.tolist(),
            "thresholds": {
                "node": node_thr.value,
                "edge": edge_thr.value,
                "subgraph": sub_thr.value,
            },
            "threshold_method": threshold_method,
            "pooling_embedding": score_bundle["pooling"],
        }

    def predict_standard(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        *,
        threshold_method: ThresholdMethod = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, object]:
        if not self.is_trained():
            raise ValueError("模型尚未训练，无法执行标准预测")
        payload = self.predict(
            coords=coords,
            values=values,
            threshold_method=threshold_method,
            percentile=percentile,
            k=k,
        )
        scores = np.asarray(payload.get("anomaly_scores", []), dtype=float)
        labels = np.asarray(payload.get("anomaly_labels", []), dtype=int)
        return {
            "scores": scores.astype(float).tolist(),
            "labels": labels.astype(int).tolist(),
            "anomaly_count": int(labels.sum()),
            "anomaly_indices": np.where(labels > 0)[0].astype(int).tolist(),
            "threshold": float(payload.get("thresholds", {}).get("node", 0.0)),
            "details": payload,
        }
