"""时空变异函数建模器适配层。"""

from __future__ import annotations

from ...services.spatiotemporal_core import SpatiotemporalVariogramModeler


class STVariogramFitter(SpatiotemporalVariogramModeler):
    """向文件结构规划暴露的时空变异函数建模器。"""
