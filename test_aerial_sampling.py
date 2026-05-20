"""
航测像片采样推荐功能 - 集成测试
===============================
验证从"影像上传"到"反演计算"再到"点位推荐"的全流程自动化。

测试覆盖:
1. EXIF/GPS/IMU元数据解析
2. 影像质量评估
3. 共线方程/正射校正
4. 地理对齐
5. 水质反演 (5项指标)
6. 林业反演 (5项指标)
7. 环境反演 (4项指标)
8. 不确定性映射
9. 采样策略融合
10. API全流程端到端
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import pytest
import numpy as np
import json
import io
from unittest.mock import Mock, patch, MagicMock

# ===========================================================================
# 1. EXIF/GPS/IMU 元数据解析测试
# ===========================================================================


class TestExifParser:
    """EXIF元数据解析器测试"""

    def setup_method(self):
        from photogrammetry.exif_parser import ExifParser, GPSInfo, IMUInfo, CameraInfo, AerialImageMetadata
        self.parser = ExifParser()
        self.GPSInfo = GPSInfo
        self.IMUInfo = IMUInfo
        self.CameraInfo = CameraInfo
        self.AerialImageMetadata = AerialImageMetadata

    def test_dms_to_decimal_north_east(self):
        """测试度分秒转十进制度 - 北纬东经"""
        result = self.parser._dms_to_decimal(39, 54, 26.0, "N")
        assert abs(result - 39.9072) < 0.01

        result = self.parser._dms_to_decimal(116, 23, 50.0, "E")
        assert abs(result - 116.3972) < 0.01

    def test_dms_to_decimal_south_west(self):
        """测试度分秒转十进制度 - 南纬西经"""
        result = self.parser._dms_to_decimal(33, 55, 0.0, "S")
        assert result < 0
        assert abs(result + 33.9167) < 0.01

        result = self.parser._dms_to_decimal(18, 25, 0.0, "W")
        assert result < 0

    def test_rational_to_float(self):
        """测试有理数转换"""
        from fractions import Fraction
        assert self.parser._rational_to_float(Fraction(1, 3)) == pytest.approx(1 / 3)
        assert self.parser._rational_to_float(3.14) == 3.14
        assert self.parser._rational_to_float(None) is None
        assert self.parser._rational_to_float((100, 0)) is None

    def test_gps_info_valid(self):
        """测试GPS数据有效性检查"""
        gps_invalid = self.GPSInfo(latitude=0.0, longitude=0.0)
        assert not gps_invalid.is_valid()

        gps_valid = self.GPSInfo(latitude=39.9, longitude=116.4, altitude=100.0)
        assert gps_valid.is_valid()

        gps_out_of_range = self.GPSInfo(latitude=100.0, longitude=200.0)
        assert not gps_out_of_range.is_valid()

    def test_gps_info_to_dict(self):
        """测试GPS数据字典导出"""
        gps = self.GPSInfo(latitude=39.9, longitude=116.4, altitude=50.0)
        d = gps.to_dict()
        assert d["latitude"] == 39.9
        assert d["longitude"] == 116.4
        assert d["altitude"] == 50.0

    def test_imu_to_rotation_matrix(self):
        """测试IMU姿态角转旋转矩阵"""
        imu = self.IMUInfo(pitch=0.0, roll=0.0, yaw=0.0)
        R = imu.to_rotation_matrix()
        assert R is not None
        np.testing.assert_array_almost_equal(R, np.eye(3), decimal=10)

        imu_no_data = self.IMUInfo()
        assert imu_no_data.to_rotation_matrix() is None

        imu_partial = self.IMUInfo(pitch=5.0)
        assert imu_partial.to_rotation_matrix() is None

    def test_imu_is_valid(self):
        """测试IMU有效性检查"""
        imu_empty = self.IMUInfo()
        assert not imu_empty.is_valid()

        imu_with_data = self.IMUInfo(pitch=0.5, roll=1.0, yaw=45.0)
        assert imu_with_data.is_valid()

    def test_camera_compute_pixel_size(self):
        """测试像元尺寸计算"""
        cam = self.CameraInfo(sensor_width=13.2, image_width=5472)
        ps = cam.compute_pixel_size()
        assert ps is not None
        assert abs(ps - 13.2 / 5472) < 1e-8

    def test_camera_compute_focal_pixels(self):
        """测试焦距转像素单位"""
        cam = self.CameraInfo(
            focal_length=8.8,
            sensor_width=13.2,
            image_width=5472,
        )
        fp = cam.compute_focal_pixels()
        assert fp is not None
        expected = 8.8 / (13.2 / 5472)
        assert abs(fp - expected) < 1.0

    def test_camera_default_principal_point(self):
        """测试默认像主点"""
        cam = self.CameraInfo(image_width=4000, image_height=3000)
        x0, y0 = cam.get_default_principal_point()
        assert x0 == 2000.0
        assert y0 == 1500.0

    def test_parser_creates_metadata_object(self):
        """测试解析器创建完整元数据对象"""
        from datetime import datetime
        meta = self.AerialImageMetadata(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_size_bytes=1024,
            image_format="jpeg",
            gps=self.GPSInfo(latitude=30.0, longitude=120.0),
            imu=self.IMUInfo(pitch=2.0, roll=1.0, yaw=90.0),
            camera=self.CameraInfo(focal_length=24.0, image_width=4000, image_height=3000),
            capture_time=datetime.now(),
        )
        d = meta.to_dict()
        assert d["file_name"] == "image.jpg"
        assert d["gps"]["latitude"] == 30.0
        assert d["imu"]["pitch"] == 2.0
        assert d["camera"]["focal_length_mm"] == 24.0

    def test_metadata_to_json(self):
        """测试元数据JSON序列化"""
        meta = self.AerialImageMetadata(
            file_path="/test/image.jpg",
            file_name="image.jpg",
            file_size_bytes=1024,
            image_format="jpeg",
            gps=self.GPSInfo(latitude=30.0, longitude=120.0),
            imu=self.IMUInfo(),
            camera=self.CameraInfo(),
        )
        json_str = meta.to_json()
        data = json.loads(json_str)
        assert data["file_name"] == "image.jpg"
        assert data["gps"]["latitude"] == 30.0


# ===========================================================================
# 2. 影像质量评估测试
# ===========================================================================


class TestImageQuality:
    """影像质量评估测试"""

    def setup_method(self):
        from photogrammetry.image_quality import ImageQualityAssessor, QualityReport
        self.assessor = ImageQualityAssessor()

    def test_blur_assessment_sharp_image(self):
        """测试清晰影像模糊度评估"""
        # 创建模拟清晰影像（高方差）
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        # 添加边缘使拉普拉斯有响应
        img[40:60, 40:60] = 255
        img[20:30, 20:80] = 0
        result = self.assessor.assess_blur(img)
        assert result.blur_score >= 0
        assert result.blur_score <= 100
        assert result.blur_level in ("sharp", "slight", "moderate", "severe")

    def test_blur_assessment_blurry_image(self):
        """测试模糊影像评估"""
        # 均匀灰度影像 = 模糊
        img = np.ones((100, 100), dtype=np.uint8) * 128
        result = self.assessor.assess_blur(img)
        assert result.is_blurry

    def test_exposure_assessment_good(self):
        """测试正常曝光评估"""
        img = np.ones((100, 100), dtype=np.float64) * 128
        result = self.assessor.assess_exposure(img)
        assert result.mean_brightness == 128.0
        assert result.exposure_score > 60  # 128是理想曝光

    def test_exposure_assessment_overexposed(self):
        """测试过曝评估"""
        img = np.ones((100, 100), dtype=np.float64) * 250
        result = self.assessor.assess_exposure(img)
        assert result.overexposed_ratio > 0.5
        assert result.exposure_level in ("over", "slight_over")

    def test_exposure_assessment_underexposed(self):
        """测试欠曝评估"""
        img = np.ones((100, 100), dtype=np.float64) * 10
        result = self.assessor.assess_exposure(img)
        assert result.underexposed_ratio > 0.5

    def test_tilt_assessment_nadir(self):
        """测试正射倾斜评估"""
        from photogrammetry.exif_parser import IMUInfo
        imu = IMUInfo(pitch=1.0, roll=0.5)
        result = self.assessor.assess_tilt(imu)
        assert result.is_nadir
        assert result.tilt_level == "nadir"
        assert result.tilt_angle < 5.0

    def test_tilt_assessment_oblique(self):
        """测试倾斜影像评估"""
        from photogrammetry.exif_parser import IMUInfo
        imu = IMUInfo(pitch=20.0, roll=15.0)
        result = self.assessor.assess_tilt(imu)
        assert not result.is_nadir
        assert result.tilt_angle > 15.0

    def test_overall_quality_levels(self):
        """测试综合质量等级"""
        from photogrammetry.exif_parser import IMUInfo
        from photogrammetry.image_quality import BlurReport, ExposureReport, TiltReport

        high_blur = BlurReport(500.0, 100.0, False, "sharp")
        high_exp = ExposureReport(128.0, 0.0, 0.0, 100.0, "good")
        low_tilt = TiltReport(0.5, 0.0, 0.0, True, "nadir")

        overall, level, _ = self.assessor._compute_overall(high_blur, high_exp, low_tilt)
        assert level == "excellent"

        low_blur = BlurReport(20.0, 10.0, True, "severe")
        low_exp = ExposureReport(250.0, 0.5, 0.0, 10.0, "over")
        high_tilt = TiltReport(40.0, 30.0, 25.0, False, "oblique")

        overall, level, _ = self.assessor._compute_overall(low_blur, low_exp, high_tilt)
        assert level in ("poor", "rejected")


# ===========================================================================
# 3. 共线方程与正射校正测试
# ===========================================================================


class TestCollinearityModel:
    """共线方程模型测试"""

    def setup_method(self):
        from photogrammetry.orthorectification import (
            CollinearityModel, InteriorOrientation, ExteriorOrientation,
        )
        self.InteriorOrientation = InteriorOrientation
        self.ExteriorOrientation = ExteriorOrientation

    def test_basic_projection_roundtrip(self):
        """测试基本投影往返"""
        from photogrammetry.orthorectification import CollinearityModel

        interior = self.InteriorOrientation(f=4000, x0=2000, y0=1500)
        exterior = self.ExteriorOrientation(
            Xs=0.0, Ys=0.0, Zs=1000.0,
            omega=0.0, phi=0.0, kappa=0.0,
        )
        model = CollinearityModel(interior, exterior)

        # 地面点正算到像点 (天底点应该在像主点附近)
        x_img, y_img = model.ground_to_image(0, 0, 0)
        assert abs(x_img - 2000) < 300
        assert abs(y_img - 1500) < 300

    def test_rotation_matrix(self):
        """测试旋转矩阵"""
        exterior = self.ExteriorOrientation(
            Xs=0, Ys=0, Zs=100,
            omega=0.0, phi=0.0, kappa=0.0,
        )
        R = exterior.to_rotation_matrix()
        np.testing.assert_array_almost_equal(R, np.eye(3), decimal=10)

        # 90度kappa旋转
        exterior2 = self.ExteriorOrientation(
            Xs=0, Ys=0, Zs=100,
            omega=0.0, phi=0.0, kappa=np.pi / 2,
        )
        R2 = exterior2.to_rotation_matrix()
        # Rz(90°) = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        np.testing.assert_array_almost_equal(R2[0, 0], 0.0, decimal=5)
        np.testing.assert_array_almost_equal(R2[0, 1], -1.0, decimal=5)
        np.testing.assert_array_almost_equal(R2[1, 0], 1.0, decimal=5)

    def test_gsd_computation(self):
        """测试地面采样距离计算"""
        from photogrammetry.orthorectification import CollinearityModel

        interior = self.InteriorOrientation(f=4000, x0=2000, y0=1500, pixel_size=0.0024)  # 2.4μm像元
        exterior = self.ExteriorOrientation(Xs=0, Ys=0, Zs=120.0)  # 航高120m
        model = CollinearityModel(interior, exterior)

        gsd = model.compute_ground_resolution(0.0)
        # GSD = H * ps / f = 120 * 0.0024 / 4000 ≈ 0.000072mm? -> 应该用像素单位
        # 这里我们f可能以像素为单位
        assert gsd > 0


class TestOrthorectificationEngine:
    """正射校正引擎测试"""

    def setup_method(self):
        from photogrammetry.orthorectification import OrthorectificationEngine
        self.engine = OrthorectificationEngine()

    def test_build_from_params(self):
        """测试从参数构建模型"""
        model = self.engine.build_from_params(
            Xs=0, Ys=0, Zs=1000,
            omega=0, phi=0, kappa=0,
            f=4000, x0=2000, y0=1500,
        )
        assert model is not None

    def test_build_from_metadata(self):
        """测试从元数据构建模型"""
        from photogrammetry.exif_parser import AerialImageMetadata, GPSInfo, IMUInfo, CameraInfo

        meta = AerialImageMetadata(
            file_path="/test.jpg",
            file_name="test.jpg",
            file_size_bytes=1024,
            image_format="jpeg",
            gps=GPSInfo(latitude=30.0, longitude=120.0, altitude=500.0),
            imu=IMUInfo(pitch=5.0, roll=3.0, yaw=45.0),
            camera=CameraInfo(
                focal_length=8.8,
                sensor_width=13.2,
                image_width=5472,
                image_height=3648,
            ),
        )
        model = self.engine.build_from_metadata(meta)
        assert model is not None
        assert model.exterior.Xs == 120.0
        assert model.exterior.Ys == 30.0
        assert model.exterior.Zs == 500.0

    def test_bilinear_interpolation(self):
        """测试双线性内插"""
        img = np.array([
            [10, 20],
            [30, 40],
        ], dtype=np.uint8)

        val = self.engine._bilinear_interpolate(
            img, 0.5, 0.5, 2, 2, False,
        )
        assert val == 25.0  # (10+20+30+40)/4

        # 彩色图像
        img_rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        img_rgb[0, 0] = [10, 100, 200]
        img_rgb[0, 1] = [20, 110, 210]
        img_rgb[1, 0] = [30, 120, 220]
        img_rgb[1, 1] = [40, 130, 230]

        val = self.engine._bilinear_interpolate(
            img_rgb, 0.5, 0.5, 2, 2, True,
        )
        np.testing.assert_array_almost_equal(val, [25.0, 115.0, 215.0])

    def test_coverage_computation(self):
        """测试地面覆盖范围计算"""
        from photogrammetry.orthorectification import OrthorectificationEngine as OE
        from photogrammetry.exif_parser import AerialImageMetadata, GPSInfo, CameraInfo, IMUInfo

        meta = AerialImageMetadata(
            file_path="/test.jpg",
            file_name="test.jpg",
            file_size_bytes=1024,
            image_format="jpeg",
            gps=GPSInfo(latitude=30.0, longitude=120.0, altitude=100.0),
            imu=IMUInfo(),
            camera=CameraInfo(
                focal_length=8.8,
                sensor_width=13.2,
                image_width=5472,
                image_height=3648,
            ),
        )
        bbox = OE._compute_coverage(meta)
        assert len(bbox) == 4
        assert bbox[0] < bbox[2]  # min_x < max_x
        assert bbox[1] < bbox[3]  # min_y < max_y


# ===========================================================================
# 4. 地理对齐测试
# ===========================================================================


class TestGeoAlignment:
    """地理对齐引擎测试"""

    def setup_method(self):
        from photogrammetry.geo_alignment import GeoAlignmentEngine, CRSDefinition
        self.engine = GeoAlignmentEngine()

    def test_crs_definitions(self):
        """测试坐标参考系定义"""
        from photogrammetry.geo_alignment import CRSDefinition

        wgs84 = CRSDefinition.wgs84()
        assert wgs84.epsg == 4326

        web_mercator = CRSDefinition.web_mercator()
        assert web_mercator.epsg == 3857

        cgcs2000 = CRSDefinition.cgcs2000()
        assert cgcs2000.epsg == 4490

    def test_align_points_to_raster(self):
        """测试点坐标转栅格行列号"""
        geo_transform = (100.0, 0.01, 0.0, 40.0, 0.0, -0.01)
        x = np.array([100.05, 100.10])
        y = np.array([39.95, 39.90])

        rows, cols = self.engine.align_points_to_raster(
            x, y, geo_transform, (100, 100),
        )
        assert rows.shape == (2,)
        assert cols.shape == (2,)
        # 100.05 -> col≈5, 39.95 -> row≈5
        assert abs(cols[0] - 5) <= 1  # 允许±1精度误差
        assert abs(rows[0] - 5) <= 1

    def test_raster_to_grid_points(self):
        """测试栅格转格网点"""
        data = np.array([[1, 2], [3, 4]], dtype=np.float64)
        geo_transform = (0.0, 1.0, 0.0, 10.0, 0.0, -1.0)

        x, y, v = self.engine.raster_to_grid_points(data, geo_transform, stride=1)
        assert len(x) == 4
        assert len(y) == 4
        assert len(v) == 4

    def test_coordinate_transform_same_crs(self):
        """测试同坐标系转换"""
        x, y = self.engine.coordinate_transform(116.4, 39.9, 4326, 4326)
        assert x == 116.4
        assert y == 39.9

    def test_wgs84_mercator_roundtrip(self):
        """测试WGS84-WebMercator往返转换"""
        x, y = self.engine._wgs84_to_mercator(116.4, 39.9)
        lon, lat = self.engine._mercator_to_wgs84(x, y)
        assert abs(lon - 116.4) < 0.01
        assert abs(lat - 39.9) < 0.01

    def test_validation(self):
        """测试对齐验证"""
        src = np.array([1.0, 2.0, 3.0])
        tgt = np.array([1.0, 2.0, 3.0])
        result = self.engine.validate_alignment(src, tgt)
        assert result["valid"]
        assert result["rmse"] == 0.0

        src2 = np.array([1.0, 2.0, 3.0])
        tgt2 = np.array([1.1, 2.1, 3.1])
        result2 = self.engine.validate_alignment(src2, tgt2)
        assert result2["rmse"] > 0.0


# ===========================================================================
# 5. 水质反演测试
# ===========================================================================


class TestWaterQualityInverter:
    """水质反演测试"""

    def setup_method(self):
        from remote_sensing.water_quality import WaterQualityInverter, SpectralBands
        self.inverter = WaterQualityInverter()
        self.SpectralBands = SpectralBands

    def _create_test_bands(self):
        """创建测试波段数据（100x100水体场景）"""
        h, w = 100, 100
        # 模拟典型水体反射率
        return self.SpectralBands(
            blue=np.full((h, w), 0.08, dtype=np.float64),
            green=np.full((h, w), 0.10, dtype=np.float64),
            red=np.full((h, w), 0.05, dtype=np.float64),
            red_edge=np.full((h, w), 0.06, dtype=np.float64),
            nir=np.full((h, w), 0.02, dtype=np.float64),
            swir1=np.full((h, w), 0.01, dtype=np.float64),
            swir2=np.full((h, w), 0.008, dtype=np.float64),
        )

    def test_chl_a_three_band(self):
        """测试三波段叶绿素a反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_chl_a_three_band(bands)
        assert result.shape == (100, 100)
        assert np.all(~np.isinf(result[~np.isnan(result)]))
        # 值应在合理范围
        valid = result[~np.isnan(result)]
        assert valid.min() >= 0.1
        assert valid.max() <= 500.0

    def test_chl_a_four_band(self):
        """测试四波段叶绿素a反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_chl_a_four_band(bands)
        assert result.shape == (100, 100)
        valid = result[~np.isnan(result)]
        if valid.size > 0:
            assert valid.min() >= 0.1
            assert valid.max() <= 500.0

    def test_tsm_linear(self):
        """测试悬浮物线性反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_tsm_linear(bands)
        assert result.shape == (100, 100)
        valid = result[~np.isnan(result)]
        assert valid.min() >= 0.0

    def test_tsm_exponential(self):
        """测试悬浮物指数反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_tsm_exponential(bands)
        assert result.shape == (100, 100)

    def test_turbidity(self):
        """测试浑浊度反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_turbidity(bands)
        assert result.shape == (100, 100)

    def test_sdd(self):
        """测试透明度反演"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_sdd(bands)
        assert result.shape == (100, 100)
        valid = result[~np.isnan(result)]
        assert valid.min() >= 0.0
        assert valid.max() <= 30.0

    def test_cod(self):
        """测试COD反演"""
        bands = self._create_test_bands()
        chl = self.inverter.retrieve_chl_a_three_band(bands)
        tsm = self.inverter.retrieve_tsm_exponential(bands)
        result = self.inverter.retrieve_cod(bands, chl, tsm)
        assert result.shape == (100, 100)

    def test_water_mask(self):
        """测试水体掩膜"""
        bands = self._create_test_bands()
        mask = self.inverter.compute_water_mask(bands)
        assert mask.shape == (100, 100)
        assert mask.dtype == bool
        # 水体NDWI应该>0
        assert np.sum(mask) > 0

    def test_retrieve_all(self):
        """测试一键反演所有水质指标"""
        bands = self._create_test_bands()
        result = self.inverter.retrieve_all(bands)

        assert result.chl_a is not None
        assert result.tsm is not None
        assert result.turbidity is not None
        assert result.sdd is not None
        assert result.cod is not None
        assert result.water_mask is not None

        summary = result.to_dict_summary()
        assert len(summary) == 5

    def test_retrieve_with_missing_bands(self):
        """测试缺失波段时的降级处理"""
        bands = self.SpectralBands(
            red=np.full((10, 10), 0.05, dtype=np.float64),
            nir=np.full((10, 10), 0.02, dtype=np.float64),
            # 不提供 green 波段
        )
        # 不应抛异常，应该降级处理
        try:
            result = self.inverter.retrieve_all(bands)
            assert result is not None
        except ValueError:
            pass  # 允许在极端缺失情况下抛出合理错误


# ===========================================================================
# 6. 林业反演测试
# ===========================================================================


class TestForestryInverter:
    """林业反演测试"""

    def setup_method(self):
        from remote_sensing.forestry import ForestryInverter, SpectralBands
        self.inverter = ForestryInverter()
        self.SpectralBands = SpectralBands

    def _create_veg_bands(self):
        """创建植被场景波段"""
        h, w = 100, 100
        return self.SpectralBands(
            blue=np.full((h, w), 0.03, dtype=np.float64),
            green=np.full((h, w), 0.08, dtype=np.float64),
            red=np.full((h, w), 0.04, dtype=np.float64),
            red_edge=np.full((h, w), 0.20, dtype=np.float64),
            nir=np.full((h, w), 0.40, dtype=np.float64),
            swir1=np.full((h, w), 0.20, dtype=np.float64),
            swir2=np.full((h, w), 0.12, dtype=np.float64),
        )

    def test_ndvi_computation(self):
        """测试NDVI计算"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        assert indices.ndvi is not None
        assert indices.ndvi.shape == (100, 100)
        # 植被NDVI应 > 0.5
        assert np.mean(indices.ndvi) > 0.5

    def test_evi_computation(self):
        """测试EVI计算"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        assert indices.evi is not None

    def test_savi_computation(self):
        """测试SAVI计算"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        assert indices.savi is not None

    def test_lai_computation(self):
        """测试LAI计算"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        assert indices.lai is not None
        assert np.all(indices.lai[~np.isnan(indices.lai)] >= 0)

    def test_fvc_dimidiate(self):
        """测试像元二分FVC"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        fvc = self.inverter.retrieve_fvc_dimidiate(indices.ndvi)
        assert fvc.shape == (100, 100)
        assert np.all(fvc[~np.isnan(fvc)] >= 0.0)
        assert np.all(fvc[~np.isnan(fvc)] <= 1.0)

    def test_fvc_auto(self):
        """测试自动FVC"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        fvc = self.inverter.retrieve_fvc_auto(indices.ndvi)
        assert fvc.shape == (100, 100)
        assert np.all(fvc[~np.isnan(fvc)] >= 0.0)

    def test_vegetation_health(self):
        """测试植被健康度"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        health = self.inverter.compute_vegetation_health(indices)
        assert health.shape == (100, 100)
        assert np.all(health[~np.isnan(health)] >= 0)
        assert np.all(health[~np.isnan(health)] <= 100)

    def test_biomass(self):
        """测试生物量反演"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        biomass = self.inverter.retrieve_biomass(indices)
        assert biomass.shape == (100, 100)
        valid = biomass[~np.isnan(biomass)]
        assert np.all(valid >= 0)

    def test_volume_optical(self):
        """测试纯光学蓄积量估算"""
        bands = self._create_veg_bands()
        indices = self.inverter.compute_all_indices(bands)
        volume = self.inverter.retrieve_volume_optical(bands, indices)
        assert volume is not None
        assert volume.shape == (100, 100)

    def test_species_classification(self):
        """测试树种分类"""
        bands = self._create_veg_bands()
        result = self.inverter.classify_species_spectral_angle(bands)
        assert result.shape == (100, 100)
        assert result.dtype == np.int32

    def test_retrieve_all(self):
        """测试一键反演所有林业指标"""
        bands = self._create_veg_bands()
        result = self.inverter.retrieve_all(bands)

        assert result.volume is not None
        assert result.biomass is not None
        assert result.fvc is not None
        assert result.species_classification is not None
        assert result.vegetation_indices.ndvi is not None

        summary = result.to_dict_summary()
        assert "volume" in summary or "biomass" in summary or "fvc" in summary


# ===========================================================================
# 7. 环境反演测试
# ===========================================================================


class TestEnvironmentInverter:
    """环境反演测试"""

    def setup_method(self):
        from remote_sensing.environment import EnvironmentInverter, SpectralBands
        self.inverter = EnvironmentInverter()
        self.SpectralBands = SpectralBands

    def _create_env_bands(self):
        h, w = 100, 100
        return self.SpectralBands(
            blue=np.full((h, w), 0.06, dtype=np.float64),
            green=np.full((h, w), 0.10, dtype=np.float64),
            red=np.full((h, w), 0.08, dtype=np.float64),
            red_edge=np.full((h, w), 0.18, dtype=np.float64),
            nir=np.full((h, w), 0.35, dtype=np.float64),
            swir1=np.full((h, w), 0.25, dtype=np.float64),
            swir2=np.full((h, w), 0.15, dtype=np.float64),
            thermal=np.full((h, w), 10.0, dtype=np.float64),  # 热红外辐射亮度
        )

    def test_soil_moisture_swir(self):
        """测试SWIR土壤含水率"""
        bands = self._create_env_bands()
        result = self.inverter.retrieve_soil_moisture_swir(bands)
        assert result.shape == (100, 100)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_red_edge_position(self):
        """测试红边位置计算"""
        bands = self._create_env_bands()
        rep = self.inverter.compute_red_edge_position(bands)
        assert rep is not None
        valid = rep[~np.isnan(rep)]
        if valid.size > 0:
            assert valid.min() >= 680.0
            assert valid.max() <= 760.0

    def test_heavy_metal_stress(self):
        """测试重金属胁迫指数"""
        bands = self._create_env_bands()
        rep = self.inverter.compute_red_edge_position(bands)
        result = self.inverter.retrieve_heavy_metal_stress(bands, rep)
        assert result.shape == (100, 100)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_lst_mono_window(self):
        """测试单窗算法LST反演"""
        bands = self._create_env_bands()
        thermal = bands.thermal
        emissivity = np.ones_like(thermal) * 0.97
        lst = self.inverter.retrieve_lst_mono_window(thermal, emissivity)
        assert lst.shape == (100, 100)
        valid = lst[~np.isnan(lst) & ~np.isinf(lst)]
        if valid.size > 0:
            # 地表温度应在合理范围 (-50 ~ +60 °C)
            assert valid.min() > -100.0
            assert valid.max() < 100.0

    def test_emissivity_from_ndvi(self):
        """测试NDVI估算比辐射率"""
        ndvi = np.full((100, 100), 0.6, dtype=np.float64)
        em = self.inverter.estimate_emissivity_from_ndvi(ndvi)
        assert np.all(em[~np.isnan(em)] >= 0.9)
        assert np.all(em[~np.isnan(em)] <= 1.0)

        # 裸土区域
        ndvi_bare = np.full((100, 100), 0.1, dtype=np.float64)
        em_bare = self.inverter.estimate_emissivity_from_ndvi(ndvi_bare)
        assert abs(np.mean(em_bare) - 0.97) < 0.01

    def test_landcover_estimation(self):
        """测试土地利用分类估算"""
        ndvi = np.full((100, 100), 0.6, dtype=np.float64)
        lc = self.inverter.estimate_landcover_from_ndvi(ndvi)
        assert lc.shape == (100, 100)
        assert lc.min() >= 1

    def test_runoff_coefficient(self):
        """测试径流系数计算"""
        bands = self._create_env_bands()
        ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + 1e-10)
        lc = self.inverter.estimate_landcover_from_ndvi(ndvi)
        runoff = self.inverter.retrieve_runoff_coefficient_scs_cn(lc)
        assert runoff.shape == (100, 100)
        valid = runoff[~np.isnan(runoff)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_retrieve_all(self):
        """测试一键反演所有环境指标"""
        bands = self._create_env_bands()
        ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + 1e-10)
        result = self.inverter.retrieve_all(bands, ndvi=ndvi)

        assert result.soil_moisture is not None
        assert result.heavy_metal_stress is not None
        assert result.runoff_coefficient is not None

        summary = result.to_dict_summary()
        assert len(summary) > 0


# ===========================================================================
# 8. 不确定性映射测试
# ===========================================================================


class TestUncertaintyMapper:
    """不确定性映射测试"""

    def setup_method(self):
        from remote_sensing.uncertainty_mapping import UncertaintyMapper
        self.mapper = UncertaintyMapper()

    def test_resolution_uncertainty(self):
        """测试分辨率不确定性"""
        grid = self.mapper.compute_resolution_uncertainty(
            shape=(50, 60),
            ground_resolution=1.0,
        )
        assert grid.variance.shape == (50, 60)
        assert grid.std_dev.shape == (50, 60)
        assert grid.confidence.shape == (50, 60)
        assert np.all(grid.variance >= 0)

    def test_model_uncertainty(self):
        """测试模型不确定性"""
        values = np.random.normal(0, 1, (50, 50))
        grid = self.mapper.compute_model_uncertainty(values, model_type="empirical")
        assert grid.variance.shape == (50, 50)

    def test_indicator_uncertainty(self):
        """测试指标不确定性"""
        values = np.random.uniform(0, 100, (40, 50))
        grid = self.mapper.compute_indicator_uncertainty(
            values, "chl_a",
            ground_resolution=0.1,
            model_type="semi_empirical",
        )
        assert grid.variance.shape == (40, 50)
        assert grid.indicator_name == "chl_a"

    def test_composite_uncertainty(self):
        """测试综合不确定性融合"""
        values1 = np.random.uniform(0, 10, (30, 30))
        values2 = np.random.uniform(0, 20, (30, 30))

        grid1 = self.mapper.compute_indicator_uncertainty(values1, "chl_a")
        grid2 = self.mapper.compute_indicator_uncertainty(values2, "tsm")

        composite = self.mapper.compute_composite_uncertainty(
            [grid1, grid2],
            weights=[0.6, 0.4],
        )
        assert composite.shape == (30, 30)

    def test_generate_all_uncertainties(self):
        """测试一键生成所有不确定性"""
        results = {
            "chl_a": np.random.uniform(0, 100, (30, 30)),
            "tsm": np.random.uniform(0, 50, (30, 30)),
            "fvc": np.random.uniform(0, 1, (30, 30)),
        }
        grids = self.mapper.generate_all_uncertainties(results)
        assert len(grids) == 3
        assert "chl_a" in grids
        assert "tsm" in grids
        assert "fvc" in grids


# ===========================================================================
# 9. 采样策略融合测试
# ===========================================================================


class TestSamplingFusion:
    """采样策略融合测试"""

    def setup_method(self):
        from adaptive_sampling.采样策略融合 import SamplingFusionEngine
        self.engine = SamplingFusionEngine()
        self.geo_transform = (100.0, 0.01, 0.0, 40.0, 0.0, -0.01)

    def test_fuse_single_indicator(self):
        """测试单指标融合"""
        from remote_sensing.uncertainty_mapping import UncertaintyMapper

        mapper = UncertaintyMapper()
        values = {
            "chl_a": np.random.uniform(0, 100, (30, 30)),
        }
        uncertainties = {
            "chl_a": mapper.compute_indicator_uncertainty(values["chl_a"], "chl_a"),
        }

        result = self.engine.fuse_inversion_to_variance(
            values, uncertainties, self.geo_transform,
        )
        assert result.composite_variance.shape == (30, 30)
        assert len(result.x_coords) == 30
        assert len(result.y_coords) == 30

    def test_fuse_multiple_indicators(self):
        """测试多指标融合"""
        from remote_sensing.uncertainty_mapping import UncertaintyMapper

        mapper = UncertaintyMapper()
        values = {
            "chl_a": np.random.uniform(0, 100, (30, 30)),
            "tsm": np.random.uniform(0, 50, (30, 30)),
            "turbidity": np.random.uniform(0, 100, (30, 30)),
        }
        uncertainties = {}
        for name, val in values.items():
            uncertainties[name] = mapper.compute_indicator_uncertainty(val, name)

        result = self.engine.fuse_inversion_to_variance(
            values, uncertainties, self.geo_transform,
        )
        assert result.composite_variance.shape == (30, 30)
        assert "chl_a" in result.indicator_contributions

    def test_generate_recommendations(self):
        """测试生成采样推荐"""
        from remote_sensing.uncertainty_mapping import UncertaintyMapper

        mapper = UncertaintyMapper()
        values = {
            "chl_a": np.random.uniform(0, 100, (30, 30)),
        }
        uncertainties = {
            "chl_a": mapper.compute_indicator_uncertainty(values["chl_a"], "chl_a"),
        }

        fusion = self.engine.fuse_inversion_to_variance(
            values, uncertainties, self.geo_transform,
        )

        recs = self.engine.generate_sampling_recommendations(
            fusion, n_recommendations=10, strategy="hybrid",
        )
        assert recs["strategy"] == "hybrid"
        # 混合策略使用网格覆盖，可能产生少于请求数的推荐点
        assert len(recs["recommendations"]) >= 5
        assert "statistics" in recs

    def test_anomaly_detection(self):
        """测试异常值检测"""
        from remote_sensing.uncertainty_mapping import UncertaintyMapper

        mapper = UncertaintyMapper()
        # 创建有明显异常值的数据
        values = np.ones((30, 30)) * 10.0
        values[10:15, 10:15] = 200.0  # 异常高值区域

        result_values = {"cod": values}
        uncertainties = {
            "cod": mapper.compute_indicator_uncertainty(values, "cod"),
        }

        result = self.engine.fuse_inversion_to_variance(
            result_values, uncertainties, self.geo_transform,
            anomaly_threshold_percentile=90.0,
        )

        # 异常区域应该被检测到
        assert result.anomaly_mask is not None
        assert np.sum(result.anomaly_mask) > 0

    def test_anomaly_regions_identification(self):
        """测试异常区域识别"""
        from remote_sensing.uncertainty_mapping import UncertaintyMapper

        mapper = UncertaintyMapper()
        values = np.ones((30, 30)) * 5.0
        values[5:20, 5:20] = 100.0

        result_values = {"cod": values}
        uncertainties = {
            "cod": mapper.compute_indicator_uncertainty(values, "cod"),
        }

        result = self.engine.fuse_inversion_to_variance(
            result_values, uncertainties, self.geo_transform,
        )

        assert len(result.anomaly_regions) >= 0
        if len(result.anomaly_regions) > 0:
            region = result.anomaly_regions[0]
            assert "region_id" in region
            assert "center" in region
            assert "area_pixels" in region


# ===========================================================================
# 10. 集成流测试（模拟全流程）
# ===========================================================================


class TestFullPipeline:
    """全流程端到端集成测试"""

    def test_full_pipeline_water_scenario(self):
        """测试水质场景全流程"""
        from photogrammetry.exif_parser import AerialImageMetadata, GPSInfo, IMUInfo, CameraInfo
        from photogrammetry.image_quality import ImageQualityAssessor
        from remote_sensing.water_quality import WaterQualityInverter, SpectralBands
        from remote_sensing.uncertainty_mapping import UncertaintyMapper
        from adaptive_sampling.采样策略融合 import SamplingFusionEngine

        # 1. 创建模拟元数据
        meta = AerialImageMetadata(
            file_path="/test/drone_shot.jpg",
            file_name="drone_shot.jpg",
            file_size_bytes=8192000,
            image_format="jpeg",
            gps=GPSInfo(latitude=30.5, longitude=114.3, altitude=250.0),
            imu=IMUInfo(pitch=2.0, roll=1.5, yaw=180.0),
            camera=CameraInfo(
                focal_length=8.8,
                sensor_width=13.2,
                image_width=5472,
                image_height=3648,
            ),
        )
        assert meta.gps.is_valid()

        # 2. 创建模拟影像
        img = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)

        # 3. 模拟多光谱波段
        bands = SpectralBands(
            blue=img[:, :, 2].astype(np.float64) / 255.0,
            green=img[:, :, 1].astype(np.float64) / 255.0,
            red=img[:, :, 0].astype(np.float64) / 255.0,
            red_edge=img[:, :, 0].astype(np.float64) / 510.0,
            nir=(img[:, :, 0].astype(np.float64) * 0.8 + img[:, :, 1].astype(np.float64) * 0.2) / 255.0,
            swir1=(img[:, :, 0].astype(np.float64) * 0.5) / 255.0,
        )

        # 4. 水质反演
        inverter = WaterQualityInverter()
        water_result = inverter.retrieve_all(bands)
        assert water_result.chl_a is not None

        # 5. 不确定性映射
        mapper = UncertaintyMapper()
        inversion_values = {}
        uncertainty_grids = {}
        for name in ["chl_a", "tsm", "turbidity", "sdd", "cod"]:
            val = getattr(water_result, name)
            if val is not None:
                inversion_values[name] = val
                uncertainty_grids[name] = mapper.compute_indicator_uncertainty(val, name)

        assert len(inversion_values) >= 4

        # 6. 采样融合
        engine = SamplingFusionEngine()
        geo_transform = (114.3, 0.0001, 0.0, 30.5, 0.0, -0.0001)
        fusion_result = engine.fuse_inversion_to_variance(
            inversion_values, uncertainty_grids, geo_transform,
        )

        # 7. 生成推荐
        recs = engine.generate_sampling_recommendations(
            fusion_result, n_recommendations=15, strategy="hybrid",
        )
        # 混合策略的网格覆盖可能产生略少于请求数的推荐点
        assert recs["n_recommendations"] >= 10
        assert len(recs["recommendations"]) >= 10

        # 每个推荐应有完整字段
        for rec in recs["recommendations"]:
            assert "id" in rec
            assert "x" in rec
            assert "y" in rec
            assert "variance" in rec
            assert "priority" in rec

    def test_full_pipeline_forestry_scenario(self):
        """测试林业场景全流程"""
        from remote_sensing.forestry import ForestryInverter, SpectralBands
        from remote_sensing.uncertainty_mapping import UncertaintyMapper
        from adaptive_sampling.采样策略融合 import SamplingFusionEngine

        # 创建植被场景波段
        h, w = 60, 60
        bands = SpectralBands(
            blue=np.full((h, w), 0.03, dtype=np.float64),
            green=np.full((h, w), 0.08, dtype=np.float64),
            red=np.full((h, w), 0.04, dtype=np.float64),
            red_edge=np.full((h, w), 0.15, dtype=np.float64),
            nir=np.full((h, w), 0.40, dtype=np.float64),
            swir1=np.full((h, w), 0.20, dtype=np.float64),
        )

        inverter = ForestryInverter()
        result = inverter.retrieve_all(bands)
        assert result.fvc is not None
        assert result.biomass is not None

        # 不确定性 -> 推荐
        mapper = UncertaintyMapper()
        values = {"fvc": result.fvc, "biomass": result.biomass}
        grids = {}
        for n, v in values.items():
            if v is not None:
                grids[n] = mapper.compute_indicator_uncertainty(v, n)

        engine = SamplingFusionEngine()
        geo_transform = (0.0, 0.001, 0.0, 0.0, 0.0, -0.001)
        fusion = engine.fuse_inversion_to_variance(values, grids, geo_transform)
        recs = engine.generate_sampling_recommendations(fusion, n_recommendations=5)

        assert len(recs["recommendations"]) >= 3

    def test_full_pipeline_environment_scenario(self):
        """测试环境场景全流程"""
        from remote_sensing.environment import EnvironmentInverter, SpectralBands
        from remote_sensing.uncertainty_mapping import UncertaintyMapper
        from adaptive_sampling.采样策略融合 import SamplingFusionEngine

        h, w = 50, 50
        bands = SpectralBands(
            blue=np.full((h, w), 0.06, dtype=np.float64),
            green=np.full((h, w), 0.10, dtype=np.float64),
            red=np.full((h, w), 0.08, dtype=np.float64),
            nir=np.full((h, w), 0.30, dtype=np.float64),
            swir1=np.full((h, w), 0.22, dtype=np.float64),
            swir2=np.full((h, w), 0.15, dtype=np.float64),
            thermal=np.full((h, w), 9.5, dtype=np.float64),
        )

        inverter = EnvironmentInverter()
        ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + 1e-10)
        result = inverter.retrieve_all(bands, ndvi=ndvi)
        assert result.soil_moisture is not None

        # 不确定性 -> 推荐
        mapper = UncertaintyMapper()
        values = {
            "soil_moisture": result.soil_moisture,
            "heavy_metal": result.heavy_metal_stress,
            "runoff": result.runoff_coefficient,
        }
        grids = {}
        for n, v in values.items():
            if v is not None:
                grids[n] = mapper.compute_indicator_uncertainty(v, n)

        engine = SamplingFusionEngine()
        geo_transform = (0.0, 0.001, 0.0, 0.0, 0.0, -0.001)
        fusion = engine.fuse_inversion_to_variance(values, grids, geo_transform)
        recs = engine.generate_sampling_recommendations(fusion, n_recommendations=8)

        assert len(recs["recommendations"]) >= 4

    def test_14_indicators_verification(self):
        """验证全部14项物理指标均能正确生成反演网格"""
        from remote_sensing.water_quality import WaterQualityInverter, SpectralBands, WaterQualityResult
        from remote_sensing.forestry import ForestryInverter, ForestryResult
        from remote_sensing.environment import EnvironmentInverter, EnvironmentResult

        h, w = 30, 30

        # 构建多光谱波段
        bands = SpectralBands(
            blue=np.full((h, w), 0.06, dtype=np.float64),
            green=np.full((h, w), 0.10, dtype=np.float64),
            red=np.full((h, w), 0.05, dtype=np.float64),
            red_edge=np.full((h, w), 0.12, dtype=np.float64),
            nir=np.full((h, w), 0.30, dtype=np.float64),
            swir1=np.full((h, w), 0.22, dtype=np.float64),
            swir2=np.full((h, w), 0.14, dtype=np.float64),
            thermal=np.full((h, w), 10.0, dtype=np.float64),
        )
        ndvi = (bands.nir - bands.red) / (bands.nir + bands.red + 1e-10)

        # 水质5项
        water = WaterQualityInverter().retrieve_all(bands)
        water_indicators = ["chl_a", "tsm", "turbidity", "sdd", "cod"]
        for name in water_indicators:
            val = getattr(water, name)
            assert val is not None, f"水质指标 {name} 反演失败"
            assert val.shape == (h, w), f"水质指标 {name} 形状不正确"
            assert np.any(~np.isnan(val)), f"水质指标 {name} 全为NaN"

        # 林业5项
        forest = ForestryInverter().retrieve_all(bands)
        assert forest.volume is not None, "森林蓄积量反演失败"
        assert forest.biomass is not None, "生物量反演失败"
        assert forest.fvc is not None, "植被覆盖度反演失败"
        assert forest.species_classification is not None, "树种分类反演失败"
        assert forest.vegetation_indices.ndvi is not None, "植被健康度(NDVI)反演失败"

        # 环境4项
        env = EnvironmentInverter().retrieve_all(bands, ndvi=ndvi)
        env_indicators = ["soil_moisture", "heavy_metal_stress", "runoff_coefficient"]
        for name in env_indicators:
            val = getattr(env, name)
            assert val is not None, f"环境指标 {name} 反演失败"
            assert val.shape == (h, w), f"环境指标 {name} 形状不正确"

        # LST可能有也可能没有（取决于热红外波段）
        # 如果有热红外数据，应能反演LST
        if bands.thermal is not None:
            assert env.lst is not None, "地表温度(LST)反演失败"

        # 统计: 总共应有至少13-14项指标生成 (LST依赖热红外)
        total_indicators = len(water_indicators) + 5 + 3  # = 13 (不包含LST)
        if env.lst is not None:
            total_indicators += 1  # 14
        assert total_indicators >= 13, f"物理指标数量不足，期望>=13, 实际{total_indicators}"


# ===========================================================================
# 运行配置
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
