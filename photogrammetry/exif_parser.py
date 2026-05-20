"""
EXIF/GPS/IMU 元数据解析模块
============================
支持 EXIF 2.3+ 标准，自动识别航测像片中的：
- GPS 信息：经度、纬度、海拔高度
- IMU 姿态角：Pitch（俯仰角）、Roll（翻滚角）、Yaw（偏航角）
- 相机参数：焦距、像主点、传感器尺寸
- 拍摄参数：曝光时间、光圈、ISO
"""
from __future__ import annotations

import struct
import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, BinaryIO

import numpy as np

# 尝试导入依赖，若缺失则使用纯Python后备方案
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class GPSInfo:
    """GPS 定位信息"""
    latitude: float          # 纬度（十进制度，北正南负）
    longitude: float         # 经度（十进制度，东正西负）
    altitude: Optional[float] = None  # 海拔高度（米，WGS84椭球高）
    altitude_ref: Optional[str] = None  # 高度参考：above_sea_level / above_ground
    hdop: Optional[float] = None  # 水平精度因子
    satellite_count: Optional[int] = None  # 卫星数量
    timestamp: Optional[datetime] = None  # GPS时间戳

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "altitude_ref": self.altitude_ref,
            "hdop": self.hdop,
            "satellite_count": self.satellite_count,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def is_valid(self) -> bool:
        """检查GPS数据是否有效"""
        return (
            self.latitude != 0.0 or self.longitude != 0.0
        ) and -90.0 <= self.latitude <= 90.0 and -180.0 <= self.longitude <= 180.0


@dataclass
class IMUInfo:
    """IMU 姿态角信息（单位：度）"""
    pitch: Optional[float] = None  # 俯仰角 (绕X轴，-90 ~ +90)
    roll: Optional[float] = None   # 翻滚角 (绕Y轴，-180 ~ +180)
    yaw: Optional[float] = None    # 偏航角 (绕Z轴，0 ~ 360)
    # 扩展IMU字段
    omega: Optional[float] = None  # 角速度X (rad/s)
    phi: Optional[float] = None    # 角速度Y (rad/s)
    kappa: Optional[float] = None  # 角速度Z (rad/s)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pitch": self.pitch,
            "roll": self.roll,
            "yaw": self.yaw,
            "omega": self.omega,
            "phi": self.phi,
            "kappa": self.kappa,
        }

    def is_valid(self) -> bool:
        """检查是否有任何有效IMU数据"""
        return any(v is not None for v in [self.pitch, self.roll, self.yaw])

    def to_rotation_matrix(self) -> Optional[np.ndarray]:
        """将欧拉角(Pitch/Roll/Yaw)转换为旋转矩阵 (R = Rz*Ry*Rx)"""
        if not all(v is not None for v in [self.pitch, self.roll, self.yaw]):
            return None

        p, r, y = np.radians([self.pitch, self.roll, self.yaw])

        # Rx (绕X轴 - pitch)
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(p), -np.sin(p)],
            [0, np.sin(p), np.cos(p)],
        ])

        # Ry (绕Y轴 - roll)
        Ry = np.array([
            [np.cos(r), 0, np.sin(r)],
            [0, 1, 0],
            [-np.sin(r), 0, np.cos(r)],
        ])

        # Rz (绕Z轴 - yaw)
        Rz = np.array([
            [np.cos(y), -np.sin(y), 0],
            [np.sin(y), np.cos(y), 0],
            [0, 0, 1],
        ])

        return Rz @ Ry @ Rx


