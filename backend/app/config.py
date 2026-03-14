"""
配置文件
"""
from pydantic_settings import BaseSettings
from pydantic import validator, Field
from typing import List, Optional
from pathlib import Path
import json

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "智能不确定性驱动空间决策平台"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS配置
    BACKEND_CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]'

    # 文件上传配置
    MAX_FILE_SIZE_MB: int = 100

    # 文件路径配置
    BASE_DIR: Path = Path(__file__).parent.parent
    RESULTS_DIR: Path = BASE_DIR / "app" / "结果文件"
    DATA_DIR: Path = BASE_DIR.parent / "data_samples"

    # 任务配置
    MAX_CONCURRENT_TASKS: int = 5
    TASK_TIMEOUT: int = 3600

    # 克里金配置
    DEFAULT_VARIOGRAM_MODEL: str = "spherical"
    GRID_RESOLUTION: int = 100

    # ArcGIS配置
    ARCGIS_API_KEY: str = "YOUR_ARCGIS_API_KEY_HERE"
    ARCGIS_PORTAL_URL: str = "https://www.arcgis.com"
    ARCGIS_ENV: str = "development"
    ARCGIS_DEFAULT_BASEMAP: str = "streets-vector"
    ARCGIS_DEFAULT_CENTER: str = "[139.767125,35.681236]"
    ARCGIS_DEFAULT_ZOOM: int = 10

    # 高德地图配置
    AMAP_API_KEY: str = "YOUR_AMAP_API_KEY_HERE"
    AMAP_SECURITY_CODE: Optional[str] = None

    # 天地图配置
    TIANDITU_API_KEY: str = "YOUR_TIANDITU_API_KEY_HERE"
    TIANDITU_TOKEN: Optional[str] = None

    # AI扩展模块配置
    AI_MODEL_PATH: Optional[str] = None
    AI_CACHE_ENABLED: bool = True
    AI_MAX_BATCH_SIZE: int = 100

    @validator('BACKEND_CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return ["http://localhost:5173"]
        return v

    @validator('ARCGIS_DEFAULT_CENTER', pre=True)
    def parse_center(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [139.767125, 35.681236]
        return v

    @validator('MAX_CONCURRENT_TASKS', 'TASK_TIMEOUT', 'GRID_RESOLUTION', 'MAX_FILE_SIZE_MB', 'AI_MAX_BATCH_SIZE')
    def validate_positive_int(cls, v):
        if v <= 0:
            raise ValueError(f'{v} must be positive')
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS允许的源列表"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return json.loads(self.BACKEND_CORS_ORIGINS)
        return self.BACKEND_CORS_ORIGINS

    @property
    def arcgis_center_list(self) -> List[float]:
        """获取ArcGIS默认中心点列表"""
        if isinstance(self.ARCGIS_DEFAULT_CENTER, str):
            return json.loads(self.ARCGIS_DEFAULT_CENTER)
        return self.ARCGIS_DEFAULT_CENTER

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()

# 确保目录存在
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
