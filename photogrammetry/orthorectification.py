"""
单片纠正引擎 - 基于共线方程的正射校正
=====================================
利用共线方程将原始倾斜航测影像投影至地面地理网格，
实现单片微分纠正。

核心算法：
1. 共线条件方程：建立像点-物点-投影中心间的几何关系
2. 直接法/间接法数字微分纠正
3. 支持DEM辅助的逐像元正射校正
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any

import numpy as np

from .exif_parser import AerialImageMetadata, GPSInfo, IMUInfo, CameraInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class ExteriorOrientation:
    """外方位元素"""
    Xs: float  # 投影中心X坐标（地面坐标系）
    Ys: float  # 投影中心Y坐标
    Zs: float  # 投影中心Z坐标（航高）
    omega: float = 0.0   # 绕X轴旋转角 (rad)
    phi: float = 0.0     # 绕Y轴旋转角 (rad)
    kappa: float = 0.0   # 绕Z轴旋转角 (rad)

    def to_rotation_matrix(self) -> np.ndarray:
        """计算旋转矩阵 R = R_omega * R_phi * R_kappa"""
        o, p, k = self.omega, self.phi, self.kappa

        # R_omega (绕X)
        R_omega = np.array([
            [1, 0, 0],
            [0, np.cos(o), -np.sin(o)],
            [0, np.sin(o), np.cos(o)],
        ])

        # R_phi (绕Y)
        R_phi = np.array([
            [np.cos(p), 0, np.sin(p)],
            [0, 1, 0],
            [-np.sin(p), 0, np.cos(p)],
        ])

        # R_kappa (绕Z)
        R_kappa = np.array([
            [np.cos(k), -np.sin(k), 0],
            [np.sin(k), np.cos(k), 0],
            [0, 0, 1],
        ])

        return R_omega @ R_phi @ R_kappa


@dataclass
class InteriorOrientation:
    """内方位元素"""
    f: float              # 焦距（像素单位或mm，需与坐标系一致）
    x0: float             # 像主点x坐标
    y0: float             # 像主点y坐标
    pixel_size: Optional[float] = None  # 像元尺寸 (mm/pixel)


@dataclass
class GroundControlPoint:
    """地面控制点"""
    id: str
    image_x: float        # 像点x坐标（像素）
    image_y: float        # 像点y坐标（像素）
    ground_x: float       # 地面X坐标
    ground_y: float       # 地面Y坐标
    ground_z: float       # 地面Z坐标（高程）


@dataclass
class OrthorectificationResult:
    """正射校正结果"""
    ortho_image: np.ndarray              # 正射影像数组
    geo_transform: Tuple[float, ...]      # GDAL地理变换参数
    projection: str                       # 投影信息 (WKT)
    coverage_bbox: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
    ground_resolution: float              # 地面分辨率
    rmse: Optional[float] = None          # 重投影均方根误差
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 共线方程模型
# ---------------------------------------------------------------------------

class CollinearityModel:
    """共线条件方程模型 - 摄影测量核心几何关系

    共线方程:
        x - x0 = -f * (r11*(X-Xs) + r21*(Y-Ys) + r31*(Z-Zs))
                     / (r13*(X-Xs) + r23*(Y-Ys) + r33*(Z-Zs))

        y - y0 = -f * (r12*(X-Xs) + r22*(Y-Ys) + r32*(Z-Zs))
                     / (r13*(X-Xs) + r23*(Y-Ys) + r33*(Z-Zs))
    """

    def __init__(
        self,
        interior: InteriorOrientation,
        exterior: ExteriorOrientation,
    ):
        self.interior = interior
        self.exterior = exterior
        self.R = exterior.to_rotation_matrix()  # 旋转矩阵

    def ground_to_image(
        self, X: float, Y: float, Z: float
    ) -> Tuple[float, float]:
        """共线方程正向投影：地面点(X, Y, Z) -> 像点(x, y)"""
        Xs, Ys, Zs = self.exterior.Xs, self.exterior.Ys, self.exterior.Zs
        f = self.interior.f
        x0, y0 = self.interior.x0, self.interior.y0

        dX, dY, dZ = X - Xs, Y - Ys, Z - Zs

        # 分子
        num_x = self.R[0, 0] * dX + self.R[1, 0] * dY + self.R[2, 0] * dZ
        num_y = self.R[0, 1] * dX + self.R[1, 1] * dY + self.R[2, 1] * dZ
        denom  = self.R[0, 2] * dX + self.R[1, 2] * dY + self.R[2, 2] * dZ

        if abs(denom) < 1e-10:
            return float("inf"), float("inf")

        x = x0 - f * num_x / denom
        y = y0 - f * num_y / denom

        return x, y

    def image_to_ground_ray(
        self, x: float, y: float, Z0: float = 0.0
    ) -> Tuple[float, float]:
        """共线方程反向投影：像点(x, y) + 高程Z0 -> 地面点(X, Y)

        通过对共线方程求逆，在给定高程Z0的条件下求解地面坐标。
        """
        Xs, Ys, Zs = self.exterior.Xs, self.exterior.Ys, self.exterior.Zs
        f = self.interior.f
        x0, y0 = self.interior.x0, self.interior.y0

        # 像空间辅助坐标
        u = self.R[0, 0] * (x - x0) + self.R[0, 1] * (y - y0) - self.R[0, 2] * f
        v = self.R[1, 0] * (x - x0) + self.R[1, 1] * (y - y0) - self.R[1, 2] * f
        w = self.R[2, 0] * (x - x0) + self.R[2, 1] * (y - y0) - self.R[2, 2] * f

        if abs(w) < 1e-10:
            return float("inf"), float("inf")

        # 投影到Z=Z0平面
        scale = (Z0 - Zs) / w
        X = Xs + scale * u
        Y = Ys + scale * v

        return X, Y

    def compute_ground_resolution(
        self, avg_ground_elevation: float
    ) -> float:
        """计算地面采样距离(GSD)"""
        f = self.interior.f
        H = self.exterior.Zs - avg_ground_elevation

        if self.interior.pixel_size and self.interior.f:
            # f_mm * pixel_size_mm -> 焦距像素
            if self.interior.f < 100:  # 判断f是否以像素为单位
                ps = self.interior.pixel_size
                return (H * ps) / self.interior.f if self.interior.f > 0 else 0.0
            else:
                return (H * self.interior.pixel_size) / self.interior.f

        # 假设f以像素为单位
        if f > 0:
            return H / f

        return 0.0


# ---------------------------------------------------------------------------
# 单片纠正引擎
# ---------------------------------------------------------------------------

class OrthorectificationEngine:
    """单片微分纠正引擎

    支持两种纠正方法：
    1. 间接法（推荐）：从正射影像格网反算原始影像坐标，双线性内插
    2. 直接法：从原始影像逐像元正算地面坐标
    """

    def __init__(self):
        self.collinearity_model: Optional[CollinearityModel] = None

    def build_from_metadata(
        self,
        metadata: AerialImageMetadata,
        ground_elevation: float = 0.0,
    ) -> CollinearityModel:
        """从航测像片元数据构建共线方程模型"""
        gps = metadata.gps
        imu = metadata.imu
        cam = metadata.camera

        # 外方位元素
        # GPS -> 投影中心位置
        Xs, Ys, Zs = gps.longitude, gps.latitude, gps.altitude or ground_elevation

        # IMU姿态角 -> 外方位角元素（需要根据坐标系定义转换）
        # 通常: omega ≈ roll, phi ≈ pitch, kappa ≈ yaw
        omega = np.radians(imu.roll or 0.0)
        phi = np.radians(imu.pitch or 0.0)
        kappa = np.radians(imu.yaw or 0.0)

        exterior = ExteriorOrientation(
            Xs=Xs, Ys=Ys, Zs=Zs,
            omega=omega, phi=phi, kappa=kappa,
        )

        # 内方位元素
        focal_px = cam.compute_focal_pixels()
        x0, y0 = cam.get_default_principal_point()

        interior = InteriorOrientation(
            f=focal_px or (cam.focal_length or 24.0),
            x0=x0,
            y0=y0,
            pixel_size=cam.pixel_size,
        )

        self.collinearity_model = CollinearityModel(interior, exterior)
        return self.collinearity_model

    def build_from_params(
        self,
        Xs: float, Ys: float, Zs: float,
        omega: float, phi: float, kappa: float,
        f: float, x0: float, y0: float,
        pixel_size: Optional[float] = None,
    ) -> CollinearityModel:
        """直接使用参数构建共线方程模型"""
        exterior = ExteriorOrientation(
            Xs=Xs, Ys=Ys, Zs=Zs,
            omega=omega, phi=phi, kappa=kappa,
        )
        interior = InteriorOrientation(
            f=f, x0=x0, y0=y0, pixel_size=pixel_size,
        )
        self.collinearity_model = CollinearityModel(interior, exterior)
        return self.collinearity_model

    def orthorectify_indirect(
        self,
        image: np.ndarray,
        ground_resolution: float,
        output_bounds: Tuple[float, float, float, float],
        dem: Optional[np.ndarray] = None,
        dem_transform: Optional[Tuple[float, ...]] = None,
        default_elevation: float = 0.0,
    ) -> OrthorectificationResult:
        """间接法正射校正

        对每个输出格网点，反算其在原始影像上的位置，
        使用双线性内插获取灰度值。

        Args:
            image: 原始影像数组 (H, W) 或 (H, W, C)
            ground_resolution: 输出正射影像的地面分辨率
            output_bounds: 输出范围 (min_x, min_y, max_x, max_y)
            dem: 可选DEM数组
            dem_transform: DEM的地理变换参数
            default_elevation: 默认地面高程
        """
        if self.collinearity_model is None:
            raise ValueError("请先调用 build_from_metadata() 或 build_from_params() 构建模型")

        min_x, min_y, max_x, max_y = output_bounds
        model = self.collinearity_model

        # 输出影像尺寸
        out_cols = int(np.ceil((max_x - min_x) / ground_resolution))
        out_rows = int(np.ceil((max_y - min_y) / ground_resolution))

        # 判断是彩色还是灰度
        is_color = len(image.shape) == 3
        if is_color:
            out_image = np.zeros((out_rows, out_cols, image.shape[2]), dtype=image.dtype)
        else:
            out_image = np.zeros((out_rows, out_cols), dtype=image.dtype)

        img_h, img_w = image.shape[:2]

        # 构建输出坐标网格
        out_x_grid = min_x + (np.arange(out_cols) + 0.5) * ground_resolution
        out_y_grid = max_y - (np.arange(out_rows) + 0.5) * ground_resolution

        # 逐像元反算
        for i in range(out_rows):
            Y_ground = out_y_grid[i]
            for j in range(out_cols):
                X_ground = out_x_grid[j]

                # 获取高程
                Z = self._get_elevation(
                    X_ground, Y_ground, dem, dem_transform, default_elevation
                )

                # 反算原始影像坐标
                x_img, y_img = model.ground_to_image(X_ground, Y_ground, Z)

                # 双线性内插
                pixel_val = self._bilinear_interpolate(
                    image, x_img, y_img, img_w, img_h, is_color
                )

                if is_color:
                    out_image[i, j] = pixel_val
                else:
                    out_image[i, j] = pixel_val

        # 构建地理变换 (GDAL格式)
        geo_transform = (
            min_x,
            ground_resolution,
            0.0,
            max_y,
            0.0,
            -ground_resolution,
        )

        return OrthorectificationResult(
            ortho_image=out_image,
            geo_transform=geo_transform,
            projection="EPSG:4326",  # WGS84地理坐标
            coverage_bbox=(min_x, min_y, max_x, max_y),
            ground_resolution=ground_resolution,
            metadata={
                "method": "indirect",
                "output_cols": out_cols,
                "output_rows": out_rows,
                "default_elevation": default_elevation,
            },
        )

    def orthorectify_direct(
        self,
        image: np.ndarray,
        ground_resolution: float,
        default_elevation: float = 0.0,
    ) -> OrthorectificationResult:
        """直接法正射校正

        从原始影像逐像元正算地面坐标，然后格网化。
        注意：直接法可能产生空洞，一般不推荐用于生产。
        """
        if self.collinearity_model is None:
            raise ValueError("请先调用 build_from_metadata() 或 build_from_params() 构建模型")

        model = self.collinearity_model
        img_h, img_w = image.shape[:2]
        is_color = len(image.shape) == 3

        # 计算四角投影后的地面范围
        corners_ground = []
        for x, y in [(0, 0), (img_w-1, 0), (img_w-1, img_h-1), (0, img_h-1)]:
            X, Y = model.image_to_ground_ray(x, y, default_elevation)
            corners_ground.append((X, Y))

        xs = [c[0] for c in corners_ground if abs(c[0]) < 1e8]
        ys = [c[1] for c in corners_ground if abs(c[1]) < 1e8]

        if not xs or not ys:
            return OrthorectificationResult(
                ortho_image=np.array([[]]),
                geo_transform=(0, 1, 0, 0, 0, -1),
                projection="EPSG:4326",
                coverage_bbox=(0, 0, 0, 0),
                ground_resolution=ground_resolution,
            )

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        return self.orthorectify_indirect(
            image, ground_resolution,
            (min_x, min_y, max_x, max_y),
            default_elevation=default_elevation,
        )

    def _get_elevation(
        self,
        x: float, y: float,
        dem: Optional[np.ndarray],
        dem_transform: Optional[Tuple[float, ...]],
        default_elevation: float,
    ) -> float:
        """从DEM中获取高程值"""
        if dem is None or dem_transform is None:
            return default_elevation

        try:
            # 从地理坐标计算DEM格网位置
            col = int((x - dem_transform[0]) / dem_transform[1])
            row = int((y - dem_transform[3]) / dem_transform[5])

            if 0 <= row < dem.shape[0] and 0 <= col < dem.shape[1]:
                return float(dem[row, col])
        except Exception:
            pass

        return default_elevation

    @staticmethod
    def _bilinear_interpolate(
        image: np.ndarray,
        x: float, y: float,
        img_w: int, img_h: int,
        is_color: bool,
    ) -> Any:
        """双线性内插"""
        x = np.clip(x, 0, img_w - 1)
        y = np.clip(y, 0, img_h - 1)

        x0, y0 = int(np.floor(x)), int(np.floor(y))
        x1, y1 = min(x0 + 1, img_w - 1), min(y0 + 1, img_h - 1)

        dx = x - x0
        dy = y - y0

        if is_color:
            # 逐通道插值
            result = np.zeros(image.shape[2], dtype=np.float64)
            for c in range(image.shape[2]):
                v00 = float(image[y0, x0, c])
                v10 = float(image[y0, x1, c])
                v01 = float(image[y1, x0, c])
                v11 = float(image[y1, x1, c])

                v0 = v00 + (v10 - v00) * dx
                v1 = v01 + (v11 - v01) * dx
                result[c] = v0 + (v1 - v0) * dy

            return np.clip(result, 0, 255).astype(image.dtype)
        else:
            v00 = float(image[y0, x0])
            v10 = float(image[y0, x1])
            v01 = float(image[y1, x0])
            v11 = float(image[y1, x1])

            v0 = v00 + (v10 - v00) * dx
            v1 = v01 + (v11 - v01) * dx

            return np.clip(v0 + (v1 - v0) * dy, 0, 255).astype(image.dtype)

    def batch_orthorectify(
        self,
        images: List[np.ndarray],
        metadatas: List[AerialImageMetadata],
        ground_resolution: float,
        default_elevation: float = 0.0,
    ) -> List[OrthorectificationResult]:
        """批量正射校正多张影像"""
        results = []
        for img, meta in zip(images, metadatas):
            self.build_from_metadata(meta, default_elevation)
            result = self.orthorectify_indirect(
                img, ground_resolution,
                output_bounds=self._compute_coverage(meta),
                default_elevation=default_elevation,
            )
            results.append(result)
        return results

    @staticmethod
    def _compute_coverage(
        metadata: AerialImageMetadata,
        margin_ratio: float = 0.5,
    ) -> Tuple[float, float, float, float]:
        """根据航高和视场角估算地面覆盖范围"""
        gps = metadata.gps
        cam = metadata.camera

        if not (gps.altitude and cam.focal_length and cam.sensor_width and cam.image_width):
            # 返回以GPS为中心的小范围
            return (
                gps.longitude - 0.001, gps.latitude - 0.001,
                gps.longitude + 0.001, gps.latitude + 0.001,
            )

        H = gps.altitude
        f = cam.focal_length
        sw = cam.sensor_width

        # 地面覆盖宽度
        ground_swath = (sw / f) * H  # mm

        # 转换为度（近似，WGS84）
        # 纬度方向：1度≈111320m，经度方向：1度≈111320*cos(lat)
        lat_rad = np.radians(gps.latitude)
        deg_per_m_lat = 1.0 / 111320.0
        deg_per_m_lon = 1.0 / (111320.0 * np.cos(lat_rad))

        half_swath_m = ground_swath / 2000.0  # mm -> m

        dlat = half_swath_m * deg_per_m_lat * (1 + margin_ratio)
        dlon = half_swath_m * deg_per_m_lon * (1 + margin_ratio)

        return (
            gps.longitude - dlon, gps.latitude - dlat,
            gps.longitude + dlon, gps.latitude + dlat,
        )
