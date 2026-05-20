"""
影像质量评估模型
================
自动分析航测影像的质量指标：
- 模糊度检测（拉普拉斯方差法）
- 曝光评估（直方图分析）
- 倾斜程度评估（基于IMU姿态角）
- 综合质量评分
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import numpy as np

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from .exif_parser import AerialImageMetadata, IMUInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class BlurReport:
    """模糊度评估报告"""
    laplacian_variance: float           # 拉普拉斯方差（越高越清晰）
    blur_score: float                   # 归一化模糊分数 (0-100, 越高越清晰)
    is_blurry: bool                     # 是否模糊
    blur_level: str                     # 模糊等级: sharp/slight_moderate/severe

    def to_dict(self) -> Dict[str, Any]:
        return {
            "laplacian_variance": self.laplacian_variance,
            "blur_score": self.blur_score,
            "is_blurry": self.is_blurry,
            "blur_level": self.blur_level,
        }


@dataclass
class ExposureReport:
    """曝光评估报告"""
    mean_brightness: float              # 平均亮度 (0-255)
    overexposed_ratio: float            # 过曝像素比例
    underexposed_ratio: float           # 欠曝像素比例
    exposure_score: float               # 归一化曝光分数 (0-100)
    exposure_level: str                 # 曝光等级: good/slight_over/slight_under/over/under

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean_brightness": self.mean_brightness,
            "overexposed_ratio": self.overexposed_ratio,
            "underexposed_ratio": self.underexposed_ratio,
            "exposure_score": self.exposure_score,
            "exposure_level": self.exposure_level,
        }


@dataclass
class TiltReport:
    """倾斜程度评估报告"""
    tilt_angle: float                   # 综合倾斜角（与竖直方向的夹角，度）
    pitch: Optional[float] = None       # 俯仰角
    roll: Optional[float] = None        # 翻滚角
    is_nadir: bool = True               # 是否近似正射（倾斜角 < 5度）
    tilt_level: str = "nadir"           # 倾斜等级: nadir/slight/moderate/oblique

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tilt_angle": self.tilt_angle,
            "pitch": self.pitch,
            "roll": self.roll,
            "is_nadir": self.is_nadir,
            "tilt_level": self.tilt_level,
        }


@dataclass
class QualityReport:
    """综合影像质量报告"""
    file_path: str
    blur: BlurReport
    exposure: ExposureReport
    tilt: TiltReport
    overall_score: float                # 综合质量分数 (0-100)
    quality_level: str                  # 质量等级: excellent/good/acceptable/poor/rejected
    recommendations: list = field(default_factory=list)  # 改进建议

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "blur": self.blur.to_dict(),
            "exposure": self.exposure.to_dict(),
            "tilt": self.tilt.to_dict(),
            "overall_score": self.overall_score,
            "quality_level": self.quality_level,
            "recommendations": self.recommendations,
        }


# ---------------------------------------------------------------------------
# 影像质量评估器
# ---------------------------------------------------------------------------

class ImageQualityAssessor:
    """影像质量自动评估器"""

    # 阈值配置
    BLUR_THRESHOLD_SHARP = 250.0        # 拉普拉斯方差 > 此值视为清晰
    BLUR_THRESHOLD_SLIGHT = 100.0       # > 此值视为轻微模糊
    BLUR_THRESHOLD_MODERATE = 30.0      # > 此值视为中度模糊

    EXPOSURE_OVER_THRESHOLD = 240       # 过曝像素阈值
    EXPOSURE_UNDER_THRESHOLD = 15       # 欠曝像素阈值
    EXPOSURE_OVER_RATIO_MAX = 0.05      # 过曝比例上限
    EXPOSURE_UNDER_RATIO_MAX = 0.05     # 欠曝比例上限

    TILT_NADIR_MAX = 5.0                # 正射最大倾斜角（度）
    TILT_SLIGHT_MAX = 15.0              # 轻微倾斜上限
    TILT_MODERATE_MAX = 30.0            # 中度倾斜上限

    def assess_all(
        self,
        image_path: str,
        metadata: Optional[AerialImageMetadata] = None,
    ) -> QualityReport:
        """对影像进行全面质量评估"""
        img_array = self._load_image_array(image_path)
        if img_array is None:
            return self._empty_report(image_path)

        blur = self.assess_blur(img_array)
        exposure = self.assess_exposure(img_array)
        tilt = self.assess_tilt(metadata.imu if metadata else IMUInfo())

        overall, level, recommendations = self._compute_overall(blur, exposure, tilt)

        return QualityReport(
            file_path=image_path,
            blur=blur,
            exposure=exposure,
            tilt=tilt,
            overall_score=overall,
            quality_level=level,
            recommendations=recommendations,
        )

    def assess_blur(self, img_array: np.ndarray) -> BlurReport:
        """使用拉普拉斯方差法评估影像模糊度"""
        if not HAS_CV2 and not self._can_compute_laplacian(img_array):
            return BlurReport(
                laplacian_variance=0.0,
                blur_score=0.0,
                is_blurry=True,
                blur_level="unknown",
            )

        # 转灰度
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2).astype(np.uint8)
        else:
            gray = img_array.astype(np.uint8)

        # 计算拉普拉斯方差
        if HAS_CV2:
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = float(laplacian.var())
        else:
            variance = self._compute_laplacian_variance_numpy(gray)

        # 归一化为0-100分数
        score = min(100.0, variance / self.BLUR_THRESHOLD_SHARP * 100.0)

        # 分级
        if variance >= self.BLUR_THRESHOLD_SHARP:
            level = "sharp"
        elif variance >= self.BLUR_THRESHOLD_SLIGHT:
            level = "slight"
        elif variance >= self.BLUR_THRESHOLD_MODERATE:
            level = "moderate"
        else:
            level = "severe"

        return BlurReport(
            laplacian_variance=variance,
            blur_score=round(score, 1),
            is_blurry=level != "sharp",
            blur_level=level,
        )

    def _compute_laplacian_variance_numpy(self, gray: np.ndarray) -> float:
        """使用NumPy计算拉普拉斯方差（无OpenCV后备方案）"""
        # 3x3拉普拉斯核
        kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
        h, w = gray.shape
        padded = np.pad(gray.astype(np.float64), 1, mode="reflect")
        result = np.zeros_like(gray, dtype=np.float64)

        for i in range(h):
            for j in range(w):
                patch = padded[i:i+3, j:j+3]
                result[i, j] = np.sum(patch * kernel)

        return float(np.var(result))

    def _can_compute_laplacian(self, img_array: np.ndarray) -> bool:
        """判断是否有足够能力计算拉普拉斯"""
        return img_array is not None and img_array.size > 0

    def assess_exposure(self, img_array: np.ndarray) -> ExposureReport:
        """基于直方图分析评估影像曝光"""
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array.astype(np.float64)

        total_pixels = gray.size
        mean_brightness = float(np.mean(gray))

        over_mask = gray > self.EXPOSURE_OVER_THRESHOLD
        under_mask = gray < self.EXPOSURE_UNDER_THRESHOLD

        over_ratio = float(np.sum(over_mask)) / total_pixels
        under_ratio = float(np.sum(under_mask)) / total_pixels

        # 曝光分数：以128为最优点，越偏离越低
        brightness_deviation = abs(mean_brightness - 128.0) / 128.0
        over_penalty = max(0.0, (over_ratio - self.EXPOSURE_OVER_RATIO_MAX) * 10)
        under_penalty = max(0.0, (under_ratio - self.EXPOSURE_UNDER_RATIO_MAX) * 10)
        score = max(0.0, 100.0 * (1.0 - brightness_deviation - over_penalty - under_penalty))

        # 分级
        if score >= 80:
            level = "good"
        elif mean_brightness > 200:
            level = "over"
        elif mean_brightness < 40:
            level = "under"
        elif mean_brightness > 160:
            level = "slight_over"
        else:
            level = "slight_under"

        return ExposureReport(
            mean_brightness=round(mean_brightness, 1),
            overexposed_ratio=round(over_ratio, 4),
            underexposed_ratio=round(under_ratio, 4),
            exposure_score=round(score, 1),
            exposure_level=level,
        )

    def assess_tilt(self, imu: IMUInfo) -> TiltReport:
        """基于IMU姿态角评估影像倾斜程度"""
        pitch = imu.pitch if imu.pitch is not None else 0.0
        roll = imu.roll if imu.roll is not None else 0.0

        # 综合倾斜角：Pitch和Roll的合成角（与竖直方向的夹角）
        tilt_angle = float(np.sqrt(pitch**2 + roll**2))

        # 分级
        if tilt_angle <= self.TILT_NADIR_MAX:
            level = "nadir"
            is_nadir = True
        elif tilt_angle <= self.TILT_SLIGHT_MAX:
            level = "slight"
            is_nadir = False
        elif tilt_angle <= self.TILT_MODERATE_MAX:
            level = "moderate"
            is_nadir = False
        else:
            level = "oblique"
            is_nadir = False

        return TiltReport(
            tilt_angle=round(tilt_angle, 2),
            pitch=round(pitch, 2) if imu.pitch is not None else None,
            roll=round(roll, 2) if imu.roll is not None else None,
            is_nadir=is_nadir,
            tilt_level=level,
        )

    def _compute_overall(
        self,
        blur: BlurReport,
        exposure: ExposureReport,
        tilt: TiltReport,
    ) -> Tuple[float, str, list]:
        """计算综合质量分数"""
        # 权重：模糊度40%，曝光30%，倾斜30%
        weights = {"blur": 0.40, "exposure": 0.30, "tilt": 0.30}

        # 倾斜分数
        if tilt.tilt_level == "nadir":
            tilt_score = 100.0
        elif tilt.tilt_level == "slight":
            tilt_score = 80.0
        elif tilt.tilt_level == "moderate":
            tilt_score = 50.0
        else:
            tilt_score = 20.0

        overall = (
            weights["blur"] * blur.blur_score
            + weights["exposure"] * exposure.exposure_score
            + weights["tilt"] * tilt_score
        )
        overall = round(overall, 1)

        # 分级
        if overall >= 85:
            level = "excellent"
        elif overall >= 70:
            level = "good"
        elif overall >= 50:
            level = "acceptable"
        elif overall >= 30:
            level = "poor"
        else:
            level = "rejected"

        # 生成改进建议
        recommendations = []
        if blur.is_blurry:
            recommendations.append("影像存在模糊，建议检查对焦和快门速度")
        if exposure.exposure_level in ("over", "under"):
            recommendations.append(f"曝光{'过度' if exposure.exposure_level == 'over' else '不足'}，建议调整曝光参数")
        if not tilt.is_nadir:
            recommendations.append(f"影像倾斜角为{tilt.tilt_angle}°，建议尽量保持正射拍摄")

        return overall, level, recommendations

    def _load_image_array(self, path: str) -> Optional[np.ndarray]:
        """加载影像为numpy数组"""
        if not Path(path).exists():
            return None

        if HAS_CV2:
            img = cv2.imread(path)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if HAS_PIL:
            try:
                img = Image.open(path)
                return np.array(img)
            except Exception:
                pass

        return None

    def _empty_report(self, path: str) -> QualityReport:
        """返回空质量报告"""
        empty_blur = BlurReport(0.0, 0.0, True, "unknown")
        empty_exp = ExposureReport(0.0, 0.0, 0.0, 0.0, "unknown")
        empty_tilt = TiltReport(0.0)
        return QualityReport(
            file_path=path,
            blur=empty_blur,
            exposure=empty_exp,
            tilt=empty_tilt,
            overall_score=0.0,
            quality_level="rejected",
            recommendations=["无法读取影像文件"],
        )

    def batch_assess(
        self,
        image_paths: list,
        metadata_dict: Optional[Dict[str, AerialImageMetadata]] = None,
    ) -> Dict[str, QualityReport]:
        """批量评估多张影像质量"""
        results = {}
        for path in image_paths:
            meta = (metadata_dict or {}).get(path)
            try:
                results[path] = self.assess_all(path, meta)
            except Exception as e:
                logger.warning(f"评估影像质量失败: {path}, {e}")
                results[path] = self._empty_report(path)
        return results
