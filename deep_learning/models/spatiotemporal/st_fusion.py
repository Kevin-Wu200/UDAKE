"""时空模型融合：融合克里金结果与深度学习预测。"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


class STModelFusion:
    """时空融合器，输出融合均值与方差。"""

    def fuse(
        self,
        kriging_mean: np.ndarray,
        kriging_variance: np.ndarray,
        dl_mean: np.ndarray,
        dl_variance: np.ndarray,
        weight_dl: float = 0.45,
    ) -> Dict[str, Any]:
        w_dl = float(np.clip(weight_dl, 0.0, 1.0))
        w_kg = 1.0 - w_dl

        kg_mean = np.asarray(kriging_mean, dtype=float)
        kg_var = np.maximum(np.asarray(kriging_variance, dtype=float), 1e-9)
        dl_mean = np.asarray(dl_mean, dtype=float)
        dl_var = np.maximum(np.asarray(dl_variance, dtype=float), 1e-9)

        if kg_mean.shape != dl_mean.shape:
            raise ValueError("kriging_mean 与 dl_mean 形状必须一致")

        fused_mean = w_kg * kg_mean + w_dl * dl_mean
        fused_var = (w_kg**2) * kg_var + (w_dl**2) * dl_var

        return {
            "mean": fused_mean,
            "variance": fused_var,
            "weights": {"kriging": w_kg, "deep_learning": w_dl},
        }
