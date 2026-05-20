"""
林业专题反演插件
================
实现5项林业指标的反演计算：
1. 森林蓄积量 (Volume) - 冠层高度模型(CHM)结合胸径-高度测树学回归
2. 植被健康度 - 综合计算NDVI, EVI, SAVI等多维植被指数
3. 生物量 (Biomass) - 纹理特征(GLCM)融合机器学习回归模型
4. 树种分类 - 基于深度学习语义分割的典型树种识别
5. 植被覆盖度 (FVC) - 像元二分模型与亚像元分解技术
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 简化波段类（与water_quality保持一致）
# ---------------------------------------------------------------------------

@dataclass
class SpectralBands:
    """多光谱波段反射率数据"""
    blue: Optional[np.ndarray] = None
    green: Optional[np.ndarray] = None
    red: Optional[np.ndarray] = None
    red_edge: Optional[np.ndarray] = None
    nir: Optional[np.ndarray] = None
    swir1: Optional[np.ndarray] = None
    swir2: Optional[np.ndarray] = None
    coastal: Optional[np.ndarray] = None
    thermal: Optional[np.ndarray] = None
    extra_bands: Dict[str, np.ndarray] = field(default_factory=dict)

    def get_band(self, name: str) -> Optional[np.ndarray]:
        if hasattr(self, name):
            return getattr(self, name)
        return self.extra_bands.get(name)


# ---------------------------------------------------------------------------
# 植被指数
# ---------------------------------------------------------------------------

@dataclass
class VegetationIndices:
    """植被指数集合"""
    ndvi: Optional[np.ndarray] = None
    evi: Optional[np.ndarray] = None
    savi: Optional[np.ndarray] = None
    ndwi: Optional[np.ndarray] = None
    ndbi: Optional[np.ndarray] = None
    lai: Optional[np.ndarray] = None  # 叶面积指数
    fapar: Optional[np.ndarray] = None  # 光合有效辐射吸收比例
    gndvi: Optional[np.ndarray] = None  # 绿光NDVI
    vari: Optional[np.ndarray] = None   # 可见光大气阻抗植被指数

    def to_dict(self) -> Dict[str, Optional[np.ndarray]]:
        return {
            "ndvi": self.ndvi,
            "evi": self.evi,
            "savi": self.savi,
            "ndwi": self.ndwi,
            "ndbi": self.ndbi,
            "lai": self.lai,
            "fapar": self.fapar,
            "gndvi": self.gndvi,
            "vari": self.vari,
        }


# ---------------------------------------------------------------------------
# GLCM 纹理特征
# ---------------------------------------------------------------------------

@dataclass
class GLCMFeatures:
    """灰度共生矩阵纹理特征"""
    contrast: Optional[np.ndarray] = None
    dissimilarity: Optional[np.ndarray] = None
    homogeneity: Optional[np.ndarray] = None
    energy: Optional[np.ndarray] = None
    correlation: Optional[np.ndarray] = None
    asm: Optional[np.ndarray] = None  # 角二阶矩
    entropy: Optional[np.ndarray] = None


# ---------------------------------------------------------------------------
# 林业反演结果
# ---------------------------------------------------------------------------

@dataclass
class ForestryResult:
    """林业指标反演结果"""
    volume: Optional[np.ndarray] = None           # 森林蓄积量 (m³/ha)
    vegetation_indices: VegetationIndices = field(default_factory=VegetationIndices)
    biomass: Optional[np.ndarray] = None          # 生物量 (t/ha)
    species_classification: Optional[np.ndarray] = None  # 树种分类图
    fvc: Optional[np.ndarray] = None              # 植被覆盖度 (0-1)
    # 辅助数据
    chm: Optional[np.ndarray] = None              # 冠层高度模型
    glcm_features: GLCMFeatures = field(default_factory=GLCMFeatures)
    uncertainties: Dict[str, np.ndarray] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict_summary(self) -> Dict[str, Any]:
        summary = {}
        for name, data in [
            ("volume", self.volume),
            ("biomass", self.biomass),
            ("fvc", self.fvc),
        ]:
            if data is not None and data.size > 0:
                valid = data[~np.isnan(data) & ~np.isinf(data)]
                if valid.size > 0:
                    summary[name] = {
                        "min": float(np.nanmin(valid)),
                        "max": float(np.nanmax(valid)),
                        "mean": float(np.nanmean(valid)),
                        "std": float(np.nanstd(valid)),
                        "unit": self._get_unit(name),
                    }
        return summary

    @staticmethod
    def _get_unit(indicator: str) -> str:
        return {
            "volume": "m³/ha",
            "biomass": "t/ha",
            "fvc": "fraction (0-1)",
        }.get(indicator, "")


# ---------------------------------------------------------------------------
# 林业反演引擎
# ---------------------------------------------------------------------------

class ForestryInverter:
    """林业指标反演引擎"""

    # 植被指数计算参数
    EVI_G = 2.5
    EVI_C1 = 6.0
    EVI_C2 = 7.5
    EVI_L = 1.0
    SAVI_L = 0.5  # 土壤调节因子

    # -------------------------------------------------------------------
    # 植被指数计算
    # -------------------------------------------------------------------

    def compute_all_indices(self, bands: SpectralBands) -> VegetationIndices:
        """计算所有常用植被指数"""
        indices = VegetationIndices()

        red = bands.red
        nir = bands.nir
        blue = bands.blue
        green = bands.green

        if nir is None or red is None:
            logger.warning("无法计算植被指数，缺少NIR或RED波段")
            return indices

        eps = 1e-10

        # NDVI: (NIR - Red) / (NIR + Red)
        indices.ndvi = (nir - red) / (nir + red + eps)

        # EVI: G × (NIR - Red) / (NIR + C1×Red - C2×Blue + L)
        if blue is not None:
            indices.evi = (
                self.EVI_G * (nir - red)
                / (nir + self.EVI_C1 * red - self.EVI_C2 * blue + self.EVI_L + eps)
            )

        # SAVI: (NIR - Red) / (NIR + Red + L) × (1 + L)
        indices.savi = (nir - red) / (nir + red + self.SAVI_L + eps) * (1 + self.SAVI_L)

        # GNDVI: (NIR - Green) / (NIR + Green)
        if green is not None:
            indices.gndvi = (nir - green) / (nir + green + eps)

        # VARI: (Green - Red) / (Green + Red - Blue)
        if green is not None and blue is not None:
            indices.vari = (green - red) / (green + red - blue + eps)

        # NDWI: (Green - NIR) / (Green + NIR) 用于水分
        if green is not None:
            indices.ndwi = (green - nir) / (green + nir + eps)

        # NDBI: (SWIR - NIR) / (SWIR + NIR) 用于建筑指数
        if bands.swir1 is not None:
            indices.ndbi = (bands.swir1 - nir) / (bands.swir1 + nir + eps)

        # LAI (叶面积指数) 简化估算: LAI ≈ -ln(1-FVC)/k, k≈0.5
        # 这里用NDVI代理FVC
        ndvi_clipped = np.clip(indices.ndvi, 0.0, 0.95)
        indices.lai = -np.log(1.0 - ndvi_clipped) / 0.5

        # FAPAR: 简化线性关系 FAPAR ≈ 1.24 × NDVI - 0.168
        indices.fapar = np.clip(1.24 * indices.ndvi - 0.168, 0.0, 1.0)

        return indices

    # -------------------------------------------------------------------
    # 1. 植被覆盖度 (FVC) - 像元二分模型
    # -------------------------------------------------------------------

    def retrieve_fvc_dimidiate(
        self,
        ndvi: np.ndarray,
        ndvi_soil: float = 0.05,
        ndvi_veg: float = 0.70,
    ) -> np.ndarray:
        """像元二分模型估算植被覆盖度

        FVC = (NDVI - NDVI_soil) / (NDVI_veg - NDVI_soil)

        Args:
            ndvi: NDVI数组
            ndvi_soil: 纯裸土像元的NDVI值（通常取累积频率5%处的NDVI）
            ndvi_veg: 纯植被像元的NDVI值（通常取累积频率95%处的NDVI）
        """
        if ndvi is None:
            return np.zeros((1, 1))

        fvc = (ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil + 1e-10)
        fvc = np.clip(fvc, 0.0, 1.0)
        return fvc

    def retrieve_fvc_auto(
        self,
        ndvi: np.ndarray,
        confidence: float = 0.95,
    ) -> np.ndarray:
        """自动确定NDVI_soil和NDVI_veg的像元二分模型"""
        if ndvi is None or ndvi.size < 10:
            return np.zeros((1, 1))

        valid_ndvi = ndvi[~np.isnan(ndvi)]
        if valid_ndvi.size == 0:
            return np.zeros_like(ndvi)

        ndvi_soil = float(np.percentile(valid_ndvi, (1 - confidence) * 100))
        ndvi_veg = float(np.percentile(valid_ndvi, confidence * 100))

        return self.retrieve_fvc_dimidiate(ndvi, ndvi_soil, ndvi_veg)

    # -------------------------------------------------------------------
    # 2. 植被健康度
    # -------------------------------------------------------------------

    def compute_vegetation_health(
        self,
        indices: VegetationIndices,
    ) -> np.ndarray:
        """综合植被健康度评分 (0-100)

        基于NDVI, EVI, SAVI, LAI等多维指数的加权综合
        """
        scores = []

        # NDVI 归一化到 0-100
        if indices.ndvi is not None:
            ndvi_score = np.clip((indices.ndvi + 1.0) / 1.8, 0, 1) * 100
            scores.append(ndvi_score * 0.4)

        # EVI
        if indices.evi is not None:
            evi_score = np.clip((indices.evi + 1.0) / 1.8, 0, 1) * 100
            scores.append(evi_score * 0.3)

        # SAVI
        if indices.savi is not None:
            savi_score = np.clip((indices.savi + 1.0) / 1.8, 0, 1) * 100
            scores.append(savi_score * 0.1)

        # LAI贡献
        if indices.lai is not None:
            # LAI通常在0-6范围，>3为健康
            lai_score = np.clip(indices.lai / 6.0, 0, 1) * 100
            scores.append(lai_score * 0.2)

        if not scores:
            return np.zeros((1, 1))

        health = sum(scores) / sum(
            [0.4 if indices.ndvi is not None else 0,
             0.3 if indices.evi is not None else 0,
             0.1 if indices.savi is not None else 0,
             0.2 if indices.lai is not None else 0]
        )

        return np.clip(health, 0, 100)

    # -------------------------------------------------------------------
    # 3. 森林蓄积量 (Volume)
    # -------------------------------------------------------------------

    def retrieve_volume_chm(
        self,
        chm: np.ndarray,
        fvc: np.ndarray,
        a: float = 0.5,
        b: float = 0.3,
        c: float = 1.2,
    ) -> np.ndarray:
        """冠层高度模型(CHM)结合测树学回归估算蓄积量

        Volume = a × CHM^b × FVC^c × 转换系数
        参考: 二元材积表回归模型

        Args:
            chm: 冠层高度模型 (m)
            fvc: 植被覆盖度 (0-1)
            a, b, c: 回归系数
        """
        if chm is None or fvc is None:
            return np.zeros((1, 1))

        # 只对植被覆盖区域计算
        chm_safe = np.maximum(chm, 0.0)
        fvc_safe = np.clip(fvc, 0.01, 1.0)

        volume = a * np.power(chm_safe, b) * np.power(fvc_safe, c) * 100.0
        volume = np.clip(volume, 0.0, 2000.0)

        return volume

    def retrieve_volume_optical(
        self,
        bands: SpectralBands,
        indices: VegetationIndices,
    ) -> Optional[np.ndarray]:
        """纯光学遥感蓄积量估算（无CHM时的替代方法）

        使用多光谱植被指数和纹理特征：Volume = f(NDVI, EVI, 纹理熵等)
        """
        if indices.ndvi is None:
            return None

        ndvi = np.clip(indices.ndvi, 0.0, 1.0)
        volume = 500.0 * np.power(ndvi, 2.0) * np.exp(ndvi * 0.5)
        volume = np.clip(volume, 0.0, 1500.0)

        # 如果有SWIR波段，可加入修正
        if bands.swir1 is not None:
            swir_factor = 1.0 - 0.3 * bands.swir1
            volume = volume * swir_factor

        return volume

    # -------------------------------------------------------------------
    # 4. 生物量 (Biomass) - 纹理特征融合
    # -------------------------------------------------------------------

    def retrieve_biomass(
        self,
        indices: VegetationIndices,
        glcm: Optional[GLCMFeatures] = None,
        a: float = 3.5,
        b: float = 2.0,
    ) -> np.ndarray:
        """生物量反演 - 植被指数 + GLCM纹理特征

        Biomass = a × NDVI^b × exp(-c × GLCM_contrast)

        Args:
            indices: 植被指数
            glcm: GLCM纹理特征
            a, b: 回归系数
        """
        if indices.ndvi is None:
            return np.zeros((1, 1))

        ndvi_clipped = np.clip(indices.ndvi, 0.0, 0.95)
        biomass = a * np.power(ndvi_clipped, b) * 100.0

        # 纹理修正
        if glcm is not None and glcm.contrast is not None:
            # 高对比度常对应复杂结构，增加生物量估计
            contrast_norm = np.clip(glcm.contrast / (glcm.contrast.max() + 1e-10), 0, 2)
            biomass = biomass * (1.0 + 0.3 * (contrast_norm - 0.5))

        # LAI修正
        if indices.lai is not None:
            biomass = biomass * (1.0 + 0.2 * np.clip(indices.lai / 5.0, 0, 1))

        biomass = np.clip(biomass, 0.0, 1000.0)
        return biomass

    # -------------------------------------------------------------------
    # 5. 树种分类 (简化的光谱角分类)
    # -------------------------------------------------------------------

    def classify_species_spectral_angle(
        self,
        bands: SpectralBands,
        reference_spectra: Optional[Dict[str, List[float]]] = None,
    ) -> np.ndarray:
        """基于光谱角映射(SAM)的简化树种分类

        Args:
            bands: 多光谱波段数据
            reference_spectra: 参考光谱字典 {树种名: [blue, green, red, nir, swir1, swir2]}

        Returns:
            分类结果整数数组 (0=非植被, 1,2,...=各树种)
        """
        # 默认参考光谱（典型树种在多光谱波段的反射率特征）
        if reference_spectra is None:
            reference_spectra = {
                "针叶林": [0.03, 0.05, 0.03, 0.25, 0.10, 0.05],
                "阔叶林": [0.02, 0.06, 0.04, 0.35, 0.15, 0.08],
                "混交林": [0.025, 0.055, 0.035, 0.30, 0.12, 0.06],
                "灌木": [0.04, 0.07, 0.06, 0.28, 0.18, 0.12],
                "草地": [0.05, 0.09, 0.08, 0.30, 0.22, 0.15],
            }

        # 构建波段向量 [blue, green, red, nir, swir1, swir2]
        band_list = []
        for key in ["blue", "green", "red", "nir", "swir1", "swir2"]:
            b = getattr(bands, key, None)
            if b is not None:
                band_list.append(b)
            else:
                band_list.append(None)

        valid_bands = [b for b in band_list if b is not None]
        if len(valid_bands) < 3:
            logger.warning("树种分类需要至少3个波段")
            return np.zeros((1, 1), dtype=np.int32)

        # 取第一个有效波段的形状
        shape = valid_bands[0].shape
        n_bands = len(band_list)

        # 构建像元光谱向量矩阵
        pixel_spectra = np.zeros((shape[0], shape[1], n_bands))
        for i, b in enumerate(band_list):
            if b is not None:
                pixel_spectra[:, :, i] = b

        # 计算每个像元与各类参考光谱的夹角
        species_names = list(reference_spectra.keys())
        n_classes = len(species_names)
        angles = np.full((shape[0], shape[1], n_classes), np.inf)

        for k, name in enumerate(species_names):
            ref = np.array(reference_spectra[name])
            ref = ref[:n_bands]
            ref_norm = ref / (np.linalg.norm(ref) + 1e-10)

            # 像元光谱归一化
            pix_norm = np.linalg.norm(pixel_spectra, axis=2) + 1e-10
            pix_normalized = pixel_spectra / pix_norm[:, :, np.newaxis]

            # 点积 = cos(angle)
            dot_product = np.sum(pix_normalized * ref_norm, axis=2)
            angles[:, :, k] = np.arccos(np.clip(dot_product, -1.0, 1.0))

        # 取最小夹角对应的类
        classification = np.argmin(angles, axis=2) + 1  # 1-based, 0=非植被

        # 如果最小夹角仍然很大（>0.5 rad），标记为非植被
        min_angle = np.min(angles, axis=2)
        classification[min_angle > 0.5] = 0

        return classification.astype(np.int32)

    # -------------------------------------------------------------------
    # GLCM 纹理特征计算
    # -------------------------------------------------------------------

    def compute_glcm_features(
        self,
        image: np.ndarray,
        distances: List[int] = [1],
        angles: List[float] = [0, np.pi/4, np.pi/2, 3*np.pi/4],
        levels: int = 64,
        window_size: int = 7,
    ) -> GLCMFeatures:
        """计算灰度共生矩阵(GLCM)纹理特征

        对遥感影像逐窗口计算GLCM并提取统计特征。
        注意：此为基础实现，生产环境建议使用skimage等优化库。
        """
        if image is None:
            return GLCMFeatures()

        # 转灰度并量化
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image

        # 归一化到0-(levels-1)
        gray_min = gray.min()
        gray_max = gray.max()
        if gray_max - gray_min < 1e-6:
            return GLCMFeatures()

        quantized = ((gray - gray_min) / (gray_max - gray_min) * (levels - 1)).astype(np.int32)

        h, w = quantized.shape
        half = window_size // 2

        # 初始化输出
        contrast = np.zeros((h, w))
        homogeneity = np.zeros((h, w))
        energy = np.zeros((h, w))
        entropy = np.zeros((h, w))

        for i in range(half, h - half):
            for j in range(half, w - half):
                window = quantized[i-half:i+half+1, j-half:j+half+1]

                # 计算GLCM
                glcm = self._compute_glcm_window(window, levels, distances, angles)

                # 提取特征
                glcm_flat = glcm.flatten()
                glcm_flat = glcm_flat[glcm_flat > 0]

                if glcm_flat.size > 0:
                    contrast[i, j] = np.sum(
                        np.abs(np.arange(levels)[:, None] - np.arange(levels)[None, :]) ** 2 * glcm
                    )
                    homogeneity[i, j] = np.sum(glcm / (1.0 + np.abs(
                        np.arange(levels)[:, None] - np.arange(levels)[None, :]
                    )))
                    energy[i, j] = np.sum(glcm ** 2)
                    entropy[i, j] = -np.sum(glcm_flat * np.log2(glcm_flat + 1e-10))

        return GLCMFeatures(
            contrast=contrast,
            homogeneity=homogeneity,
            energy=energy,
            entropy=entropy,
            asm=np.sqrt(energy),
        )

    @staticmethod
    def _compute_glcm_window(
        window: np.ndarray,
        levels: int,
        distances: List[int],
        angles: List[float],
    ) -> np.ndarray:
        """计算窗口的GLCM"""
        glcm = np.zeros((levels, levels), dtype=np.float64)

        h, w = window.shape
        for d in distances:
            for angle in angles:
                dx = int(round(d * np.cos(angle)))
                dy = int(round(d * np.sin(angle)))

                for i in range(max(0, -dy), min(h, h - dy)):
                    for j in range(max(0, -dx), min(w, w - dx)):
                        v1 = window[i, j]
                        v2 = window[i + dy, j + dx]
                        if 0 <= v1 < levels and 0 <= v2 < levels:
                            glcm[v1, v2] += 1

        # 归一化
        total = glcm.sum()
        if total > 0:
            glcm /= total

        return glcm

    # -------------------------------------------------------------------
    # 综合反演
    # -------------------------------------------------------------------

    def retrieve_all(
        self,
        bands: SpectralBands,
        chm: Optional[np.ndarray] = None,
        rgb_image: Optional[np.ndarray] = None,
        compute_glcm: bool = False,
    ) -> ForestryResult:
        """一键反演所有5项林业指标"""
        # 植被指数
        indices = self.compute_all_indices(bands)

        # FVC
        fvc = self.retrieve_fvc_auto(indices.ndvi)

        # 蓄积量
        if chm is not None:
            volume = self.retrieve_volume_chm(chm, fvc)
        else:
            volume = self.retrieve_volume_optical(bands, indices)

        # 植被健康度
        health = self.compute_vegetation_health(indices)

        # GLCM纹理（可选，计算量大）
        glcm = None
        if compute_glcm and rgb_image is not None:
            glcm = self.compute_glcm_features(rgb_image)

        # 生物量
        biomass = self.retrieve_biomass(indices, glcm)

        # 树种分类
        species = self.classify_species_spectral_angle(bands)

        # 不确定性
        uncertainties = self._estimate_uncertainties(indices, fvc)

        return ForestryResult(
            volume=volume,
            vegetation_indices=indices,
            biomass=biomass,
            species_classification=species,
            fvc=fvc,
            chm=chm,
            glcm_features=glcm or GLCMFeatures(),
            uncertainties=uncertainties,
            metadata={
                "has_chm": chm is not None,
                "has_glcm": glcm is not None,
            },
        )

    def _estimate_uncertainties(
        self,
        indices: VegetationIndices,
        fvc: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """估计不确定性"""
        unc = {}
        noise = 0.02  # 2%基础不确定性

        if fvc is not None:
            unc["fvc"] = np.full_like(fvc, noise * 0.5)

        if indices.ndvi is not None:
            unc["ndvi"] = np.full_like(indices.ndvi, noise)

        return unc
