"""不确定性量化模型特征提取与分解示例。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deep_learning.models.uncertainty import (
    decompose_uncertainty_sources,
    extract_model_features,
    feature_name_mapping,
)


def _sample_predictions() -> dict[str, dict[str, Any]]:
    return {
        "bnn": {
            "mean": np.array([0.10, 0.24], dtype=float),
            "variance": np.array([0.03, 0.06], dtype=float),
            "aleatoric": np.array([0.01, 0.02], dtype=float),
            "epistemic": np.array([0.02, 0.04], dtype=float),
            "lower": np.array([-0.11, 0.01], dtype=float),
            "upper": np.array([0.29, 0.42], dtype=float),
            "confidence": 0.94,
            "num_samples": 64,
        },
        "mc_dropout": {
            "mean": np.array([0.31, 0.48], dtype=float),
            "variance": np.array([0.05, 0.08], dtype=float),
            "aleatoric": np.array([0.02, 0.03], dtype=float),
            "epistemic": np.array([0.03, 0.05], dtype=float),
            "lower": np.array([0.11, 0.25], dtype=float),
            "upper": np.array([0.50, 0.71], dtype=float),
            "confidence": 0.92,
            "t": 30,
        },
        "deep_ensemble": {
            "mean": np.array([0.42, 0.57], dtype=float),
            "variance": np.array([0.04, 0.07], dtype=float),
            "aleatoric": np.array([0.02, 0.03], dtype=float),
            "epistemic": np.array([0.02, 0.04], dtype=float),
            "quantiles": {
                "q10": np.array([0.24, 0.39], dtype=float),
                "q50": np.array([0.42, 0.57], dtype=float),
                "q90": np.array([0.61, 0.76], dtype=float),
            },
            "member_ids": ["m0", "m1", "m2"],
            "aggregation": "mean",
        },
        "edl": {
            "logits": np.array([[1.4, 0.6, -0.2]], dtype=float),
            "evidence": np.array([[4.0, 2.1, 1.2]], dtype=float),
            "alpha": np.array([[5.0, 3.1, 2.2]], dtype=float),
            "probabilities": np.array([[0.61, 0.27, 0.12]], dtype=float),
            "prediction": np.array([0], dtype=int),
            "confidence": np.array([0.79], dtype=float),
            "uncertainty": {
                "total": np.array([0.36], dtype=float),
                "data": np.array([0.13], dtype=float),
                "knowledge": np.array([0.23], dtype=float),
                "threshold": 0.95,
            },
        },
    }


def _to_jsonable(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _to_jsonable(v) for k, v in data.items()}
    if isinstance(data, np.ndarray):
        return data.astype(float).tolist()
    if isinstance(data, np.floating):
        return float(data)
    if isinstance(data, np.integer):
        return int(data)
    return data


def main() -> None:
    name_mapping = feature_name_mapping()
    results: dict[str, dict[str, Any]] = {}

    for model_type, prediction in _sample_predictions().items():
        extracted = extract_model_features(model_type, prediction)
        decomposition = decompose_uncertainty_sources(model_type, prediction)

        results[model_type] = {
            "feature_keys": sorted(extracted.keys()),
            "feature_labels": {
                key: name_mapping.get(key, key)
                for key in sorted(extracted.keys())
                if key in name_mapping
            },
            "decomposition": _to_jsonable(decomposition),
        }

    print(json.dumps({"uncertainty_feature_analysis_demo": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
