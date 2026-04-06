"""LIME 时空解释示例。"""

from __future__ import annotations

import numpy as np

from app.dl_services.lime_explainer import SpatiotemporalLIMEExplainer


def main() -> None:
    coords = np.asarray(
        [
            [120.10, 30.20],
            [120.15, 30.22],
            [120.20, 30.25],
            [120.18, 30.28],
        ],
        dtype=float,
    )
    series = np.asarray(
        [
            [[1.0, 0.2], [1.1, 0.3], [1.2, 0.4], [1.3, 0.45], [1.35, 0.5]],
            [[0.95, 0.25], [1.05, 0.3], [1.12, 0.35], [1.2, 0.4], [1.28, 0.46]],
            [[1.1, 0.22], [1.16, 0.27], [1.22, 0.32], [1.3, 0.39], [1.34, 0.43]],
            [[1.02, 0.28], [1.08, 0.34], [1.17, 0.38], [1.22, 0.42], [1.29, 0.48]],
        ],
        dtype=float,
    )
    pred_mean = np.asarray(
        [
            [1.36, 1.40],
            [1.30, 1.34],
            [1.35, 1.39],
            [1.31, 1.35],
        ],
        dtype=float,
    )

    explainer = SpatiotemporalLIMEExplainer()
    payload = explainer.explain(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=3,
    )

    print("summary:", payload["summary"])
    print("top_features:", payload["summary"]["top_features"])
    print("summary_text:", payload["visualization"]["summary_text"])


if __name__ == "__main__":
    main()
