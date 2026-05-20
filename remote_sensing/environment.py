"""
环境/土壤专题反演插件
=====================
实现4项环境/土壤指标的反演计算：
1. 土壤含水率 - 基于热红外指数或短波红外(SWIR)的水分亏缺指数
2. 土壤重金属胁迫 - 监测植被红边位置(Red-edge Position)的特征偏移
3. 地表温度(LST) - 基于单窗算法或劈窗算法的热红外反演
4. 地表径流系数 - 结合土地利用分类(LULC)与SCS-CN模型估算
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 波段类（保持一致性）
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
# 反演结果
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentResult:
    """环境指标反演结果"""
    soil_moisture: Optional[np.ndarray] = None    # 土壤含水率 (0-1 或 %)
    heavy_metal_stress: Optional[np.ndarray] = None  # 重金属胁迫指数
    lst: Optional[np.ndarray] = None              # 地表温度 (K 或 °C)
    runoff_coefficient: Optional[np.ndarray] = None  # 地表径流系数 (0-1)
    # 附加
    red_edge_position: Optional[np.ndarray] = None  # 红边位置 (nm)
    uncertainties: Dict[str, np.ndarray] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict_summary(self) -> Dict[str, Any]:
        summary = {}
        for name in ["soil_moisture", "heavy_metal_stress", "lst", "runoff_coefficient"]:
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
        return {
            "soil_moisture": "fraction (0-1)",
            "heavy_metal_stress": "index",
            "lst": "°C",
            "runoff_coefficient": "fraction (0-1)",
        }.get(indicator, "")


# ---------------------------------------------------------------------------
# 环境反演引擎
# ---------------------------------------------------------------------------

class EnvironmentInverter:
    """环境/土壤指标反演引擎"""

    # -------------------------------------------------------------------
    # 1. 土壤含水率
    # -------------------------------------------------------------------

    def retrieve_soil_moisture_swir(
        self,
        bands: SpectralBands,
    ) -> np.ndarray:
        """基于SWIR的土壤水分亏缺指数

        方法1: 使用短波红外波段的水分吸收特征
        SWIR水分指数 = (SWIR1 - SWIR2) / (SWIR1 + SWIR2)
        或使用归一化差异水分指数 NDMI = (NIR - SWIR1) / (NIR + SWIR1)

        Gao (1996) NDWI/NDMI 方法
        """
        nir = bands.nir
        swir1 = bands.swir1
        swir2 = bands.swir2

        if swir1 is None:
            logger.warning("土壤含水率反演需要SWIR波段")
            return np.zeros((1, 1))

        eps = 1e-10

        if nir is not None:
            # NDMI (归一化差异水分指数)
            ndmi = (nir - swir1) / (nir + swir1 + eps)
            # 线性映射到含水率 (0-1)，NDMI范围约-1到1
            soil_moisture = np.clip((ndmi + 1.0) / 2.0, 0.0, 1.0)
        elif swir2 is not None:
            # SWIR差异指数
            swir_index = (swir1 - swir2) / (swir1 + swir2 + eps)
            soil_moisture = np.clip(swir_index, 0.0, 1.0)
        else:
            soil_moisture = 1.0 - swir1 / (swir1.max() + eps)

        return soil_moisture

    def retrieve_soil_moisture_thermal(
        self,
        lst: np.ndarray,
        ndvi: np.ndarray,
    ) -> np.ndarray:
        """基于热红外指数（LST-NDVI梯形法）估算土壤含水率

        利用地表温度-植被指数特征空间中的干边/湿边概念。
        土壤含水率 ∝ (LST_max - LST) / (LST_max - LST_min)
        """
        if lst is None or ndvi is None:
            return np.zeros((1, 1))

        valid_mask = ~np.isnan(lst) & ~np.isnan(ndvi)
        if not np.any(valid_mask):
            return np.full_like(lst, np.nan)

        # 分NDVI区间估算干湿边
        ndvi_bins = np.linspace(0.2, 0.9, 8)
        lst_max_line = np.full_like(lst, np.nan)
        lst_min_line = np.full_like(lst, np.nan)

        for i in range(len(ndvi_bins) - 1):
            mask = (ndvi >= ndvi_bins[i]) & (ndvi < ndvi_bins[i + 1]) & valid_mask
            if mask.sum() > 5:
                lst_bin = lst[mask]
                lst_max_line[mask] = np.percentile(lst_bin, 98)
                lst_min_line[mask] = np.percentile(lst_bin, 2)

        # 土壤含水率
        denom = lst_max_line - lst_min_line + 1e-10
        moisture = (lst_max_line - lst) / denom
        moisture = np.clip(moisture, 0.0, 1.0)

        return moisture

    def retrieve_soil_moisture(
        self,
        bands: SpectralBands,
        lst: Optional[np.ndarray] = None,
        ndvi: Optional[np.ndarray] = None,
        method: str = "swir",
    ) -> np.ndarray:
        """土壤含水率反演统一入口"""
        if method == "thermal" and lst is not None and ndvi is not None:
            return self.retrieve_soil_moisture_thermal(lst, ndvi)
        return self.retrieve_soil_moisture_swir(bands)

    # -------------------------------------------------------------------
    # 2. 红边位置与重金属胁迫
    # -------------------------------------------------------------------

    def compute_red_edge_position(
        self,
        bands: SpectralBands,
    ) -> Optional[np.ndarray]:
        """计算红边位置(REP)

        红边位置是植被反射率在680-760nm之间斜率最大处的波长。
        重金属胁迫会导致红边位置向短波方向偏移（蓝移）。

        使用线性内插法(Linear Interpolation Method)：
        REP = 700 + 40 * ((R670 + R780)/2 - R700) / (R740 - R700)
        """
        red = bands.red          # ~670nm
        red_edge = bands.red_edge  # ~700-740nm
        nir = bands.nir          # ~780nm

        if red is None or nir is None:
            logger.warning("红边位置计算需要红波段和近红外波段")
            return None

        if red_edge is None:
            # 线性内插近似
            red_700 = red + (nir - red) * (700 - 670) / (780 - 670)
        else:
            red_700 = red_edge

        true_red = red
        true_nir = nir

        # 红边拐点处的反射率（简化为红和NIR的中点）
        r_re = (true_red + true_nir) / 2.0

        # REP计算（基于四点内插法）
        # 取红边前后的四个点：670, 700, 740, 780 nm
        rep = np.full_like(red, np.nan)

        denom = red_700 - red + 1e-10
        rep_val = 700.0 + 40.0 * ((r_re - red) / denom)
        rep = np.clip(rep_val, 680.0, 760.0)

        return rep

    def retrieve_heavy_metal_stress(
        self,
        bands: SpectralBands,
        red_edge_position: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """重金属胁迫监测

        基于红边位置偏移的程度评估重金属胁迫：
        1. 计算当前红边位置与健康植被参考位置的偏差
        2. 结合叶绿素吸收特征 (REIP)
        3. 归一化为胁迫指数 (0-1, 越高越严重)
        """
        if red_edge_position is None:
            red_edge_position = self.compute_red_edge_position(bands)

        if red_edge_position is None or bands.nir is None:
            return np.zeros((1, 1))

        # 健康植被红边位置参考值 ~720-730nm
        healthy_rep = 725.0

        # 红边蓝移量
        rep_shift = healthy_rep - red_edge_position
        max_expected_shift = 40.0  # 最大预期蓝移 ~40nm

        stress = np.clip(rep_shift / max_expected_shift, 0.0, 1.0)

        # 结合NDVI进行交叉验证：低NDVI且红边蓝移严重 = 强胁迫
        if bands.red is not None:
            eps = 1e-10
            ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + eps)
            # 如果NDVI已经表明非植被，降低胁迫权重
            veg_factor = np.clip(ndvi, 0.0, 1.0)
            stress = stress * veg_factor

        return stress

    # -------------------------------------------------------------------
    # 3. 地表温度 (LST) - 单窗算法
    # -------------------------------------------------------------------

    def retrieve_lst_mono_window(
        self,
        thermal_band: np.ndarray,
        emissivity: np.ndarray,
        transmittance: float = 0.85,
        mean_atmospheric_temp: float = 293.0,  # K (~20°C)
        sensor: str = "landsat8_tirs10",
    ) -> np.ndarray:
        """单窗算法反演地表温度

        基于辐射传输方程的单窗算法 (Qin et al., 2001 / Jimenez-Munoz et al., 2014)

        公式:
        LST = [a*(1-C-D) + (b*(1-C-D)+C+D)*T_sensor - D*T_a] / C

        其中:
        C = ε × τ
        D = (1 - τ) × [1 + (1 - ε) × τ]
        a, b = 普朗克线性化系数

        Args:
            thermal_band: 热红外波段辐射亮度 (W/(m²·sr·μm)) 或DN值
            emissivity: 地表比辐射率 (0-1)
            transmittance: 大气透过率
            mean_atmospheric_temp: 平均大气作用温度 (K)
            sensor: 传感器类型
        """
        if thermal_band is None:
            return np.zeros((1, 1))

        if emissivity is None:
            emissivity = np.ones_like(thermal_band) * 0.97  # 默认植被比辐射率

        # 传感器特定参数
        sensor_params = {
            "landsat8_tirs10": {"K1": 774.89, "K2": 1321.08, "a": -67.355351, "b": 0.458606},
            "landsat8_tirs11": {"K1": 480.89, "K2": 1201.14, "a": -67.355351, "b": 0.458606},
            "sentinel3_slstr": {"K1": 1053.0, "K2": 1186.0, "a": -64.0, "b": 0.44},
            "generic": {"K1": 774.89, "K2": 1321.08, "a": -67.355351, "b": 0.458606},
        }

        params = sensor_params.get(sensor, sensor_params["generic"])

        # 如果是DN值，需先转换为辐射亮度 (此处假设已为辐射亮度)
        L_lambda = thermal_band.astype(np.float64)

        # 计算普朗克亮温 (T_sensor, K)
        T_sensor = params["K2"] / np.log(params["K1"] / (L_lambda + 1e-10) + 1.0)

        # 单窗算法参数
        e = np.clip(emissivity, 0.01, 1.0)
        t = transmittance

        C = e * t
        D = (1.0 - t) * (1.0 + (1.0 - e) * t)

        a = params["a"]
        b = params["b"]

        # LST计算
        numerator = (
            a * (1.0 - C - D)
            + (b * (1.0 - C - D) + C + D) * T_sensor
            - D * mean_atmospheric_temp
        )
        lst_kelvin = numerator / (C + 1e-10)

        # 转换为摄氏度
        lst_celsius = lst_kelvin - 273.15

        return lst_celsius

    def retrieve_lst_split_window(
        self,
        tir1: np.ndarray,
        tir2: np.ndarray,
        emissivity1: np.ndarray,
        emissivity2: np.ndarray,
        transmittance: float = 0.85,
        sensor: str = "landsat8",
    ) -> np.ndarray:
        """劈窗算法反演地表温度

        需要两个热红外波段。
        公式 (Wan & Dozier, 1996 / Becker & Li, 1990):
        LST = A0 + A1*T1 - A2*T2

        Args:
            tir1, tir2: 两个热红外波段辐射亮度
            emissivity1, emissivity2: 对应比辐射率
            transmittance: 大气透过率
        """
        if tir1 is None or tir2 is None:
            logger.warning("劈窗算法需要两个热红外波段")
            return np.zeros((1, 1))

        # 转换为普朗克亮温（简化：使用通用K1/K2）
        K1, K2 = 774.89, 1321.08
        T1 = K2 / np.log(K1 / (tir1 + 1e-10) + 1.0)
        T2 = K2 / np.log(K1 / (tir2 + 1e-10) + 1.0)

        # 平均比辐射率和差异
        e_mean = (emissivity1 + emissivity2) / 2.0
        e_diff = emissivity1 - emissivity2

        # 劈窗系数（经验值，需根据当地大气条件调整）
        A0 = (
            0.39 * (T1 - T2) * (1.0 - e_mean / e_mean)
            + 0.42 * e_diff
        )
        A1 = 1.0 + 0.51 * (1.0 - e_mean) / e_mean - 0.53 * e_diff / (e_mean ** 2 + 1e-10)
        A2 = 0.51 * (1.0 - e_mean) / e_mean + 0.53 * e_diff / (e_mean ** 2 + 1e-10)

        lst = A0 + A1 * T1 - A2 * T2

        return lst - 273.15  # 转换为°C

    def estimate_emissivity_from_ndvi(
        self,
        ndvi: np.ndarray,
    ) -> np.ndarray:
        """从NDVI估算地表比辐射率

        采用Sobrino et al. (2004)的NDVI阈值法:
        - NDVI < 0.2: 裸土，ε = 0.97
        - 0.2 ≤ NDVI ≤ 0.5: 混合像元，ε = 0.004*FVC + 0.986
        - NDVI > 0.5: 植被，ε = 0.99
        """
        if ndvi is None:
            return np.ones((1, 1)) * 0.97

        emissivity = np.full_like(ndvi, 0.97)

        # 植被覆盖度
        ndvi_soil = 0.2
        ndvi_veg = 0.5
        fvc = np.clip((ndvi - ndvi_soil) / (ndvi_veg - ndvi_soil + 1e-10), 0.0, 1.0)

        # 混合区域
        mix_mask = (ndvi >= 0.2) & (ndvi <= 0.5)
        emissivity[mix_mask] = 0.004 * fvc[mix_mask] + 0.986

        # 植被区域
        veg_mask = ndvi > 0.5
        emissivity[veg_mask] = 0.99

        return emissivity

    def retrieve_lst(
        self,
        thermal_band: np.ndarray,
        ndvi: Optional[np.ndarray] = None,
        emissivity: Optional[np.ndarray] = None,
        transmittance: float = 0.85,
        mean_atmospheric_temp: float = 293.0,
        method: str = "mono_window",
    ) -> np.ndarray:
        """地表温度反演统一入口"""
        if emissivity is None and ndvi is not None:
            emissivity = self.estimate_emissivity_from_ndvi(ndvi)
        elif emissivity is None:
            emissivity = np.ones_like(thermal_band) * 0.97

        return self.retrieve_lst_mono_window(
            thermal_band, emissivity, transmittance, mean_atmospheric_temp
        )

    # -------------------------------------------------------------------
    # 4. 地表径流系数 - SCS-CN模型
    # -------------------------------------------------------------------

    def retrieve_runoff_coefficient_scs_cn(
        self,
        landcover_class: np.ndarray,
        soil_hydrologic_group: Optional[np.ndarray] = None,
        precipitation: float = 100.0,  # mm/event
    ) -> np.ndarray:
        """SCS-CN模型估算地表径流系数

        SCS曲线数法:
        Q = (P - 0.2*S)² / (P + 0.8*S)  (当 P > 0.2*S)
        其中 S = 25400/CN - 254

        径流系数 = Q / P

        Args:
            landcover_class: 土地利用分类图 (整数编码)
            soil_hydrologic_group: 土壤水文分组 (A/B/C/D, 编码1-4)
            precipitation: 设计降雨量 (mm)
        """
        if landcover_class is None:
            return np.zeros((1, 1))

        # CN值查找表 (AMC-II条件)
        # 格式: {土地利用编码: {土壤组: CN}}
        cn_lookup = {
            # 水体
            1: {"A": 100, "B": 100, "C": 100, "D": 100},
            # 不透水面/建成区
            2: {"A": 77, "B": 85, "C": 90, "D": 92},
            # 裸土
            3: {"A": 72, "B": 82, "C": 87, "D": 89},
            # 草地/牧场
            4: {"A": 39, "B": 61, "C": 74, "D": 80},
            # 农田
            5: {"A": 67, "B": 78, "C": 85, "D": 89},
            # 灌木
            6: {"A": 30, "B": 48, "C": 65, "D": 73},
            # 林地（良好）
            7: {"A": 25, "B": 55, "C": 70, "D": 77},
            # 林地（稀疏）
            8: {"A": 45, "B": 66, "C": 77, "D": 83},
        }

        soil_groups = ["A", "B", "C", "D"]

        h, w = landcover_class.shape
        cn_map = np.full((h, w), 80.0, dtype=np.float64)  # 默认CN

        if soil_hydrologic_group is None:
            # 默认假设土壤组B
            soil_hydrologic_group = np.full((h, w), 2, dtype=np.int32)

        for lc_code, cn_dict in cn_lookup.items():
            lc_mask = landcover_class == lc_code
            for sg_idx, sg_name in enumerate(soil_groups):
                sg_mask = soil_hydrologic_group == (sg_idx + 1)
                combined_mask = lc_mask & sg_mask
                cn_map[combined_mask] = cn_dict[sg_name]

        # SCS公式
        S = 25400.0 / cn_map - 254.0
        Ia = 0.2 * S  # 初始截留

        Q = np.zeros_like(S)
        runoff_mask = precipitation > Ia
        Q[runoff_mask] = (
            (precipitation - 0.2 * S[runoff_mask]) ** 2
            / (precipitation + 0.8 * S[runoff_mask] + 1e-10)
        )

        # 径流系数
        coefficient = np.clip(Q / (precipitation + 1e-10), 0.0, 1.0)

        return coefficient

    def estimate_landcover_from_ndvi(
        self,
        ndvi: np.ndarray,
        ndbi: Optional[np.ndarray] = None,
        ndwi: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """从植被指数和水体指数估算简化土地利用分类

        分类方案 (简化):
        1 = 水体 (NDWI > 0 且 NDVI < 0.2)
        2 = 建成区 (NDBI > 0 且 NDVI < 0.3)
        3 = 裸土 (NDVI < 0.2 且 NDWI < 0)
        4 = 草地 (0.2 ≤ NDVI < 0.5)
        5 = 农田 (0.5 ≤ NDVI < 0.7)
        6 = 灌木 (0.3 ≤ NDVI < 0.6)
        7 = 密林 (NDVI ≥ 0.7)
        8 = 疏林 (0.5 ≤ NDVI < 0.7)
        """
        if ndvi is None:
            return np.ones((1, 1), dtype=np.int32) * 4  # 默认草地

        lc = np.full(ndvi.shape, 4, dtype=np.int32)  # 默认草地

        # 水体
        if ndwi is not None:
            water_mask = (ndwi > 0.0) & (ndvi < 0.2)
            lc[water_mask] = 1

        # 建成区
        if ndbi is not None:
            built_mask = (ndbi > 0.0) & (ndvi < 0.3) & ~(lc == 1)
            lc[built_mask] = 2

        # 裸土
        bare_mask = (ndvi < 0.2) & (lc != 1) & (lc != 2)
        lc[bare_mask] = 3

        # 密林
        dense_forest = ndvi >= 0.7
        lc[dense_forest] = 7

        # 疏林/农田
        medium_veg = (ndvi >= 0.5) & (ndvi < 0.7) & (lc < 4)
        lc[medium_veg] = 5

        # 灌木
        shrub = (ndvi >= 0.3) & (ndvi < 0.5) & (lc < 4)
        lc[shrub] = 6

        return lc

    # -------------------------------------------------------------------
    # 综合反演
    # -------------------------------------------------------------------

    def retrieve_all(
        self,
        bands: SpectralBands,
        ndvi: Optional[np.ndarray] = None,
        ndwi: Optional[np.ndarray] = None,
        ndbi: Optional[np.ndarray] = None,
        precipitation: float = 100.0,
    ) -> EnvironmentResult:
        """一键反演所有4项环境/土壤指标"""
        # 计算NDVI（如果未提供）
        if ndvi is None and bands.nir is not None and bands.red is not None:
            ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + 1e-10)

        # 1. 土壤含水率
        soil_moisture = self.retrieve_soil_moisture_swir(bands)

        # 2. 红边位置 + 重金属胁迫
        rep = self.compute_red_edge_position(bands)
        heavy_metal = self.retrieve_heavy_metal_stress(bands, rep)

        # 3. 地表温度
        if bands.thermal is not None:
            lst = self.retrieve_lst_mono_window(
                bands.thermal,
                self.estimate_emissivity_from_ndvi(ndvi) if ndvi is not None
                else np.ones_like(bands.thermal) * 0.97,
            )
        else:
            lst = None

        # 4. 径流系数
        lc = self.estimate_landcover_from_ndvi(ndvi, ndbi, ndwi)
        runoff = self.retrieve_runoff_coefficient_scs_cn(lc, precipitation=precipitation)

        # 不确定性
        uncertainties = self._estimate_uncertainties(bands)

        return EnvironmentResult(
            soil_moisture=soil_moisture,
            heavy_metal_stress=heavy_metal,
            lst=lst,
            runoff_coefficient=runoff,
            red_edge_position=rep,
            uncertainties=uncertainties,
            metadata={"lc_classes": 8, "precipitation_mm": precipitation},
        )

    def _estimate_uncertainties(self, bands: SpectralBands) -> Dict[str, np.ndarray]:
        """估计不确定性"""
        unc = {}
        base_noise = 0.03  # 3%基础误差

        for name, band in [
            ("soil_moisture", bands.swir1),
            ("lst", bands.thermal),
        ]:
            if band is not None:
                unc[name] = np.full_like(band, base_noise)

        return unc