@dataclass
class CameraInfo:
    """相机内参信息"""
    focal_length: Optional[float] = None      # 焦距 (mm)
    focal_length_35mm: Optional[float] = None  # 35mm等效焦距 (mm)
    sensor_width: Optional[float] = None       # 传感器宽度 (mm)
    sensor_height: Optional[float] = None      # 传感器高度 (mm)
    image_width: Optional[int] = None          # 影像宽度 (像素)
    image_height: Optional[int] = None         # 影像高度 (像素)
    principal_point_x: Optional[float] = None  # 像主点X (像素)
    principal_point_y: Optional[float] = None  # 像主点Y (像素)
    pixel_size: Optional[float] = None         # 像元尺寸 (mm/pixel)
    f_number: Optional[float] = None           # 光圈值
    exposure_time: Optional[float] = None      # 曝光时间 (秒)
    iso: Optional[int] = None                  # ISO感光度
    make: Optional[str] = None                 # 相机制造商
    model: Optional[str] = None                # 相机型号

    def to_dict(self) -> Dict[str, Any]:
        return {
            "focal_length_mm": self.focal_length,
            "focal_length_35mm": self.focal_length_35mm,
            "sensor_width_mm": self.sensor_width,
            "sensor_height_mm": self.sensor_height,
            "image_width_px": self.image_width,
            "image_height_px": self.image_height,
            "principal_point_x_px": self.principal_point_x,
            "principal_point_y_px": self.principal_point_y,
            "pixel_size_mm": self.pixel_size,
            "f_number": self.f_number,
            "exposure_time_s": self.exposure_time,
            "iso": self.iso,
            "make": self.make,
            "model": self.model,
        }

    def compute_pixel_size(self) -> Optional[float]:
        """根据传感器尺寸和影像分辨率推算像元尺寸"""
        if self.sensor_width and self.image_width:
            return self.sensor_width / self.image_width
        return None

    def compute_focal_pixels(self) -> Optional[float]:
        """将焦距从毫米转换为像素单位"""
        ps = self.pixel_size or self.compute_pixel_size()
        if self.focal_length and ps:
            return self.focal_length / ps
        return None

    def get_default_principal_point(self) -> Tuple[float, float]:
        """获取默认像主点（影像中心）"""
        if self.principal_point_x and self.principal_point_y:
            return self.principal_point_x, self.principal_point_y
        if self.image_width and self.image_height:
            return self.image_width / 2.0, self.image_height / 2.0
        return 0.0, 0.0


@dataclass
class AerialImageMetadata:
    """航测像片完整元数据"""
    file_path: str
    file_name: str
    file_size_bytes: int
    image_format: str
    gps: GPSInfo
    imu: IMUInfo = field(default_factory=IMUInfo)
    camera: CameraInfo = field(default_factory=CameraInfo)
    capture_time: Optional[datetime] = None
    extra_tags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "image_format": self.image_format,
            "gps": self.gps.to_dict(),
            "imu": self.imu.to_dict(),
            "camera": self.camera.to_dict(),
            "capture_time": self.capture_time.isoformat() if self.capture_time else None,
            "extra_tags": self.extra_tags,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# EXIF 解析引擎
# ---------------------------------------------------------------------------

