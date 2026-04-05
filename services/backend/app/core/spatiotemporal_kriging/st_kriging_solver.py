"""时空克里金求解器适配层。"""

from __future__ import annotations

from ...services.spatiotemporal_core import SpatiotemporalKrigingSolver


class STKrigingSolver(SpatiotemporalKrigingSolver):
    """向文件结构规划暴露的时空克里金求解器。"""
