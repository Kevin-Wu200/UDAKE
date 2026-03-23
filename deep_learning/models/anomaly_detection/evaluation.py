"""异常检测评估、可视化数据与基准对比。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    auc,
    confusion_matrix,
    precision_recall_curve,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
)

from .common import safe_minmax


@dataclass
class EvaluationResult:
    precision: float
    recall: float
    f1: float
    auc_roc: float
    auc_pr: float


class AnomalyEvaluator:
    """评估指标 + 可视化 + 基准对比 + 消融实验。"""

    def evaluate(self, y_true: np.ndarray, scores: np.ndarray, threshold: float | None = None) -> dict[str, float]:
        yt = np.asarray(y_true, dtype=int).reshape(-1)
        sc = np.asarray(scores, dtype=float).reshape(-1)
        if len(yt) != len(sc):
            raise ValueError("标签与分数长度不一致")

        if threshold is None:
            threshold = float(np.percentile(sc, 95.0))
        y_pred = (sc >= threshold).astype(int)

        precision = float(precision_score(yt, y_pred, zero_division=0))
        recall = float(recall_score(yt, y_pred, zero_division=0))
        f1 = float(f1_score(yt, y_pred, zero_division=0))

        if len(np.unique(yt)) > 1:
            auc_roc = float(roc_auc_score(yt, sc))
            p, r, _ = precision_recall_curve(yt, sc)
            auc_pr = float(auc(r, p))
        else:
            auc_roc = 0.5
            auc_pr = 0.5

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "auc_roc": auc_roc,
            "auc_pr": auc_pr,
        }

    def visualizations(
        self,
        coords: np.ndarray,
        y_true: np.ndarray,
        scores: np.ndarray,
        threshold: float | None = None,
        embeddings: np.ndarray | None = None,
    ) -> dict[str, Any]:
        c = np.asarray(coords, dtype=float)
        yt = np.asarray(y_true, dtype=int).reshape(-1)
        sc = np.asarray(scores, dtype=float).reshape(-1)
        if threshold is None:
            threshold = float(np.percentile(sc, 95.0))
        yp = (sc >= threshold).astype(int)

        fpr, tpr, roc_th = roc_curve(yt, sc) if len(np.unique(yt)) > 1 else (np.array([0.0, 1.0]), np.array([0.0, 1.0]), np.array([1.0, 0.0]))
        precision, recall, pr_th = precision_recall_curve(yt, sc)
        cm = confusion_matrix(yt, yp, labels=[0, 1])

        if embeddings is None:
            emb = np.stack([safe_minmax(c[:, 0]), safe_minmax(c[:, 1])], axis=1)
        else:
            emb = np.asarray(embeddings, dtype=float)
            if emb.ndim == 1:
                emb = emb.reshape(-1, 1)
            if emb.shape[1] == 1:
                emb = np.concatenate([emb, np.zeros((len(emb), 1), dtype=float)], axis=1)

        heatmap = [{"x": float(c[i, 0]), "y": float(c[i, 1]), "score": float(sc[i])} for i in range(len(c))]
        feature_space = [{"x": float(emb[i, 0]), "y": float(emb[i, 1]), "label": int(yt[i])} for i in range(len(emb))]

        return {
            "anomaly_heatmap": heatmap,
            "roc_curve": {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": roc_th.tolist(),
            },
            "pr_curve": {
                "precision": precision.tolist(),
                "recall": recall.tolist(),
                "thresholds": pr_th.tolist(),
            },
            "confusion_matrix": cm.tolist(),
            "feature_space": feature_space,
        }

    def benchmark_against_isolation_forest(
        self,
        features: np.ndarray,
        y_true: np.ndarray,
        model_scores: np.ndarray,
        random_state: int = 42,
    ) -> dict[str, Any]:
        x = np.asarray(features, dtype=float)
        y = np.asarray(y_true, dtype=int).reshape(-1)
        sc = np.asarray(model_scores, dtype=float).reshape(-1)

        iso = IsolationForest(contamination=0.1, random_state=random_state)
        iso.fit(x)
        # score_samples 越大越正常，转换为异常分数。
        baseline_scores = -iso.score_samples(x)

        model_metrics = self.evaluate(y, sc)
        baseline_metrics = self.evaluate(y, baseline_scores)

        # 统计显著性检验：对每个样本分数进行配对 t 检验。
        t_stat, p_value = stats.ttest_rel(sc, baseline_scores)

        return {
            "model": model_metrics,
            "isolation_forest": baseline_metrics,
            "delta_f1": float(model_metrics["f1"] - baseline_metrics["f1"]),
            "delta_auc_roc": float(model_metrics["auc_roc"] - baseline_metrics["auc_roc"]),
            "significance": {
                "t_stat": float(t_stat) if np.isfinite(t_stat) else 0.0,
                "p_value": float(p_value) if np.isfinite(p_value) else 1.0,
            },
        }

    def ablation_study(
        self,
        y_true: np.ndarray,
        component_scores: dict[str, np.ndarray],
        weights: dict[str, float] | None = None,
    ) -> dict[str, dict[str, float]]:
        yt = np.asarray(y_true, dtype=int).reshape(-1)
        if not component_scores:
            return {}

        keys = list(component_scores.keys())
        if weights is None:
            weights = {k: 1.0 / len(keys) for k in keys}

        normalized = {k: safe_minmax(np.asarray(v, dtype=float).reshape(-1)) for k, v in component_scores.items()}

        full = np.zeros_like(next(iter(normalized.values())))
        for k in keys:
            full += float(weights.get(k, 0.0)) * normalized[k]
        result = {"full": self.evaluate(yt, full)}

        for drop_key in keys:
            remain = [k for k in keys if k != drop_key]
            if not remain:
                continue
            score = np.zeros_like(full)
            total = sum(float(weights.get(k, 0.0)) for k in remain) + 1e-9
            for key in remain:
                score += float(weights.get(key, 0.0)) / total * normalized[key]
            result[f"drop_{drop_key}"] = self.evaluate(yt, score)

        return result

    def generate_report(
        self,
        model_name: str,
        metrics: dict[str, float],
        benchmark: dict[str, Any] | None = None,
        ablation: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, Any]:
        lines = [
            f"# {model_name} 异常检测评估报告",
            "",
            "## 核心指标",
            f"- Precision: {metrics.get('precision', 0.0):.4f}",
            f"- Recall: {metrics.get('recall', 0.0):.4f}",
            f"- F1: {metrics.get('f1', 0.0):.4f}",
            f"- AUC-ROC: {metrics.get('auc_roc', 0.0):.4f}",
            f"- AUC-PR: {metrics.get('auc_pr', 0.0):.4f}",
        ]

        if benchmark is not None:
            lines.extend(
                [
                    "",
                    "## 基准对比",
                    f"- Delta F1 vs IsolationForest: {benchmark.get('delta_f1', 0.0):.4f}",
                    f"- Delta AUC-ROC vs IsolationForest: {benchmark.get('delta_auc_roc', 0.0):.4f}",
                    f"- p-value: {benchmark.get('significance', {}).get('p_value', 1.0):.6f}",
                ]
            )

        if ablation is not None:
            lines.append("")
            lines.append("## 消融实验")
            for key, value in ablation.items():
                lines.append(f"- {key}: F1={value.get('f1', 0.0):.4f}, AUC-ROC={value.get('auc_roc', 0.0):.4f}")

        return {
            "model": model_name,
            "metrics": metrics,
            "benchmark": benchmark or {},
            "ablation": ablation or {},
            "markdown": "\n".join(lines),
        }
