"""
3D克里金系统测试
覆盖：变异函数、距离计算、普通克里金、泛克里金、指示克里金、数据处理、API接口
"""
import pytest
import numpy as np
import json
from pathlib import Path


# ============================================================
# 测试数据生成
# ============================================================

def generate_3d_test_data(n=50, seed=42):
    """生成3D测试数据：带空间相关性的随机场"""
    rng = np.random.RandomState(seed)
    x = rng.uniform(0, 10, n)
    y = rng.uniform(0, 10, n)
    z = rng.uniform(0, 5, n)
    # 带趋势和噪声的值
    values = 2.0 * x + 1.5 * y - 0.5 * z + rng.normal(0, 0.5, n)
    points = np.column_stack([x, y, z])
    return points, values


def generate_3d_geojson(n=30, seed=42):
    """生成3D GeoJSON测试数据"""
    rng = np.random.RandomState(seed)
    features = []
    for i in range(n):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(rng.uniform(100, 110)),
                    float(rng.uniform(30, 40)),
                    float(rng.uniform(0, 100))
                ]
            },
            "properties": {
                "value": float(rng.uniform(0, 50)),
                "label": f"P{i}"
            }
        })
    return {"type": "FeatureCollection", "features": features}


# ============================================================
# 距离计算测试
# ============================================================

