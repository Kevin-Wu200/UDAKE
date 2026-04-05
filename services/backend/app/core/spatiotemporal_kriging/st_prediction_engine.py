"""时空预测引擎适配层。"""

from __future__ import annotations

from ...services.spatiotemporal_core import SpatiotemporalPredictionEngine


class STPredictionEngine(SpatiotemporalPredictionEngine):
    """向文件结构规划暴露的时空预测引擎。"""