class ExifParser:
    """EXIF 元数据解析器 - 支持 EXIF 2.3+ 标准"""

    # XMP无人机扩展字段映射
    XMP_DRONE_KEYS = {
        "drone-dji:FlightPitchDegree": "pitch",
        "drone-dji:FlightRollDegree": "roll",
        "drone-dji:FlightYawDegree": "yaw",
        "drone-dji:GimbalPitchDegree": "gimbal_pitch",
        "drone-dji:GimbalRollDegree": "gimbal_roll",
        "drone-dji:GimbalYawDegree": "gimbal_yaw",
        "drone-dji:GPSLongitude": "gps_longitude",
        "drone-dji:GPSLatitude": "gps_latitude",
        "drone-dji:AbsoluteAltitude": "absolute_altitude",
        "drone-dji:RelativeAltitude": "relative_altitude",
        "drone-dji:FlightSpeedX": "flight_speed_x",
        "drone-dji:FlightSpeedY": "flight_speed_y",
        "drone-dji:FlightSpeedZ": "flight_speed_z",
    }

    # GPS标签的EXIF ID映射
    GPS_TAG_IDS = {
        0x0000: "GPSVersionID",
        0x0001: "GPSLatitudeRef",
        0x0002: "GPSLatitude",
        0x0003: "GPSLongitudeRef",
        0x0004: "GPSLongitude",
        0x0005: "GPSAltitudeRef",
        0x0006: "GPSAltitude",
        0x0007: "GPSTimeStamp",
        0x000D: "GPSImgDirectionRef",
        0x000E: "GPSImgDirection",
        0x0012: "GPSMapDatum",
        0x001D: "GPSDateStamp",
    }

    # 常见EXIF制造商注释中IMU位置的偏移量 (DJI, Autel, Parrot等)
    MAKER_IMU_OFFSETS = {
        "DJI": {"pitch": 0x0010, "roll": 0x0012, "yaw": 0x0014},
        "Autel": {"pitch": 0x0020, "roll": 0x0022, "yaw": 0x0024},
    }

    @staticmethod
    def _dms_to_decimal(degrees: float, minutes: float, seconds: float, ref: str) -> float:
        """将度分秒(DMS)转换为十进制度"""
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal

    @staticmethod
    def _rational_to_float(rational) -> Optional[float]:
        """将EXIF有理数转换为浮点数"""
        if rational is None:
            return None
        if hasattr(rational, "numerator") and hasattr(rational, "denominator"):
            try:
                return float(rational.numerator) / float(rational.denominator)
            except (ZeroDivisionError, TypeError):
                return None
        if isinstance(rational, (int, float)):
            return float(rational)
        if isinstance(rational, tuple) and len(rational) >= 2:
            try:
                return float(rational[0]) / float(rational[1])
            except (ZeroDivisionError, TypeError, ValueError):
                return None
        return None

    @staticmethod
    def parse_gps_dms(gps_data: Dict) -> Optional[Tuple[float, float, float]]:
        """从GPS DMS数据中提取度、分、秒"""
        values = []
        for key in ["GPSLatitude", "GPSLongitude"]:
            dms = gps_data.get(key)
            if dms is None:
                return None
            if hasattr(dms, "values"):
                parts = [ExifParser._rational_to_float(v) for v in dms.values]
            elif isinstance(dms, (tuple, list)):
                parts = [ExifParser._rational_to_float(v) for v in dms[:3]]
            else:
                return None
            if None in parts:
                return None
            values.extend(parts)
        if len(values) >= 6:
            return (values[0], values[1], values[2], values[3], values[4], values[5])
        return None

    def parse_with_pil(self, file_path: str) -> AerialImageMetadata:
        """使用PIL/Pillow解析EXIF"""
        img = Image.open(file_path)
        exif_data = img._getexif() or {}

        # 获取基本文件信息
        path = Path(file_path)
        file_size = path.stat().st_size

        # 解析GPS
        gps_info = self._extract_gps_pil(exif_data, img)

        # 解析IMU
        imu_info = self._extract_imu_pil(exif_data)

        # 解析相机参数
        camera_info = self._extract_camera_pil(exif_data, img)

        # 解析拍摄时间
        capture_time = None
        raw_datetime = exif_data.get(36867) or exif_data.get(36868) or exif_data.get(306)
        if raw_datetime:
            try:
                capture_time = datetime.strptime(str(raw_datetime), "%Y:%m:%d %H:%M:%S")
            except (ValueError, TypeError):
                pass

        return AerialImageMetadata(
            file_path=str(path.absolute()),
            file_name=path.name,
            file_size_bytes=file_size,
            image_format=img.format or path.suffix.lstrip("."),
            gps=gps_info,
            imu=imu_info,
            camera=camera_info,
            capture_time=capture_time,
        )

    def _extract_gps_pil(self, exif_data: Dict, img) -> GPSInfo:
        """从PIL EXIF中提取GPS信息"""
        gps_data = {}
        gps_ifd = exif_data.get(34853)  # GPSInfo IFD
        if gps_ifd:
            for tag_id, value in gps_ifd.items():
                tag_name = GPSTAGS.get(tag_id, f"GPS_{tag_id}")
                gps_data[tag_name] = value

        lat = lon = alt = None
        lat_ref = lon_ref = None
        hdop = None
        satellite_count = None
        gps_time = None

        # 解析经纬度
        if "GPSLatitude" in gps_data and "GPSLatitudeRef" in gps_data:
            lat_ref = str(gps_data["GPSLatitudeRef"]).strip()
            lat = self._parse_dms_value(gps_data["GPSLatitude"], lat_ref)

        if "GPSLongitude" in gps_data and "GPSLongitudeRef" in gps_data:
            lon_ref = str(gps_data["GPSLongitudeRef"]).strip()
            lon = self._parse_dms_value(gps_data["GPSLongitude"], lon_ref)

        # 解析海拔
        if "GPSAltitude" in gps_data:
            alt = self._rational_to_float(gps_data["GPSAltitude"])
            alt_ref = str(gps_data.get("GPSAltitudeRef", "")).strip()
            if alt is not None and alt_ref == "1":
                alt = -alt

        return GPSInfo(
            latitude=lat or 0.0,
            longitude=lon or 0.0,
            altitude=alt,
        )

    def _parse_dms_value(self, dms_value, ref: str) -> Optional[float]:
        """解析度分秒值"""
        parts = None
        if hasattr(dms_value, "numerator"):
            parts = [float(dms_value)]
        elif hasattr(dms_value, "values"):
            parts = [self._rational_to_float(v) for v in dms_value.values]
        elif isinstance(dms_value, (tuple, list)):
            parts = [self._rational_to_float(v) for v in dms_value[:3]]

        if not parts or None in parts:
            return None

        if len(parts) == 3:
            return self._dms_to_decimal(parts[0], parts[1], parts[2], ref)
        return parts[0]

    def _extract_imu_pil(self, exif_data: Dict) -> IMUInfo:
        """从PIL EXIF中提取IMU姿态角"""
        imu = IMUInfo()
        maker_note = exif_data.get(37500)  # MakerNote

        if maker_note and isinstance(maker_note, dict):
            # 尝试从DJI XMP标签提取
            for key, attr in self.XMP_DRONE_KEYS.items():
                val = maker_note.get(key)
                if val is not None:
                    setattr(imu, attr, self._rational_to_float(val))

        # 也尝试从常规EXIF标签和XMP中查找
        xmp_data = exif_data.get(0x02BC) or exif_data.get(700)  # XMP packet
        if xmp_data:
            imu = self._extract_imu_from_xmp(imu, str(xmp_data))

        return imu

    def _extract_imu_from_xmp(self, imu: IMUInfo, xmp_str: str) -> IMUInfo:
        """从XMP字符串中提取IMU数据"""
        patterns = {
            "pitch": [
                r'drone-dji:FlightPitchDegree="([+-]?\d+\.?\d*)"',
                r'FlightPitchDegree[":\s]+([+-]?\d+\.?\d*)',
            ],
            "roll": [
                r'drone-dji:FlightRollDegree="([+-]?\d+\.?\d*)"',
                r'FlightRollDegree[":\s]+([+-]?\d+\.?\d*)',
            ],
            "yaw": [
                r'drone-dji:FlightYawDegree="([+-]?\d+\.?\d*)"',
                r'FlightYawDegree[":\s]+([+-]?\d+\.?\d*)',
            ],
        }

        for attr, pat_list in patterns.items():
            if getattr(imu, attr) is not None:
                continue
            for pat in pat_list:
                m = re.search(pat, xmp_str)
                if m:
                    try:
                        setattr(imu, attr, float(m.group(1)))
                    except (ValueError, TypeError):
                        pass
                    break

        return imu

    def _extract_camera_pil(self, exif_data: Dict, img) -> CameraInfo:
        """从PIL EXIF中提取相机参数"""
        cam = CameraInfo()

        # 基本属性
        cam.image_width, cam.image_height = img.size
        cam.focal_length = self._rational_to_float(exif_data.get(37386))  # FocalLength
        cam.focal_length_35mm = self._rational_to_float(exif_data.get(41989))  # FocalLengthIn35mmFilm
        cam.f_number = self._rational_to_float(exif_data.get(33437))  # FNumber
        cam.exposure_time = self._rational_to_float(exif_data.get(33434))  # ExposureTime
        cam.iso = exif_data.get(34855)  # ISOSpeedRatings
        cam.make = str(exif_data.get(271, "")) if exif_data.get(271) else None  # Make
        cam.model = str(exif_data.get(272, "")) if exif_data.get(272) else None  # Model

        # 传感器尺寸（根据型号推断，DJI常见无人机）
        cam.sensor_width = self._infer_sensor_width(cam.make or "", cam.model or "")

        # 像元尺寸
        cam.pixel_size = cam.compute_pixel_size()

        return cam

    def _infer_sensor_width(self, make: str, model: str) -> Optional[float]:
        """根据相机型号推断传感器宽度(mm)"""
        make_lower = make.lower()
        model_lower = model.lower()

        # DJI 无人机常见传感器
        sensor_db = {
            "fc220": 6.17,    # Mavic Pro (1/2.3")
            "fc2204": 6.17,   # Phantom 4
            "fc300s": 6.17,   # Phantom 3
            "fc330": 6.17,    # Phantom 4
            "fc350": 13.2,    # Phantom 4 Pro (1")
            "fc6310": 13.2,   # Phantom 4 Pro/Advanced (1")
            "fc550": 17.3,    # Zenmuse X5 (M4/3)
            "fc6520": 17.3,   # Zenmuse X5S
            "fc6540": 17.3,   # Zenmuse X4S
            "l1d-20c": 13.2,  # Mavic 2 Pro (1")
            "fc3170": 6.4,    # Mavic Air 2 (1/2")
            "fc7203": 13.2,   # Mavic 3 (4/3")
            "fc4382": 8.8,    # Mini 3 Pro (1/1.3")
            "fc8482": 8.8,    # Air 3
            "fc8282": 13.2,   # Mavic 3 Classic/Pro
        }

        for key, width in sensor_db.items():
            if key in model_lower.replace(" ", "").lower():
                return width

        # 根据传感器尺寸字符串推断
        if "1/2.3" in model_lower:
            return 6.17
        if "1\"" in model_lower or "1 inch" in model_lower:
            return 13.2
        if "4/3" in model_lower:
            return 17.3
        if "1/1.3" in model_lower:
            return 8.8

        return None

    def parse_with_exifread(self, file_path: str) -> AerialImageMetadata:
        """使用exifread库解析EXIF"""

    def parse_raw_bytes(self, data: bytes, file_name: str = "unknown.jpg") -> AerialImageMetadata:
        """直接解析二进制EXIF数据（用于无PIL环境的后备方案）"""
        # 基础的JPEG EXIF解析
        gps_info = GPSInfo(latitude=0.0, longitude=0.0)
        imu_info = IMUInfo()
        camera_info = CameraInfo()

        # 搜索APP1标记(0xFFE1)和EXIF标识符
        if data[:2] != b"\xff\xd8":
            return AerialImageMetadata(
                file_path=file_name,
                file_name=file_name,
                file_size_bytes=len(data),
                image_format="unknown",
                gps=gps_info,
                imu=imu_info,
                camera=camera_info,
            )

        # 基础JPEG解析（TODO：完整实现二进制EXIF解析）
        image_format = "jpeg"
        if data[6:10] == b"JFIF":
            image_format = "jpeg"

        return AerialImageMetadata(
            file_path=file_name,
            file_name=file_name,
            file_size_bytes=len(data),
            image_format=image_format,
            gps=gps_info,
            imu=imu_info,
            camera=camera_info,
        )

    def parse(self, file_path: str) -> AerialImageMetadata:
        """解析航测像片的EXIF元数据（自动选择最佳解析器）"""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"影像文件不存在: {file_path}")

        if HAS_PIL:
            try:
                return self.parse_with_pil(file_path)
            except Exception:
                pass

        if HAS_EXIFREAD:
            try:
                return self.parse_with_exifread(file_path)
            except Exception:
                pass

        # 后备方案：纯二进制解析
        with open(file_path, "rb") as f:
            data = f.read()
        return self.parse_raw_bytes(data, Path(file_path).name)

    def parse_directory(self, directory: str, extensions: Tuple[str, ...] = (".jpg", ".jpeg", ".tif", ".tiff")) -> Dict[str, AerialImageMetadata]:
        """批量解析目录中的所有航测像片"""
        results = {}
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"目录不存在: {directory}")

        for ext in extensions:
            for img_path in dir_path.glob(f"*{ext}"):
                try:
                    results[str(img_path)] = self.parse(str(img_path))
                except Exception:
                    results[str(img_path)] = None

        return results


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def parse_aerial_image(file_path: str) -> AerialImageMetadata:
    """快速解析单张航测像片"""
    parser = ExifParser()
    return parser.parse(file_path)


def parse_aerial_directory(directory: str) -> Dict[str, AerialImageMetadata]:
    """快速批量解析目录中的航测像片"""
    parser = ExifParser()
    return parser.parse_directory(directory)