class TestDistance3D:
    """3D距离计算测试"""

    def test_euclidean_basic(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        p1 = np.array([0, 0, 0])
        p2 = np.array([3, 4, 0])
        d = Distance3D.euclidean(p1, p2)
        assert abs(d - 5.0) < 1e-10

    def test_euclidean_3d(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        p1 = np.array([1, 2, 3])
        p2 = np.array([4, 6, 3])
        d = Distance3D.euclidean(p1, p2)
        assert abs(d - 5.0) < 1e-10

    def test_euclidean_matrix_symmetry(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
        dist = Distance3D.euclidean_matrix(points)
        assert dist.shape == (4, 4)
        # 对称性
        np.testing.assert_array_almost_equal(dist, dist.T)
        # 对角线为0
        np.testing.assert_array_almost_equal(np.diag(dist), np.zeros(4))

    def test_euclidean_matrix_values(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        dist = Distance3D.euclidean_matrix(points)
        assert abs(dist[0, 1] - 1.0) < 1e-10
        assert abs(dist[0, 2] - 1.0) < 1e-10
        assert abs(dist[1, 2] - np.sqrt(2)) < 1e-10

    def test_anisotropic_matrix(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
        dist_iso = Distance3D.euclidean_matrix(points)
        dist_aniso = Distance3D.anisotropic_matrix(points, ratio_xy=2.0, ratio_xz=1.0)
        # 各向异性距离应与各向同性不同
        assert not np.allclose(dist_iso, dist_aniso)
        # 仍然对称
        np.testing.assert_array_almost_equal(dist_aniso, dist_aniso.T)

    def test_directional_distance(self):
        from app.kriging_3d.core.距离计算 import Distance3D
        points = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
            [2, 0, 0], [0, 2, 0]
        ])
        dist, mask = Distance3D.directional_distance(
            points, azimuth=90, dip=0, tolerance=30
        )
        # 应该有一些有效的点对
        assert mask.sum() > 0
        assert dist.shape == (6, 6)


# ============================================================
# 变异函数测试
# ============================================================

class TestVariogram3D:
    """3D变异函数测试"""

    def test_spherical_model(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        h = np.array([0, 1, 2, 3, 5, 10])
        gamma = Variogram3D.spherical(h, nugget=0.1, sill=1.0, range_=5.0)
        assert gamma[0] == 0.0  # h=0时为0
        assert abs(gamma[-1] - 1.0) < 1e-10  # h>=range时为sill
        # 单调递增
        for i in range(1, len(gamma)):
            assert gamma[i] >= gamma[i - 1]

    def test_exponential_model(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        h = np.array([0, 1, 5, 10, 50])
        gamma = Variogram3D.exponential(h, nugget=0.0, sill=1.0, range_=5.0)
        assert gamma[0] == 0.0
        assert gamma[-1] > 0.99  # 渐近趋近sill

    def test_gaussian_model(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        h = np.array([0, 1, 5, 10, 50])
        gamma = Variogram3D.gaussian(h, nugget=0.0, sill=1.0, range_=5.0)
        assert gamma[0] == 0.0
        assert gamma[-1] > 0.99

    def test_linear_model(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        h = np.array([0, 2.5, 5, 10])
        gamma = Variogram3D.linear(h, nugget=0.0, sill=1.0, range_=5.0)
        assert gamma[0] == 0.0
        assert abs(gamma[1] - 0.5) < 1e-10  # 线性中点
        assert abs(gamma[2] - 1.0) < 1e-10  # range处为sill
        assert abs(gamma[3] - 1.0) < 1e-10  # 超过range仍为sill

    def test_compute_experimental(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        points, values = generate_3d_test_data(100)
        lags, sv, counts = Variogram3D.compute_experimental(points, values, nlags=10)
        assert len(lags) == 10
        assert len(sv) == 10
        assert len(counts) == 10
        assert all(c >= 0 for c in counts)

    def test_fit_variogram(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        points, values = generate_3d_test_data(100)
        lags, sv, counts = Variogram3D.compute_experimental(points, values, nlags=10)
        result = Variogram3D.fit(lags, sv, "spherical", counts)
        assert "nugget" in result
        assert "sill" in result
        assert "range" in result
        assert "r_squared" in result
        assert result["nugget"] >= 0
        assert result["sill"] >= 0
        assert result["range"] > 0

    def test_auto_fit(self):
        from app.kriging_3d.core.变异函数3D import Variogram3D
        points, values = generate_3d_test_data(100)
        result = Variogram3D.auto_fit(points, values, nlags=10)
        assert result["model_type"] in ["spherical", "exponential", "gaussian", "linear"]
        assert "r_squared" in result


# ============================================================
# 3D普通克里金测试
# ============================================================

class TestOrdinaryKriging3D:
    """3D普通克里金测试"""

    def test_basic_interpolation(self):
        from app.kriging_3d.core.普通克里金3D import OrdinaryKriging3D
        points, values = generate_3d_test_data(30)
        grid_x = np.linspace(0, 10, 5)
        grid_y = np.linspace(0, 10, 5)
        grid_z = np.linspace(0, 5, 3)

        ok3d = OrdinaryKriging3D()
        result = ok3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                  variogram_model="spherical", nlags=8, n_closest=10)

        assert "prediction" in result
        assert "variance" in result
        assert "variogram" in result
        assert result["prediction"].shape == (5, 5, 3)
        assert result["variance"].shape == (5, 5, 3)

    def test_prediction_within_range(self):
        from app.kriging_3d.core.普通克里金3D import OrdinaryKriging3D
        points, values = generate_3d_test_data(40)
        grid_x = np.linspace(0, 10, 4)
        grid_y = np.linspace(0, 10, 4)
        grid_z = np.linspace(0, 5, 3)

        ok3d = OrdinaryKriging3D()
        result = ok3d.interpolate(points, values, grid_x, grid_y, grid_z, n_closest=12)
        pred = result["prediction"]
        assert pred.min() > values.min() - 3 * values.std()
        assert pred.max() < values.max() + 3 * values.std()

    def test_variance_non_negative(self):
        from app.kriging_3d.core.普通克里金3D import OrdinaryKriging3D
        points, values = generate_3d_test_data(30)
        grid_x = np.linspace(0, 10, 4)
        grid_y = np.linspace(0, 10, 4)
        grid_z = np.linspace(0, 5, 3)

        ok3d = OrdinaryKriging3D()
        result = ok3d.interpolate(points, values, grid_x, grid_y, grid_z, n_closest=10)
        assert np.all(result["variance"] >= 0)

    def test_different_variogram_models(self):
        from app.kriging_3d.core.普通克里金3D import OrdinaryKriging3D
        points, values = generate_3d_test_data(30)
        grid_x = np.linspace(0, 10, 3)
        grid_y = np.linspace(0, 10, 3)
        grid_z = np.linspace(0, 5, 2)

        ok3d = OrdinaryKriging3D()
        for model in ["spherical", "exponential", "gaussian"]:
            result = ok3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                      variogram_model=model, n_closest=10)
            assert result["prediction"].shape == (3, 3, 2)


# ============================================================
# 3D泛克里金测试
# ============================================================

class TestUniversalKriging3D:
    """3D泛克里金测试"""

    def test_basic_interpolation(self):
        from app.kriging_3d.core.泛克里金3D import UniversalKriging3D
        points, values = generate_3d_test_data(40)
        grid_x = np.linspace(0, 10, 4)
        grid_y = np.linspace(0, 10, 4)
        grid_z = np.linspace(0, 5, 3)

        uk3d = UniversalKriging3D()
        result = uk3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                  drift_terms=["regional_linear"], n_closest=12)

        assert "prediction" in result
        assert "variance" in result
        assert "trend_coefficients" in result
        assert result["prediction"].shape == (4, 4, 3)

    def test_trend_detection(self):
        from app.kriging_3d.core.泛克里金3D import UniversalKriging3D
        rng = np.random.RandomState(42)
        n = 50
        points = rng.uniform(0, 10, (n, 3))
        values = 3.0 * points[:, 0] + 2.0 * points[:, 1] + rng.normal(0, 0.1, n)

        grid_x = np.linspace(0, 10, 3)
        grid_y = np.linspace(0, 10, 3)
        grid_z = np.linspace(0, 10, 2)

        uk3d = UniversalKriging3D()
        result = uk3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                  drift_terms=["regional_linear"], n_closest=15)
        assert len(result["trend_coefficients"]) > 0


# ============================================================
# 3D指示克里金测试
# ============================================================

class TestIndicatorKriging3D:
    """3D指示克里金测试"""

    def test_basic_interpolation(self):
        from app.kriging_3d.core.指示克里金3D import IndicatorKriging3D
        points, values = generate_3d_test_data(40)
        threshold = float(np.median(values))
        grid_x = np.linspace(0, 10, 4)
        grid_y = np.linspace(0, 10, 4)
        grid_z = np.linspace(0, 5, 3)

        ik3d = IndicatorKriging3D()
        result = ik3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                  threshold=threshold, n_closest=12)

        assert "probability" in result
        assert "variance" in result
        assert result["probability"].shape == (4, 4, 3)

    def test_probability_range(self):
        from app.kriging_3d.core.指示克里金3D import IndicatorKriging3D
        points, values = generate_3d_test_data(40)
        threshold = float(np.median(values))
        grid_x = np.linspace(0, 10, 4)
        grid_y = np.linspace(0, 10, 4)
        grid_z = np.linspace(0, 5, 3)

        ik3d = IndicatorKriging3D()
        result = ik3d.interpolate(points, values, grid_x, grid_y, grid_z,
                                  threshold=threshold, n_closest=12)
        prob = result["probability"]
        assert np.all(prob >= 0.0)
        assert np.all(prob <= 1.0)


# ============================================================
# 3D数据处理测试
# ============================================================

class TestDataProcessor3D:
    """3D数据处理器测试"""

    def test_parse_geojson_3d(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        processor = DataProcessor3D()
        geojson = generate_3d_geojson(20)
        data = processor.parse_geojson_3d(geojson)
        assert len(data.points) == 20
        assert all(hasattr(p, 'z') for p in data.points)

    def test_parse_csv_3d(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        processor = DataProcessor3D()
        csv_content = "x,y,z,value\n1.0,2.0,3.0,10.0\n4.0,5.0,6.0,20.0\n7.0,8.0,9.0,30.0"
        data = processor.parse_csv_3d(csv_content)
        assert len(data.points) == 3
        assert data.points[0].x == 1.0
        assert data.points[0].z == 3.0

    def test_parse_borehole_data(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        processor = DataProcessor3D()
        borehole_data = {
            "boreholes": [
                {
                    "id": "BH1", "x": 100.0, "y": 200.0,
                    "samples": [
                        {"depth": 0, "value": 10},
                        {"depth": 5, "value": 15},
                        {"depth": 10, "value": 20}
                    ]
                },
                {
                    "id": "BH2", "x": 150.0, "y": 250.0,
                    "samples": [
                        {"depth": 0, "value": 12},
                        {"depth": 5, "value": 18}
                    ]
                }
            ]
        }
        data = processor.parse_borehole_data(borehole_data)
        assert len(data.points) == 5
        assert data.points[0].label == "BH1"

    def test_clean_data(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        points = [
            Point3D(x=1, y=2, z=3, value=10),
            Point3D(x=1, y=2, z=3, value=10),  # 重复
            Point3D(x=4, y=5, z=6, value=float('nan')),  # NaN
            Point3D(x=7, y=8, z=9, value=30),
        ]
        data = SpatialData3D(points=points)
        cleaned = processor.clean_data(data)
        assert len(cleaned.points) == 2

    def test_detect_outliers_iqr(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        rng = np.random.RandomState(42)
        points = [Point3D(x=float(i), y=0, z=0, value=float(rng.normal(10, 1))) for i in range(50)]
        points.append(Point3D(x=50, y=0, z=0, value=100.0))  # 异常值
        data = SpatialData3D(points=points)
        cleaned, outliers = processor.detect_outliers(data, method="iqr")
        assert len(outliers) >= 1
        assert len(cleaned.points) < len(data.points)

    def test_normalize_coordinates(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        points = [
            Point3D(x=0, y=0, z=0, value=1),
            Point3D(x=10, y=20, z=5, value=2),
        ]
        data = SpatialData3D(points=points)
        normed, transform = processor.normalize_coordinates(data)
        assert normed.points[0].x == 0.0
        assert normed.points[1].x == 1.0
        assert "min_x" in transform

    def test_vertical_layers(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        rng = np.random.RandomState(42)
        points = [Point3D(x=float(rng.uniform(0, 10)), y=float(rng.uniform(0, 10)),
                          z=float(rng.uniform(0, 100)), value=float(rng.normal(10, 2)))
                  for _ in range(100)]
        data = SpatialData3D(points=points)
        layers = processor.vertical_layers(data, n_layers=5)
        assert len(layers) <= 5
        total = sum(len(l.points) for l in layers.values())
        assert total == 100

    def test_downsample_grid(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        rng = np.random.RandomState(42)
        points = [Point3D(x=float(rng.uniform(0, 10)), y=float(rng.uniform(0, 10)),
                          z=float(rng.uniform(0, 5)), value=float(rng.normal(10, 2)))
                  for _ in range(200)]
        data = SpatialData3D(points=points)
        downsampled = processor.downsample_grid(data, cell_size=2.0)
        assert len(downsampled.points) < len(data.points)

    def test_get_bounds(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        points = [
            Point3D(x=1, y=2, z=3, value=10),
            Point3D(x=10, y=20, z=30, value=20),
        ]
        data = SpatialData3D(points=points)
        bounds = processor.get_bounds(data)
        assert bounds.min_x == 1
        assert bounds.max_z == 30

    def test_get_statistics(self):
        from app.kriging_3d.services.数据处理3D import DataProcessor3D
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        processor = DataProcessor3D()
        points = [Point3D(x=float(i), y=float(i), z=float(i), value=float(i * 10))
                  for i in range(10)]
        data = SpatialData3D(points=points)
        stats = processor.get_statistics(data)
        assert stats["point_count"] == 10
        assert "value_stats" in stats
        assert stats["value_stats"]["min"] == 0.0
        assert stats["value_stats"]["max"] == 90.0


# ============================================================
# 3D调度器测试
# ============================================================

class TestKrigingScheduler3D:
    """3D克里金调度器测试"""

    def _make_spatial_data(self, n=30):
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        rng = np.random.RandomState(42)
        points = [
            Point3D(
                x=float(rng.uniform(0, 10)),
                y=float(rng.uniform(0, 10)),
                z=float(rng.uniform(0, 5)),
                value=float(rng.normal(10, 2))
            )
            for _ in range(n)
        ]
        return SpatialData3D(points=points)

    def test_ordinary_dispatch(self):
        from app.kriging_3d.core.调度器3D import KrigingScheduler3D
        from app.kriging_3d.schemas.参数模型 import KrigingParameters3D
        scheduler = KrigingScheduler3D()
        data = self._make_spatial_data(30)
        params = KrigingParameters3D(
            data_id="test",
            method="ordinary",
            grid_resolution_x=4,
            grid_resolution_y=4,
            grid_resolution_z=3,
            nlags=8,
            n_closest=10
        )
        result = scheduler.execute("test-ok", data, params)
        assert "prediction" in result
        assert result["method"] == "ordinary"
        assert result["grid_shape"] == [4, 4, 3]

    def test_universal_dispatch(self):
        from app.kriging_3d.core.调度器3D import KrigingScheduler3D
        from app.kriging_3d.schemas.参数模型 import KrigingParameters3D
        scheduler = KrigingScheduler3D()
        data = self._make_spatial_data(40)
        params = KrigingParameters3D(
            data_id="test",
            method="universal",
            grid_resolution_x=3,
            grid_resolution_y=3,
            grid_resolution_z=2,
            nlags=8,
            n_closest=12,
            drift_terms=["regional_linear"]
        )
        result = scheduler.execute("test-uk", data, params)
        assert "prediction" in result
        assert result["method"] == "universal"

    def test_indicator_dispatch(self):
        from app.kriging_3d.core.调度器3D import KrigingScheduler3D
        from app.kriging_3d.schemas.参数模型 import KrigingParameters3D
        scheduler = KrigingScheduler3D()
        data = self._make_spatial_data(40)
        params = KrigingParameters3D(
            data_id="test",
            method="indicator",
            grid_resolution_x=3,
            grid_resolution_y=3,
            grid_resolution_z=2,
            nlags=8,
            n_closest=12,
            indicator_threshold=10.0
        )
        result = scheduler.execute("test-ik", data, params)
        assert "probability" in result
        assert result["method"] == "indicator"


# ============================================================
# Pydantic模型测试
# ============================================================

class TestSchemas:
    """数据模型验证测试"""

    def test_point3d(self):
        from app.kriging_3d.schemas.数据模型 import Point3D
        p = Point3D(x=1.0, y=2.0, z=3.0, value=10.0)
        assert p.x == 1.0
        assert p.z == 3.0

    def test_spatial_data_3d(self):
        from app.kriging_3d.schemas.数据模型 import SpatialData3D, Point3D
        points = [Point3D(x=i, y=i, z=i, value=i * 10) for i in range(5)]
        data = SpatialData3D(points=points)
        assert len(data.points) == 5
        assert data.crs == "EPSG:4326"

    def test_kriging_parameters_3d_defaults(self):
        from app.kriging_3d.schemas.参数模型 import KrigingParameters3D
        params = KrigingParameters3D(data_id="test123")
        assert params.method.value == "ordinary"
        assert params.variogram_model.value == "spherical"
        assert params.grid_resolution_x == 50
        assert params.grid_resolution_z == 20
        assert params.n_closest == 16

    def test_kriging_parameters_3d_custom(self):
        from app.kriging_3d.schemas.参数模型 import KrigingParameters3D
        params = KrigingParameters3D(
            data_id="test",
            method="indicator",
            variogram_model="gaussian",
            grid_resolution_x=30,
            grid_resolution_y=30,
            grid_resolution_z=10,
            indicator_threshold=5.0
        )
        assert params.method.value == "indicator"
        assert params.indicator_threshold == 5.0

    def test_anisotropy_params(self):
        from app.kriging_3d.schemas.参数模型 import AnisotropyParams
        aniso = AnisotropyParams(ratio_xy=2.0, ratio_xz=1.5, angle_xy=45.0)
        assert aniso.ratio_xy == 2.0
        assert aniso.angle_xy == 45.0

    def test_slice_params(self):
        from app.kriging_3d.schemas.参数模型 import SliceParams
        sp = SliceParams(axis="z", position=5.0)
        assert sp.axis == "z"
        assert sp.resolution == 100

    def test_bounding_box_3d(self):
        from app.kriging_3d.schemas.数据模型 import BoundingBox3D
        bb = BoundingBox3D(min_x=0, min_y=0, min_z=0, max_x=10, max_y=10, max_z=5)
        assert bb.max_z == 5


# ============================================================
# API接口测试
# ============================================================

class TestKriging3DAPI:
    """3D克里金API接口测试"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_upload_3d_geojson(self, client, tmp_path):
        geojson = generate_3d_geojson(15)
        file_path = tmp_path / "test_3d.geojson"
        file_path.write_text(json.dumps(geojson))

        with open(file_path, "rb") as f:
            resp = client.post("/api/kriging3d/upload", files={"file": ("test_3d.geojson", f, "application/json")})
        assert resp.status_code == 200
        data = resp.json()
        assert "data_id" in data
        assert data["point_count"] == 15

    def test_upload_3d_csv(self, client, tmp_path):
        csv_content = "x,y,z,value\n1,2,3,10\n4,5,6,20\n7,8,9,30\n10,11,12,40"
        file_path = tmp_path / "test_3d.csv"
        file_path.write_text(csv_content)

        with open(file_path, "rb") as f:
            resp = client.post("/api/kriging3d/upload", files={"file": ("test_3d.csv", f, "text/csv")})
        assert resp.status_code == 200
        assert resp.json()["point_count"] == 4

    def test_upload_borehole_data(self, client, tmp_path):
        borehole = {
            "boreholes": [
                {"id": "BH1", "x": 100, "y": 200, "samples": [
                    {"depth": 0, "value": 10}, {"depth": 5, "value": 15}
                ]},
                {"id": "BH2", "x": 150, "y": 250, "samples": [
                    {"depth": 0, "value": 12}
                ]}
            ]
        }
        file_path = tmp_path / "boreholes.json"
        file_path.write_text(json.dumps(borehole))

        with open(file_path, "rb") as f:
            resp = client.post("/api/kriging3d/upload", files={"file": ("boreholes.json", f, "application/json")})
        assert resp.status_code == 200
        assert resp.json()["point_count"] == 3

    def test_start_kriging3d(self, client, tmp_path):
        # 先上传数据
        geojson = generate_3d_geojson(20)
        file_path = tmp_path / "test.geojson"
        file_path.write_text(json.dumps(geojson))
        with open(file_path, "rb") as f:
            upload_resp = client.post("/api/kriging3d/upload", files={"file": ("test.geojson", f, "application/json")})
        data_id = upload_resp.json()["data_id"]

        # 启动插值
        resp = client.post("/api/kriging3d/start", json={
            "data_id": data_id,
            "method": "ordinary",
            "grid_resolution_x": 3,
            "grid_resolution_y": 3,
            "grid_resolution_z": 2,
            "nlags": 8,
            "n_closest": 10
        })
        assert resp.status_code == 200
        result = resp.json()
        assert "task_id" in result
        assert result["status"] == "pending"

    def test_get_status_not_found(self, client):
        resp = client.get("/api/kriging3d/status/nonexistent-id")
        assert resp.status_code == 404

    def test_get_data_stats(self, client, tmp_path):
        geojson = generate_3d_geojson(10)
        file_path = tmp_path / "stats_test.geojson"
        file_path.write_text(json.dumps(geojson))
        with open(file_path, "rb") as f:
            upload_resp = client.post("/api/kriging3d/upload", files={"file": ("stats_test.geojson", f, "application/json")})
        data_id = upload_resp.json()["data_id"]

        resp = client.get(f"/api/kriging3d/data/{data_id}/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["point_count"] == 10
        assert "value_stats" in stats

    def test_preprocess_data(self, client, tmp_path):
        geojson = generate_3d_geojson(25)
        file_path = tmp_path / "preprocess_test.geojson"
        file_path.write_text(json.dumps(geojson))
        with open(file_path, "rb") as f:
            upload_resp = client.post("/api/kriging3d/upload", files={"file": ("preprocess_test.geojson", f, "application/json")})
        data_id = upload_resp.json()["data_id"]

        resp = client.post(f"/api/kriging3d/data/{data_id}/preprocess?remove_outliers=true")
        assert resp.status_code == 200
        result = resp.json()
        assert "data_id" in result
        assert result["message"] == "预处理完成"

    def test_get_layers(self, client, tmp_path):
        geojson = generate_3d_geojson(30)
        file_path = tmp_path / "layers_test.geojson"
        file_path.write_text(json.dumps(geojson))
        with open(file_path, "rb") as f:
            upload_resp = client.post("/api/kriging3d/upload", files={"file": ("layers_test.geojson", f, "application/json")})
        data_id = upload_resp.json()["data_id"]

        resp = client.post(f"/api/kriging3d/data/{data_id}/layers?n_layers=3")
        assert resp.status_code == 200
        result = resp.json()
        assert "layer_count" in result
        assert result["layer_count"] <= 3

    def test_upload_invalid_format(self, client, tmp_path):
        file_path = tmp_path / "bad.json"
        file_path.write_text("not valid json{{{")
        with open(file_path, "rb") as f:
            resp = client.post("/api/kriging3d/upload", files={"file": ("bad.json", f, "application/json")})
        assert resp.status_code == 400
