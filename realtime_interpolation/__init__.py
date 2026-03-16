"""
实时插值系统
Real-time Interpolation System

增量式实时插值功能，支持新数据到达时快速更新插值结果
"""

__version__ = "1.0.0"
__author__ = "UDAKE Team"

from .core.incremental_kriging import IncrementalKriging
from .core.matrix_update import ShermanMorrisonUpdater, WoodburyUpdater
from .index.quadtree import QuadTree, BoundingBox, DataPoint
from .cache.cache_manager import CacheManager
from .events.event_system import EventSystem

__all__ = [
    "IncrementalKriging",
    "ShermanMorrisonUpdater",
    "WoodburyUpdater",
    "QuadTree",
    "BoundingBox",
    "DataPoint",
    "CacheManager",
    "EventSystem",
]