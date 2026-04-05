"""时空模型自动选择器适配层。"""

from __future__ import annotations

from ...services.spatiotemporal_core import SpatiotemporalModelAutoSelector


class STModelSelector(SpatiotemporalModelAutoSelector):
    """向文件结构规划暴露的时空模型选择器。"""
