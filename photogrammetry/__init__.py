"""
摄影测量模块 - 航测像片处理与几何解算
=========================================
支持航测像片的EXIF元数据解析、影像质量评估、单片纠正及地理对齐。

子模块:
- exif_parser: EXIF 2.3+ GPS/IMU 元数据解析
- image_quality: 影像质量自动评估（模糊度、曝光、倾斜程度）
- orthorectification: 基于共线方程的单片纠正引擎
- geo_alignment: 无缝地理对齐模块
"""

from .exif_parser import ExifParser, AerialImageMetadata
from .image_quality import ImageQualityAssessor, QualityReport
from .orthorectification import OrthorectificationEngine, CollinearityModel
from .geo_alignment import GeoAlignmentEngine, AlignmentResult

__all__ = [
    "ExifParser",
    "AerialImageMetadata",
    "ImageQualityAssessor",
    "QualityReport",
    "OrthorectificationEngine",
    "CollinearityModel",
    "GeoAlignmentEngine",
    "AlignmentResult",
]
