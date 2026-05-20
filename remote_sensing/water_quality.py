"""
水质专题反演插件
================
实现5项水质指标的反演计算：
1. 叶绿素a (Chl-a) - 三波段/四波段生物光学模型
2. 悬浮物浓度 (TSM) - 红光/近红外反射率线性或指数模型
3. 浑浊度 (Turbidity) - 波段比值法 (Red/Green)
4. 水体透明度 (SDD) - 基于反射率转换的经验回归模型
5. 有机污染 (COD/BOD) - 多波段光谱特征拟合与水色指数关联分析

所有算法基于多光谱遥感原理，支持常见卫星/无人机多光谱传感器波段配置。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 光谱波段配置
# ---------------------------------------------------------------------------

@dataclass
class SpectralBands:
    """多光谱波段反射率数据

    支持的波段命名约定（波长范围参考Sentinel-2 / Landsat-8）：
    - coastal: 海岸/气溶胶波段 (430-450nm)
    - blue: 蓝波段 (450-520nm)
    - green: 绿波段 (520-600nm)
    - red: 红波段 (630-690nm)
    - red_edge: 红边波段 (690-740nm)
    - nir: 近红外波段 (770-900nm)
    - swir1: 短波红外1 (1550-1750nm)
    - swir2: 短波红外2 (2080-2350nm)
    - thermal: 热红外 (10400-12500nm)
    """
    blue: Optional[np.ndarray] = None
    green: Optional[np.ndarray] = None
    red: Optional[np.ndarray] = None
    red_edge: Optional[np.ndarray] = None
    nir: Optional[np.ndarray] = None
    swir1: Optional[np.ndarray] = None
    swir2: Optional[np.ndarray] = None
    coastal: Optional[np.ndarray] = None
    thermal: Optional[np.ndarray] = None
    # 自定义波段
    extra_bands: Dict[str, np.ndarray] = field(default_factory=dict)

    def get_band(self, name: str) -> Optional[np.ndarray]:
        """获取指定波段数据"""
        if hasattr(self, name):
            return getattr(self, name)
        return self.extra_bands.get(name)


# ---------------------------------------------------------------------------
# 水质反演结果
# ---------------------------------------------------------------------------

@dataclass
class WaterQualityResult:
    """水质指标反演结果"""
    chl_a: Optional[np.ndarray] = None           # 叶绿素a (μg/L)
    tsm: Optional[np.ndarray] = None             # 悬浮物浓度 (mg/L)
    turbidity: Optional[np.ndarray] = None       # 浑浊度 (NTU)
    sdd: Optional[np.ndarray] = None             # 水体透明度 (m)
    cod: Optional[np.ndarray] = None             # 化学需氧量 (mg/L)
    # 不确定性和元数据
    uncertainties: Dict[str, np.ndarray] = field(default_factory=dict)
    water_mask: Optional[np.ndarray] = None      # 水体掩膜
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict_summary(self) -> Dict[str, Any]:
        """生成摘要统计"""
        summary = {}
        for name in ["chl_a", "tsm", "turbidity", "sdd", "cod"]:
            data = getattr(self, name)
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
        units = {
            "chl_a": "μg/L",
            "tsm": "mg/L",
            "turbidity": "NTU",
            "sdd": "m",
            "cod": "mg/L",
        }
        return units.get(indicator, "")


# ---------------------------------------------------------------------------
# 水质反演引擎
# ---------------------------------------------------------------------------

class WaterQualityInverter:
    """水质指标反演引擎

    参考:
    - Gitelson et al. (2008) 三波段叶绿素模型
    - Le et al. (2009) 四波段模型
    - Doxaran et al. (2002) 悬浮物反演
    - 各算法的系数为文献经验值，实际使用需根据当地实测数据率定
    """

    # -------------------------------------------------------------------
    # 1. 叶绿素a (Chl-a)
    # -------------------------------------------------------------------

    def retrieve_chl_a_three_band(
        self,
        bands: SpectralBands,
        a: float = 1.0,
        b: float = 1.0,
    ) -> np.ndarray:
        """三波段叶绿素a反演模型

        公式: Chl-a ∝ [Rrs(λ1)^-1 - Rrs(λ2)^-1] × Rrs(λ3)
        其中 λ1≈670nm(红), λ2≈710nm(红边), λ3≈750nm(近红外)

        Args:
            bands: 多光谱波段数据
            a, b: 经验回归系数 (log10(Chl-a) = a * index + b)

        Returns:
            叶绿素a浓度 (μg/L)
        """
        red = bands.red
        red_edge = bands.red_edge
        nir = bands.nir

        if red is None or nir is None:
            logger.warning("三波段模型需要红波段和近红外波段")
            return np.full_like(red or nir, np.nan)

        # 防止除零
        red_safe = np.where(red > 0.001, red, np.nan)
        nir_safe = np.where(nir > 0.001, nir, np.nan)

        if red_edge is not None:
            re_safe = np.where(red_edge > 0.001, red_edge, np.nan)
            index = (1.0 / red_safe - 1.0 / re_safe) * nir_safe
        else:
            # 无红边波段时降级为二波段比值
            index = nir_safe / red_safe

        # 经验系数（需根据实际数据率定）
        chl_a = np.power(10.0, a * index + b)

        # 限制在合理范围
        chl_a = np.clip(chl_a, 0.1, 500.0)

        return chl_a

    def retrieve_chl_a_four_band(
        self,
        bands: SpectralBands,
        a: float = 25.28,
        b: float = 14.85,
    ) -> np.ndarray:
        """四波段叶绿素a反演模型 (Le et al., 2009)

        公式: Chl-a = a × [Rrs(λ1)^-1 - Rrs(λ2)^-1] / [Rrs(λ3)^-1 - Rrs(λ4)^-1] + b
        适用于高浑浊水体

        Returns:
            叶绿素a浓度 (μg/L)
        """
        blue = bands.blue
        green = bands.green
        red = bands.red
        nir = bands.nir

        if not all(b is not None for b in [blue, green, red, nir]):
            logger.warning("四波段模型需要蓝绿红近红外四个波段")
            return np.full_like(red or nir or np.zeros((1, 1)), np.nan)

        blue_s = np.where(blue > 0.001, blue, np.nan)
        green_s = np.where(green > 0.001, green, np.nan)
        red_s = np.where(red > 0.001, red, np.nan)
        nir_s = np.where(nir > 0.001, nir, np.nan)

        numerator = 1.0 / red_s - 1.0 / nir_s
        denominator = 1.0 / blue_s - 1.0 / green_s

        chl_a = np.full_like(red, np.nan)
        valid = (denominator != 0) & ~np.isnan(denominator)
        chl_a[valid] = a * numerator[valid] / denominator[valid] + b

        chl_a = np.clip(chl_a, 0.1, 500.0)
        return chl_a

    def retrieve_chl_a(
        self,
        bands: SpectralBands,
        method: str = "three_band",
    ) -> np.ndarray:
        """叶绿素a反演统一入口"""
        if method == "four_band":
            return self.retrieve_chl_a_four_band(bands)
        return self.retrieve_chl_a_three_band(bands)

    # -------------------------------------------------------------------
    # 2. 悬浮物浓度 (TSM)
    # -------------------------------------------------------------------

    def retrieve_tsm_linear(
        self,
        bands: SpectralBands,
        a: float = 50.0,
        b: float = -5.0,
    ) -> np.ndarray:
        """悬浮物浓度线性反演模型

        TSM = a × Rrs(red或nir) + b
        适用于中低浓度水体 (Doxaran et al., 2002)
        """
        red = bands.red
        nir = bands.nir

        if red is None and nir is None:
            logger.warning("TSM反演需要红波段或近红外波段")
            return np.full((1, 1), np.nan)

        # 优先使用近红外波段（对高浓度更敏感），否则使用红波段
        reflectance = nir if nir is not None else red

        tsm = a * reflectance + b
        tsm = np.clip(tsm, 0.0, 500.0)

        return tsm

    def retrieve_tsm_exponential(
        self,
        bands: SpectralBands,
        a: float = 100.0,
        b: float = 3.0,
    ) -> np.ndarray:
        """悬浮物浓度指数反演模型

        TSM = a × exp(b × Rrs(nir))
        适用于中高浓度水体
        """
        nir = bands.nir
        red = bands.red

        reflectance = nir if nir is not None else red
        if reflectance is None:
            return np.full((1, 1), np.nan)

        tsm = a * np.exp(b * reflectance)
        tsm = np.clip(tsm, 0.0, 1000.0)

        return tsm

    def retrieve_tsm(
        self,
        bands: SpectralBands,
        method: str = "exponential",
    ) -> np.ndarray:
        """悬浮物浓度反演统一入口"""
        if method == "linear":
            return self.retrieve_tsm_linear(bands)
        return self.retrieve_tsm_exponential(bands)

    # -------------------------------------------------------------------
    # 3. 浑浊度 (Turbidity)
    # -------------------------------------------------------------------

    def retrieve_turbidity(
        self,
        bands: SpectralBands,
        a: float = 8.93,
        b: float = -6.39,
    ) -> np.ndarray:
        """浑浊度反演 - 波段比值法 (Red/Green)

        Turbidity = a × (Rrs_red / Rrs_green) + b
        参考: Nechad et al. (2009)
        """
        red = bands.red
        green = bands.green

        if red is None or green is None:
            logger.warning("浑浊度反演需要红波段和绿波段")
            return np.full_like(red or green or np.zeros((1, 1)), np.nan)

        green_safe = np.where(green > 0.001, green, np.nan)
        ratio = red / green_safe

        turbidity = a * ratio + b
        turbidity = np.clip(turbidity, 0.0, 1000.0)

        return turbidity

    # -------------------------------------------------------------------
    # 4. 水体透明度 (SDD)
    # -------------------------------------------------------------------

    def retrieve_sdd(
        self,
        bands: SpectralBands,
        a: float = 2.5,
        b: float = 0.3,
    ) -> np.ndarray:
        """水体透明度(SDD/Secchi Disk Depth)反演

        基于反射率转换的经验回归模型:
        SDD = a × (Rrs_blue / Rrs_red)^b
        或使用红蓝波段比值的对数线性模型

        Returns:
            透明度 (m)
        """
        blue = bands.blue
        red = bands.red

        if blue is None or red is None:
            logger.warning("SDD反演需要蓝波段和红波段")
            return np.full_like(blue or red or np.zeros((1, 1)), np.nan)

        red_safe = np.where(red > 0.001, red, np.nan)
        ratio = blue / red_safe

        sdd = a * np.power(ratio, b)
        sdd = np.clip(sdd, 0.0, 30.0)  # 透明度一般不超过30m

        return sdd

    # -------------------------------------------------------------------
    # 5. 有机污染 (COD/BOD)
    # -------------------------------------------------------------------

    def retrieve_cod(
        self,
        bands: SpectralBands,
        chl_a: Optional[np.ndarray] = None,
        tsm: Optional[np.ndarray] = None,
        a: float = 1.5,
        b: float = 0.8,
        c: float = 10.0,
    ) -> np.ndarray:
        """化学需氧量(COD)反演

        基于多波段光谱特征拟合与水色指数关联分析:
        COD = a × Chl-a + b × TSM + c × (Rrs_nir / Rrs_red)

        当无Chl-a和TSM反演结果时，使用简化的波段比值法。
        """
        red = bands.red
        nir = bands.nir

        if chl_a is not None and tsm is not None:
            # 完整模型
            cod = a * chl_a + b * tsm
        elif red is not None and nir is not None:
            # 简化模型 - 基于水色指数
            red_safe = np.where(red > 0.001, red, np.nan)
            nir_red_ratio = nir / red_safe
            cod = c * nir_red_ratio
        else:
            return np.full((1, 1), np.nan)

        # 加入蓝绿波段比值的修正
        if bands.blue is not None and bands.green is not None:
            green_safe = np.where(bands.green > 0.001, bands.green, np.nan)
            color_index = bands.blue / green_safe
            cod = cod + 2.0 * (color_index - 1.0)

        cod = np.clip(cod, 0.0, 500.0)
        return cod

    # -------------------------------------------------------------------
    # 水体掩膜
    # -------------------------------------------------------------------

    def compute_water_mask(
        self,
        bands: SpectralBands,
        method: str = "ndwi",
    ) -> np.ndarray:
        """水体提取掩膜

        支持两种方法:
        - ndwi: (绿 - 近红外) / (绿 + 近红外) > 阈值
        - mndwi: (绿 - 中红外) / (绿 + 中红外) > 阈值
        """
        if method == "mndwi" and bands.swir1 is not None:
            green = bands.green
            swir = bands.swir1

            if green is not None:
                ndwi = (green - swir) / (green + swir + 1e-10)
                return ndwi > 0.0

        # NDWI: (Green - NIR) / (Green + NIR)
        green = bands.green
        nir = bands.nir

        if green is not None and nir is not None:
            ndwi = (green - nir) / (green + nir + 1e-10)
            return ndwi > 0.0

        logger.warning("无法计算水体掩膜，缺少必要波段")
        # 使用全True掩膜，但需要避免 "truth value of array" 错误
        if green is not None:
            return np.ones_like(green, dtype=bool)
        if nir is not None:
            return np.ones_like(nir, dtype=bool)
        return np.ones((1, 1), dtype=bool)

    # -------------------------------------------------------------------
    # 综合反演
    # -------------------------------------------------------------------

    def retrieve_all(
        self,
        bands: SpectralBands,
        chl_method: str = "three_band",
        tsm_method: str = "exponential",
    ) -> WaterQualityResult:
        """一键反演所有5项水质指标"""
        # 水体掩膜
        water_mask = self.compute_water_mask(bands)

        # 叶绿素a
        chl_a = self.retrieve_chl_a(bands, chl_method)

        # 悬浮物
        tsm = self.retrieve_tsm(bands, tsm_method)

        # 浑浊度
        turbidity = self.retrieve_turbidity(bands)

        # 透明度
        sdd = self.retrieve_sdd(bands)

        # COD
        cod = self.retrieve_cod(bands, chl_a, tsm)

        # 不确定性估计（简化：基于反射率的信噪比）
        uncertainties = self._estimate_uncertainties(bands, chl_a, tsm, turbidity, sdd, cod)

        return WaterQualityResult(
            chl_a=chl_a,
            tsm=tsm,
            turbidity=turbidity,
            sdd=sdd,
            cod=cod,
            uncertainties=uncertainties,
            water_mask=water_mask,
            metadata={
                "chl_method": chl_method,
                "tsm_method": tsm_method,
                "sensor": "multispectral",
            },
        )

    def _estimate_uncertainties(
        self,
        bands: SpectralBands,
        chl_a: np.ndarray,
        tsm: np.ndarray,
        turbidity: np.ndarray,
        sdd: np.ndarray,
        cod: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """估计各指标的不确定性（简化模型）"""
        unc = {}

        # 基于近红外噪声水平估计相对不确定性
        if bands.nir is not None:
            noise_level = np.nanstd(bands.nir) * 0.1  # 假设10%噪声

            if chl_a is not None and chl_a.size > 0:
                unc["chl_a"] = np.full_like(chl_a, noise_level * 5.0)  # μg/L

            if tsm is not None and tsm.size > 0:
                unc["tsm"] = np.full_like(tsm, noise_level * 10.0)  # mg/L

            if turbidity is not None and turbidity.size > 0:
                unc["turbidity"] = np.full_like(turbidity, noise_level * 2.0)  # NTU

            if sdd is not None and sdd.size > 0:
                unc["sdd"] = np.full_like(sdd, noise_level * 0.5)  # m

            if cod is not None and cod.size > 0:
                unc["cod"] = np.full_like(cod, noise_level * 15.0)  # mg/L

        return unc
