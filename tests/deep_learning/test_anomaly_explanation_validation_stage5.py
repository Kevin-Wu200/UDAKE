from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from services.backend.app.dl_services.service import DeepLearningService


MODELS = ("vae", "gcae", "gan", "contrastive")


@dataclass
class QualityMetric:
    completeness: float
    consistency: float
    interpretability: float
    expert_score: float


def _make_data(n: int = 84, seed: int = 209) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.1) + np.cos(coords[:, 1] * 3.7) + rng.normal(0.0, 0.04, size=n)
    for idx in (9, 24, 41, 66):
        values[idx] += 1.2
    return coords, values


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _top_feature_set(explain_payload: dict, limit: int = 5) -> set[str]:
    items = explain_payload.get("summary", {}).get("top_features", [])[:limit]
    names = []
    for item in items:
        feature_name = str(item.get("feature_name", "")).strip().lower()
        if feature_name:
            names.append(feature_name)
    return set(names)


def _node_set(branch_payload: dict, limit: int = 8) -> set[int]:
    nodes = []
    for item in branch_payload.get("batch_explanations", [])[:limit]:
        if "node_index" in item:
            nodes.append(int(item["node_index"]))
    return set(nodes)


def _branch_consistency(branch_payload: dict) -> float:
    anomaly_score_exp = branch_payload.get("anomaly_score_explanation", {})
    consistency = anomaly_score_exp.get("consistency_validation", {})
    corr = float(consistency.get("score_corr", 0.0))
    coverage = float(consistency.get("coverage", 0.0))
    corr_norm = max(0.0, min(1.0, (corr + 1.0) / 2.0))
    coverage_norm = max(0.0, min(1.0, coverage))
    rule_bonus = 1.0 if bool(consistency.get("is_reasonable", False)) else 0.0
    return 0.45 * corr_norm + 0.45 * coverage_norm + 0.10 * rule_bonus


def _branch_interpretability(branch_payload: dict) -> float:
    batch = branch_payload.get("batch_explanations", [])
    if not batch:
        return 0.0
    readable = 0
    for item in batch:
        reason = str(item.get("reason", "")).strip()
        contributions = item.get("top_contributions", [])
        has_reason = len(reason) >= 6
        has_contrib = isinstance(contributions, list) and len(contributions) > 0
        if has_reason or has_contrib:
            readable += 1
    return readable / len(batch)


def _evaluate_quality(explain_payload: dict) -> QualityMetric:
    root_required = ("model_name", "summary", "lime", "shap")
    summary_required = ("method", "top_features", "feature_count", "max_explain_nodes")
    completeness_root = sum(1 for key in root_required if key in explain_payload) / len(root_required)
    completeness_summary = sum(1 for key in summary_required if key in explain_payload.get("summary", {})) / len(summary_required)
    completeness = (completeness_root + completeness_summary) / 2.0

    lime = explain_payload.get("lime", {})
    shap = explain_payload.get("shap", {})
    lime_features = _top_feature_set(lime)
    shap_features = _top_feature_set(shap)
    feature_overlap = _jaccard(lime_features, shap_features)

    lime_nodes = _node_set(lime)
    shap_nodes = _node_set(shap)
    node_overlap = _jaccard({str(x) for x in lime_nodes}, {str(x) for x in shap_nodes})

    branch_consistency = max(_branch_consistency(lime), _branch_consistency(shap))
    consistency = 0.4 * feature_overlap + 0.3 * node_overlap + 0.3 * branch_consistency

    interpretability = (_branch_interpretability(lime) + _branch_interpretability(shap)) / 2.0
    expert_score = 0.4 * completeness + 0.35 * consistency + 0.25 * interpretability
    return QualityMetric(completeness=completeness, consistency=consistency, interpretability=interpretability, expert_score=expert_score)


def test_stage5_explanation_quality_metrics_and_expert_review() -> None:
    coords, values = _make_data(seed=301)
    service = DeepLearningService()

    for model_name in MODELS:
        service.train_anomaly_model(model_name, coords.tolist(), values.tolist(), epochs=12)
        explain_out = service.explain_anomaly(
            model_name=model_name,
            coords=coords.tolist(),
            values=values.tolist(),
            method="hybrid",
            top_k=5,
            max_explain_nodes=7,
            include_prediction=True,
            num_samples=160,
            nsamples=120,
        )

        metric = _evaluate_quality(explain_out)
        assert metric.completeness >= 0.85
        assert metric.consistency >= 0.45
        assert metric.interpretability >= 0.65
        assert metric.expert_score >= 0.68


def test_stage5_explanation_consistency_analysis() -> None:
    coords, values = _make_data(seed=307)
    service = DeepLearningService()

    for model_name in MODELS:
        service.train_anomaly_model(model_name, coords.tolist(), values.tolist(), epochs=12)
        explain_out = service.explain_anomaly(
            model_name=model_name,
            coords=coords.tolist(),
            values=values.tolist(),
            method="hybrid",
            top_k=6,
            max_explain_nodes=6,
            include_prediction=True,
            num_samples=150,
            nsamples=100,
        )
        lime = explain_out["lime"]
        shap = explain_out["shap"]

        lime_features = _top_feature_set(lime, limit=6)
        shap_features = _top_feature_set(shap, limit=6)
        feature_overlap = _jaccard(lime_features, shap_features)
        assert feature_overlap >= 0.20

        lime_nodes = _node_set(lime, limit=6)
        shap_nodes = _node_set(shap, limit=6)
        node_overlap = _jaccard({str(x) for x in lime_nodes}, {str(x) for x in shap_nodes})
        assert node_overlap >= 0.20


def test_stage5_explanation_understandability_and_boundary_cases() -> None:
    coords, values = _make_data(seed=311)
    steady_values = np.full_like(values, fill_value=float(np.mean(values)))
    steady_values[3] += 1.0
    steady_values[17] -= 0.8

    for model_name in MODELS:
        service = DeepLearningService()
        service.train_anomaly_model(model_name, coords.tolist(), values.tolist(), epochs=10)

        explain_standard = service.explain_anomaly(
            model_name=model_name,
            coords=coords.tolist(),
            values=values.tolist(),
            method="hybrid",
            top_k=10,
            max_explain_nodes=300,
            include_prediction=True,
            num_samples=140,
            nsamples=90,
        )
        for branch_name in ("lime", "shap"):
            branch = explain_standard[branch_name]
            batch = branch["batch_explanations"]
            assert 1 <= len(batch) <= len(values)
            first = batch[0]
            assert "node_index" in first
            assert "top_contributions" in first
            assert isinstance(first["top_contributions"], list)

        explain_steady = service.explain_anomaly(
            model_name=model_name,
            coords=coords.tolist(),
            values=steady_values.tolist(),
            method="hybrid",
            top_k=8,
            max_explain_nodes=6,
            include_prediction=True,
            num_samples=120,
            nsamples=80,
        )
        assert explain_steady["summary"]["method"] == "hybrid"
        assert len(explain_steady["summary"]["top_features"]) >= 1

        for item in explain_steady["summary"]["top_features"]:
            value = float(item.get("importance", 0.0))
            assert np.isfinite(value)
